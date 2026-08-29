// AES-256-GCM authenticated encryption and decryption.
//
// Frozen profile for this baseline (see experiments/aes-256-gcm/PROFILE.md):
//   * AES-256 only; 128-bit blocks; FIPS 197 forward cipher.
//   * IV: the 96-bit fast path and the GHASH path for any other length.
//   * Tag: 1..16 bytes, truncated by keeping the leftmost bytes.
//   * Decryption releases plaintext only after the tag verifies. Plaintext is
//     therefore buffered internally, which bounds the message length to
//     MAX_TEXT_BYTES. That bound is part of the profile, not a hidden limit.
//   * On tag failure: no plaintext is emitted, tag_ok is low, and the output
//     buffer and working state are cleared.
//
// Streaming framing: after `start`, the input byte stream carries the IV, then
// the AAD, then the payload, using the lengths latched at start. Both streams
// use valid/ready and tolerate stalls in either direction at any phase.

module aes_gcm #(
    parameter int MAX_TEXT_BYTES = 512
) (
    input  logic         clk,
    input  logic         rst_n,

    // Operation setup, latched on `start`.
    input  logic         start,
    input  logic [255:0] key,
    input  logic         decrypt,
    input  logic [15:0]  iv_bytes,
    input  logic [31:0]  aad_bytes,
    input  logic [31:0]  txt_bytes,
    input  logic [4:0]   tag_bytes,
    input  logic [127:0] exp_tag,

    // Input byte stream: IV, then AAD, then payload.
    input  logic         in_valid,
    output logic         in_ready,
    input  logic [7:0]   in_data,

    // Output byte stream: ciphertext when encrypting, verified plaintext when
    // decrypting.
    output logic         out_valid,
    input  logic         out_ready,
    output logic [7:0]   out_data,

    output logic         busy,
    output logic         done,
    output logic [127:0] tag,
    output logic         tag_ok
);
  typedef enum logic [4:0] {
    S_IDLE, S_H, S_IV, S_IV_PAD, S_IV_LEN, S_J0, S_EK0,
    S_AAD, S_AAD_PAD, S_TEXT_FILL, S_TEXT_AES, S_TEXT_EMIT, S_TEXT_GH,
    S_LEN, S_TAG, S_FLUSH, S_DONE, S_GH
  } state_e;

  state_e state_q, gh_return_q;

  logic [255:0] key_q;
  logic         decrypt_q;
  logic [15:0]  iv_bytes_q;
  logic [31:0]  aad_bytes_q, txt_bytes_q;
  logic [4:0]   tag_bytes_q;
  logic [127:0] exp_tag_q;

  logic [127:0] h_q, j0_q, ctr_q, y_q, ek0_q, tag_q;
  logic [127:0] block_q, keystream_q, out_block_q, gh_block_q;
  logic [31:0]  in_count_q, out_count_q;
  logic [4:0]   fill_q, emit_len_q, emit_idx_q;
  logic         tag_ok_q, done_q, busy_q;

  // Plaintext buffer: decryption must not release bytes before the tag
  // verifies, so the design holds them here.
  logic [7:0]   obuf_q [0:MAX_TEXT_BYTES-1];
  logic [31:0]  flush_idx_q;

  // --- Shared AES engine --------------------------------------------------
  logic         aes_start;
  logic [127:0] aes_in, aes_out;
  logic         aes_busy, aes_done;
  aes256_enc u_aes (
      .clk(clk), .rst_n(rst_n), .start(aes_start), .key(key_q),
      .block_in(aes_in), .busy(aes_busy), .done(aes_done), .block_out(aes_out)
  );

  // --- Shared GHASH multiplier -------------------------------------------
  logic         gh_start;
  logic [127:0] gh_x, gh_z;
  logic         gh_busy, gh_done;
  ghash_mul u_ghash (
      .clk(clk), .rst_n(rst_n), .start(gh_start), .x(gh_x), .y(h_q),
      .busy(gh_busy), .done(gh_done), .z(gh_z)
  );
  assign gh_x = y_q ^ gh_block_q;

  // Byte lane helpers: byte 0 of a block is the most significant byte.
  // These assign to the function name rather than using `return`, which the
  // Yosys Verilog frontend does not accept inside a function.
  function automatic logic [127:0] insert_byte(
      input logic [127:0] blk, input logic [4:0] index, input logic [7:0] value);
    begin
      insert_byte = blk;
      insert_byte[127 - 8*index -: 8] = value;
    end
  endfunction

  function automatic logic [7:0] extract_byte(
      input logic [127:0] blk, input logic [4:0] index);
    begin
      extract_byte = blk[127 - 8*index -: 8];
    end
  endfunction

  // Zero the bytes at and beyond `len`, for GHASH of a partial final block.
  function automatic logic [127:0] mask_tail(
      input logic [127:0] blk, input logic [4:0] len);
    integer i;
    begin
      mask_tail = '0;
      for (i = 0; i < 16; i = i + 1) begin
        if (i < len) mask_tail[127 - 8*i -: 8] = blk[127 - 8*i -: 8];
      end
    end
  endfunction

  logic [31:0] aad_remaining, txt_remaining;
  assign aad_remaining = aad_bytes_q - in_count_q;
  assign txt_remaining = txt_bytes_q - in_count_q;

  // Ready must fall in the same cycle the phase's last byte has been taken.
  // Asserting it during the transition cycle would let a producer hand over a
  // byte that the state machine has already stopped accepting.
  assign in_ready = ((state_q == S_IV)        && (in_count_q < {16'd0, iv_bytes_q})) ||
                    ((state_q == S_AAD)       && (in_count_q < aad_bytes_q)) ||
                    ((state_q == S_TEXT_FILL) && (in_count_q < txt_bytes_q));
  assign out_valid = ((state_q == S_TEXT_EMIT) && !decrypt_q && (emit_idx_q < emit_len_q)) ||
                     ((state_q == S_FLUSH) && (flush_idx_q < txt_bytes_q));
  assign out_data  = (state_q == S_FLUSH) ? obuf_q[flush_idx_q]
                                          : extract_byte(out_block_q, emit_idx_q);

  assign busy   = busy_q;
  assign done   = done_q;
  assign tag    = tag_q;
  assign tag_ok = tag_ok_q;

  // Mask keeping only the leftmost tag_bytes_q bytes, for truncated tags.
  logic [127:0] tag_mask;
  always_comb begin
    tag_mask = '0;
    for (int i = 0; i < 16; i++) begin
      if (i < int'(tag_bytes_q)) tag_mask[127 - 8*i -: 8] = 8'hff;
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state_q <= S_IDLE; gh_return_q <= S_IDLE;
      key_q <= '0; decrypt_q <= 1'b0; iv_bytes_q <= '0;
      aad_bytes_q <= '0; txt_bytes_q <= '0; tag_bytes_q <= '0; exp_tag_q <= '0;
      h_q <= '0; j0_q <= '0; ctr_q <= '0; y_q <= '0; ek0_q <= '0; tag_q <= '0;
      block_q <= '0; keystream_q <= '0; out_block_q <= '0; gh_block_q <= '0;
      in_count_q <= '0; out_count_q <= '0; fill_q <= '0;
      emit_len_q <= '0; emit_idx_q <= '0; flush_idx_q <= '0;
      tag_ok_q <= 1'b0; done_q <= 1'b0; busy_q <= 1'b0;
      aes_start <= 1'b0; aes_in <= '0; gh_start <= 1'b0;
    end else begin
      aes_start <= 1'b0;
      gh_start  <= 1'b0;
      done_q    <= 1'b0;

      unique case (state_q)
        S_IDLE: begin
          if (start) begin
            key_q <= key; decrypt_q <= decrypt;
            iv_bytes_q <= iv_bytes; aad_bytes_q <= aad_bytes;
            txt_bytes_q <= txt_bytes; tag_bytes_q <= tag_bytes;
            exp_tag_q <= exp_tag;
            y_q <= '0; block_q <= '0; fill_q <= '0; in_count_q <= '0;
            out_count_q <= '0; flush_idx_q <= '0; tag_ok_q <= 1'b0;
            busy_q <= 1'b1;
            // H = E(K, 0^128). The key register is written this cycle, so the
            // AES start is issued in the next state.
            state_q <= S_H;
          end
        end

        // --- H ------------------------------------------------------------
        S_H: begin
          if (!aes_busy && !aes_done && !aes_start) begin
            aes_in <= '0;
            aes_start <= 1'b1;
          end else if (aes_done) begin
            h_q <= aes_out;
            in_count_q <= '0;
            block_q <= '0;
            fill_q <= '0;
            state_q <= S_IV;
          end
        end

        // --- IV -----------------------------------------------------------
        S_IV: begin
          if (iv_bytes_q == 16'd12) begin
            if (in_valid) begin
              block_q <= insert_byte(block_q, fill_q, in_data);
              fill_q <= fill_q + 5'd1;
              in_count_q <= in_count_q + 32'd1;
              if (in_count_q + 32'd1 == 32'd12) begin
                state_q <= S_J0;
              end
            end
          end else begin
            if (in_count_q == {16'b0, iv_bytes_q}) begin
              state_q <= S_IV_PAD;
            end else if (in_valid) begin
              block_q <= insert_byte(block_q, fill_q, in_data);
              in_count_q <= in_count_q + 32'd1;
              if (fill_q == 5'd15) begin
                gh_block_q <= insert_byte(block_q, fill_q, in_data);
                gh_return_q <= S_IV;
                fill_q <= '0;
                block_q <= '0;
                state_q <= S_GH;
              end else begin
                fill_q <= fill_q + 5'd1;
              end
            end
          end
        end

        S_IV_PAD: begin
          if (fill_q != 5'd0) begin
            gh_block_q <= block_q;          // already zero-padded on the right
            gh_return_q <= S_IV_LEN;
            fill_q <= '0;
            block_q <= '0;
            state_q <= S_GH;
          end else begin
            state_q <= S_IV_LEN;
          end
        end

        S_IV_LEN: begin
          gh_block_q <= {64'd0, 45'd0, iv_bytes_q, 3'd0};  // 0^64 || len(IV) in bits
          gh_return_q <= S_J0;
          state_q <= S_GH;
        end

        S_J0: begin
          if (iv_bytes_q == 16'd12) begin
            j0_q <= {block_q[127:32], 32'd1};
            ctr_q <= {block_q[127:32], 32'd2};
          end else begin
            j0_q <= y_q;
            ctr_q <= {y_q[127:32], y_q[31:0] + 32'd1};
          end
          y_q <= '0;                         // GHASH restarts for AAD/payload
          aes_in <= (iv_bytes_q == 16'd12) ? {block_q[127:32], 32'd1} : y_q;
          aes_start <= 1'b1;
          state_q <= S_EK0;
        end

        S_EK0: begin
          if (aes_done) begin
            ek0_q <= aes_out;
            in_count_q <= '0;
            fill_q <= '0;
            block_q <= '0;
            state_q <= S_AAD;
          end
        end

        // --- AAD ----------------------------------------------------------
        S_AAD: begin
          if (in_count_q == aad_bytes_q) begin
            state_q <= S_AAD_PAD;
          end else if (in_valid) begin
            block_q <= insert_byte(block_q, fill_q, in_data);
            in_count_q <= in_count_q + 32'd1;
            if (fill_q == 5'd15) begin
              gh_block_q <= insert_byte(block_q, fill_q, in_data);
              gh_return_q <= S_AAD;
              fill_q <= '0;
              block_q <= '0;
              state_q <= S_GH;
            end else begin
              fill_q <= fill_q + 5'd1;
            end
          end
        end

        S_AAD_PAD: begin
          if (fill_q != 5'd0) begin
            gh_block_q <= block_q;
            gh_return_q <= S_TEXT_FILL;
            fill_q <= '0;
            block_q <= '0;
            in_count_q <= '0;
            state_q <= S_GH;
          end else begin
            in_count_q <= '0;
            state_q <= S_TEXT_FILL;
          end
        end

        // --- Payload ------------------------------------------------------
        S_TEXT_FILL: begin
          if (in_count_q == txt_bytes_q) begin
            if (fill_q != 5'd0) begin
              aes_in <= ctr_q;
              aes_start <= 1'b1;
              state_q <= S_TEXT_AES;
            end else begin
              state_q <= S_LEN;
            end
          end else if (in_valid) begin
            block_q <= insert_byte(block_q, fill_q, in_data);
            in_count_q <= in_count_q + 32'd1;
            if (fill_q == 5'd15) begin
              block_q <= insert_byte(block_q, fill_q, in_data);
              fill_q <= 5'd16;
              aes_in <= ctr_q;
              aes_start <= 1'b1;
              state_q <= S_TEXT_AES;
            end else begin
              fill_q <= fill_q + 5'd1;
            end
          end
        end

        S_TEXT_AES: begin
          if (aes_done) begin
            keystream_q <= aes_out;
            out_block_q <= block_q ^ aes_out;
            emit_len_q <= fill_q;
            emit_idx_q <= '0;
            ctr_q <= {ctr_q[127:32], ctr_q[31:0] + 32'd1};
            state_q <= S_TEXT_EMIT;
          end
        end

        S_TEXT_EMIT: begin
          if (emit_idx_q == emit_len_q) begin
            // GHASH absorbs the ciphertext, zero-padded on the right. When
            // encrypting that is the produced block; when decrypting it is the
            // block that arrived.
            gh_block_q <= decrypt_q ? mask_tail(block_q, emit_len_q)
                                    : mask_tail(out_block_q, emit_len_q);
            gh_return_q <= S_TEXT_GH;
            state_q <= S_GH;
          end else if (decrypt_q) begin
            // Buffered, not released: the tag has not been checked yet.
            obuf_q[out_count_q] <= extract_byte(out_block_q, emit_idx_q);
            out_count_q <= out_count_q + 32'd1;
            emit_idx_q <= emit_idx_q + 5'd1;
          end else if (out_ready) begin
            out_count_q <= out_count_q + 32'd1;
            emit_idx_q <= emit_idx_q + 5'd1;
          end
        end

        S_TEXT_GH: begin
          fill_q <= '0;
          block_q <= '0;
          state_q <= (in_count_q == txt_bytes_q) ? S_LEN : S_TEXT_FILL;
        end

        // --- Lengths and tag ----------------------------------------------
        S_LEN: begin
          gh_block_q <= {29'd0, aad_bytes_q, 3'd0, 29'd0, txt_bytes_q, 3'd0};
          gh_return_q <= S_TAG;
          state_q <= S_GH;
        end

        S_TAG: begin
          tag_q <= y_q ^ ek0_q;
          if (decrypt_q) begin
            if (((y_q ^ ek0_q) & tag_mask) == (exp_tag_q & tag_mask)) begin
              tag_ok_q <= 1'b1;
              flush_idx_q <= '0;
              state_q <= S_FLUSH;
            end else begin
              // Authentication failed: emit nothing, and do not expose the
              // tag that was computed. Publishing it would hand an attacker
              // the value needed to forge this message.
              tag_ok_q <= 1'b0;
              tag_q <= '0;
              y_q <= '0;
              keystream_q <= '0;
              out_block_q <= '0;
              block_q <= '0;
              state_q <= S_DONE;
            end
          end else begin
            tag_ok_q <= 1'b1;
            state_q <= S_DONE;
          end
        end

        S_FLUSH: begin
          if (flush_idx_q == txt_bytes_q) begin
            state_q <= S_DONE;
          end else if (out_ready) begin
            flush_idx_q <= flush_idx_q + 32'd1;
          end
        end

        S_DONE: begin
          done_q <= 1'b1;
          busy_q <= 1'b0;
          y_q <= '0;
          keystream_q <= '0;
          state_q <= S_IDLE;
        end

        // --- Shared GHASH sequencer ---------------------------------------
        S_GH: begin
          if (!gh_busy && !gh_done && !gh_start) begin
            gh_start <= 1'b1;
          end else if (gh_done) begin
            y_q <= gh_z;
            state_q <= gh_return_q;
          end
        end

        default: state_q <= S_IDLE;
      endcase
    end
  end

endmodule
