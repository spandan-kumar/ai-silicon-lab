// riscv-formal wrapper for the AI Silicon Lab RV32I multi-cycle core.
//
// The memory response signals are left free. The solver may return any data,
// grant at any time, and respond at any time, so the proofs hold for every
// memory behaviour the interface permits rather than for the one memory model
// a testbench happens to implement. That is the difference between this and
// the simulation loop: no stimulus is chosen here.

module rvfi_wrapper (
    input         clock,
    input         reset,
    `RVFI_OUTPUTS
);
  (* keep *) `rvformal_rand_reg        mem_gnt;
  (* keep *) `rvformal_rand_reg        mem_rvalid;
  (* keep *) `rvformal_rand_reg [31:0] mem_rdata;

  (* keep *) wire        mem_req;
  (* keep *) wire        mem_we;
  (* keep *) wire [3:0]  mem_be;
  (* keep *) wire [31:0] mem_addr;
  (* keep *) wire [31:0] mem_wdata;

  rv32i_core uut (
      .clk       (clock),
      .rst_n     (!reset),

      .mem_req   (mem_req),
      .mem_we    (mem_we),
      .mem_be    (mem_be),
      .mem_addr  (mem_addr),
      .mem_wdata (mem_wdata),
      .mem_gnt   (mem_gnt),
      .mem_rvalid(mem_rvalid),
      .mem_rdata (mem_rdata),

      // Simulation-only observation ports, unused by the proofs.
      .retire_valid      (),
      .retire_pc         (),
      .retire_instruction(),
      .halted            (),
      .trap              (),
      .trap_cause        (),
      .dbg_addr          (5'd0),
      .dbg_data          (),

      `RVFI_CONN32
  );

`ifdef AISL_FAIRNESS
  // Liveness needs the environment to make progress. Without this the solver
  // can withhold every memory response forever, and "the core never retires an
  // instruction" is a legitimate behaviour of a core whose memory never
  // answers. The assumption constrains the environment, not the design.
  reg [3:0] gnt_wait = 0;
  reg [3:0] rvalid_wait = 0;

  always @(posedge clock) begin
    gnt_wait <= (mem_req && !mem_gnt) ? gnt_wait + 1 : 0;
    rvalid_wait <= !mem_rvalid ? rvalid_wait + 1 : 0;
    assume (gnt_wait < 4);
    assume (rvalid_wait < 4);
  end
`endif
endmodule
