#include <verilated.h>
#include "Vaes_sbox_probe.h"

#include <cstdio>

#include "sbox_vectors.h"

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    Vaes_sbox_probe dut;
    for (unsigned value = 0; value < 256; ++value) {
        dut.data_in = value;
        dut.eval();
        if (dut.forward_out != kSbox[value] || dut.inverse_out != kInvSbox[value]) {
            std::fprintf(stderr,
                         "S-box mismatch input=%02x forward=%02x/%02x inverse=%02x/%02x\n",
                         value, dut.forward_out, kSbox[value], dut.inverse_out, kInvSbox[value]);
            return 1;
        }
    }
    std::puts("S-box RTL: PASS forward=256 inverse=256 implementation=nist-slp-g113-g121");
    return 0;
}
