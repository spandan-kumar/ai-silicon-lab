// Primitive-level testbench for the AES-256 block cipher.
//
// The GCM testbench exercises the cipher indirectly. This one drives it
// directly so that a block-level known-answer failure is distinguishable from
// a mode-level one, and so that per-block latency is measured rather than
// inferred from a whole GCM operation.

#include "Vaes256_enc.h"
#include "verilated.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace {

Vaes256_enc* dut = nullptr;
uint64_t cycles = 0;

void tick() { dut->clk = 0; dut->eval(); dut->clk = 1; dut->eval(); cycles++; }

template <typename W>
void put_be(W& dst, const uint8_t* bytes, int nbytes) {
  const int words = nbytes / 4;
  for (int w = 0; w < words; w++) {
    const uint8_t* p = bytes + (nbytes - 4 * (w + 1));
    dst[w] = (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
  }
}
template <typename W>
void get_be(const W& src, uint8_t* bytes, int nbytes) {
  const int words = nbytes / 4;
  for (int w = 0; w < words; w++) {
    uint8_t* p = bytes + (nbytes - 4 * (w + 1));
    p[0] = (uint8_t)(src[w] >> 24); p[1] = (uint8_t)(src[w] >> 16);
    p[2] = (uint8_t)(src[w] >> 8);  p[3] = (uint8_t)src[w];
  }
}
int hexval(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return (c >= 'A' && c <= 'F') ? c - 'A' + 10 : -1;
}
void unhex(const std::string& s, uint8_t* out) {
  for (size_t i = 0; i + 1 < s.size(); i += 2) out[i / 2] = (uint8_t)(hexval(s[i]) * 16 + hexval(s[i + 1]));
}

}  // namespace

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  const char* stimulus_path = nullptr;
  const char* output_path = nullptr;
  const char* metrics_path = nullptr;
  for (int i = 1; i < argc; i++) {
    std::string arg = argv[i];
    auto next = [&]() { return (i + 1 < argc) ? argv[++i] : nullptr; };
    if (arg == "--stimulus") stimulus_path = next();
    else if (arg == "--output") output_path = next();
    else if (arg == "--metrics") metrics_path = next();
  }
  if (!stimulus_path || !output_path) {
    fprintf(stderr, "usage: --stimulus FILE --output FILE [--metrics FILE]\n");
    return 2;
  }

  std::ifstream input(stimulus_path);
  if (!input) { fprintf(stderr, "cannot open %s\n", stimulus_path); return 2; }

  dut = new Vaes256_enc;
  dut->rst_n = 0; dut->start = 0;
  for (int i = 0; i < 4; i++) tick();
  dut->rst_n = 1; tick();

  std::ofstream out(output_path);
  std::ostringstream metrics;
  out << "{\n \"vectors\": [\n";
  metrics << "{\n \"per_case\": [\n";

  std::string line;
  bool first = true;
  uint64_t total = 0, count = 0;
  bool constant_latency = true;
  uint64_t reference_latency = 0;

  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') continue;
    std::istringstream fields(line);
    std::string id, keyhex, blkhex;
    if (!(fields >> id >> keyhex >> blkhex)) continue;
    uint8_t key[32] = {0}, blk[16] = {0}, result[16] = {0};
    unhex(keyhex, key); unhex(blkhex, blk);
    put_be(dut->key, key, 32);
    put_be(dut->block_in, blk, 16);
    const uint64_t t0 = cycles;
    dut->start = 1; tick(); dut->start = 0;
    int guard = 0;
    while (!dut->done && guard++ < 200) tick();
    get_be(dut->block_out, result, 16);
    const uint64_t latency = cycles - t0;
    if (count == 0) reference_latency = latency;
    else if (latency != reference_latency) constant_latency = false;
    total += latency; count++;

    char hex[33];
    for (int i = 0; i < 16; i++) snprintf(hex + 2 * i, 3, "%02x", result[i]);
    if (!first) { out << ",\n"; metrics << ",\n"; }
    first = false;
    out << "  {\"id\": \"" << id << "\", \"ciphertext\": \"" << hex << "\"}";
    metrics << "  {\"id\": \"" << id << "\", \"cycles\": " << latency << "}";
  }
  out << "\n ]\n}\n";
  metrics << "\n ],\n \"total_cycles\": " << total << ",\n \"cases\": " << count
          << ",\n \"cycles_per_block\": " << reference_latency
          << ",\n \"constant_block_latency\": " << (constant_latency ? "true" : "false")
          << "\n}\n";
  out.close();
  if (metrics_path) { std::ofstream m(metrics_path); m << metrics.str(); }

  dut->final(); delete dut;
  return 0;
}
