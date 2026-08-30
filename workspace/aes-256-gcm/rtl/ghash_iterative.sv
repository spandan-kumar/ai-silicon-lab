module ghash_iterative (
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
  logic [7:0] bit_index;
  logic [127:0] x_register;
  logic [127:0] z_register;
  logic [127:0] v_register;

  wire [127:0] z_next = z_register ^ (x_register[127 - bit_index] ? v_register : 128'h0);
  wire [127:0] v_next = (v_register >> 1)
      ^ (128'he1000000000000000000000000000000 & {128{v_register[0]}});

  assign in_ready = !busy && !out_valid;

  always_ff @(posedge clk) begin
    if (rst || zeroize) begin
      busy <= 1'b0;
      bit_index <= 8'h0;
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
        bit_index <= 8'h0;
        x_register <= x;
        z_register <= 128'h0;
        v_register <= h;
      end else if (busy) begin
        if (bit_index == 127) begin
          out <= z_next;
          out_valid <= 1'b1;
          busy <= 1'b0;
          bit_index <= 8'h0;
          x_register <= 128'h0;
          z_register <= 128'h0;
          v_register <= 128'h0;
        end else begin
          z_register <= z_next;
          v_register <= v_next;
          bit_index <= bit_index + 1'b1;
        end
      end
    end
  end
endmodule

