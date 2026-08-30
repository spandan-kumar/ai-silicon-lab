#!/usr/bin/env python3
"""Generate the auditable SystemVerilog AES lookup/function include."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from aes_gcm import INV_SBOX, SBOX


def lookup(name: str, values: tuple[int, ...]) -> str:
    packed = "".join(f"{value:02x}" for value in reversed(values))
    return "\n".join([
        f"function automatic [7:0] {name}(input [7:0] value);",
        "  reg [2047:0] lookup_bits;",
        "  begin",
        f"    lookup_bits = 2048'h{packed};",
        f"    {name} = lookup_bits[value*8 +: 8];",
        "  end",
        "endfunction",
        "",
    ])


BODY = r'''function automatic [7:0] aes_xtime(input [7:0] value);
  aes_xtime = {value[6:0], 1'b0} ^ (8'h1b & {8{value[7]}});
endfunction

function automatic [7:0] aes_gf_mul(input [7:0] left, input [7:0] right);
  reg [7:0] x2;
  reg [7:0] x4;
  reg [7:0] x8;
  begin
    x2 = aes_xtime(right);
    x4 = aes_xtime(x2);
    x8 = aes_xtime(x4);
    case (left)
      8'h01: aes_gf_mul = right;
      8'h02: aes_gf_mul = x2;
      8'h03: aes_gf_mul = x2 ^ right;
      8'h09: aes_gf_mul = x8 ^ right;
      8'h0b: aes_gf_mul = x8 ^ x2 ^ right;
      8'h0d: aes_gf_mul = x8 ^ x4 ^ right;
      8'h0e: aes_gf_mul = x8 ^ x4 ^ x2;
      default: aes_gf_mul = 8'h00;
    endcase
  end
endfunction

function automatic [127:0] aes_sub_bytes(input [127:0] state);
  integer i;
  begin
    for (i = 0; i < 16; i = i + 1)
      aes_sub_bytes[127 - i*8 -: 8] = aes_sbox(state[127 - i*8 -: 8]);
  end
endfunction

function automatic [127:0] aes_inv_sub_bytes(input [127:0] state);
  integer i;
  begin
    for (i = 0; i < 16; i = i + 1)
      aes_inv_sub_bytes[127 - i*8 -: 8] = aes_inv_sbox(state[127 - i*8 -: 8]);
  end
endfunction

function automatic [127:0] aes_shift_rows(input [127:0] state);
  integer row;
  integer column;
  integer source_column;
  begin
    for (column = 0; column < 4; column = column + 1)
      for (row = 0; row < 4; row = row + 1) begin
        source_column = (column + row) % 4;
        aes_shift_rows[127 - (4*column + row)*8 -: 8] = state[127 - (4*source_column + row)*8 -: 8];
      end
  end
endfunction

function automatic [127:0] aes_inv_shift_rows(input [127:0] state);
  integer row;
  integer column;
  integer source_column;
  begin
    for (column = 0; column < 4; column = column + 1)
      for (row = 0; row < 4; row = row + 1) begin
        source_column = (column - row + 4) % 4;
        aes_inv_shift_rows[127 - (4*column + row)*8 -: 8] = state[127 - (4*source_column + row)*8 -: 8];
      end
  end
endfunction

function automatic [127:0] aes_mix_columns(input [127:0] state);
  reg [7:0] a0;
  reg [7:0] a1;
  reg [7:0] a2;
  reg [7:0] a3;
  integer column;
  begin
    for (column = 0; column < 4; column = column + 1) begin
      a0 = state[127 - (4*column + 0)*8 -: 8];
      a1 = state[127 - (4*column + 1)*8 -: 8];
      a2 = state[127 - (4*column + 2)*8 -: 8];
      a3 = state[127 - (4*column + 3)*8 -: 8];
      aes_mix_columns[127 - (4*column + 0)*8 -: 8] = aes_gf_mul(8'h02, a0) ^ aes_gf_mul(8'h03, a1) ^ a2 ^ a3;
      aes_mix_columns[127 - (4*column + 1)*8 -: 8] = a0 ^ aes_gf_mul(8'h02, a1) ^ aes_gf_mul(8'h03, a2) ^ a3;
      aes_mix_columns[127 - (4*column + 2)*8 -: 8] = a0 ^ a1 ^ aes_gf_mul(8'h02, a2) ^ aes_gf_mul(8'h03, a3);
      aes_mix_columns[127 - (4*column + 3)*8 -: 8] = aes_gf_mul(8'h03, a0) ^ a1 ^ a2 ^ aes_gf_mul(8'h02, a3);
    end
  end
endfunction

function automatic [127:0] aes_inv_mix_columns(input [127:0] state);
  reg [7:0] a0;
  reg [7:0] a1;
  reg [7:0] a2;
  reg [7:0] a3;
  integer column;
  begin
    for (column = 0; column < 4; column = column + 1) begin
      a0 = state[127 - (4*column + 0)*8 -: 8];
      a1 = state[127 - (4*column + 1)*8 -: 8];
      a2 = state[127 - (4*column + 2)*8 -: 8];
      a3 = state[127 - (4*column + 3)*8 -: 8];
      aes_inv_mix_columns[127 - (4*column + 0)*8 -: 8] = aes_gf_mul(8'h0e, a0) ^ aes_gf_mul(8'h0b, a1) ^ aes_gf_mul(8'h0d, a2) ^ aes_gf_mul(8'h09, a3);
      aes_inv_mix_columns[127 - (4*column + 1)*8 -: 8] = aes_gf_mul(8'h09, a0) ^ aes_gf_mul(8'h0e, a1) ^ aes_gf_mul(8'h0b, a2) ^ aes_gf_mul(8'h0d, a3);
      aes_inv_mix_columns[127 - (4*column + 2)*8 -: 8] = aes_gf_mul(8'h0d, a0) ^ aes_gf_mul(8'h09, a1) ^ aes_gf_mul(8'h0e, a2) ^ aes_gf_mul(8'h0b, a3);
      aes_inv_mix_columns[127 - (4*column + 3)*8 -: 8] = aes_gf_mul(8'h0b, a0) ^ aes_gf_mul(8'h0d, a1) ^ aes_gf_mul(8'h09, a2) ^ aes_gf_mul(8'h0e, a3);
    end
  end
endfunction

function automatic [127:0] aes_round(input [127:0] state, input [127:0] round_key);
  aes_round = aes_mix_columns(aes_shift_rows(aes_sub_bytes(state))) ^ round_key;
endfunction

function automatic [127:0] aes_final_round(input [127:0] state, input [127:0] round_key);
  aes_final_round = aes_shift_rows(aes_sub_bytes(state)) ^ round_key;
endfunction

function automatic [127:0] aes_inv_round(input [127:0] state, input [127:0] round_key);
  aes_inv_round = aes_inv_mix_columns(aes_inv_sub_bytes(aes_inv_shift_rows(state)) ^ round_key);
endfunction

function automatic [127:0] aes_inv_final_round(input [127:0] state, input [127:0] round_key);
  aes_inv_final_round = aes_inv_sub_bytes(aes_inv_shift_rows(state)) ^ round_key;
endfunction

function automatic [7:0] aes_rcon(input [3:0] pair_index);
  begin
    case (pair_index)
      4'd1: aes_rcon = 8'h01;
      4'd2: aes_rcon = 8'h02;
      4'd3: aes_rcon = 8'h04;
      4'd4: aes_rcon = 8'h08;
      4'd5: aes_rcon = 8'h10;
      4'd6: aes_rcon = 8'h20;
      4'd7: aes_rcon = 8'h40;
      default: aes_rcon = 8'h00;
    endcase
  end
endfunction

function automatic [31:0] aes_sub_word(input [31:0] word);
  aes_sub_word = {aes_sbox(word[31:24]), aes_sbox(word[23:16]), aes_sbox(word[15:8]), aes_sbox(word[7:0])};
endfunction

function automatic [255:0] aes_next_key_pair(input [255:0] current, input [3:0] pair_index);
  reg [31:0] w0;
  reg [31:0] w1;
  reg [31:0] w2;
  reg [31:0] w3;
  reg [31:0] w4;
  reg [31:0] w5;
  reg [31:0] w6;
  reg [31:0] w7;
  reg [31:0] n0;
  reg [31:0] n1;
  reg [31:0] n2;
  reg [31:0] n3;
  reg [31:0] n4;
  reg [31:0] n5;
  reg [31:0] n6;
  reg [31:0] n7;
  begin
    {w0, w1, w2, w3, w4, w5, w6, w7} = current;
    n0 = w0 ^ aes_sub_word({w7[23:0], w7[31:24]}) ^ {aes_rcon(pair_index), 24'h0};
    n1 = w1 ^ n0;
    n2 = w2 ^ n1;
    n3 = w3 ^ n2;
    n4 = w4 ^ aes_sub_word(n3);
    n5 = w5 ^ n4;
    n6 = w6 ^ n5;
    n7 = w7 ^ n6;
    aes_next_key_pair = {n0, n1, n2, n3, n4, n5, n6, n7};
  end
endfunction

'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "rtl" / "aes_functions.svh")
    args = parser.parse_args()
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    text = "// Generated by tools/generate_rtl_functions.py; do not edit by hand.\n\n"
    text += lookup("aes_sbox", SBOX)
    text += lookup("aes_inv_sbox", INV_SBOX)
    text += BODY
    output.write_text(text)
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
