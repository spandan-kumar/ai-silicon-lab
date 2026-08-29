// Independent cross-check testbench: the same programs on CV32E40P.
//
// The reference model and the two local cores in this experiment were written
// from the same specification by the same author. If that author misread the
// specification, all three would agree and the loop would report success.
// CV32E40P was developed elsewhere and is silicon-proven, so agreement with it
// is evidence that no such shared misreading exists.
//
// CV32E40P exposes no register-file read port and this repository must not
// modify it, so architectural state is observed the portable way: the program
// writes its own final register values to a signature area in memory, and the
// memory image is compared afterwards. Nothing in this file knows what any
// instruction means, and no comparison happens here.

#include "Vcv32e40p_top.h"
#include "verilated.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <deque>
#include <fstream>
#include <map>
#include <string>
#include <vector>

namespace {

Vcv32e40p_top* dut = nullptr;
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

// OBI allows several outstanding transactions; CV32E40P's prefetcher uses that.
// Responses are queued and returned one per cycle, in order.
std::deque<uint32_t> instr_responses;
std::deque<uint32_t> data_responses;

}  // namespace

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  const char* image_path = nullptr;
  const char* output_path = nullptr;
  uint32_t load_address = 0;
  uint32_t halt_address = 0x1500;
  uint32_t signature_base = 0x1400;
  uint32_t signature_words = 31;
  uint64_t max_cycles = 4000000;

  for (int i = 1; i < argc; i++) {
    std::string arg = argv[i];
    auto next = [&]() { return (i + 1 < argc) ? argv[++i] : nullptr; };
    if (arg == "--image") image_path = next();
    else if (arg == "--output") output_path = next();
    else if (arg == "--load-address") load_address = (uint32_t)strtoul(next(), nullptr, 0);
    else if (arg == "--halt-address") halt_address = (uint32_t)strtoul(next(), nullptr, 0);
    else if (arg == "--signature-base") signature_base = (uint32_t)strtoul(next(), nullptr, 0);
    else if (arg == "--signature-words") signature_words = (uint32_t)strtoul(next(), nullptr, 0);
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

  dut = new Vcv32e40p_top;
  dut->rst_ni = 0;
  dut->pulp_clock_en_i = 0;
  dut->scan_cg_en_i = 0;
  dut->boot_addr_i = load_address;
  dut->mtvec_addr_i = 0;
  dut->dm_halt_addr_i = 0;
  dut->hart_id_i = 0;
  dut->dm_exception_addr_i = 0;
  dut->irq_i = 0;
  dut->debug_req_i = 0;
  dut->fetch_enable_i = 0;
  dut->instr_gnt_i = 0;
  dut->instr_rvalid_i = 0;
  dut->instr_rdata_i = 0;
  dut->data_gnt_i = 0;
  dut->data_rvalid_i = 0;
  dut->data_rdata_i = 0;

  for (int i = 0; i < 10; i++) { dut->clk_i = 0; dut->eval(); dut->clk_i = 1; dut->eval(); }
  dut->rst_ni = 1;
  dut->fetch_enable_i = 1;

  std::string stop_reason = "cycle-limit";
  uint64_t data_writes = 0;

  while (cycles < max_cycles) {
    dut->clk_i = 0;
    dut->eval();

    // Always ready to accept; responses arrive from the queues.
    dut->instr_gnt_i = 1;
    dut->data_gnt_i = 1;
    dut->instr_rvalid_i = !instr_responses.empty();
    dut->instr_rdata_i = instr_responses.empty() ? 0 : instr_responses.front();
    dut->data_rvalid_i = !data_responses.empty();
    dut->data_rdata_i = data_responses.empty() ? 0 : data_responses.front();
    dut->eval();

    if (dut->instr_rvalid_i && !instr_responses.empty()) instr_responses.pop_front();
    if (dut->data_rvalid_i && !data_responses.empty()) data_responses.pop_front();

    bool halted = false;
    if (dut->instr_req_o && dut->instr_gnt_i) {
      instr_responses.push_back(read_word(dut->instr_addr_o & ~3u));
    }
    if (dut->data_req_o && dut->data_gnt_i) {
      const uint32_t address = dut->data_addr_o & ~3u;
      if (dut->data_we_o) {
        if (address == (halt_address & ~3u)) {
          halted = true;
          stop_reason = "halt-store";
        }
        write_word(address, dut->data_wdata_o, (uint8_t)dut->data_be_o);
        data_writes++;
      }
      data_responses.push_back(read_word(address));
    }

    dut->clk_i = 1;
    dut->eval();
    cycles++;
    if (halted) break;
  }

  std::ofstream out(output_path);
  out << "{\n \"stop_reason\": \"" << stop_reason << "\",\n";
  out << " \"cycles\": " << cycles << ",\n";
  out << " \"data_writes\": " << data_writes << ",\n";
  out << " \"signature\": [";
  for (uint32_t i = 0; i < signature_words; i++) {
    out << read_word(signature_base + 4 * i) << (i + 1 < signature_words ? ", " : "");
  }
  out << "]\n}\n";
  out.close();

  dut->final();
  delete dut;
  return 0;
}
