#include <cryptominisat5/cryptominisat.h>

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace
{
using CMSat::Lit;
using CMSat::SATSolver;
using CMSat::l_False;
using CMSat::l_True;

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
  if ( !input ) return std::nullopt;
  completion_problem problem;
  std::string line;
  while ( std::getline( input, line ) )
  {
    if ( line.empty() || line.front() == '#' ) continue;
    std::istringstream stream( line );
    std::string kind, value;
    stream >> kind >> value;
    if ( kind == "DIM" )
      problem.dimension = static_cast<uint32_t>( std::stoul( value ) );
    else if ( kind == "SOURCE" || kind == "TARGET" )
      ( kind == "SOURCE" ? problem.sources : problem.targets )
          .push_back( std::stoull( value, nullptr, 16 ) );
    else
      return std::nullopt;
  }
  if ( problem.dimension == 0u || problem.dimension > 64u ||
       problem.sources.empty() || problem.targets.empty() )
    return std::nullopt;
  return compress_problem( std::move( problem ) );
}

class completion_sat
{
public:
  completion_sat( completion_problem const& problem, uint32_t steps,
                  uint64_t conflict_limit, bool order_targets,
                  std::vector<uint32_t> target_steps )
      : problem_( problem ), steps_( steps ),
        source_count_( static_cast<uint32_t>( problem.sources.size() ) ),
        target_count_( static_cast<uint32_t>( problem.targets.size() ) ),
        select_sources_( steps_ * source_count_ ),
        select_steps_( ( steps_ * ( steps_ - 1u ) ) / 2u ),
        values_( steps_ * problem.dimension ),
        target_matches_( target_count_ * steps_ )
  {
    solver_.set_num_threads( 1u );
    solver_.set_allow_otf_gauss();
    solver_.set_max_confl( conflict_limit );
    solver_.set_single_run();
    allocate( select_sources_ );
    allocate( select_steps_ );
    allocate( values_ );
    allocate( target_matches_ );
    constrain_two_operands();
    constrain_values();
    constrain_outputs();
    if ( !target_steps.empty() ) constrain_target_steps( target_steps );
    if ( order_targets ) constrain_target_order();
    constrain_step_usage();
  }

  CMSat::lbool solve() { return solver_.solve(); }

  std::vector<std::pair<uint32_t, uint32_t>> extract_steps() const
  {
    auto const& model = solver_.get_model();
    std::vector<std::pair<uint32_t, uint32_t>> result;
    for ( uint32_t step = 0u; step < steps_; ++step )
    {
      std::vector<uint32_t> operands;
      for ( uint32_t index = 0u; index < source_count_ + step; ++index )
        if ( model.at( selected( step, index ) ) == l_True )
          operands.push_back( index );
      if ( operands.size() != 2u )
        throw std::runtime_error( "SAT model does not select two operands" );
      result.emplace_back( operands[0], operands[1] );
    }
    return result;
  }

private:
  uint32_t new_variable()
  {
    const auto variable = solver_.nVars();
    solver_.new_var();
    return variable;
  }

  void allocate( std::vector<uint32_t>& variables )
  {
    for ( auto& variable : variables ) variable = new_variable();
  }

  void add_clause( std::initializer_list<Lit> literals )
  {
    solver_.add_clause( std::vector<Lit>( literals ) );
  }

  uint32_t and_variable( Lit left, Lit right )
  {
    const auto output = new_variable();
    const Lit result( output, false );
    add_clause( { ~left, ~right, result } );
    add_clause( { left, ~result } );
    add_clause( { right, ~result } );
    return output;
  }

  uint32_t xor_variable( Lit left, Lit right )
  {
    const auto output = new_variable();
    solver_.add_xor_clause(
        std::vector<Lit>{ left, right, Lit( output, false ) }, false );
    return output;
  }

  void constrain_two_operands()
  {
    for ( uint32_t step = 0u; step < steps_; ++step )
    {
      std::vector<Lit> operands, unselected;
      for ( uint32_t index = 0u; index < source_count_ + step; ++index )
      {
        const Lit literal( selected( step, index ), false );
        operands.push_back( literal );
        unselected.push_back( ~literal );
      }
      solver_.add_bnn_clause( operands, 2 );
      solver_.add_bnn_clause(
          unselected, static_cast<int>( unselected.size() ) - 2 );
    }
  }

  void constrain_values()
  {
    for ( uint32_t step = 0u; step < steps_; ++step )
    {
      std::vector<std::vector<uint32_t>> selected_previous(
          step, std::vector<uint32_t>( problem_.dimension ) );
      for ( uint32_t previous = 0u; previous < step; ++previous )
        for ( uint32_t bit = 0u; bit < problem_.dimension; ++bit )
          selected_previous[previous][bit] = and_variable(
              Lit( step_selected( step, previous ), false ),
              Lit( value( previous, bit ), false ) );

      for ( uint32_t bit = 0u; bit < problem_.dimension; ++bit )
      {
        std::vector<unsigned> parity{ value( step, bit ) };
        for ( uint32_t source = 0u; source < source_count_; ++source )
          if ( ( problem_.sources[source] >> bit ) & 1u )
            parity.push_back( source_selected( step, source ) );
        for ( uint32_t previous = 0u; previous < step; ++previous )
          parity.push_back( selected_previous[previous][bit] );
        solver_.add_xor_clause( parity, false );
      }

      for ( auto source_value : problem_.sources )
      {
        std::vector<Lit> differs;
        for ( uint32_t bit = 0u; bit < problem_.dimension; ++bit )
          differs.emplace_back( value( step, bit ),
                                ( ( source_value >> bit ) & 1u ) != 0u );
        solver_.add_clause( differs );
      }
      for ( uint32_t previous = 0u; previous < step; ++previous )
      {
        std::vector<Lit> differs;
        for ( uint32_t bit = 0u; bit < problem_.dimension; ++bit )
          differs.emplace_back(
              xor_variable( Lit( value( step, bit ), false ),
                            Lit( value( previous, bit ), false ) ), false );
        solver_.add_clause( differs );
      }
    }
  }

  void constrain_outputs()
  {
    for ( uint32_t target = 0u; target < target_count_; ++target )
    {
      if ( std::find( problem_.sources.begin(), problem_.sources.end(),
                      problem_.targets[target] ) != problem_.sources.end() )
      {
        for ( uint32_t step = 0u; step < steps_; ++step )
          add_clause( { ~Lit( output( target, step ), false ) } );
        continue;
      }
      std::vector<Lit> realizers;
      for ( uint32_t step = 0u; step < steps_; ++step )
      {
        const Lit match( output( target, step ), false );
        std::vector<Lit> reverse_clause{ match };
        for ( uint32_t bit = 0u; bit < problem_.dimension; ++bit )
        {
          const Lit equal( value( step, bit ),
                           ( ( problem_.targets[target] >> bit ) & 1u ) == 0u );
          add_clause( { ~match, equal } );
          reverse_clause.push_back( ~equal );
        }
        solver_.add_clause( reverse_clause );
        realizers.push_back( match );
      }
      solver_.add_clause( realizers );
    }
  }

  void constrain_step_usage()
  {
    for ( uint32_t step = 0u; step < steps_; ++step )
    {
      std::vector<Lit> uses;
      for ( uint32_t later = step + 1u; later < steps_; ++later )
        uses.emplace_back( step_selected( later, step ), false );
      for ( uint32_t target = 0u; target < target_count_; ++target )
        uses.emplace_back( output( target, step ), false );
      solver_.add_clause( uses );
    }
  }

  void constrain_target_order()
  {
    /* Optional search-only symmetry breaker.  It retains circuits whose
       distinct target-producing steps follow the problem's target order.
       The unrestricted three-argument run remains the proof-capable mode. */
    for ( uint32_t first = 0u; first < target_count_; ++first )
      for ( uint32_t second = first + 1u; second < target_count_; ++second )
        for ( uint32_t first_step = 0u; first_step < steps_; ++first_step )
          for ( uint32_t second_step = 0u;
                second_step <= first_step && second_step < steps_; ++second_step )
            add_clause( { ~Lit( output( first, first_step ), false ),
                          ~Lit( output( second, second_step ), false ) } );
  }

  void constrain_target_steps( std::vector<uint32_t> const& target_steps )
  {
    if ( target_steps.size() != target_count_ )
      throw std::runtime_error( "target-step count does not match targets" );
    for ( uint32_t target = 0u; target < target_count_; ++target )
    {
      if ( target_steps[target] >= steps_ )
        throw std::runtime_error( "target step is out of range" );
      add_clause( { Lit( output( target, target_steps[target] ), false ) } );
    }
  }

  uint32_t source_selected( uint32_t step, uint32_t source ) const
  { return select_sources_.at( step * source_count_ + source ); }
  uint32_t step_selected( uint32_t step, uint32_t previous ) const
  { return select_steps_.at( ( ( step - 1u ) * step ) / 2u + previous ); }
  uint32_t selected( uint32_t step, uint32_t index ) const
  {
    return index < source_count_ ? source_selected( step, index )
                                 : step_selected( step, index - source_count_ );
  }
  uint32_t value( uint32_t step, uint32_t bit ) const
  { return values_.at( step * problem_.dimension + bit ); }
  uint32_t output( uint32_t target, uint32_t step ) const
  { return target_matches_.at( target * steps_ + step ); }

private:
  completion_problem const& problem_;
  uint32_t steps_, source_count_, target_count_;
  std::vector<uint32_t> select_sources_, select_steps_, values_, target_matches_;
  SATSolver solver_;
};
} // namespace

int main( int argc, char** argv )
{
  if ( argc < 4 || argc > 6 )
  {
    std::cerr << "usage: xor_completion_cms PROBLEM.txt STEPS CONFLICT_LIMIT "
                 "[TARGET_MODE] [SOURCE_INDICES]\n";
    return 2;
  }
  auto problem = read_problem( argv[1] );
  if ( !problem )
  {
    std::cerr << "failed to read completion problem\n";
    return 2;
  }
  const auto steps = static_cast<uint32_t>( std::stoul( argv[2] ) );
  std::vector<uint32_t> target_steps;
  bool order_targets = false;
  if ( argc >= 5 )
  {
    const std::string mode = argv[4];
    if ( mode == "order" )
      order_targets = true;
    else if ( mode != "none" )
    {
      std::istringstream stream( mode );
      std::string piece;
      while ( std::getline( stream, piece, ',' ) )
        target_steps.push_back( static_cast<uint32_t>( std::stoul( piece ) ) );
    }
  }
  if ( argc == 6 )
  {
    std::vector<uint64_t> selected_sources;
    std::istringstream stream( argv[5] );
    std::string piece;
    while ( std::getline( stream, piece, ',' ) )
    {
      const auto index = static_cast<uint32_t>( std::stoul( piece ) );
      if ( index >= problem->sources.size() )
        throw std::runtime_error( "source index is out of range" );
      selected_sources.push_back( problem->sources[index] );
    }
    if ( selected_sources.empty() )
      throw std::runtime_error( "source restriction is empty" );
    problem->sources = std::move( selected_sources );
    *problem = compress_problem( std::move( *problem ) );
  }
  completion_sat solver( *problem, steps, std::stoull( argv[3] ), order_targets,
                         std::move( target_steps ) );
  const auto result = solver.solve();
  if ( result != l_True )
  {
    std::cout << "RESULT status=" << ( result == l_False ? "unsat" : "timeout" )
              << " sources=" << problem->sources.size()
              << " targets=" << problem->targets.size()
              << " steps=" << steps << "\n";
    return 1;
  }

  auto values = problem->sources;
  const auto selected_steps = solver.extract_steps();
  for ( uint32_t step = 0u; step < selected_steps.size(); ++step )
  {
    const auto [left, right] = selected_steps[step];
    const auto computed = values.at( left ) ^ values.at( right );
    values.push_back( computed );
    std::cout << "STEP " << step << " " << left << " " << right << " "
              << std::hex << computed << std::dec << "\n";
  }
  for ( uint32_t target = 0u; target < problem->targets.size(); ++target )
  {
    const auto found =
        std::find( values.begin(), values.end(), problem->targets[target] );
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
