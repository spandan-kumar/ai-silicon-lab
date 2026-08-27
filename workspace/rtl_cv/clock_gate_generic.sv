// Generic synthesizable fallback. ASIC/FPGA integration should replace this
// with the target technology's glitch-free clock-gating primitive.
module cv32e40p_clock_gate (
    input  logic clk_i,
    input  logic en_i,
    input  logic scan_cg_en_i,
    output logic clk_o
);
  // Keeping the clock running is functionally safe and deterministic; it only
  // forgoes CV32E40P's optional idle power saving.
  assign clk_o = clk_i;
endmodule
