module aes256_iterative (
    input  logic         clk,
    input  logic         rst,
    input  logic         zeroize,
    input  logic         key_valid,
    output logic         key_ready,
    output logic         key_loaded,
    input  logic [255:0] key_in,
    input  logic         block_valid,
    output logic         block_ready,
    input  logic         decrypt,
    input  logic [127:0] block_in,
    output logic         block_out_valid,
    input  logic         block_out_ready,
    output logic [127:0] block_out
);
  `include "aes_functions.svh"

  logic [127:0] round_keys [0:14];
  logic [255:0] schedule_key;
  logic [3:0] schedule_pair;
  logic key_busy;

  logic block_busy;
  logic block_decrypt;
  logic [3:0] round_index;
  logic [127:0] round_state;

  wire [255:0] next_schedule = aes_next_key_pair(schedule_key, schedule_pair);

  assign key_ready = !key_busy && !block_busy && !block_out_valid;
  assign block_ready = key_loaded && !key_busy && !block_busy && !block_out_valid;

  integer key_index;
  always_ff @(posedge clk) begin
    if (rst || zeroize) begin
      key_loaded <= 1'b0;
      key_busy <= 1'b0;
      schedule_key <= 256'h0;
      schedule_pair <= 4'h0;
      block_busy <= 1'b0;
      block_decrypt <= 1'b0;
      round_index <= 4'h0;
      round_state <= 128'h0;
      block_out <= 128'h0;
      block_out_valid <= 1'b0;
      for (key_index = 0; key_index < 15; key_index = key_index + 1)
        round_keys[key_index] <= 128'h0;
    end else begin
      if (block_out_valid && block_out_ready) begin
        block_out_valid <= 1'b0;
        block_out <= 128'h0;
      end

      if (key_valid && key_ready) begin
        key_loaded <= 1'b0;
        key_busy <= 1'b1;
        schedule_key <= key_in;
        schedule_pair <= 4'd1;
        round_keys[0] <= key_in[255:128];
        round_keys[1] <= key_in[127:0];
      end else if (key_busy) begin
        schedule_key <= next_schedule;
        round_keys[2*schedule_pair] <= next_schedule[255:128];
        if (schedule_pair < 7)
          round_keys[2*schedule_pair + 1] <= next_schedule[127:0];
        if (schedule_pair == 7) begin
          key_busy <= 1'b0;
          key_loaded <= 1'b1;
          schedule_key <= 256'h0;
          schedule_pair <= 4'h0;
        end else begin
          schedule_pair <= schedule_pair + 1'b1;
        end
      end

      if (block_valid && block_ready) begin
        block_busy <= 1'b1;
        block_decrypt <= decrypt;
        if (decrypt) begin
          round_state <= block_in ^ round_keys[14];
          round_index <= 4'd13;
        end else begin
          round_state <= block_in ^ round_keys[0];
          round_index <= 4'd1;
        end
      end else if (block_busy) begin
        if (block_decrypt) begin
          if (round_index == 0) begin
            block_out <= aes_inv_final_round(round_state, round_keys[0]);
            block_out_valid <= 1'b1;
            block_busy <= 1'b0;
            round_state <= 128'h0;
          end else begin
            round_state <= aes_inv_round(round_state, round_keys[round_index]);
            round_index <= round_index - 1'b1;
          end
        end else begin
          if (round_index == 14) begin
            block_out <= aes_final_round(round_state, round_keys[14]);
            block_out_valid <= 1'b1;
            block_busy <= 1'b0;
            round_state <= 128'h0;
          end else begin
            round_state <= aes_round(round_state, round_keys[round_index]);
            round_index <= round_index + 1'b1;
          end
        end
      end
    end
  end
endmodule

