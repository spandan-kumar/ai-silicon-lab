// Two-stage Karatsuba GHASH multiplier.
//
// The operands use the GCM bit ordering (bit 127 is coefficient zero).  The
// first stage forms three 64x64 carry-less products; the second stage performs
// the Karatsuba recombination and constant-time reduction modulo
// x^128+x^7+x^2+x+1.  This is an exploratory architecture point, not a claim
// of priority: related AES-GCM circuit/architecture co-design is cited in the
// experiment research notes.
module ghash_karatsuba (
    input  logic         clk,
    input  logic         rst,
    input  logic         zeroize,
    input  logic         in_valid,
    output logic         in_ready,
    input  logic [127:0] x,
    input  logic [127:0] h,
    output logic         out_valid,
    input  logic         out_ready,
    output logic [127:0] out
);
  logic stage_valid;
  logic [127:0] p0_register;
  logic [127:0] p1_register;
  logic [127:0] pm_register;

  function automatic [127:0] carryless_mul64(
      input logic [63:0] a, input logic [63:0] b);
    integer i;
    integer j;
    begin
      carryless_mul64 = 128'h0;
      for (i = 0; i < 64; i = i + 1)
        for (j = 0; j < 64; j = j + 1)
          if (a[63-i] && b[63-j])
            carryless_mul64[127-(i+j)] =
                carryless_mul64[127-(i+j)] ^ 1'b1;
    end
  endfunction

  function automatic [127:0] karatsuba_reduce(
      input logic [127:0] p0, input logic [127:0] p1,
      input logic [127:0] pm);
    logic [127:0] cross_product;
    logic [255:0] product;
    integer bit_index;
    begin
      cross_product = pm ^ p0 ^ p1;
      product = {p0, 128'h0} ^ {64'h0, cross_product, 64'h0} ^ {128'h0, p1};
      // High product coefficients occupy product[127:0].  Walk from the
      // highest degree to the lowest so newly generated terms are reduced.
      for (bit_index = 0; bit_index < 128; bit_index = bit_index + 1) begin
        if (product[bit_index]) begin
          product[bit_index] = 1'b0;
          product[128 + bit_index] = product[128 + bit_index] ^ 1'b1;
          product[127 + bit_index] = product[127 + bit_index] ^ 1'b1;
          product[126 + bit_index] = product[126 + bit_index] ^ 1'b1;
          product[121 + bit_index] = product[121 + bit_index] ^ 1'b1;
        end
      end
      karatsuba_reduce = product[255:128];
    end
  endfunction

  assign in_ready = !stage_valid && !out_valid;

  always_ff @(posedge clk) begin
    if (rst || zeroize) begin
      stage_valid <= 1'b0;
      p0_register <= 128'h0;
      p1_register <= 128'h0;
      pm_register <= 128'h0;
      out_valid <= 1'b0;
      out <= 128'h0;
    end else begin
      if (out_valid && out_ready) begin
        out_valid <= 1'b0;
        out <= 128'h0;
      end
      if (stage_valid) begin
        out <= karatsuba_reduce(p0_register, p1_register, pm_register);
        out_valid <= 1'b1;
        stage_valid <= 1'b0;
        p0_register <= 128'h0;
        p1_register <= 128'h0;
        pm_register <= 128'h0;
      end else if (in_valid && in_ready) begin
        p0_register <= carryless_mul64(x[127:64], h[127:64]);
        p1_register <= carryless_mul64(x[63:0], h[63:0]);
        pm_register <= carryless_mul64(x[127:64] ^ x[63:0],
                                       h[127:64] ^ h[63:0]);
        stage_valid <= 1'b1;
      end
    end
  end
endmodule
