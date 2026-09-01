#include <mockturtle/algorithms/linear_resynthesis.hpp>
#include <mockturtle/networks/xag.hpp>

#include <bill/sat/solver.hpp>

#include <cstdint>
#include <fstream>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
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
  return problem;
}

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
} // namespace

int main( int argc, char** argv )
{
  if ( argc != 5 )
  {
    std::cerr << "usage: xor_linear_exact PROBLEM.txt UPPER_BOUND "
                 "CONFLICT_LIMIT SOURCE_INDICES\n";
    return 2;
  }
  auto problem = read_problem( argv[1] );
  if ( !problem ) return 2;
  std::vector<uint32_t> source_map;
  std::vector<uint64_t> selected_sources;
  std::istringstream stream( argv[4] );
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
  if ( problem->dimension != problem->sources.size() )
  {
    std::cerr << "selected sources must be linearly independent\n";
    return 2;
  }

  std::vector<std::vector<bool>> matrix;
  for ( auto target : problem->targets )
  {
    std::vector<bool> row( problem->dimension );
    for ( uint32_t bit = 0u; bit < problem->dimension; ++bit )
      row[bit] = ( target >> bit ) & 1u;
    matrix.push_back( std::move( row ) );
  }
  mockturtle::exact_linear_synthesis_params params;
  params.upper_bound = static_cast<uint32_t>( std::stoul( argv[2] ) );
  params.conflict_limit = std::stoi( argv[3] );
  params.verbose = true;
  mockturtle::exact_linear_synthesis_stats stats;
  const auto network = mockturtle::exact_linear_synthesis<
      mockturtle::xag_network, bill::solvers::glucose_41>( matrix, params, &stats );
  stats.report();
  if ( !network )
  {
    std::cout << "RESULT status=no-solution-or-timeout upper_bound="
              << *params.upper_bound << "\n";
    return 1;
  }

  std::unordered_map<uint32_t, uint32_t> signal_index;
  std::unordered_map<uint32_t, uint64_t> value;
  network->foreach_pi( [&]( auto node, auto index ) {
    signal_index[node] = index;
    value[node] = uint64_t{ 1 } << index;
    std::cout << "SOURCE " << index << " " << source_map[index] << "\n";
  } );
  uint32_t step = 0u;
  network->foreach_gate( [&]( auto node ) {
    std::vector<uint32_t> children;
    network->foreach_fanin( node, [&]( auto signal ) {
      if ( network->is_complemented( signal ) )
        throw std::runtime_error( "linear solution contains a complement" );
      children.push_back( network->get_node( signal ) );
    } );
    if ( children.size() != 2u )
      throw std::runtime_error( "linear solution gate is not binary" );
    const auto left = signal_index.at( children[0] );
    const auto right = signal_index.at( children[1] );
    signal_index[node] = static_cast<uint32_t>( problem->sources.size() ) + step;
    value[node] = value.at( children[0] ) ^ value.at( children[1] );
    std::cout << "STEP " << step++ << " " << left << " " << right << " "
              << std::hex << value[node] << std::dec << "\n";
  } );
  network->foreach_po( [&]( auto signal, auto index ) {
    const auto node = network->get_node( signal );
    if ( network->is_complemented( signal ) || value.at( node ) != problem->targets[index] )
      throw std::runtime_error( "extracted solution fails matrix verification" );
    std::cout << "TARGET " << index << " " << signal_index.at( node ) << "\n";
  } );
  std::cout << "RESULT status=sat steps=" << network->num_gates()
            << " inputs=" << network->num_pis()
            << " targets=" << network->num_pos() << "\n";
  return 0;
}
