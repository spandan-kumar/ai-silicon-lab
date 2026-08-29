// Differential testbench for the pipelined RV32I core.
//
// Emits exactly the format the multi-cycle testbench emits, so the same
// harness, reference model, and stimulus compare both designs without
// modification. Like the other testbench it models no part of the ISA and
// performs no comparison.

#include "Vrv32i_pipe.h"
#include "verilated.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <string>
#include <vector>

namespace {

Vrv32i_pipe* dut = nullptr;
uint64_t cycles = 0;
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

  for (int i = 1; i < argc; i++) {
    std::string arg = argv[i];
    auto next = [&]() { return (i + 1 < argc) ? argv[++i] : nullptr; };
    if (arg == "--image") image_path = next();
    else if (arg == "--output") output_path = next();
    else if (arg == "--load-address") load_address = (uint32_t)strtoul(next(), nullptr, 0);
    else if (arg == "--max-cycles") max_cycles = strtoull(next(), nullptr, 10);
  }
  if (!image_path || !output_path) {
    fprintf(stderr, "usage: --image FILE --output FILE\n");
    return 2;
  }

  std::ifstream image(image_path, std::ios::binary);
  if (!image) { fprintf(stderr, "cannot open image %s\n", image_path); return 2; }
  std::vector<char> bytes((std::istreambuf_iterator<char>(image)),
                          std::istreambuf_iterator<char>());
  for (size_t i = 0; i < bytes.size(); i++) {
    memory[load_address + (uint32_t)i] = (uint8_t)bytes[i];
  }

  dut = new Vrv32i_pipe;
  dut->rst_n = 0;
  dut->imem_rdata = 0;
  dut->dmem_rdata = 0;
  dut->dbg_addr = 0;
  for (int i = 0; i < 4; i++) { dut->clk = 0; dut->eval(); dut->clk = 1; dut->eval(); }
  dut->rst_n = 1;

  std::vector<Retire> trace;
  std::string stop_reason = "cycle-limit";
  int drain = -1;

  while (cycles < max_cycles) {
    dut->clk = 0;
    dut->eval();

    dut->imem_rdata = read_word(dut->imem_addr & ~3u);
    dut->dmem_rdata = read_word(dut->dmem_addr & ~3u);
    dut->eval();

    if (dut->retire_valid) {
      Retire record;
      record.pc = dut->retire_pc;
      record.instruction = dut->retire_instruction;
      for (int r = 0; r < 32; r++) {
        dut->dbg_addr = (uint8_t)r;
        dut->eval();
        record.regs[r] = dut->dbg_data;
      }
      dut->dbg_addr = 0;
      dut->eval();
      trace.push_back(record);
    }

    if (dut->halted && drain < 0) {
      stop_reason = dut->trap ? (dut->trap_cause == 3 ? "ebreak"
                              : dut->trap_cause == 11 ? "ecall" : "illegal")
                              : "halted";
      drain = 4;    // let instructions already past EX complete their writeback
    }

    if (dut->dmem_req && dut->dmem_we) {
      write_word(dut->dmem_addr & ~3u, dut->dmem_wdata, (uint8_t)dut->dmem_be);
    }

    dut->clk = 1;
    dut->eval();
    cycles++;

    if (drain >= 0) {
      if (drain == 0) break;
      drain--;
    }
  }

  uint32_t final_regs[32];
  dut->clk = 0;
  dut->eval();
  for (int r = 0; r < 32; r++) {
    dut->dbg_addr = (uint8_t)r;
    dut->eval();
    final_regs[r] = dut->dbg_data;
  }

  std::ofstream out(output_path);
  out << "{\n \"stop_reason\": \"" << stop_reason << "\",\n";
  out << " \"cycles\": " << cycles << ",\n";
  out << " \"retired\": " << trace.size() << ",\n";
  out << " \"final_regs\": [";
  for (int r = 0; r < 32; r++) out << final_regs[r] << (r < 31 ? ", " : "");
  out << "],\n \"trace\": [\n";
  for (size_t i = 0; i < trace.size(); i++) {
    out << "  {\"pc\": " << trace[i].pc << ", \"instruction\": " << trace[i].instruction
        << ", \"regs\": [";
    for (int r = 0; r < 32; r++) out << trace[i].regs[r] << (r < 31 ? "," : "");
    out << "]}" << (i + 1 < trace.size() ? "," : "") << "\n";
  }
  out << " ]\n}\n";
  out.close();

  dut->final();
  delete dut;
  return 0;
}
