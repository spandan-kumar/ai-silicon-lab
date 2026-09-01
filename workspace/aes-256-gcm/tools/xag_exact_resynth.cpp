#include <mockturtle/algorithms/extract_linear.hpp>
#include <mockturtle/algorithms/cut_rewriting.hpp>
#include <mockturtle/algorithms/linear_resynthesis.hpp>
#include <mockturtle/algorithms/node_resynthesis/xag_npn.hpp>
#include <mockturtle/algorithms/sim_resub.hpp>
#include <mockturtle/algorithms/simulation.hpp>
#include <mockturtle/algorithms/xag_optimization.hpp>
#include <mockturtle/algorithms/xag_resub.hpp>
#include <mockturtle/io/write_verilog.hpp>
#include <mockturtle/networks/xag.hpp>
#include <mockturtle/properties/mccost.hpp>
#include <mockturtle/utils/node_map.hpp>
#include <mockturtle/views/topo_view.hpp>
#include <mockturtle/views/depth_view.hpp>
#include <mockturtle/views/fanout_view.hpp>

#include <kitty/static_truth_table.hpp>

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

namespace
{

std::string trim( std::string value )
{
  const auto first = value.find_first_not_of( " \t\r\n" );
  if ( first == std::string::npos )
  {
    return {};
  }
  const auto last = value.find_last_not_of( " \t\r\n" );
  return value.substr( first, last - first + 1 );
}

std::optional<mockturtle::xag_network> read_xag_bench( std::string const& path )
{
  std::ifstream input( path );
  if ( !input )
  {
    return std::nullopt;
  }
  mockturtle::xag_network network;
  std::unordered_map<std::string, mockturtle::xag_network::signal> signals;
  std::vector<std::string> outputs;
  std::string raw;
  while ( std::getline( input, raw ) )
  {
    const auto line = trim( raw );
    if ( line.empty() || line.front() == '#' )
    {
      continue;
    }
    if ( line.rfind( "INPUT(", 0 ) == 0 && line.back() == ')' )
    {
      signals[line.substr( 6, line.size() - 7 )] = network.create_pi();
      continue;
    }
    if ( line.rfind( "OUTPUT(", 0 ) == 0 && line.back() == ')' )
    {
      outputs.push_back( line.substr( 7, line.size() - 8 ) );
      continue;
    }

    const auto equal = line.find( '=' );
    const auto open = line.find( '(', equal );
    const auto comma = line.find( ',', open );
    const auto close = line.find( ')', comma );
    if ( equal == std::string::npos || open == std::string::npos ||
         comma == std::string::npos || close == std::string::npos )
    {
      return std::nullopt;
    }
    const auto destination = trim( line.substr( 0, equal ) );
    const auto operation = trim( line.substr( equal + 1, open - equal - 1 ) );
    const auto left_name = trim( line.substr( open + 1, comma - open - 1 ) );
    const auto right_name = trim( line.substr( comma + 1, close - comma - 1 ) );
    if ( !signals.count( left_name ) || !signals.count( right_name ) )
    {
      return std::nullopt;
    }
    const auto left = signals.at( left_name );
    const auto right = signals.at( right_name );
    if ( operation == "AND" )
    {
      signals[destination] = network.create_and( left, right );
    }
    else if ( operation == "XOR" )
    {
      signals[destination] = network.create_xor( left, right );
    }
    else if ( operation == "XNOR" )
    {
      signals[destination] = network.create_xnor( left, right );
    }
    else
    {
      return std::nullopt;
    }
  }
  for ( auto const& output : outputs )
  {
    if ( !signals.count( output ) )
    {
      return std::nullopt;
    }
    network.create_po( signals.at( output ) );
  }
  return network;
}

uint32_t count_xors( mockturtle::xag_network const& network )
{
  uint32_t count = 0;
  network.foreach_gate( [&]( auto node ) {
    if ( network.is_xor( node ) )
    {
      ++count;
    }
  } );
  return count;
}

uint32_t gate_depth( mockturtle::xag_network const& network )
{
  mockturtle::depth_view depth{ network };
  return depth.depth();
}

uint32_t count_complemented_trivial_outputs(
    mockturtle::xag_network const& linear,
    std::vector<bool> const& output_phases )
{
  uint32_t count = 0u;
  linear.foreach_po( [&]( auto output, auto index ) {
    const auto node = linear.get_node( output );
    if ( output_phases.at( index ) &&
         ( linear.is_constant( node ) || linear.is_pi( node ) ) )
    {
      ++count;
    }
  } );
  return count;
}

std::pair<mockturtle::xag_network, std::vector<bool>> strip_affine_phases(
    mockturtle::xag_network const& source )
{
  mockturtle::xag_network destination;
  mockturtle::node_map<mockturtle::xag_network::signal,
                       mockturtle::xag_network>
      old_to_new( source );
  old_to_new[source.get_constant( false )] =
      destination.get_constant( false );
  mockturtle::node_map<bool, mockturtle::xag_network> phases( source, false );
  source.foreach_pi( [&]( auto node ) {
    old_to_new[node] = destination.create_pi();
  } );

  mockturtle::topo_view topo{ source };
  topo.foreach_node( [&]( auto node ) {
    if ( source.is_constant( node ) || source.is_pi( node ) )
    {
      return;
    }
    std::array<mockturtle::xag_network::signal, 2> children{};
    std::array<bool, 2> child_phases{};
    source.foreach_fanin( node, [&]( auto fanin, auto index ) {
      children[index] = old_to_new[fanin];
      child_phases[index] =
          phases[fanin] ^ source.is_complemented( fanin );
    } );
    if ( !source.is_xor( node ) )
    {
      std::cerr << "affine extraction unexpectedly contains a nonlinear node\n";
      std::abort();
    }
    old_to_new[node] = destination.create_xor( children[0], children[1] );
    phases[node] = child_phases[0] ^ child_phases[1];
  } );
  std::vector<bool> output_phases;
  source.foreach_po( [&]( auto output ) {
    destination.create_po( old_to_new[output] );
    output_phases.push_back(
        phases[output] ^ source.is_complemented( output ) );
  } );
  return { destination, output_phases };
}

mockturtle::xag_network apply_output_phases(
    mockturtle::xag_network const& source,
    std::vector<bool> const& output_phases )
{
  mockturtle::xag_network destination;
  mockturtle::node_map<mockturtle::xag_network::signal,
                       mockturtle::xag_network>
      old_to_new( source );
  old_to_new[source.get_constant( false )] =
      destination.get_constant( false );
  source.foreach_pi( [&]( auto node ) {
    old_to_new[node] = destination.create_pi();
  } );
  mockturtle::topo_view topo{ source };
  topo.foreach_node( [&]( auto node ) {
    if ( source.is_constant( node ) || source.is_pi( node ) )
    {
      return;
    }
    std::array<mockturtle::xag_network::signal, 2> children{};
    source.foreach_fanin( node, [&]( auto fanin, auto index ) {
      children[index] = old_to_new[fanin] ^ source.is_complemented( fanin );
    } );
    old_to_new[node] = destination.create_xor( children[0], children[1] );
  } );
  source.foreach_po( [&]( auto output, auto index ) {
    destination.create_po(
        old_to_new[output] ^ source.is_complemented( output ) ^
        output_phases.at( index ) );
  } );
  return destination;
}

std::vector<std::vector<uint32_t>> availability_constraints(
    uint32_t original_outputs, uint32_t original_inputs, uint32_t ands )
{
  std::vector<std::vector<uint32_t>> ignored( original_outputs );
  for ( uint32_t index = 0; index < ands; ++index )
  {
    std::vector<uint32_t> future;
    for ( uint32_t future_index = index; future_index < ands; ++future_index )
    {
      future.push_back( original_inputs + future_index );
    }
    ignored.push_back( future );
    ignored.push_back( future );
  }
  return ignored;
}

} // namespace

int main( int argc, char** argv )
{
  if ( argc < 5 || argc > 7 )
  {
    std::cerr << "usage: xag_exact_resynth INPUT.bench OUTPUT.v UPPER_BOUND "
                 "CONFLICT_LIMIT [MAX_AND_DEPTH] [MAX_AND_GATES]\n";
    return 2;
  }

  const auto maybe_parsed_network = read_xag_bench( argv[1] );
  if ( !maybe_parsed_network )
  {
    std::cerr << "failed to parse input BENCH\n";
    return 2;
  }
  const auto& network = *maybe_parsed_network;
  if ( network.num_pis() != 8u )
  {
    std::cerr << "expected an eight-input S-box network\n";
    return 2;
  }
  const auto maybe_ands = mockturtle::multiplicative_complexity( network );
  if ( !maybe_ands )
  {
    std::cerr << "could not determine multiplicative complexity\n";
    return 2;
  }
  const uint32_t ands = *maybe_ands;
  const uint32_t original_and_depth =
      *mockturtle::multiplicative_complexity_depth( network );
  const uint32_t original_inputs = network.num_pis();
  const uint32_t original_outputs = network.num_pos();
  const uint32_t original_xors = count_xors( network );
  const uint32_t upper_bound = static_cast<uint32_t>( std::stoul( argv[3] ) );
  const int conflict_limit = std::stoi( argv[4] );
  const uint32_t maximum_and_depth =
      argc >= 6 ? static_cast<uint32_t>( std::stoul( argv[5] ) )
                : original_and_depth;
  const uint32_t maximum_and_gates =
      argc == 7 ? static_cast<uint32_t>( std::stoul( argv[6] ) ) : ands;

  const auto constant_optimized =
      mockturtle::xag_constant_fanin_optimization( network );
  const auto original_truth =
      mockturtle::simulate<kitty::static_truth_table<8>>( network );
  const auto constant_truth =
      mockturtle::simulate<kitty::static_truth_table<8>>( constant_optimized );
  std::cout << "HEURISTIC method=constant-fanin"
            << " original_xors=" << original_xors
            << " synthesized_xors=" << count_xors( constant_optimized )
            << " synthesized_ands="
            << *mockturtle::multiplicative_complexity( constant_optimized )
            << " equivalent=" << ( constant_truth == original_truth ) << "\n";

  const auto dont_care_optimized =
      mockturtle::xag_dont_cares_optimization( network );
  const auto dont_care_truth =
      mockturtle::simulate<kitty::static_truth_table<8>>( dont_care_optimized );
  std::cout << "HEURISTIC method=dont-care"
            << " original_xors=" << original_xors
            << " synthesized_xors=" << count_xors( dont_care_optimized )
            << " synthesized_ands="
            << *mockturtle::multiplicative_complexity( dont_care_optimized )
            << " equivalent=" << ( dont_care_truth == original_truth ) << "\n";

  auto resub_optimized = mockturtle::cleanup_dangling( network );
  mockturtle::resubstitution_params resub_params;
  resub_params.max_pis = 8u;
  resub_params.max_divisors = 150u;
  resub_params.max_inserts = 2u;
  resub_params.preserve_depth = true;
  uint32_t resub_passes = 0u;
  for ( ; resub_passes < 8u; ++resub_passes )
  {
    const auto gates_before = resub_optimized.num_gates();
    {
      mockturtle::fanout_view fanout{ resub_optimized };
      mockturtle::depth_view resub_view{ fanout };
      mockturtle::xag_resubstitution( resub_view, resub_params );
    }
    resub_optimized = mockturtle::cleanup_dangling( resub_optimized );
    if ( resub_optimized.num_gates() >= gates_before )
    {
      ++resub_passes;
      break;
    }
  }
  const auto resub_truth =
      mockturtle::simulate<kitty::static_truth_table<8>>( resub_optimized );
  std::cout << "HEURISTIC method=xag-resubstitution"
            << " original_xors=" << original_xors
            << " synthesized_xors=" << count_xors( resub_optimized )
            << " synthesized_ands="
            << *mockturtle::multiplicative_complexity( resub_optimized )
            << " synthesized_and_depth="
            << *mockturtle::multiplicative_complexity_depth( resub_optimized )
            << " synthesized_gate_depth=" << gate_depth( resub_optimized )
            << " passes=" << resub_passes
            << " equivalent=" << ( resub_truth == original_truth ) << "\n";

  auto dc_resub_optimized = mockturtle::cleanup_dangling( network );
  resub_params.use_dont_cares = true;
  resub_params.window_size = 12u;
  uint32_t dc_resub_passes = 0u;
  for ( ; dc_resub_passes < 8u; ++dc_resub_passes )
  {
    const auto gates_before = dc_resub_optimized.num_gates();
    {
      mockturtle::fanout_view dc_fanout{ dc_resub_optimized };
      mockturtle::depth_view dc_resub_view{ dc_fanout };
      mockturtle::xag_resubstitution( dc_resub_view, resub_params );
    }
    dc_resub_optimized = mockturtle::cleanup_dangling( dc_resub_optimized );
    if ( dc_resub_optimized.num_gates() >= gates_before )
    {
      ++dc_resub_passes;
      break;
    }
  }
  const auto dc_resub_truth =
      mockturtle::simulate<kitty::static_truth_table<8>>( dc_resub_optimized );
  std::cout << "HEURISTIC method=xag-resubstitution-dc"
            << " original_xors=" << original_xors
            << " synthesized_xors=" << count_xors( dc_resub_optimized )
            << " synthesized_ands="
            << *mockturtle::multiplicative_complexity( dc_resub_optimized )
            << " synthesized_and_depth="
            << *mockturtle::multiplicative_complexity_depth( dc_resub_optimized )
            << " synthesized_gate_depth=" << gate_depth( dc_resub_optimized )
            << " passes=" << dc_resub_passes
            << " equivalent=" << ( dc_resub_truth == original_truth ) << "\n";

  auto sweep_best = mockturtle::cleanup_dangling( network );
  uint32_t sweep_trials = 0u;
  for ( auto max_pis : { 4u, 6u, 8u } )
  {
    for ( auto max_divisors : { 50u, 150u } )
    {
      for ( auto max_inserts : { 0u, 1u, 2u } )
      {
        for ( auto use_dont_cares : { false, true } )
        {
          auto candidate = mockturtle::cleanup_dangling( network );
          mockturtle::resubstitution_params params;
          params.max_pis = max_pis;
          params.max_divisors = max_divisors;
          params.max_inserts = max_inserts;
          params.preserve_depth = true;
          params.use_dont_cares = use_dont_cares;
          params.window_size = 12u;
          {
            mockturtle::fanout_view candidate_fanout{ candidate };
            mockturtle::depth_view candidate_view{ candidate_fanout };
            mockturtle::xag_resubstitution( candidate_view, params );
          }
          candidate = mockturtle::cleanup_dangling( candidate );
          ++sweep_trials;
          const auto candidate_truth =
              mockturtle::simulate<kitty::static_truth_table<8>>( candidate );
          const auto candidate_and_depth =
              *mockturtle::multiplicative_complexity_depth( candidate );
          if ( candidate_truth == original_truth &&
               candidate_and_depth <= original_and_depth &&
               candidate.num_gates() < sweep_best.num_gates() )
          {
            sweep_best = std::move( candidate );
          }
        }
      }
    }
  }
  std::cout << "HEURISTIC method=xag-resubstitution-sweep"
            << " trials=" << sweep_trials
            << " original_xors=" << original_xors
            << " synthesized_xors=" << count_xors( sweep_best )
            << " synthesized_ands="
            << *mockturtle::multiplicative_complexity( sweep_best )
            << " synthesized_and_depth="
            << *mockturtle::multiplicative_complexity_depth( sweep_best )
            << " synthesized_gate_depth=" << gate_depth( sweep_best )
            << " equivalent="
            << ( mockturtle::simulate<kitty::static_truth_table<8>>( sweep_best ) ==
                 original_truth )
            << "\n";

  auto cut_rewrite = mockturtle::cleanup_dangling( network );
  {
    mockturtle::xag_npn_resynthesis<
        mockturtle::xag_network, mockturtle::xag_network,
        mockturtle::xag_npn_db_kind::xag_complete>
        resynthesis;
    mockturtle::cut_rewriting_params params;
    params.cut_enumeration_ps.cut_size = 4u;
    params.min_cand_cut_size = 2u;
    params.min_cand_cut_size_override = 3u;
    cut_rewrite = mockturtle::cut_rewriting(
        cut_rewrite, resynthesis, params );
    cut_rewrite = mockturtle::cleanup_dangling( cut_rewrite );
  }
  std::cout << "HEURISTIC method=xag-npn4-complete"
            << " original_xors=" << original_xors
            << " synthesized_xors=" << count_xors( cut_rewrite )
            << " synthesized_ands="
            << *mockturtle::multiplicative_complexity( cut_rewrite )
            << " synthesized_and_depth="
            << *mockturtle::multiplicative_complexity_depth( cut_rewrite )
            << " synthesized_gate_depth=" << gate_depth( cut_rewrite )
            << " equivalent="
            << ( mockturtle::simulate<kitty::static_truth_table<8>>( cut_rewrite ) ==
                 original_truth )
            << "\n";

  auto cut_rewrite_depth = mockturtle::cleanup_dangling( network );
  {
    mockturtle::xag_npn_resynthesis<
        mockturtle::xag_network, mockturtle::xag_network,
        mockturtle::xag_npn_db_kind::xag_complete>
        resynthesis;
    mockturtle::cut_rewriting_params params;
    params.cut_enumeration_ps.cut_size = 4u;
    params.min_cand_cut_size = 2u;
    params.min_cand_cut_size_override = 3u;
    params.preserve_depth = true;
    params.allow_zero_gain = true;
    cut_rewrite_depth = mockturtle::cut_rewriting(
        cut_rewrite_depth, resynthesis, params );
    cut_rewrite_depth = mockturtle::cleanup_dangling( cut_rewrite_depth );
  }
  std::cout << "HEURISTIC method=xag-npn4-complete-depth"
            << " original_xors=" << original_xors
            << " synthesized_xors=" << count_xors( cut_rewrite_depth )
            << " synthesized_ands="
            << *mockturtle::multiplicative_complexity( cut_rewrite_depth )
            << " synthesized_and_depth="
            << *mockturtle::multiplicative_complexity_depth( cut_rewrite_depth )
            << " synthesized_gate_depth=" << gate_depth( cut_rewrite_depth )
            << " equivalent="
            << ( mockturtle::simulate<kitty::static_truth_table<8>>( cut_rewrite_depth ) ==
                 original_truth )
            << "\n";

  auto sim_resub_optimized = mockturtle::cleanup_dangling( network );
  {
    mockturtle::resubstitution_params params;
    params.max_pis = 8u;
    params.max_divisors = 150u;
    params.max_inserts = 2u;
    params.preserve_depth = true;
    params.conflict_limit = 10000u;
    mockturtle::sim_resubstitution( sim_resub_optimized, params );
    sim_resub_optimized =
        mockturtle::cleanup_dangling( sim_resub_optimized );
  }
  std::cout << "HEURISTIC method=simulation-guided-resubstitution"
            << " original_xors=" << original_xors
            << " synthesized_xors=" << count_xors( sim_resub_optimized )
            << " synthesized_ands="
            << *mockturtle::multiplicative_complexity( sim_resub_optimized )
            << " synthesized_and_depth="
            << *mockturtle::multiplicative_complexity_depth( sim_resub_optimized )
            << " synthesized_gate_depth=" << gate_depth( sim_resub_optimized )
            << " equivalent="
            << ( mockturtle::simulate<kitty::static_truth_table<8>>( sim_resub_optimized ) ==
                 original_truth )
            << "\n";

  auto const* local_best_ptr = &network;
  for ( auto const* candidate :
        { &resub_optimized, &dc_resub_optimized, &sweep_best, &cut_rewrite,
          &cut_rewrite_depth, &sim_resub_optimized } )
  {
    const auto candidate_and_depth =
        *mockturtle::multiplicative_complexity_depth( *candidate );
    const auto candidate_ands =
        *mockturtle::multiplicative_complexity( *candidate );
    const auto better_size =
        candidate->num_gates() < local_best_ptr->num_gates();
    const auto equal_size_better_depth =
        candidate->num_gates() == local_best_ptr->num_gates() &&
        gate_depth( *candidate ) < gate_depth( *local_best_ptr );
    const auto equal_size_depth_better_and_depth =
        candidate->num_gates() == local_best_ptr->num_gates() &&
        gate_depth( *candidate ) == gate_depth( *local_best_ptr ) &&
        candidate_and_depth <
            *mockturtle::multiplicative_complexity_depth( *local_best_ptr );
    if ( candidate_ands <= maximum_and_gates &&
         candidate_and_depth <= maximum_and_depth &&
         ( better_size || equal_size_better_depth ||
           equal_size_depth_better_and_depth ) )
    {
      local_best_ptr = candidate;
    }
  }
  const auto& local_best = *local_best_ptr;
  const auto local_best_ands = *mockturtle::multiplicative_complexity( local_best );
  const auto local_best_xors = count_xors( local_best );
  const auto local_best_truth =
      mockturtle::simulate<kitty::static_truth_table<8>>( local_best );
  if ( local_best_truth == original_truth &&
       local_best_ands <= maximum_and_gates &&
       local_best_xors <= upper_bound )
  {
    mockturtle::write_verilog( local_best, argv[2] );
    std::cout << "RESULT status=improved method=xag-resubstitution"
              << " inputs=" << original_inputs
              << " outputs=" << original_outputs
              << " ands=" << local_best_ands
              << " original_xors=" << original_xors
              << " optimized_xors=" << local_best_xors
              << " upper_bound=" << upper_bound << "\n";
    return 0;
  }

  auto [affine_linear, ignored_tuples] =
      mockturtle::extract_linear_circuit( network );
  (void)ignored_tuples;
  auto [linear, output_phases] = strip_affine_phases( affine_linear );
  if ( linear.num_pis() != original_inputs + ands ||
       linear.num_pos() != original_outputs + 2 * ands )
  {
    std::cerr << "unexpected extracted linear-network dimensions\n";
    return 2;
  }

  const auto paar_linear = mockturtle::linear_resynthesis_paar( linear );
  std::cout << "HEURISTIC method=paar"
            << " original_xors=" << count_xors( linear )
            << " synthesized_xors=" << count_xors( paar_linear )
            << " complemented_trivial_outputs="
            << count_complemented_trivial_outputs( linear, output_phases )
            << "\n";

  mockturtle::exact_linear_synthesis_params params;
  params.upper_bound = upper_bound;
  params.conflict_limit = conflict_limit;
  params.ignore_inputs = availability_constraints(
      original_outputs, original_inputs, ands );
  params.verbose = true;

  mockturtle::exact_linear_synthesis_stats stats;
  const auto optimized_linear =
      mockturtle::exact_linear_resynthesis( linear, params, &stats );
  if ( !optimized_linear )
  {
    std::cout << "RESULT status=no-improvement"
              << " inputs=" << original_inputs
              << " outputs=" << original_outputs
              << " ands=" << ands
              << " original_xors=" << original_xors
              << " upper_bound=" << upper_bound << "\n";
    return 1;
  }

  const auto phased_linear =
      apply_output_phases( *optimized_linear, output_phases );
  const auto optimized =
      mockturtle::merge_linear_circuit( phased_linear, ands );
  if ( original_inputs != 8u )
  {
    std::cerr << "S-box must have eight inputs\n";
    return 2;
  }

  const auto optimized_truth =
      mockturtle::simulate<kitty::static_truth_table<8>>( optimized );
  if ( original_truth != optimized_truth )
  {
    std::cerr << "optimized network is not equivalent\n";
    return 2;
  }

  mockturtle::write_verilog( optimized, argv[2] );
  std::cout << "RESULT status=improved"
            << " inputs=" << original_inputs
            << " outputs=" << original_outputs
            << " ands=" << *mockturtle::multiplicative_complexity( optimized )
            << " original_xors=" << original_xors
            << " optimized_xors=" << count_xors( optimized )
            << " upper_bound=" << upper_bound << "\n";
  return 0;
}
