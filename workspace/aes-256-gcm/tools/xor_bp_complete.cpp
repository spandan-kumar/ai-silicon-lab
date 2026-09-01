#include <algorithm>
#include <bitset>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace
{
struct problem_t
{
  uint32_t dimension{};
  std::vector<uint64_t> sources;
  std::vector<uint64_t> targets;
};

problem_t compress_problem( problem_t problem )
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
  for ( auto source : problem.sources )
  {
    auto [remainder, coordinate] = reduce( source );
    if ( remainder )
    {
      const auto pivot = 63u - static_cast<uint32_t>( __builtin_clzll( remainder ) );
      basis_value[pivot] = remainder;
      basis_coordinate[pivot] = uint64_t{ 1 } << rank;
      coordinate ^= uint64_t{ 1 } << rank++;
    }
    compressed_sources.push_back( coordinate );
  }
  std::vector<uint64_t> compressed_targets;
  for ( auto target : problem.targets )
  {
    const auto [remainder, coordinate] = reduce( target );
    if ( remainder ) throw std::runtime_error( "target is outside source span" );
    compressed_targets.push_back( coordinate );
  }
  problem.dimension = rank;
  problem.sources = std::move( compressed_sources );
  problem.targets = std::move( compressed_targets );
  return problem;
}

std::optional<problem_t> read_problem( std::string const& path )
{
  std::ifstream input( path );
  if ( !input ) return std::nullopt;
  problem_t problem;
  std::string line;
  while ( std::getline( input, line ) )
  {
    if ( line.empty() || line.front() == '#' ) continue;
    std::istringstream stream( line );
    std::string kind, value;
    stream >> kind >> value;
    if ( kind == "DIM" ) problem.dimension = std::stoul( value );
    else if ( kind == "SOURCE" || kind == "TARGET" )
      ( kind == "SOURCE" ? problem.sources : problem.targets )
          .push_back( std::stoull( value, nullptr, 16 ) );
    else return std::nullopt;
  }
  if ( problem.dimension == 0u || problem.dimension > 64u ||
       problem.sources.empty() || problem.targets.empty() ) return std::nullopt;
  return compress_problem( std::move( problem ) );
}

uint32_t weight( uint64_t mask )
{
  return static_cast<uint32_t>( __builtin_popcountll( mask ) );
}

struct sparse_index
{
  explicit sparse_index( std::vector<uint64_t> const& sources )
      : sources( sources )
  {
    if ( sources.size() > 63u )
      throw std::runtime_error( "at most 63 sources are supported" );
    subsets2.emplace_back( 0u, 0u );
    subsets3.emplace_back( 0u, 0u );
    subsets4.emplace_back( 0u, 0u );
    add3[0u].push_back( 0u );
    add4[0u].push_back( 0u );
    for ( uint32_t i = 0u; i < sources.size(); ++i )
    {
      const uint64_t mi = uint64_t{ 1 } << i;
      subsets2.emplace_back( sources[i], mi );
      subsets3.emplace_back( sources[i], mi );
      subsets4.emplace_back( sources[i], mi );
      add3[sources[i]].push_back( mi );
      add4[sources[i]].push_back( mi );
      for ( uint32_t j = i + 1u; j < sources.size(); ++j )
      {
        const uint64_t mij = mi | ( uint64_t{ 1 } << j );
        const uint64_t vij = sources[i] ^ sources[j];
        subsets2.emplace_back( vij, mij );
        subsets3.emplace_back( vij, mij );
        subsets4.emplace_back( vij, mij );
        add3[vij].push_back( mij );
        add4[vij].push_back( mij );
        for ( uint32_t k = j + 1u; k < sources.size(); ++k )
        {
          const auto mijk = mij | ( uint64_t{ 1 } << k );
          const auto vijk = vij ^ sources[k];
          subsets3.emplace_back( vijk, mijk );
          subsets4.emplace_back( vijk, mijk );
          add3[vijk].push_back( mijk );
          add4[vijk].push_back( mijk );
          for ( uint32_t l = k + 1u; l < sources.size(); ++l )
          {
            const auto mijkl = mijk | ( uint64_t{ 1 } << l );
            const auto vijkl = vijk ^ sources[l];
            subsets4.emplace_back( vijkl, mijkl );
            add4[vijkl].push_back( mijkl );
          }
        }
      }
    }
    const auto by_weight = []( auto const& a, auto const& b ) {
      return weight( a.second ) < weight( b.second );
    };
    std::stable_sort( subsets2.begin(), subsets2.end(), by_weight );
    std::stable_sort( subsets3.begin(), subsets3.end(), by_weight );
    std::stable_sort( subsets4.begin(), subsets4.end(), by_weight );

    uint64_t union_value = 0u;
    for ( auto value : sources ) union_value |= value;
    const auto bits = union_value ? 64u - static_cast<uint32_t>( __builtin_clzll( union_value ) ) : 0u;
    if ( bits <= 22u )
    {
      representations5.assign( uint64_t{ 1 } << bits, ~uint64_t{ 0 } );
      representations5[0u] = 0u;
      const auto record = [&]( uint64_t value, uint64_t mask ) {
        auto& current = representations5[value];
        if ( current == ~uint64_t{ 0 } || weight( mask ) < weight( current ) )
          current = mask;
      };
      for ( uint32_t i = 0u; i < sources.size(); ++i )
      {
        const auto mi = uint64_t{ 1 } << i;
        const auto vi = sources[i];
        record( vi, mi );
        for ( uint32_t j = i + 1u; j < sources.size(); ++j )
        {
          const auto mij = mi | ( uint64_t{ 1 } << j );
          const auto vij = vi ^ sources[j];
          record( vij, mij );
          for ( uint32_t k = j + 1u; k < sources.size(); ++k )
          {
            const auto mijk = mij | ( uint64_t{ 1 } << k );
            const auto vijk = vij ^ sources[k];
            record( vijk, mijk );
            for ( uint32_t l = k + 1u; l < sources.size(); ++l )
            {
              const auto mijkl = mijk | ( uint64_t{ 1 } << l );
              const auto vijkl = vijk ^ sources[l];
              record( vijkl, mijkl );
              for ( uint32_t m = l + 1u; m < sources.size(); ++m )
                record( vijkl ^ sources[m],
                        mijkl | ( uint64_t{ 1 } << m ) );
            }
          }
        }
      }
    }
  }

  std::optional<uint64_t> representation( uint64_t target,
                                          uint32_t maximum_weight ) const
  {
    if ( maximum_weight <= 5u && target < representations5.size() )
    {
      const auto mask = representations5[target];
      if ( mask != ~uint64_t{ 0 } && weight( mask ) <= maximum_weight )
        return mask;
      return std::nullopt;
    }
    std::optional<uint64_t> best;
    uint32_t best_weight = maximum_weight + 1u;
    const auto& left_subsets = maximum_weight >= 8u ? subsets4
                                                    : maximum_weight >= 6u ? subsets3
                                                                           : subsets2;
    const auto& right_index = maximum_weight >= 7u ? add4 : add3;
    for ( auto const& [left_value, left_mask] : left_subsets )
    {
      const auto left_weight = weight( left_mask );
      if ( left_weight >= best_weight ) break;
      const auto found = right_index.find( target ^ left_value );
      if ( found == right_index.end() ) continue;
      for ( auto right_mask : found->second )
      {
        if ( left_mask & right_mask ) continue;
        const auto combined = left_mask | right_mask;
        const auto combined_weight = weight( combined );
        if ( combined_weight <= maximum_weight && combined_weight < best_weight )
        {
          best = combined;
          best_weight = combined_weight;
          if ( best_weight == 0u ) return best;
        }
      }
    }
    return best;
  }

  std::vector<uint64_t> const& sources;
  std::vector<std::pair<uint64_t, uint64_t>> subsets2;
  std::vector<std::pair<uint64_t, uint64_t>> subsets3;
  std::vector<std::pair<uint64_t, uint64_t>> subsets4;
  std::unordered_map<uint64_t, std::vector<uint64_t>> add3;
  std::unordered_map<uint64_t, std::vector<uint64_t>> add4;
  std::vector<uint64_t> representations5;
};

uint32_t add_xor( std::vector<uint64_t>& sources,
                  std::vector<std::pair<uint32_t, uint32_t>>& steps,
                  uint32_t left, uint32_t right )
{
  const auto value = sources.at( left ) ^ sources.at( right );
  const auto found = std::find( sources.begin(), sources.end(), value );
  if ( found != sources.end() )
    return static_cast<uint32_t>( std::distance( sources.begin(), found ) );
  steps.emplace_back( left, right );
  sources.push_back( value );
  return static_cast<uint32_t>( sources.size() - 1u );
}

bool materialize( std::vector<uint64_t>& sources,
                  std::vector<std::pair<uint32_t, uint32_t>>& steps,
                  uint64_t mask, uint32_t maximum_steps )
{
  std::vector<uint32_t> terms;
  for ( uint32_t i = 0u; i < 64u; ++i )
    if ( ( mask >> i ) & 1u ) terms.push_back( i );
  if ( terms.empty() ) return false;
  auto accumulator = terms.front();
  for ( uint32_t i = 1u; i < terms.size(); ++i )
  {
    if ( steps.size() >= maximum_steps ) return false;
    accumulator = add_xor( sources, steps, accumulator, terms[i] );
  }
  return true;
}
} // namespace

int main( int argc, char** argv )
{
  if ( argc < 4 || argc > 6 )
  {
    std::cerr << "usage: xor_bp_complete PROBLEM.txt MAX_STEPS SEED "
                 "[SLACK] [SOURCE_INDICES]\n";
    return 2;
  }
  auto problem = read_problem( argv[1] );
  if ( !problem ) return 2;
  const uint32_t maximum_steps = std::stoul( argv[2] );
  std::mt19937_64 random( std::stoull( argv[3] ) );
  const uint32_t slack = argc >= 5 ? std::stoul( argv[4] ) : 0u;
  std::vector<uint32_t> source_map;
  if ( argc == 6 )
  {
    std::vector<uint64_t> selected_sources;
    std::istringstream stream( argv[5] );
    std::string piece;
    while ( std::getline( stream, piece, ',' ) )
    {
      const auto index = static_cast<uint32_t>( std::stoul( piece ) );
      if ( index >= problem->sources.size() ) return 2;
      source_map.push_back( index );
      selected_sources.push_back( problem->sources[index] );
    }
    problem->sources = std::move( selected_sources );
    *problem = compress_problem( std::move( *problem ) );
  }
  auto sources = problem->sources;
  std::vector<std::pair<uint32_t, uint32_t>> steps;

  while ( steps.size() < maximum_steps )
  {
    sparse_index index( sources );
    std::vector<std::optional<uint64_t>> direct;
    uint32_t direct_cost = 0u;
    for ( auto target : problem->targets )
    {
      if ( std::find( sources.begin(), sources.end(), target ) != sources.end() )
      {
        direct.push_back( std::nullopt );
        continue;
      }
      auto representation = index.representation( target, 8u );
      if ( !representation )
      {
        std::cout << "RESULT status=unrepresented steps=" << steps.size() << "\n";
        return 1;
      }
      direct_cost += weight( *representation ) - 1u;
      direct.push_back( representation );
    }
    std::cout << "PROGRESS steps=" << steps.size()
              << " direct_cost=" << direct_cost << "\n";
    if ( direct_cost <= maximum_steps - steps.size() )
    {
      for ( auto const& representation : direct )
        if ( representation &&
             !materialize( sources, steps, *representation, maximum_steps ) )
          break;
      break;
    }

    struct candidate_t
    {
      uint32_t left, right, sum, squares;
    };
    std::vector<candidate_t> candidates;
    uint32_t best_sum = std::numeric_limits<uint32_t>::max();
    std::unordered_map<uint32_t, uint32_t> best_squares;
    std::unordered_set<uint64_t> seen_values;
    for ( uint32_t left = 0u; left < sources.size(); ++left )
      for ( uint32_t right = left + 1u; right < sources.size(); ++right )
      {
        const auto value = sources[left] ^ sources[right];
        if ( std::find( sources.begin(), sources.end(), value ) != sources.end() ||
             !seen_values.insert( value ).second ) continue;
        uint32_t sum = 0u, squares = 0u;
        for ( uint32_t target_index = 0u;
              target_index < problem->targets.size(); ++target_index )
        {
          const auto target = problem->targets[target_index];
          uint32_t cost = direct[target_index]
                              ? weight( *direct[target_index] ) - 1u
                              : 0u;
          if ( target == value ) cost = 0u;
          else if ( auto residual = index.representation( target ^ value, 5u ) )
            cost = std::min( cost, weight( *residual ) );
          sum += cost;
          squares += cost * cost;
        }
        best_sum = std::min( best_sum, sum );
        best_squares[sum] = std::max( best_squares[sum], squares );
        candidates.push_back( { left, right, sum, squares } );
      }
    std::vector<candidate_t> eligible;
    std::vector<double> weights;
    for ( auto const& candidate : candidates )
      if ( candidate.sum <= best_sum + slack &&
           candidate.squares == best_squares[candidate.sum] )
      {
        eligible.push_back( candidate );
        weights.push_back( double( uint64_t{ 1 } <<
                                   std::min( slack - ( candidate.sum - best_sum ),
                                             20u ) ) );
      }
    if ( eligible.empty() ) break;
    std::discrete_distribution<size_t> choose( weights.begin(), weights.end() );
    const auto selected = eligible[choose( random )];
    std::cout << "PAIR left=" << selected.left << " right=" << selected.right
              << " next_sum=" << selected.sum
              << " choices=" << eligible.size() << " slack=" << slack << "\n";
    add_xor( sources, steps, selected.left, selected.right );
  }

  for ( auto target : problem->targets )
    if ( std::find( sources.begin(), sources.end(), target ) == sources.end() )
    {
      std::cout << "RESULT status=no-completion steps=" << steps.size() << "\n";
      return 1;
    }
  auto values = problem->sources;
  for ( uint32_t source = 0u; source < source_map.size(); ++source )
    std::cout << "SOURCE " << source << " " << source_map[source] << "\n";
  for ( uint32_t step = 0u; step < steps.size(); ++step )
  {
    const auto [left, right] = steps[step];
    const auto value = values.at( left ) ^ values.at( right );
    values.push_back( value );
    std::cout << "STEP " << step << " " << left << " " << right << " "
              << std::hex << value << std::dec << "\n";
  }
  std::cout << "RESULT status=completed steps=" << steps.size() << "\n";
  return 0;
}
