// AI Silicon Lab CV32E40P SoC with a deterministic single external-memory
// port.  The CV32E40P and MMIO integration live in aisl_soc_cv; this wrapper
// arbitrates the core's independent OBI instruction/data ports onto the same
// neutral memory interface used by the cycle-accurate simulator.
module aisl_soc (
    input  logic clk,
    input  logic resetn,

    output logic        mem_valid,
    output logic        mem_instr,
    input  logic        mem_ready,
    output logic [31:0] mem_addr,
    output logic [31:0] mem_wdata,
    output logic [ 3:0] mem_wstrb,
    input  logic [31:0] mem_rdata,

    input logic [31:0] cfg_frame_count,
    input logic [31:0] cfg_frame_warmup,
    input logic [31:0] cfg_input_count,
    input logic [31:0] cfg_wad_size,
    input logic [31:0] cfg_skill,
    input logic [31:0] cfg_episode,
    input logic [31:0] cfg_map,

    output logic        uart_tx_valid,
    output logic [ 7:0] uart_tx_data,
    output logic        event_valid,
    output logic [31:0] event_code,
    output logic        frame_capture_valid,
    output logic        status_booted,
    output logic        status_doom_started,
    output logic        status_finished,
    output logic        status_failed,
    output logic [31:0] frame_address,
    output logic [31:0] frame_index,
    output logic [31:0] stat_simulation_frames,
    output logic [31:0] stat_game_tics,
    output logic [31:0] stat_captured_frames,
    output logic [31:0] stat_exit_code,

    output logic        trap,
    output logic        trace_valid,
    output logic [35:0] trace_data,
    output logic        rvfi_valid,
    output logic [63:0] rvfi_order,
    output logic [31:0] rvfi_insn,
    output logic        rvfi_trap,
    output logic        rvfi_halt,
    output logic        rvfi_intr,
    output logic [ 1:0] rvfi_mode,
    output logic [ 1:0] rvfi_ixl,
    output logic [ 4:0] rvfi_rs1_addr,
    output logic [ 4:0] rvfi_rs2_addr,
    output logic [31:0] rvfi_rs1_rdata,
    output logic [31:0] rvfi_rs2_rdata,
    output logic [ 4:0] rvfi_rd_addr,
    output logic [31:0] rvfi_rd_wdata,
    output logic [31:0] rvfi_pc_rdata,
    output logic [31:0] rvfi_pc_wdata,
    output logic [31:0] rvfi_mem_addr,
    output logic [ 3:0] rvfi_mem_rmask,
    output logic [ 3:0] rvfi_mem_wmask,
    output logic [31:0] rvfi_mem_rdata,
    output logic [31:0] rvfi_mem_wdata
);
  logic        instr_req;
  logic        instr_gnt;
  logic        instr_rvalid;
  logic [31:0] instr_addr;
  logic [31:0] instr_rdata;
  logic        data_req;
  logic        data_gnt;
  logic        data_rvalid;
  logic        data_we;
  logic [ 3:0] data_be;
  logic [31:0] data_addr;
  logic [31:0] data_wdata;
  logic [31:0] data_rdata;

  // Data has deterministic priority. A response is returned one cycle after
  // an accepted request, as required by CV32E40P's OBI interface.
  wire choose_data = data_req;
  wire choose_instr = !data_req && instr_req;

  assign mem_valid = choose_data || choose_instr;
  assign mem_instr = choose_instr;
  assign mem_addr = choose_data ? data_addr : instr_addr;
  assign mem_wdata = data_wdata;
  assign mem_wstrb = choose_data && data_we ? data_be : 4'b0000;
  assign data_gnt = choose_data && mem_ready;
  assign instr_gnt = choose_instr && mem_ready;

  always_ff @(posedge clk or negedge resetn) begin
    if (!resetn) begin
      data_rvalid <= 1'b0;
      instr_rvalid <= 1'b0;
      data_rdata <= 32'b0;
      instr_rdata <= 32'b0;
    end else begin
      data_rvalid <= data_gnt;
      instr_rvalid <= instr_gnt;
      if (data_gnt) data_rdata <= mem_rdata;
      if (instr_gnt) instr_rdata <= mem_rdata;
    end
  end

  aisl_soc_cv soc (
      .clk,
      .resetn,
      .instr_req,
      .instr_gnt,
      .instr_rvalid,
      .instr_addr,
      .instr_rdata,
      .data_req,
      .data_gnt,
      .data_rvalid,
      .data_we,
      .data_be,
      .data_addr,
      .data_wdata,
      .data_rdata,
      .cfg_frame_count,
      .cfg_frame_warmup,
      .cfg_input_count,
      .cfg_wad_size,
      .cfg_skill,
      .cfg_episode,
      .cfg_map,
      .uart_tx_valid,
      .uart_tx_data,
      .event_valid,
      .event_code,
      .frame_capture_valid,
      .status_booted,
      .status_doom_started,
      .status_finished,
      .status_failed,
      .frame_address,
      .frame_index,
      .stat_simulation_frames,
      .stat_game_tics,
      .stat_captured_frames,
      .stat_exit_code,
      .trap,
      .trace_valid,
      .trace_data,
      .rvfi_valid,
      .rvfi_order,
      .rvfi_insn,
      .rvfi_trap,
      .rvfi_halt,
      .rvfi_intr,
      .rvfi_mode,
      .rvfi_ixl,
      .rvfi_rs1_addr,
      .rvfi_rs2_addr,
      .rvfi_rs1_rdata,
      .rvfi_rs2_rdata,
      .rvfi_rd_addr,
      .rvfi_rd_wdata,
      .rvfi_pc_rdata,
      .rvfi_pc_wdata,
      .rvfi_mem_addr,
      .rvfi_mem_rmask,
      .rvfi_mem_wmask,
      .rvfi_mem_rdata,
      .rvfi_mem_wdata
  );
endmodule
