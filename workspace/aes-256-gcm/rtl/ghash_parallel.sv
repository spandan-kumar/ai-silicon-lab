// Eight-bit-per-cycle GHASH comparison point (16 cycles per multiplication).
module ghash_parallel (
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
  logic busy;
  logic [3:0] byte_index;
  logic [127:0] x_register;
  logic [127:0] z_register;
  logic [127:0] v_register;
  logic [127:0] z_step;
  logic [127:0] v_step;
  integer offset;

  always_comb begin
    z_step = z_register;
    v_step = v_register;
    for (offset = 0; offset < 8; offset = offset + 1) begin
      if (x_register[127 - (byte_index*8 + offset)]) z_step = z_step ^ v_step;
      v_step = (v_step >> 1)
          ^ (128'he1000000000000000000000000000000 & {128{v_step[0]}});
    end
  end

  assign in_ready = !busy && !out_valid;

  always_ff @(posedge clk) begin
    if (rst || zeroize) begin
      busy <= 1'b0;
      byte_index <= 4'h0;
      x_register <= 128'h0;
      z_register <= 128'h0;
      v_register <= 128'h0;
      out_valid <= 1'b0;
      out <= 128'h0;
    end else begin
      if (out_valid && out_ready) begin
        out_valid <= 1'b0;
        out <= 128'h0;
      end
      if (in_valid && in_ready) begin
        busy <= 1'b1;
        byte_index <= 4'h0;
        x_register <= x;
        z_register <= 128'h0;
        v_register <= h;
      end else if (busy) begin
        if (byte_index == 15) begin
          out <= z_step;
          out_valid <= 1'b1;
          busy <= 1'b0;
          byte_index <= 4'h0;
          x_register <= 128'h0;
          z_register <= 128'h0;
          v_register <= 128'h0;
        end else begin
          z_register <= z_step;
          v_register <= v_step;
          byte_index <= byte_index + 1'b1;
        end
      end
    end
  end
endmodule
