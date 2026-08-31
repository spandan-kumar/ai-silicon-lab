// AES-256 block encryption, one round per cycle, with an on-the-fly key
// schedule. GCM uses the forward cipher only -- for both encryption and
// decryption -- so no inverse datapath exists here.
//
// FIPS 197 with Nk=8, Nr=14. Round key r is the upper half of the schedule
// register on even r and the lower half on odd r; the register advances by
// eight words after every odd round, giving the seven advances that AES-256
// needs to reach round key 14.

module aes256_enc (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         start,
    input  logic [255:0] key,
    input  logic [127:0] block_in,
    output logic         busy,
    output logic         done,
    output logic [127:0] block_out
);
  // Byte i of the AES state occupies bits [127-8i -: 8]; row = i%4, col = i/4.
  function automatic logic [7:0] xtime(input logic [7:0] value);
    xtime = {value[6:0], 1'b0} ^ (value[7] ? 8'h1b : 8'h00);
  endfunction

  logic [127:0] state_q;
  logic [255:0] sched_q;
  logic [3:0]   round_q;
  logic         busy_q;
  logic         done_q;

  logic [127:0] subbed;
  for (genvar i = 0; i < 16; i++) begin : g_state_sbox
    aes_sbox u_sbox (.in(state_q[127-8*i -: 8]), .out(subbed[127-8*i -: 8]));
  end

  // ShiftRows: output byte (r, c) takes input byte (r, (c+r) % 4).
  logic [127:0] shifted;
  always_comb begin
    for (int c = 0; c < 4; c++) begin
      for (int r = 0; r < 4; r++) begin
        shifted[127-8*(c*4+r) -: 8] = subbed[127-8*(((c+r)%4)*4+r) -: 8];
      end
    end
  end

  logic [127:0] mixed;
  always_comb begin
    logic [7:0] b0, b1, b2, b3;
    for (int c = 0; c < 4; c++) begin
      b0 = shifted[127-8*(c*4+0) -: 8];
      b1 = shifted[127-8*(c*4+1) -: 8];
      b2 = shifted[127-8*(c*4+2) -: 8];
      b3 = shifted[127-8*(c*4+3) -: 8];
      mixed[127-8*(c*4+0) -: 8] = xtime(b0) ^ (xtime(b1) ^ b1) ^ b2 ^ b3;
      mixed[127-8*(c*4+1) -: 8] = b0 ^ xtime(b1) ^ (xtime(b2) ^ b2) ^ b3;
      mixed[127-8*(c*4+2) -: 8] = b0 ^ b1 ^ xtime(b2) ^ (xtime(b3) ^ b3);
      mixed[127-8*(c*4+3) -: 8] = (xtime(b0) ^ b0) ^ b1 ^ b2 ^ xtime(b3);
    end
  end

  logic [127:0] round_key;
  assign round_key = round_q[0] ? sched_q[127:0] : sched_q[255:128];

  // Key-schedule advance: eight new words derived from the current eight.
  // These are named nets rather than an unpacked array so that synthesis does
  // not report inferring a memory for what is combinational logic.
  logic [31:0] w0, w1, w2, w3, w4, w5, w6, w7;
  assign {w0, w1, w2, w3, w4, w5, w6, w7} = sched_q;

  logic [31:0] rot_word, rot_sub, plain_sub;
  assign rot_word = {w7[23:0], w7[31:24]};
  for (genvar b = 0; b < 4; b++) begin : g_rot_sbox
    aes_sbox u_rot (.in(rot_word[31-8*b -: 8]), .out(rot_sub[31-8*b -: 8]));
  end

  logic [31:0] nw0, nw1, nw2, nw3, nw4, nw5, nw6, nw7;
  logic [7:0]  rcon;
  // Advance k (1..7) uses Rcon 0x01 << (k-1); AES-256 never reaches 0x80.
  assign rcon = 8'h01 << round_q[3:1];
  assign nw0  = w0 ^ {rot_sub[31:24] ^ rcon, rot_sub[23:0]};
  assign nw1  = w1 ^ nw0;
  assign nw2  = w2 ^ nw1;
  assign nw3  = w3 ^ nw2;
  for (genvar b = 0; b < 4; b++) begin : g_plain_sbox
    aes_sbox u_plain (.in(nw3[31-8*b -: 8]), .out(plain_sub[31-8*b -: 8]));
  end
  assign nw4 = w4 ^ plain_sub;
  assign nw5 = w5 ^ nw4;
  assign nw6 = w6 ^ nw5;
  assign nw7 = w7 ^ nw6;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state_q <= '0;
      sched_q <= '0;
      round_q <= '0;
      busy_q  <= 1'b0;
      done_q  <= 1'b0;
    end else begin
      done_q <= 1'b0;
      if (start && !busy_q) begin
        state_q <= block_in ^ key[255:128];  // AddRoundKey with RK0
        sched_q <= key;
        round_q <= 4'd1;
        busy_q  <= 1'b1;
      end else if (busy_q) begin
        state_q <= (round_q == 4'd14) ? (shifted ^ round_key) : (mixed ^ round_key);
        if (round_q[0]) begin
          sched_q <= {nw0, nw1, nw2, nw3, nw4, nw5, nw6, nw7};
        end
        if (round_q == 4'd14) begin
          busy_q <= 1'b0;
          done_q <= 1'b1;
        end else begin
          round_q <= round_q + 4'd1;
        end
      end
    end
  end

  assign busy      = busy_q;
  assign done      = done_q;
  assign block_out = state_q;
endmodule
