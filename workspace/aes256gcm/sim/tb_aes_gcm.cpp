// Cycle-accurate testbench for the AES-256-GCM RTL.
//
// This program is the candidate. It receives only stimulus: key, IV, AAD, and
// payload, plus the tag that a decrypt operation must verify against, which is
// an input to decryption by definition. It never reads expected ciphertext,
// expected plaintext, or an expected verdict; the harness performs every
// comparison after this process exits.
//
// Backpressure on both streams is driven by a deterministic per-case LFSR so
// that stall patterns are reproducible and interface behaviour is exercised
// rather than assumed.

#include "Vaes_gcm.h"
#include "verilated.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace {

Vaes_gcm* dut = nullptr;
uint64_t global_cycles = 0;

void tick_low() {
  dut->clk = 0;
  dut->eval();
}

void tick_high() {
  dut->clk = 1;
  dut->eval();
  global_cycles++;
}

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
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

std::vector<uint8_t> unhex(const std::string& s) {
  std::vector<uint8_t> out;
  if (s == "-") return out;
  for (size_t i = 0; i + 1 < s.size(); i += 2) {
    out.push_back((uint8_t)(hexval(s[i]) * 16 + hexval(s[i + 1])));
  }
  return out;
}

std::string tohex(const std::vector<uint8_t>& v) {
  static const char* digits = "0123456789abcdef";
  std::string out;
  out.reserve(v.size() * 2);
  for (uint8_t b : v) { out.push_back(digits[b >> 4]); out.push_back(digits[b & 15]); }
  return out;
}

// Deterministic stall generator. Seed 0 means "never stall".
struct Stalls {
  uint32_t state;
  explicit Stalls(uint32_t seed) : state(seed ? seed : 0u) {}
  bool go() {
    if (state == 0) return true;
    state ^= state << 13; state ^= state >> 17; state ^= state << 5;
    return (state & 3u) != 0u;  // stall roughly one cycle in four
  }
};

struct Case {
  std::string id;
  int mode = 0;                 // 0 encrypt, 1 decrypt
  std::vector<uint8_t> key, iv, aad, text, exp_tag;
  int tag_bytes = 16;
  uint32_t stall_seed = 0;
};

struct Result {
  std::string id;
  std::string out_hex;          // ciphertext, or plaintext when released
  std::string tag_hex;
  bool tag_ok = false;
  bool released = false;
  uint64_t cycles = 0;
  uint64_t out_bytes = 0;
};

Result run_case(const Case& c, uint64_t max_cycles) {
  Result r;
  r.id = c.id;

  // Reset between cases: no state may cross an operation boundary.
  dut->rst_n = 0; dut->start = 0; dut->in_valid = 0; dut->out_ready = 0;
  for (int i = 0; i < 4; i++) { tick_low(); tick_high(); }
  dut->rst_n = 1; tick_low(); tick_high();

  uint8_t keybuf[32] = {0};
  memcpy(keybuf, c.key.data(), c.key.size());
  put_be(dut->key, keybuf, 32);

  uint8_t tagbuf[16] = {0};
  for (size_t i = 0; i < c.exp_tag.size() && i < 16; i++) tagbuf[i] = c.exp_tag[i];
  put_be(dut->exp_tag, tagbuf, 16);

  dut->decrypt   = c.mode;
  dut->iv_bytes  = (uint16_t)c.iv.size();
  dut->aad_bytes = (uint32_t)c.aad.size();
  dut->txt_bytes = (uint32_t)c.text.size();
  dut->tag_bytes = (uint8_t)c.tag_bytes;

  // The input stream is IV, then AAD, then payload, in that order.
  std::vector<uint8_t> stream;
  stream.insert(stream.end(), c.iv.begin(), c.iv.end());
  stream.insert(stream.end(), c.aad.begin(), c.aad.end());
  stream.insert(stream.end(), c.text.begin(), c.text.end());

  const uint64_t start_cycles = global_cycles;
  dut->start = 1; tick_low(); tick_high(); dut->start = 0;

  size_t in_index = 0;
  std::vector<uint8_t> captured;
  Stalls in_stall(c.stall_seed), out_stall(c.stall_seed ? c.stall_seed ^ 0x9e3779b9u : 0u);
  bool finished = false;

  while (!finished && (global_cycles - start_cycles) < max_cycles) {
    tick_low();

    const bool offer = in_index < stream.size() && in_stall.go();
    dut->in_valid = offer;
    dut->in_data  = offer ? stream[in_index] : 0;
    dut->out_ready = out_stall.go();
    dut->eval();

    if (dut->in_valid && dut->in_ready) in_index++;
    if (dut->out_valid && dut->out_ready) captured.push_back(dut->out_data);
    if (dut->done) finished = true;

    tick_high();
  }

  uint8_t tagout[16];
  get_be(dut->tag, tagout, 16);
  r.tag_hex = tohex(std::vector<uint8_t>(tagout, tagout + c.tag_bytes));
  r.tag_ok = dut->tag_ok != 0;
  r.released = !captured.empty();
  r.out_hex = tohex(captured);
  r.out_bytes = captured.size();
  r.cycles = global_cycles - start_cycles;
  if (!finished) { r.tag_ok = false; r.tag_hex = "timeout"; }
  return r;
}

}  // namespace

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  const char* stimulus_path = nullptr;
  const char* output_path = nullptr;
  const char* metrics_path = nullptr;
  uint64_t max_cycles = 4000000;

  for (int i = 1; i < argc; i++) {
    std::string arg = argv[i];
    auto next = [&]() { return (i + 1 < argc) ? argv[++i] : nullptr; };
    if (arg == "--stimulus") stimulus_path = next();
    else if (arg == "--output") output_path = next();
    else if (arg == "--metrics") metrics_path = next();
    else if (arg == "--max-cycles") max_cycles = strtoull(next(), nullptr, 10);
  }
  if (!stimulus_path || !output_path) {
    fprintf(stderr, "usage: --stimulus FILE --output FILE [--metrics FILE]\n");
    return 2;
  }

  std::ifstream input(stimulus_path);
  if (!input) { fprintf(stderr, "cannot open stimulus %s\n", stimulus_path); return 2; }

  std::vector<Case> cases;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') continue;
    std::istringstream fields(line);
    Case c;
    std::string key, iv, aad, text, tag;
    if (!(fields >> c.id >> c.mode >> key >> iv >> aad >> text >> c.tag_bytes >> tag
                 >> c.stall_seed)) {
      fprintf(stderr, "malformed stimulus line: %s\n", line.c_str());
      return 2;
    }
    c.key = unhex(key); c.iv = unhex(iv); c.aad = unhex(aad);
    c.text = unhex(text); c.exp_tag = unhex(tag);
    cases.push_back(c);
  }

  dut = new Vaes_gcm;
  std::vector<Result> results;
  results.reserve(cases.size());
  for (const Case& c : cases) results.push_back(run_case(c, max_cycles));
  dut->final();

  // Correctness outputs. Only values the RTL produced appear here.
  std::ofstream out(output_path);
  out << "{\n \"vectors\": [\n";
  for (size_t i = 0; i < results.size(); i++) {
    const Result& r = results[i];
    out << "  {\"id\": \"" << r.id << "\", \"output\": \"" << r.out_hex
        << "\", \"tag\": \"" << r.tag_hex << "\", \"tag_ok\": "
        << (r.tag_ok ? "true" : "false") << ", \"released\": "
        << (r.released ? "true" : "false") << "}"
        << (i + 1 < results.size() ? "," : "") << "\n";
  }
  out << " ]\n}\n";
  out.close();

  // Cycle measurements are kept apart from the compared outputs. Only
  // deterministic counts are written; wall time is reported by the harness.
  if (metrics_path) {
    uint64_t total = 0, bytes = 0;
    std::ofstream m(metrics_path);
    m << "{\n \"per_case\": [\n";
    for (size_t i = 0; i < results.size(); i++) {
      total += results[i].cycles;
      bytes += results[i].out_bytes;
      m << "  {\"id\": \"" << results[i].id << "\", \"cycles\": " << results[i].cycles
        << ", \"output_bytes\": " << results[i].out_bytes << "}"
        << (i + 1 < results.size() ? "," : "") << "\n";
    }
    m << " ],\n \"total_cycles\": " << total << ",\n \"total_output_bytes\": " << bytes
      << ",\n \"cases\": " << results.size() << "\n}\n";
  }

  delete dut;
  return 0;
}
