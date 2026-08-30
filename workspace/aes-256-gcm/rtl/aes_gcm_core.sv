module aes_gcm_core #(
    parameter integer ARCH = 0  // 0: one-round/one-bit, 1: two-round/eight-bit
) (
    input  logic         clk,
    input  logic         rst,
    input  logic         zeroize,

    input  logic         key_valid,
    output logic         key_ready,
    output logic         key_loaded,
    input  logic [255:0] key_in,

    input  logic         cmd_valid,
    output logic         cmd_ready,
    input  logic         cmd_encrypt,
    input  logic [4:0]   cmd_iv_bytes,
    input  logic [6:0]   cmd_aad_bytes,
    input  logic [6:0]   cmd_data_bytes,

    input  logic         in_valid,
    output logic         in_ready,
    input  logic [7:0]   in_data,

    input  logic         tag_in_valid,
    output logic         tag_in_ready,
    input  logic [127:0] tag_in,

    output logic         out_valid,
    input  logic         out_ready,
    output logic [7:0]   out_data,

    output logic         result_valid,
    input  logic         result_ready,
    output logic [1:0]   result_status,
    output logic         result_auth_ok,
    output logic [127:0] result_tag,
    output logic [31:0]  result_cycles,
    output logic [31:0]  result_stall_cycles
);
  localparam logic [1:0] STATUS_OK = 2'd0;
  localparam logic [1:0] STATUS_AUTH = 2'd1;
  localparam logic [1:0] STATUS_LENGTH = 2'd2;
  localparam logic [1:0] STATUS_NO_KEY = 2'd3;

  typedef enum logic [4:0] {
    ST_IDLE,
    ST_INPUT_IV,
    ST_INPUT_AAD,
    ST_INPUT_DATA,
    ST_INPUT_TAG,
    ST_AES_H_START,
    ST_AES_H_WAIT,
    ST_IV_GHASH_START,
    ST_IV_GHASH_WAIT,
    ST_IV_LENGTH_START,
    ST_IV_LENGTH_WAIT,
    ST_AES_S0_START,
    ST_AES_S0_WAIT,
    ST_AAD_GHASH_START,
    ST_AAD_GHASH_WAIT,
    ST_DATA_AES_START,
    ST_DATA_AES_WAIT,
    ST_DATA_GHASH_START,
    ST_DATA_GHASH_WAIT,
    ST_LENGTH_GHASH_START,
    ST_LENGTH_GHASH_WAIT,
    ST_OUTPUT,
    ST_RESULT
  } state_t;

  state_t state;
  logic operation_encrypt;
  logic [4:0] iv_length;
  logic [6:0] aad_length;
  logic [6:0] data_length;
  logic [6:0] input_index;
  logic [2:0] block_index;
  logic [6:0] output_index;

  logic [7:0] iv_memory [0:11];
  logic [7:0] aad_memory [0:63];
  logic [7:0] data_memory [0:63];
  logic [7:0] output_memory [0:63];

  logic [127:0] hash_subkey;
  logic [127:0] ghash_state;
  logic [127:0] j0;
  logic [127:0] counter;
  logic [127:0] tag_mask;
  logic [127:0] expected_tag;
  logic [127:0] cipher_block;
  logic [31:0] transaction_cycles;
  logic [31:0] transaction_stalls;

  logic aes_key_valid;
  logic aes_key_ready;
  logic aes_key_loaded;
  logic aes_block_valid;
  logic aes_block_ready;
  logic [127:0] aes_block_input;
  logic aes_output_valid;
  logic aes_output_ready;
  logic [127:0] aes_output;

  logic ghash_input_valid;
  logic ghash_input_ready;
  logic [127:0] ghash_input;
  logic ghash_output_valid;
  logic ghash_output_ready;
  logic [127:0] ghash_output;

  function automatic [127:0] increment_counter(input [127:0] value);
    increment_counter = {value[127:32], value[31:0] + 1'b1};
  endfunction

  function automatic [127:0] iv_fast_block;
    integer byte_index;
    begin
      iv_fast_block = 128'h00000000000000000000000000000001;
      for (byte_index = 0; byte_index < 12; byte_index = byte_index + 1)
        iv_fast_block[127 - byte_index*8 -: 8] = iv_memory[byte_index];
    end
  endfunction

  function automatic [127:0] iv_general_block;
    begin
      iv_general_block = 128'h0;
      iv_general_block[127:120] = iv_memory[0];
    end
  endfunction

  function automatic [127:0] aad_block(input [2:0] selected_block);
    integer byte_index;
    integer absolute_index;
    begin
      aad_block = 128'h0;
      for (byte_index = 0; byte_index < 16; byte_index = byte_index + 1) begin
        absolute_index = selected_block * 16 + byte_index;
        if (absolute_index < aad_length)
          aad_block[127 - byte_index*8 -: 8] = aad_memory[absolute_index];
      end
    end
  endfunction

  function automatic [127:0] data_block(input [2:0] selected_block);
    integer byte_index;
    integer absolute_index;
    begin
      data_block = 128'h0;
      for (byte_index = 0; byte_index < 16; byte_index = byte_index + 1) begin
        absolute_index = selected_block * 16 + byte_index;
        if (absolute_index < data_length)
          data_block[127 - byte_index*8 -: 8] = data_memory[absolute_index];
      end
    end
  endfunction

  function automatic [127:0] masked_xor_block(
      input [2:0] selected_block, input [127:0] stream_block);
    integer byte_index;
    integer absolute_index;
    begin
      masked_xor_block = 128'h0;
      for (byte_index = 0; byte_index < 16; byte_index = byte_index + 1) begin
        absolute_index = selected_block * 16 + byte_index;
        if (absolute_index < data_length)
          masked_xor_block[127 - byte_index*8 -: 8] =
              data_memory[absolute_index] ^ stream_block[127 - byte_index*8 -: 8];
      end
    end
  endfunction

  function automatic [127:0] message_length_block;
    reg [63:0] aad_bits;
    reg [63:0] data_bits;
    begin
      aad_bits = {57'h0, aad_length};
      data_bits = {57'h0, data_length};
      message_length_block = {aad_bits << 3, data_bits << 3};
    end
  endfunction

  generate
    if (ARCH == 0) begin : gen_iterative
      aes256_iterative_enc aes_unit (
          .clk, .rst, .zeroize, .key_valid(aes_key_valid), .key_ready(aes_key_ready),
          .key_loaded(aes_key_loaded), .key_in, .block_valid(aes_block_valid),
          .block_ready(aes_block_ready), .block_in(aes_block_input),
          .block_out_valid(aes_output_valid), .block_out_ready(aes_output_ready),
          .block_out(aes_output));
      ghash_iterative ghash_unit (
          .clk, .rst, .zeroize, .in_valid(ghash_input_valid), .in_ready(ghash_input_ready),
          .x(ghash_input), .h(hash_subkey), .out_valid(ghash_output_valid),
          .out_ready(ghash_output_ready), .out(ghash_output));
    end else begin : gen_parallel
      aes256_parallel_enc aes_unit (
          .clk, .rst, .zeroize, .key_valid(aes_key_valid), .key_ready(aes_key_ready),
          .key_loaded(aes_key_loaded), .key_in, .block_valid(aes_block_valid),
          .block_ready(aes_block_ready), .block_in(aes_block_input),
          .block_out_valid(aes_output_valid), .block_out_ready(aes_output_ready),
          .block_out(aes_output));
      ghash_parallel ghash_unit (
          .clk, .rst, .zeroize, .in_valid(ghash_input_valid), .in_ready(ghash_input_ready),
          .x(ghash_input), .h(hash_subkey), .out_valid(ghash_output_valid),
          .out_ready(ghash_output_ready), .out(ghash_output));
    end
  endgenerate

  assign key_ready = (state == ST_IDLE) && !result_valid && aes_key_ready;
  assign key_loaded = aes_key_loaded;
  assign aes_key_valid = key_valid && key_ready;
  assign cmd_ready = (state == ST_IDLE) && !result_valid && !key_valid;
  assign in_ready = state == ST_INPUT_IV || state == ST_INPUT_AAD || state == ST_INPUT_DATA;
  assign tag_in_ready = state == ST_INPUT_TAG;
  assign out_valid = state == ST_OUTPUT;
  assign out_data = output_memory[output_index[5:0]];

  always_comb begin
    aes_block_valid = 1'b0;
    aes_block_input = 128'h0;
    aes_output_ready = 1'b0;
    case (state)
      ST_AES_H_START: begin
        aes_block_valid = 1'b1;
        aes_block_input = 128'h0;
      end
      ST_AES_S0_START: begin
        aes_block_valid = 1'b1;
        aes_block_input = j0;
      end
      ST_DATA_AES_START: begin
        aes_block_valid = 1'b1;
        aes_block_input = counter;
      end
      ST_AES_H_WAIT, ST_AES_S0_WAIT, ST_DATA_AES_WAIT: aes_output_ready = 1'b1;
      default: begin end
    endcase
  end

  always_comb begin
    ghash_input_valid = 1'b0;
    ghash_input = 128'h0;
    ghash_output_ready = 1'b0;
    case (state)
      ST_IV_GHASH_START: begin
        ghash_input_valid = 1'b1;
        ghash_input = iv_general_block();
      end
      ST_IV_LENGTH_START: begin
        ghash_input_valid = 1'b1;
        ghash_input = ghash_state ^ 128'h00000000000000000000000000000008;
      end
      ST_AAD_GHASH_START: begin
        ghash_input_valid = 1'b1;
        ghash_input = ghash_state ^ aad_block(block_index);
      end
      ST_DATA_GHASH_START: begin
        ghash_input_valid = 1'b1;
        ghash_input = ghash_state ^ cipher_block;
      end
      ST_LENGTH_GHASH_START: begin
        ghash_input_valid = 1'b1;
        ghash_input = ghash_state ^ message_length_block();
      end
      ST_IV_GHASH_WAIT, ST_IV_LENGTH_WAIT, ST_AAD_GHASH_WAIT,
      ST_DATA_GHASH_WAIT, ST_LENGTH_GHASH_WAIT: ghash_output_ready = 1'b1;
      default: begin end
    endcase
  end

  integer clear_index;
  integer store_index;
  always_ff @(posedge clk) begin
    if (rst || zeroize) begin
      state <= ST_IDLE;
      operation_encrypt <= 1'b0;
      iv_length <= 5'h0;
      aad_length <= 7'h0;
      data_length <= 7'h0;
      input_index <= 7'h0;
      block_index <= 3'h0;
      output_index <= 7'h0;
      hash_subkey <= 128'h0;
      ghash_state <= 128'h0;
      j0 <= 128'h0;
      counter <= 128'h0;
      tag_mask <= 128'h0;
      expected_tag <= 128'h0;
      cipher_block <= 128'h0;
      transaction_cycles <= 32'h0;
      transaction_stalls <= 32'h0;
      result_valid <= 1'b0;
      result_status <= STATUS_OK;
      result_auth_ok <= 1'b0;
      result_tag <= 128'h0;
      result_cycles <= 32'h0;
      result_stall_cycles <= 32'h0;
      for (clear_index = 0; clear_index < 12; clear_index = clear_index + 1)
        iv_memory[clear_index] <= 8'h0;
      for (clear_index = 0; clear_index < 64; clear_index = clear_index + 1) begin
        aad_memory[clear_index] <= 8'h0;
        data_memory[clear_index] <= 8'h0;
        output_memory[clear_index] <= 8'h0;
      end
    end else begin
      if (state != ST_IDLE && state != ST_RESULT)
        transaction_cycles <= transaction_cycles + 1'b1;
      if ((in_ready && !in_valid) || (tag_in_ready && !tag_in_valid)
          || (out_valid && !out_ready))
        transaction_stalls <= transaction_stalls + 1'b1;

      case (state)
        ST_IDLE: begin
          if (cmd_valid && cmd_ready) begin
            transaction_cycles <= 32'd1;
            transaction_stalls <= 32'h0;
            result_status <= STATUS_OK;
            result_auth_ok <= 1'b0;
            result_tag <= 128'h0;
            result_cycles <= 32'h0;
            result_stall_cycles <= 32'h0;
            operation_encrypt <= cmd_encrypt;
            iv_length <= cmd_iv_bytes;
            aad_length <= cmd_aad_bytes;
            data_length <= cmd_data_bytes;
            input_index <= 7'h0;
            if (!aes_key_loaded) begin
              result_status <= STATUS_NO_KEY;
              result_cycles <= 32'd1;
              result_valid <= 1'b1;
              state <= ST_RESULT;
            end else if (!((cmd_iv_bytes == 1) || (cmd_iv_bytes == 12))
                         || cmd_aad_bytes > 64 || cmd_data_bytes > 64) begin
              result_status <= STATUS_LENGTH;
              result_cycles <= 32'd1;
              result_valid <= 1'b1;
              state <= ST_RESULT;
            end else begin
              state <= ST_INPUT_IV;
            end
          end
        end

        ST_INPUT_IV: if (in_valid && in_ready) begin
          iv_memory[input_index[3:0]] <= in_data;
          if (input_index + 1'b1 == {2'b0, iv_length}) begin
            input_index <= 7'h0;
            if (aad_length != 0) state <= ST_INPUT_AAD;
            else if (data_length != 0) state <= ST_INPUT_DATA;
            else if (!operation_encrypt) state <= ST_INPUT_TAG;
            else state <= ST_AES_H_START;
          end else input_index <= input_index + 1'b1;
        end

        ST_INPUT_AAD: if (in_valid && in_ready) begin
          aad_memory[input_index[5:0]] <= in_data;
          if (input_index + 1'b1 == aad_length) begin
            input_index <= 7'h0;
            if (data_length != 0) state <= ST_INPUT_DATA;
            else if (!operation_encrypt) state <= ST_INPUT_TAG;
            else state <= ST_AES_H_START;
          end else input_index <= input_index + 1'b1;
        end

        ST_INPUT_DATA: if (in_valid && in_ready) begin
          data_memory[input_index[5:0]] <= in_data;
          if (input_index + 1'b1 == data_length) begin
            input_index <= 7'h0;
            if (!operation_encrypt) state <= ST_INPUT_TAG;
            else state <= ST_AES_H_START;
          end else input_index <= input_index + 1'b1;
        end

        ST_INPUT_TAG: if (tag_in_valid && tag_in_ready) begin
          expected_tag <= tag_in;
          state <= ST_AES_H_START;
        end

        ST_AES_H_START: if (aes_block_valid && aes_block_ready) state <= ST_AES_H_WAIT;
        ST_AES_H_WAIT: if (aes_output_valid && aes_output_ready) begin
          hash_subkey <= aes_output;
          ghash_state <= 128'h0;
          if (iv_length == 12) begin
            j0 <= iv_fast_block();
            state <= ST_AES_S0_START;
          end else state <= ST_IV_GHASH_START;
        end

        ST_IV_GHASH_START: if (ghash_input_valid && ghash_input_ready) state <= ST_IV_GHASH_WAIT;
        ST_IV_GHASH_WAIT: if (ghash_output_valid && ghash_output_ready) begin
          ghash_state <= ghash_output;
          state <= ST_IV_LENGTH_START;
        end
        ST_IV_LENGTH_START: if (ghash_input_valid && ghash_input_ready) state <= ST_IV_LENGTH_WAIT;
        ST_IV_LENGTH_WAIT: if (ghash_output_valid && ghash_output_ready) begin
          j0 <= ghash_output;
          ghash_state <= 128'h0;
          state <= ST_AES_S0_START;
        end

        ST_AES_S0_START: if (aes_block_valid && aes_block_ready) state <= ST_AES_S0_WAIT;
        ST_AES_S0_WAIT: if (aes_output_valid && aes_output_ready) begin
          tag_mask <= aes_output;
          counter <= increment_counter(j0);
          ghash_state <= 128'h0;
          block_index <= 3'h0;
          if (aad_length != 0) state <= ST_AAD_GHASH_START;
          else if (data_length != 0) state <= ST_DATA_AES_START;
          else state <= ST_LENGTH_GHASH_START;
        end

        ST_AAD_GHASH_START: if (ghash_input_valid && ghash_input_ready) state <= ST_AAD_GHASH_WAIT;
        ST_AAD_GHASH_WAIT: if (ghash_output_valid && ghash_output_ready) begin
          ghash_state <= ghash_output;
          if ({block_index, 4'h0} + 7'd16 < aad_length) begin
            block_index <= block_index + 1'b1;
            state <= ST_AAD_GHASH_START;
          end else begin
            block_index <= 3'h0;
            if (data_length != 0) state <= ST_DATA_AES_START;
            else state <= ST_LENGTH_GHASH_START;
          end
        end

        ST_DATA_AES_START: if (aes_block_valid && aes_block_ready) state <= ST_DATA_AES_WAIT;
        ST_DATA_AES_WAIT: if (aes_output_valid && aes_output_ready) begin
          cipher_block <= operation_encrypt ? masked_xor_block(block_index, aes_output)
                                            : data_block(block_index);
          for (store_index = 0; store_index < 16; store_index = store_index + 1)
            if (block_index * 16 + store_index < data_length)
              output_memory[block_index * 16 + store_index] <=
                  data_memory[block_index * 16 + store_index]
                  ^ aes_output[127 - store_index*8 -: 8];
          state <= ST_DATA_GHASH_START;
        end
        ST_DATA_GHASH_START: if (ghash_input_valid && ghash_input_ready) state <= ST_DATA_GHASH_WAIT;
        ST_DATA_GHASH_WAIT: if (ghash_output_valid && ghash_output_ready) begin
          ghash_state <= ghash_output;
          if ({block_index, 4'h0} + 7'd16 < data_length) begin
            block_index <= block_index + 1'b1;
            counter <= increment_counter(counter);
            state <= ST_DATA_AES_START;
          end else begin
            block_index <= 3'h0;
            state <= ST_LENGTH_GHASH_START;
          end
        end

        ST_LENGTH_GHASH_START: if (ghash_input_valid && ghash_input_ready) state <= ST_LENGTH_GHASH_WAIT;
        ST_LENGTH_GHASH_WAIT: if (ghash_output_valid && ghash_output_ready) begin
          result_tag <= tag_mask ^ ghash_output;
          if (!operation_encrypt && |(expected_tag ^ tag_mask ^ ghash_output)) begin
            result_status <= STATUS_AUTH;
            result_auth_ok <= 1'b0;
            result_cycles <= transaction_cycles + 1'b1;
            result_stall_cycles <= transaction_stalls;
            result_valid <= 1'b1;
            state <= ST_RESULT;
          end else begin
            result_status <= STATUS_OK;
            result_auth_ok <= 1'b1;
            output_index <= 7'h0;
            if (data_length == 0) begin
              result_cycles <= transaction_cycles + 1'b1;
              result_stall_cycles <= transaction_stalls;
              result_valid <= 1'b1;
              state <= ST_RESULT;
            end else state <= ST_OUTPUT;
          end
        end

        ST_OUTPUT: if (out_valid && out_ready) begin
          if (output_index + 1'b1 == data_length) begin
            result_cycles <= transaction_cycles + 1'b1;
            result_stall_cycles <= transaction_stalls;
            result_valid <= 1'b1;
            output_index <= 7'h0;
            state <= ST_RESULT;
          end else output_index <= output_index + 1'b1;
        end

        ST_RESULT: if (result_valid && result_ready) begin
          result_valid <= 1'b0;
          result_status <= STATUS_OK;
          result_auth_ok <= 1'b0;
          result_tag <= 128'h0;
          hash_subkey <= 128'h0;
          ghash_state <= 128'h0;
          j0 <= 128'h0;
          counter <= 128'h0;
          tag_mask <= 128'h0;
          expected_tag <= 128'h0;
          cipher_block <= 128'h0;
          transaction_cycles <= 32'h0;
          transaction_stalls <= 32'h0;
          for (clear_index = 0; clear_index < 12; clear_index = clear_index + 1)
            iv_memory[clear_index] <= 8'h0;
          for (clear_index = 0; clear_index < 64; clear_index = clear_index + 1) begin
            aad_memory[clear_index] <= 8'h0;
            data_memory[clear_index] <= 8'h0;
            output_memory[clear_index] <= 8'h0;
          end
          state <= ST_IDLE;
        end
        default: state <= ST_IDLE;
      endcase
    end
  end
endmodule
