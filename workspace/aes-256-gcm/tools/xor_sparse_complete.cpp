#include <mockturtle/networks/xag.hpp>
#include <mockturtle/views/cnf_view.hpp>

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>
#include <numeric>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace
{

using problem_t = mockturtle::cnf_view<mockturtle::xag_network, false,
                                       bill::solvers::glucose_41>;
using signal_t = mockturtle::signal<problem_t>;

struct completion_problem
{
  uint32_t dimension{};
  std::vector<uint64_t> sources;
  std::vector<uint64_t> targets;
};

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
      ( kind == "SOURCE" ? problem.sources : problem.targets )
          .push_back( std::stoull( value, nullptr, 16 ) );
    }
    else
    {
      return std::nullopt;
    }
  }
  return problem.dimension > 0u && problem.dimension <= 64u &&
                 !problem.sources.empty() && !problem.targets.empty()
             ? std::optional<completion_problem>{ problem }
             : std::nullopt;
}

class sparse_representation_sat
{
public:
  sparse_representation_sat( std::vector<uint64_t> const& sources,
                             uint64_t target, uint32_t dimension,
                             uint32_t weight, int conflict_limit )
      : sources_( sources ),
        target_( target ),
        dimension_( dimension ),
        weight_( weight ),
        conflict_limit_( conflict_limit ),
        selected_( sources.size() )
  {
    std::generate( selected_.begin(), selected_.end(), [&]() { return network_.create_pi(); } );
    constrain_value();
    constrain_weight();
  }

  std::optional<std::vector<uint32_t>> solve()
  {
    const auto result = network_.solve( conflict_limit_ );
    if ( !result || !*result )
    {
      return std::nullopt;
    }
    std::vector<uint32_t> selected;
    for ( uint32_t index = 0u; index < selected_.size(); ++index )
    {
      if ( network_.model_value( selected_[index] ) )
      {
        selected.push_back( index );
      }
    }
    return selected;
  }

private:
  void constrain_value()
  {
    for ( uint32_t bit = 0u; bit < dimension_; ++bit )
    {
      std::vector<signal_t> terms;
      for ( uint32_t source = 0u; source < sources_.size(); ++source )
      {
        if ( ( sources_[source] >> bit ) & 1u )
        {
          terms.push_back( selected_[source] );
        }
      }
      const auto parity = terms.empty() ? network_.get_constant( false )
                                        : network_.create_nary_xor( terms );
      network_.add_clause( ( target_ >> bit ) & 1u ? parity : !parity );
    }
  }

  void constrain_weight()
  {
    std::vector<signal_t> at_least( weight_ + 2u, network_.get_constant( false ) );
    for ( uint32_t index = 0u; index < selected_.size(); ++index )
    {
      auto next = at_least;
      const uint32_t maximum = std::min<uint32_t>( weight_ + 1u, index + 1u );
      for ( uint32_t count = 2u; count <= maximum; ++count )
      {
        next[count] = network_.create_or(
            at_least[count],
            network_.create_and( at_least[count - 1u], selected_[index] ) );
      }
      next[1] = network_.create_or( at_least[1], selected_[index] );
      at_least = std::move( next );
    }
    network_.add_clause( at_least[weight_] );
    network_.add_clause( !at_least[weight_ + 1u] );
  }

private:
  std::vector<uint64_t> const& sources_;
  uint64_t target_;
  uint32_t dimension_;
  uint32_t weight_;
  int conflict_limit_;
  std::vector<signal_t> selected_;
  problem_t network_;
};

std::vector<uint32_t> xor_representations( std::vector<uint32_t> const& left,
                                           std::vector<uint32_t> const& right )
{
  std::vector<uint32_t> result;
  std::set_symmetric_difference( left.begin(), left.end(), right.begin(), right.end(),
                                 std::back_inserter( result ) );
  return result;
}

std::optional<std::vector<uint32_t>> randomized_basis_representation(
    std::vector<uint64_t> const& sources, uint64_t target,
    uint32_t dimension, std::mt19937_64& random )
{
  std::optional<std::vector<uint32_t>> best;
  std::vector<uint32_t> order( sources.size() );
  std::iota( order.begin(), order.end(), 0u );
  for ( uint32_t trial = 0u; trial < 256u; ++trial )
  {
    std::shuffle( order.begin(), order.end(), random );
    std::vector<uint64_t> basis_values( dimension, 0u );
    std::vector<std::vector<uint32_t>> basis_representations( dimension );
    for ( auto index : order )
    {
      auto value = sources[index];
      std::vector<uint32_t> representation{ index };
      for ( int bit = static_cast<int>( dimension ) - 1; bit >= 0; --bit )
      {
        if ( ( ( value >> bit ) & 1u ) == 0u )
        {
          continue;
        }
        if ( basis_values[bit] == 0u )
        {
          basis_values[bit] = value;
          basis_representations[bit] = std::move( representation );
          value = 0u;
          break;
        }
        value ^= basis_values[bit];
        representation = xor_representations(
            representation, basis_representations[bit] );
      }
    }

    auto residual = target;
    std::vector<uint32_t> representation;
    for ( int bit = static_cast<int>( dimension ) - 1; bit >= 0; --bit )
    {
      if ( ( ( residual >> bit ) & 1u ) == 0u )
      {
        continue;
      }
      if ( basis_values[bit] == 0u )
      {
        residual = ~uint64_t{ 0 };
        break;
      }
      residual ^= basis_values[bit];
      representation = xor_representations(
          representation, basis_representations[bit] );
    }
    if ( residual == 0u && ( !best || representation.size() < best->size() ) )
    {
      best = std::move( representation );
    }
  }
  return best;
}

std::optional<std::vector<uint32_t>> minimum_representation(
    std::vector<uint64_t> const& sources, uint64_t target,
    uint32_t dimension, uint32_t maximum_weight, int conflict_limit,
    std::mt19937_64& random )
{
  const auto direct = std::find( sources.begin(), sources.end(), target );
  if ( direct != sources.end() )
  {
    return std::vector<uint32_t>{
        static_cast<uint32_t>( std::distance( sources.begin(), direct ) ) };
  }
  std::vector<uint32_t> order( sources.size() );
  std::iota( order.begin(), order.end(), 0u );
  std::shuffle( order.begin(), order.end(), random );
  std::vector<uint64_t> permuted_sources;
  permuted_sources.reserve( sources.size() );
  for ( auto index : order )
  {
    permuted_sources.push_back( sources[index] );
  }
  for ( uint32_t weight = 2u; weight <= maximum_weight; ++weight )
  {
    sparse_representation_sat solver(
        permuted_sources, target, dimension, weight, conflict_limit );
    if ( auto result = solver.solve() )
    {
      for ( auto& index : *result )
      {
        index = order[index];
      }
      return result;
    }
  }
  return randomized_basis_representation(
      sources, target, dimension, random );
}

uint32_t add_xor( std::vector<uint64_t>& sources,
                  std::vector<std::pair<uint32_t, uint32_t>>& steps,
                  uint32_t left, uint32_t right )
{
  const auto value = sources.at( left ) ^ sources.at( right );
  const auto found = std::find( sources.begin(), sources.end(), value );
  if ( found != sources.end() )
  {
    return static_cast<uint32_t>( std::distance( sources.begin(), found ) );
  }
  steps.emplace_back( left, right );
  sources.push_back( value );
  return static_cast<uint32_t>( sources.size() - 1u );
}

bool materialize_representation(
    std::vector<uint64_t>& sources,
    std::vector<std::pair<uint32_t, uint32_t>>& steps,
    std::vector<uint32_t> const& representation, uint32_t maximum_steps )
{
  if ( representation.empty() )
  {
    return false;
  }
  uint32_t accumulator = representation[0];
  for ( uint32_t index = 1u; index < representation.size(); ++index )
  {
    if ( steps.size() >= maximum_steps )
    {
      return false;
    }
    accumulator = add_xor( sources, steps, accumulator, representation[index] );
  }
  return true;
}

} // namespace

int main( int argc, char** argv )
{
  if ( argc != 6 )
  {
    std::cerr << "usage: xor_sparse_complete PROBLEM.txt MAX_STEPS MAX_WEIGHT CONFLICT_LIMIT SEED\n";
    return 2;
  }
  const auto problem = read_problem( argv[1] );
  if ( !problem )
  {
    std::cerr << "failed to read completion problem\n";
    return 2;
  }
  const uint32_t maximum_steps = static_cast<uint32_t>( std::stoul( argv[2] ) );
  const uint32_t maximum_weight = static_cast<uint32_t>( std::stoul( argv[3] ) );
  const int conflict_limit = std::stoi( argv[4] );
  std::mt19937_64 random( std::stoull( argv[5] ) );

  auto sources = problem->sources;
  std::vector<std::pair<uint32_t, uint32_t>> steps;
  while ( steps.size() < maximum_steps )
  {
    std::vector<std::vector<uint32_t>> representations;
    uint32_t direct_cost = 0u;
    bool failed = false;
    for ( auto target : problem->targets )
    {
      auto representation = minimum_representation(
          sources, target, problem->dimension, maximum_weight, conflict_limit,
          random );
      if ( !representation )
      {
        failed = true;
        break;
      }
      direct_cost += representation->empty() ? 0u
                                             : static_cast<uint32_t>( representation->size() - 1u );
      representations.push_back( *representation );
    }
    if ( failed )
    {
      std::cout << "RESULT status=representation-timeout steps=" << steps.size() << "\n";
      return 1;
    }
    std::cout << "PROGRESS steps=" << steps.size()
              << " direct_cost=" << direct_cost << " weights=";
    for ( auto const& representation : representations )
    {
      std::cout << representation.size() << ",";
    }
    std::cout << "\n";
    if ( steps.empty() )
    {
      for ( uint32_t target = 0u; target < representations.size(); ++target )
      {
        std::cout << "REP " << target;
        for ( auto source : representations[target] )
        {
          std::cout << " " << source;
        }
        std::cout << "\n";
      }
    }
    if ( direct_cost <= maximum_steps - steps.size() )
    {
      for ( auto const& representation : representations )
      {
        if ( !materialize_representation(
                 sources, steps, representation, maximum_steps ) )
        {
          std::cout << "RESULT status=materialization-overflow steps=" << steps.size() << "\n";
          return 1;
        }
      }
      break;
    }

    std::map<std::pair<uint32_t, uint32_t>, uint32_t> frequencies;
    for ( auto const& representation : representations )
    {
      for ( uint32_t i = 1u; i < representation.size(); ++i )
      {
        for ( uint32_t j = 0u; j < i; ++j )
        {
          const auto pair = std::minmax( representation[i], representation[j] );
          const auto value = sources[pair.first] ^ sources[pair.second];
          if ( std::find( sources.begin(), sources.end(), value ) == sources.end() )
          {
            ++frequencies[pair];
          }
        }
      }
    }
    if ( frequencies.empty() )
    {
      break;
    }
    uint32_t best_frequency = 0u;
    std::vector<std::pair<uint32_t, uint32_t>> best_pairs;
    for ( auto const& [pair, frequency] : frequencies )
    {
      if ( frequency > best_frequency )
      {
        best_frequency = frequency;
        best_pairs = { pair };
      }
      else if ( frequency == best_frequency )
      {
        best_pairs.push_back( pair );
      }
    }
    std::uniform_int_distribution<size_t> choice( 0u, best_pairs.size() - 1u );
    const auto selected = best_pairs[choice( random )];
    std::cout << "PAIR frequency=" << best_frequency
              << " choices=" << best_pairs.size()
              << " left=" << selected.first
              << " right=" << selected.second << "\n";
    add_xor( sources, steps, selected.first, selected.second );
  }

  for ( auto target : problem->targets )
  {
    if ( std::find( sources.begin(), sources.end(), target ) == sources.end() )
    {
      std::cout << "RESULT status=no-completion steps=" << steps.size() << "\n";
      return 1;
    }
  }
  auto values = problem->sources;
  for ( uint32_t step = 0u; step < steps.size(); ++step )
  {
    const auto [left, right] = steps[step];
    const auto value = values[left] ^ values[right];
    values.push_back( value );
    std::cout << "STEP " << step << " " << left << " " << right << " "
              << std::hex << value << std::dec << "\n";
  }
  std::cout << "RESULT status=completed steps=" << steps.size() << "\n";
  return 0;
}
