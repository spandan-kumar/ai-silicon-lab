// Differential testbench for the RV32I core.
//
// Loads a flat memory image, runs the core to a halt, and writes the retired
// instruction trace and final architectural state as JSON. It contains no
// model of the ISA: it does not know what any instruction should do, and it
// never compares anything. Comparison happens in the harness, after this
// process exits, against a reference this program cannot see.

#include "Vrv32i_core.h"
#include "verilated.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <string>
#include <vector>

namespace {

Vrv32i_core* dut = nullptr;
uint64_t cycles = 0;

// Flat little-endian memory. Sparse, so an image need not cover the space.
std::map<uint32_t, uint8_t> memory;

uint32_t read_word(uint32_t address) {
  uint32_t value = 0;
  for (int i = 0; i < 4; i++) {
    auto it = memory.find(address + i);
    if (it != memory.end()) value |= (uint32_t)it->second << (8 * i);
  }
  return value;
}

void write_word(uint32_t address, uint32_t data, uint8_t be) {
  for (int i = 0; i < 4; i++) {
    if (be & (1u << i)) memory[address + i] = (uint8_t)(data >> (8 * i));
  }
}

struct Retire {
  uint32_t pc;
  uint32_t instruction;
  uint32_t regs[32];
};

}  // namespace

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  const char* image_path = nullptr;
  const char* output_path = nullptr;
  uint32_t load_address = 0;
  uint64_t max_cycles = 2000000;
  bool trace_registers = true;

  for (int i = 1; i < argc; i++) {
    std::string arg = argv[i];
    auto next = [&]() { return (i + 1 < argc) ? argv[++i] : nullptr; };
    if (arg == "--image") image_path = next();
    else if (arg == "--output") output_path = next();
    else if (arg == "--load-address") load_address = (uint32_t)strtoul(next(), nullptr, 0);
    else if (arg == "--max-cycles") max_cycles = strtoull(next(), nullptr, 10);
    else if (arg == "--no-register-trace") trace_registers = false;
  }
  if (!image_path || !output_path) {
    fprintf(stderr, "usage: --image FILE --output FILE [--load-address N]\n");
    return 2;
  }

  std::ifstream image(image_path, std::ios::binary);
  if (!image) { fprintf(stderr, "cannot open image %s\n", image_path); return 2; }
  std::vector<char> bytes((std::istreambuf_iterator<char>(image)),
                          std::istreambuf_iterator<char>());
  for (size_t i = 0; i < bytes.size(); i++) {
    memory[load_address + (uint32_t)i] = (uint8_t)bytes[i];
  }

  dut = new Vrv32i_core;
  dut->rst_n = 0;
  dut->mem_gnt = 0;
  dut->mem_rvalid = 0;
  dut->mem_rdata = 0;
  dut->dbg_addr = 0;
  for (int i = 0; i < 4; i++) { dut->clk = 0; dut->eval(); dut->clk = 1; dut->eval(); }
  dut->rst_n = 1;

  std::vector<Retire> trace;
  bool response_pending = false;
  uint32_t response_data = 0;
  std::string stop_reason = "cycle-limit";

  while (cycles < max_cycles) {
    dut->clk = 0;
    dut->eval();

    // Memory responds to a request in the cycle after it is accepted.
    dut->mem_gnt = 1;
    dut->mem_rvalid = response_pending;
    dut->mem_rdata = response_data;
    dut->eval();

    if (dut->retire_valid) {
      Retire record;
      record.pc = dut->retire_pc;
      record.instruction = dut->retire_instruction;
      if (trace_registers) {
        for (int r = 0; r < 32; r++) {
          dut->dbg_addr = (uint8_t)r;
          dut->eval();
          record.regs[r] = dut->dbg_data;
        }
        dut->dbg_addr = 0;
        dut->eval();
      } else {
        memset(record.regs, 0, sizeof(record.regs));
      }
      trace.push_back(record);
    }

    if (dut->halted) {
      stop_reason = dut->trap ? (dut->trap_cause == 3 ? "ebreak"
                                : dut->trap_cause == 11 ? "ecall"
                                : dut->trap_cause == 4 ? "misaligned"
                                : "illegal")
                              : "halted";
      break;
    }

    // Latch a new transaction if one is being accepted this cycle.
    bool next_pending = false;
    uint32_t next_data = 0;
    if (dut->mem_req && dut->mem_gnt) {
      const uint32_t address = dut->mem_addr & ~3u;
      if (dut->mem_we) {
        write_word(address, dut->mem_wdata, (uint8_t)dut->mem_be);
      } else {
        next_data = read_word(address);
      }
      next_pending = true;
    }

    dut->clk = 1;
    dut->eval();
    cycles++;

    response_pending = next_pending;
    response_data = next_data;
  }

  // Final architectural state.
  uint32_t final_regs[32];
  dut->clk = 0;
  dut->eval();
  for (int r = 0; r < 32; r++) {
    dut->dbg_addr = (uint8_t)r;
    dut->eval();
    final_regs[r] = dut->dbg_data;
  }

  std::ofstream out(output_path);
  out << "{\n";
  out << " \"stop_reason\": \"" << stop_reason << "\",\n";
  out << " \"cycles\": " << cycles << ",\n";
  out << " \"retired\": " << trace.size() << ",\n";
  out << " \"final_regs\": [";
  for (int r = 0; r < 32; r++) out << final_regs[r] << (r < 31 ? ", " : "");
  out << "],\n";
  out << " \"trace\": [\n";
  for (size_t i = 0; i < trace.size(); i++) {
    out << "  {\"pc\": " << trace[i].pc << ", \"instruction\": " << trace[i].instruction;
    if (trace_registers) {
      out << ", \"regs\": [";
      for (int r = 0; r < 32; r++) out << trace[i].regs[r] << (r < 31 ? "," : "");
      out << "]";
    }
    out << "}" << (i + 1 < trace.size() ? "," : "") << "\n";
  }
  out << " ]\n}\n";
  out.close();

  dut->final();
  delete dut;
  return 0;
}
