// Test-only exhaustive probe for the shared forward and inverse S-box logic.
module aes_sbox_probe (
    input  logic [7:0] data_in,
    output logic [7:0] forward_out,
    output logic [7:0] inverse_out
);
  `include "aes_functions.svh"
  assign forward_out = aes_sbox(data_in);
  assign inverse_out = aes_inv_sbox(data_in);
endmodule
