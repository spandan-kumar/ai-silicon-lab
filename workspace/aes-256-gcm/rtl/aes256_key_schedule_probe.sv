// Test-only probe for direct comparison of all AES-256 round keys.
module aes256_key_schedule_probe (
    input  logic [255:0]  key_in,
    output logic [1919:0] round_keys_flat
);
  `include "aes_functions.svh"

  logic [255:0] schedule;
  integer pair_index;
  always_comb begin
    round_keys_flat = 1920'h0;
    round_keys_flat[1919 -: 128] = key_in[255:128];
    round_keys_flat[1791 -: 128] = key_in[127:0];
    schedule = key_in;
    for (pair_index = 1; pair_index <= 7; pair_index = pair_index + 1) begin
      schedule = aes_next_key_pair(schedule, pair_index[3:0]);
      round_keys_flat[1919 - (2*pair_index)*128 -: 128] = schedule[255:128];
      if (pair_index < 7)
        round_keys_flat[1919 - (2*pair_index + 1)*128 -: 128] = schedule[127:0];
    end
  end
endmodule
