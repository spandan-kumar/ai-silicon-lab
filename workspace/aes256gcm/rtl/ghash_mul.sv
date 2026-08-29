// Bit-serial multiplication in GF(2^128) using the GCM field convention.
//
// SP 800-38D numbers bits from the left, so specification bit 0 is the most
// significant bit of the register, the reduction polynomial appears as 0xE1 in
// the top byte, and the shift is to the right. One bit per cycle: 128 cycles
// per multiply. This is the deliberate baseline structure; a folded or
// Karatsuba multiplier is an architecture-exploration variant, not a fix.

module ghash_mul (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         start,
    input  logic [127:0] x,
    input  logic [127:0] y,
    output logic         busy,
    output logic         done,
    output logic [127:0] z
);
  localparam logic [127:0] R_POLY = 128'hE100_0000_0000_0000_0000_0000_0000_0000;

  logic [127:0] z_q, v_q, x_q;
  logic [7:0]   count_q;
  logic         busy_q, done_q;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      z_q <= '0; v_q <= '0; x_q <= '0;
      count_q <= '0; busy_q <= 1'b0; done_q <= 1'b0;
    end else begin
      done_q <= 1'b0;
      if (start && !busy_q) begin
        z_q <= '0;
        v_q <= y;
        x_q <= x;
        count_q <= 8'd0;
        busy_q <= 1'b1;
      end else if (busy_q) begin
        // Consume x from its most significant bit downwards.
        if (x_q[127]) z_q <= z_q ^ v_q;
        x_q <= {x_q[126:0], 1'b0};
        v_q <= v_q[0] ? ((v_q >> 1) ^ R_POLY) : (v_q >> 1);
        if (count_q == 8'd127) begin
          busy_q <= 1'b0;
          done_q <= 1'b1;
        end else begin
          count_q <= count_q + 8'd1;
        end
      end
    end
  end

  assign busy = busy_q;
  assign done = done_q;
  assign z    = z_q;
endmodule
