#include <mockturtle/networks/xag.hpp>
#include <mockturtle/views/cnf_view.hpp>

#include <bill/sat/solver.hpp>

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{

#if defined(COMPLETION_USE_MAPLE)
constexpr auto completion_solver = bill::solvers::maple;
#elif defined(COMPLETION_USE_BMCG)
constexpr auto completion_solver = bill::solvers::bmcg;
#else
constexpr auto completion_solver = bill::solvers::glucose_41;
#endif
using problem_t =
    mockturtle::cnf_view<mockturtle::xag_network, false, completion_solver>;
using signal_t = mockturtle::signal<problem_t>;

struct completion_problem
{
  uint32_t dimension{};
  std::vector<uint64_t> sources;
  std::vector<uint64_t> targets;
};

completion_problem compress_problem( completion_problem problem )
{
  std::vector<uint64_t> basis_value( 64u ), basis_coordinate( 64u );
  uint32_t rank = 0u;
  const auto reduce = [&]( uint64_t value ) {
    uint64_t coordinate = 0u;
    for ( int32_t bit = 63; bit >= 0; --bit )
      if ( ( ( value >> bit ) & 1u ) && basis_value[bit] )
      {
        value ^= basis_value[bit];
        coordinate ^= basis_coordinate[bit];
      }
    return std::pair<uint64_t, uint64_t>{ value, coordinate };
  };

  std::vector<uint64_t> compressed_sources;
  compressed_sources.reserve( problem.sources.size() );
  for ( auto source : problem.sources )
  {
    auto [remainder, coordinate] = reduce( source );
    if ( remainder )
    {
      if ( rank == 64u ) throw std::runtime_error( "rank exceeds 64" );
      const auto pivot = 63u - static_cast<uint32_t>( __builtin_clzll( remainder ) );
      basis_value[pivot] = remainder;
      basis_coordinate[pivot] = uint64_t{ 1 } << rank;
      coordinate ^= uint64_t{ 1 } << rank++;
    }
    compressed_sources.push_back( coordinate );
  }
  std::vector<uint64_t> compressed_targets;
  compressed_targets.reserve( problem.targets.size() );
  for ( auto target : problem.targets )
  {
    const auto [remainder, coordinate] = reduce( target );
    if ( remainder )
      throw std::runtime_error( "target is outside the source span" );
    compressed_targets.push_back( coordinate );
  }
  problem.dimension = rank;
  problem.sources = std::move( compressed_sources );
  problem.targets = std::move( compressed_targets );
  return problem;
}

std::optional<completion_problem> read_problem( std::string const& path )
{
  std::ifstream input( path );
  if ( !input )
  {
    return std::nullopt;
  }
  completion_problem problem;
  std::string line;
  while ( std::getline( input, line ) )
  {
    if ( line.empty() || line.front() == '#' )
    {
      continue;
    }
    std::istringstream stream( line );
    std::string kind;
    std::string value;
    stream >> kind >> value;
    if ( kind == "DIM" )
    {
      problem.dimension = static_cast<uint32_t>( std::stoul( value ) );
    }
    else if ( kind == "SOURCE" || kind == "TARGET" )
    {
      const auto parsed = std::stoull( value, nullptr, 16 );
      ( kind == "SOURCE" ? problem.sources : problem.targets ).push_back( parsed );
    }
    else
    {
      return std::nullopt;
    }
  }
  if ( problem.dimension == 0u || problem.dimension > 64u ||
       problem.sources.empty() || problem.targets.empty() )
  {
    return std::nullopt;
  }
  const uint64_t mask = problem.dimension == 64u
                            ? ~uint64_t{ 0 }
                            : ( uint64_t{ 1 } << problem.dimension ) - 1u;
  for ( auto value : problem.sources )
  {
    if ( value == 0u || ( value & ~mask ) != 0u )
    {
      return std::nullopt;
    }
  }
  for ( auto value : problem.targets )
  {
    if ( ( value & ~mask ) != 0u )
    {
      return std::nullopt;
    }
  }
  return compress_problem( std::move( problem ) );
}

class completion_sat
{
public:
  completion_sat( completion_problem const& problem, uint32_t steps, int conflict_limit,
                  std::vector<uint32_t> const& target_steps )
      : problem_( problem ),
        steps_( steps ),
        conflict_limit_( conflict_limit ),
        source_count_( static_cast<uint32_t>( problem.sources.size() ) ),
        target_count_( static_cast<uint32_t>( problem.targets.size() ) ),
        select_sources_( steps_ * source_count_ ),
        select_steps_( ( steps_ * ( steps_ - 1u ) ) / 2u ),
        values_( steps_ * problem.dimension )
  {
    std::generate( select_sources_.begin(), select_sources_.end(), [&]() { return network_.create_pi(); } );
    std::generate( select_steps_.begin(), select_steps_.end(), [&]() { return network_.create_pi(); } );
    constrain_two_operands();
    constrain_values();
    constrain_outputs();
    if ( !target_steps.empty() ) constrain_target_steps( target_steps );
    constrain_step_usage();
  }

  std::optional<bool> solve()
  {
    return network_.solve( conflict_limit_ );
  }

  std::vector<std::pair<uint32_t, uint32_t>> extract_steps() const
  {
    std::vector<std::pair<uint32_t, uint32_t>> result;
    for ( uint32_t step = 0u; step < steps_; ++step )
    {
      std::vector<uint32_t> operands;
      for ( uint32_t index = 0u; index < source_count_ + step; ++index )
      {
        if ( network_.model_value( selected( step, index ) ) )
        {
          operands.push_back( index );
        }
      }
      if ( operands.size() != 2u )
      {
        throw std::runtime_error( "SAT model does not select two operands" );
      }
      result.emplace_back( operands[0], operands[1] );
    }
    return result;
  }

private:
  void constrain_two_operands()
  {
    for ( uint32_t step = 0u; step < steps_; ++step )
    {
      const uint32_t available = source_count_ + step;
      auto seen_one = network_.get_constant( false );
      auto seen_two = network_.get_constant( false );
      auto seen_three = network_.get_constant( false );
      for ( uint32_t index = 0u; index < available; ++index )
      {
        const auto literal = selected( step, index );
        seen_three = network_.create_or(
            seen_three, network_.create_and( seen_two, literal ) );
        seen_two = network_.create_or(
            seen_two, network_.create_and( seen_one, literal ) );
        seen_one = network_.create_or( seen_one, literal );
      }
      network_.add_clause( seen_two );
      network_.add_clause( !seen_three );
    }
  }

  void constrain_values()
  {
    for ( uint32_t step = 0u; step < steps_; ++step )
    {
      for ( uint32_t bit = 0u; bit < problem_.dimension; ++bit )
      {
        std::vector<signal_t> terms;
        for ( uint32_t source = 0u; source < source_count_; ++source )
        {
          if ( ( problem_.sources[source] >> bit ) & 1u )
          {
            terms.push_back( source_selected( step, source ) );
          }
        }
        for ( uint32_t previous = 0u; previous < step; ++previous )
        {
          terms.push_back( network_.create_and( step_selected( step, previous ),
                                                value( previous, bit ) ) );
        }
        value( step, bit ) = terms.empty()
                                 ? network_.get_constant( false )
                                 : network_.create_nary_xor( terms );
      }

      /* Do not rediscover an existing source or an earlier new step. */
      for ( auto source_value : problem_.sources )
      {
        std::vector<signal_t> differs;
        for ( uint32_t bit = 0u; bit < problem_.dimension; ++bit )
        {
          differs.push_back( value( step, bit ) ^ ( ( source_value >> bit ) & 1u ) );
        }
        network_.add_clause( differs );
      }
      for ( uint32_t previous = 0u; previous < step; ++previous )
      {
        std::vector<signal_t> differs;
        for ( uint32_t bit = 0u; bit < problem_.dimension; ++bit )
        {
          differs.push_back( network_.create_xor( value( step, bit ),
                                                  value( previous, bit ) ) );
        }
        network_.add_clause( differs );
      }
    }
  }

  void constrain_outputs()
  {
    target_matches_.reserve( target_count_ * steps_ );
    for ( uint32_t target = 0u; target < target_count_; ++target )
    {
      const auto target_value = problem_.targets[target];
      if ( std::find( problem_.sources.begin(), problem_.sources.end(), target_value ) !=
           problem_.sources.end() )
      {
        for ( uint32_t step = 0u; step < steps_; ++step )
        {
          target_matches_.push_back( network_.get_constant( false ) );
        }
        continue;
      }
      std::vector<signal_t> realizers;
      for ( uint32_t step = 0u; step < steps_; ++step )
      {
        std::vector<signal_t> equal_bits;
        for ( uint32_t bit = 0u; bit < problem_.dimension; ++bit )
        {
          equal_bits.push_back( network_.create_xnor(
              value( step, bit ), network_.get_constant( ( target_value >> bit ) & 1u ) ) );
        }
        const auto equal = network_.create_nary_and( equal_bits );
        target_matches_.push_back( equal );
        realizers.push_back( output( target, step ) );
      }
      network_.add_clause( realizers );
    }
  }

  void constrain_step_usage()
  {
    /* A minimum completion has no dead gates.  Requiring each synthesized
       value to feed a later step or realize a target removes large families
       of padded and permuted models without excluding any minimum circuit. */
    for ( uint32_t step = 0u; step < steps_; ++step )
    {
      std::vector<signal_t> uses;
      for ( uint32_t later = step + 1u; later < steps_; ++later )
      {
        uses.push_back( step_selected( later, step ) );
      }
      for ( uint32_t target = 0u; target < target_count_; ++target )
      {
        uses.push_back( output( target, step ) );
      }
      network_.add_clause( uses );
    }
  }

  void constrain_target_steps( std::vector<uint32_t> const& target_steps )
  {
    if ( target_steps.size() != target_count_ )
      throw std::runtime_error( "target-step count does not match targets" );
    for ( uint32_t target = 0u; target < target_count_; ++target )
    {
      if ( target_steps[target] >= steps_ )
        throw std::runtime_error( "target step is out of range" );
      network_.add_clause( output( target, target_steps[target] ) );
    }
  }

  const signal_t& source_selected( uint32_t step, uint32_t source ) const
  {
    return select_sources_[step * source_count_ + source];
  }

  const signal_t& step_selected( uint32_t step, uint32_t previous ) const
  {
    return select_steps_[( ( step - 1u ) * step ) / 2u + previous];
  }

  const signal_t& selected( uint32_t step, uint32_t index ) const
  {
    return index < source_count_ ? source_selected( step, index )
                                 : step_selected( step, index - source_count_ );
  }

  signal_t& value( uint32_t step, uint32_t bit )
  {
    return values_[step * problem_.dimension + bit];
  }

  const signal_t& value( uint32_t step, uint32_t bit ) const
  {
    return values_[step * problem_.dimension + bit];
  }

  const signal_t& output( uint32_t target, uint32_t step ) const
  {
    return target_matches_[target * steps_ + step];
  }

private:
  completion_problem const& problem_;
  uint32_t steps_;
  int conflict_limit_;
  uint32_t source_count_;
  uint32_t target_count_;
  std::vector<signal_t> select_sources_;
  std::vector<signal_t> select_steps_;
  std::vector<signal_t> target_matches_;
  std::vector<signal_t> values_;
  problem_t network_;
};

} // namespace

int main( int argc, char** argv )
{
  if ( argc != 4 && argc != 6 )
  {
    std::cerr << "usage: xor_completion_sat PROBLEM.txt STEPS CONFLICT_LIMIT "
                 "[TARGET_STEPS SOURCE_INDICES]\n";
    return 2;
  }
  auto problem = read_problem( argv[1] );
  if ( !problem )
  {
    std::cerr << "failed to read completion problem\n";
    return 2;
  }
  std::vector<uint32_t> target_steps;
  if ( argc == 6 )
  {
    std::istringstream target_stream( argv[4] );
    std::string piece;
    while ( std::getline( target_stream, piece, ',' ) )
      target_steps.push_back( static_cast<uint32_t>( std::stoul( piece ) ) );

    std::vector<uint64_t> selected_sources;
    std::istringstream source_stream( argv[5] );
    while ( std::getline( source_stream, piece, ',' ) )
    {
      const auto index = static_cast<uint32_t>( std::stoul( piece ) );
      if ( index >= problem->sources.size() )
        throw std::runtime_error( "source index is out of range" );
      selected_sources.push_back( problem->sources[index] );
    }
    problem->sources = std::move( selected_sources );
    *problem = compress_problem( std::move( *problem ) );
  }
  const uint32_t steps = static_cast<uint32_t>( std::stoul( argv[2] ) );
  const int conflict_limit = std::stoi( argv[3] );
  completion_sat solver( *problem, steps, conflict_limit, target_steps );
  const auto result = solver.solve();
  if ( !result )
  {
    std::cout << "RESULT status=timeout sources=" << problem->sources.size()
              << " targets=" << problem->targets.size()
              << " steps=" << steps << "\n";
    return 1;
  }
  if ( !*result )
  {
    std::cout << "RESULT status=unsat sources=" << problem->sources.size()
              << " targets=" << problem->targets.size()
              << " steps=" << steps << "\n";
    return 1;
  }

  auto values = problem->sources;
  const auto selected_steps = solver.extract_steps();
  for ( uint32_t step = 0u; step < selected_steps.size(); ++step )
  {
    const auto [left, right] = selected_steps[step];
    const auto computed = values[left] ^ values[right];
    values.push_back( computed );
    std::cout << "STEP " << step << " " << left << " " << right << " "
              << std::hex << computed << std::dec << "\n";
  }
  for ( uint32_t target = 0u; target < problem->targets.size(); ++target )
  {
    const auto found = std::find( values.begin(), values.end(), problem->targets[target] );
    if ( found == values.end() )
    {
      std::cerr << "SAT model failed target verification\n";
      return 2;
    }
    std::cout << "TARGET " << target << " "
              << std::distance( values.begin(), found ) << "\n";
  }
  std::cout << "RESULT status=sat sources=" << problem->sources.size()
            << " targets=" << problem->targets.size()
            << " steps=" << steps << "\n";
  return 0;
}
