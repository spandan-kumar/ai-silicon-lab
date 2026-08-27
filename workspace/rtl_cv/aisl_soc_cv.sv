// AI Silicon Lab CV32E40P SoC draft.
//
// The processor is the exact pinned upstream CV32E40P RTL under vendor/.
// The only simulation-only logic is the diagnostic retirement projection,
// guarded out for synthesis. The processor, OBI memory plumbing, MMIO, and
// run-state registers are synthesizable.
module aisl_soc_cv (
    input  logic clk,
    input  logic resetn,

    // Independent OBI instruction port.
    output logic        instr_req,
    input  logic        instr_gnt,
    input  logic        instr_rvalid,
    output logic [31:0] instr_addr,
    input  logic [31:0] instr_rdata,

    // Independent OBI data port for the external 64 MiB memory window.
    output logic        data_req,
    input  logic        data_gnt,
    input  logic        data_rvalid,
    output logic        data_we,
    output logic [ 3:0] data_be,
    output logic [31:0] data_addr,
    output logic [31:0] data_wdata,
    input  logic [31:0] data_rdata,

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

    // Deterministic diagnostic trace. This is not claimed as formal RVFI.
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
  localparam logic [31:0] MMIO_BASE = 32'h1000_0000;

  logic cpu_data_req, cpu_data_gnt, cpu_data_rvalid, cpu_data_we;
  logic [3:0] cpu_data_be;
  logic [31:0] cpu_data_addr, cpu_data_wdata, cpu_data_rdata;
  logic mmio_rvalid_q;
  logic [31:0] mmio_rdata_q;
  logic irq_ack;
  logic [4:0] irq_id;

  wire external_data_select = cpu_data_addr[31:26] == 6'b000000;
  wire mmio_select = cpu_data_addr[31:8] == MMIO_BASE[31:8];
  wire mmio_grant = cpu_data_req && mmio_select;
  wire mmio_write = mmio_grant && cpu_data_we;

  assign data_req   = cpu_data_req && external_data_select;
  assign data_we    = cpu_data_we;
  assign data_be    = cpu_data_be;
  assign data_addr  = cpu_data_addr;
  assign data_wdata = cpu_data_wdata;
  assign cpu_data_gnt = external_data_select ? data_gnt :
                        mmio_select ? cpu_data_req : 1'b0;
  assign cpu_data_rvalid = data_rvalid | mmio_rvalid_q;
  assign cpu_data_rdata = mmio_rvalid_q ? mmio_rdata_q : data_rdata;

  function automatic logic [31:0] merge_write(
      input logic [31:0] old_value,
      input logic [31:0] new_value,
      input logic [ 3:0] write_strobe
  );
    merge_write = old_value;
    if (write_strobe[0]) merge_write[ 7: 0] = new_value[ 7: 0];
    if (write_strobe[1]) merge_write[15: 8] = new_value[15: 8];
    if (write_strobe[2]) merge_write[23:16] = new_value[23:16];
    if (write_strobe[3]) merge_write[31:24] = new_value[31:24];
  endfunction

  always_ff @(posedge clk or negedge resetn) begin
    if (!resetn) begin
      mmio_rvalid_q <= 1'b0;
      mmio_rdata_q <= 32'b0;
      uart_tx_valid <= 1'b0;
      uart_tx_data <= 8'b0;
      event_valid <= 1'b0;
      event_code <= 32'b0;
      frame_capture_valid <= 1'b0;
      status_booted <= 1'b0;
      status_doom_started <= 1'b0;
      status_finished <= 1'b0;
      status_failed <= 1'b0;
      frame_address <= 32'b0;
      frame_index <= 32'b0;
      stat_simulation_frames <= 32'b0;
      stat_game_tics <= 32'b0;
      stat_captured_frames <= 32'b0;
      stat_exit_code <= 32'b0;
    end else begin
      mmio_rvalid_q <= mmio_grant;
      uart_tx_valid <= 1'b0;
      event_valid <= 1'b0;
      frame_capture_valid <= 1'b0;

      if (mmio_grant) begin
        case (cpu_data_addr[7:0])
          8'h08: mmio_rdata_q <= frame_address;
          8'h0c: mmio_rdata_q <= frame_index;
          8'h10: mmio_rdata_q <= cfg_frame_count;
          8'h14: mmio_rdata_q <= cfg_frame_warmup;
          8'h18: mmio_rdata_q <= cfg_input_count;
          8'h1c: mmio_rdata_q <= cfg_wad_size;
          8'h20: mmio_rdata_q <= cfg_skill;
          8'h24: mmio_rdata_q <= cfg_episode;
          8'h28: mmio_rdata_q <= cfg_map;
          default: mmio_rdata_q <= 32'b0;
        endcase
      end

      if (mmio_write) begin
        case (cpu_data_addr[7:0])
          8'h00: begin
            uart_tx_valid <= 1'b1;
            uart_tx_data <= cpu_data_wdata[7:0];
          end
          8'h04: begin
            event_valid <= 1'b1;
            event_code <= cpu_data_wdata;
            case (cpu_data_wdata)
              32'h0000_0001: status_booted <= 1'b1;
              32'h0000_0002: status_doom_started <= 1'b1;
              32'h0000_0003: frame_capture_valid <= 1'b1;
              32'h0000_0004: status_finished <= 1'b1;
              32'h0000_dead: status_failed <= 1'b1;
              default: begin end
            endcase
          end
          8'h08: frame_address <= merge_write(frame_address, cpu_data_wdata, cpu_data_be);
          8'h0c: frame_index <= merge_write(frame_index, cpu_data_wdata, cpu_data_be);
          8'h30: stat_simulation_frames <= merge_write(stat_simulation_frames, cpu_data_wdata, cpu_data_be);
          8'h34: stat_game_tics <= merge_write(stat_game_tics, cpu_data_wdata, cpu_data_be);
          8'h38: stat_captured_frames <= merge_write(stat_captured_frames, cpu_data_wdata, cpu_data_be);
          8'h3c: stat_exit_code <= merge_write(stat_exit_code, cpu_data_wdata, cpu_data_be);
          default: begin end
        endcase
      end
    end
  end

  // CV32E40P's architectural minstret event is used for a compact,
  // deterministic diagnostic retirement stream in simulation. The upstream
  // source remains byte-for-byte unchanged.
`ifndef SYNTHESIS
  wire diagnostic_retire = cpu.core_i.mhpmevent_minstret;
  wire [31:0] diagnostic_pc = cpu.core_i.pc_id;
  wire [31:0] diagnostic_insn = cpu.core_i.id_stage_i.instr;
  wire diagnostic_compressed = cpu.core_i.id_stage_i.is_compressed_i;
  wire diagnostic_trap = cpu.core_i.id_valid && cpu.core_i.is_decoding &&
      (cpu.core_i.id_stage_i.illegal_insn_dec ||
       cpu.core_i.id_stage_i.ecall_insn_dec ||
       cpu.core_i.id_stage_i.ebrk_insn_dec);
`else
  wire diagnostic_retire = 1'b0;
  wire [31:0] diagnostic_pc = 32'b0;
  wire [31:0] diagnostic_insn = 32'b0;
  wire diagnostic_compressed = 1'b0;
  wire diagnostic_trap = 1'b0;
`endif

  always_ff @(posedge clk or negedge resetn) begin
    if (!resetn) rvfi_order <= 64'b0;
    else if (diagnostic_retire) rvfi_order <= rvfi_order + 1'b1;
  end

  always_comb begin
    trap = diagnostic_trap;
    trace_valid = diagnostic_retire;
    trace_data = {4'h2, diagnostic_pc};
    rvfi_valid = diagnostic_retire;
    rvfi_insn = diagnostic_insn;
    rvfi_trap = diagnostic_trap;
    rvfi_halt = 1'b0;
    rvfi_intr = 1'b0;
    rvfi_mode = 2'b11;
    rvfi_ixl = 2'b01;
    rvfi_rs1_addr = 5'b0;
    rvfi_rs2_addr = 5'b0;
    rvfi_rs1_rdata = 32'b0;
    rvfi_rs2_rdata = 32'b0;
    rvfi_rd_addr = 5'b0;
    rvfi_rd_wdata = 32'b0;
    rvfi_pc_rdata = diagnostic_pc;
    rvfi_pc_wdata = diagnostic_pc + (diagnostic_compressed ? 32'd2 : 32'd4);
    rvfi_mem_addr = 32'b0;
    rvfi_mem_rmask = 4'b0;
    rvfi_mem_wmask = 4'b0;
    rvfi_mem_rdata = 32'b0;
    rvfi_mem_wdata = 32'b0;
  end

  cv32e40p_top #(
      .COREV_PULP(0),
      .COREV_CLUSTER(0),
      .FPU(0),
      .ZFINX(0),
      .NUM_MHPMCOUNTERS(1)
  ) cpu (
      .clk_i(clk),
      .rst_ni(resetn),
      .pulp_clock_en_i(1'b1),
      .scan_cg_en_i(1'b0),
      .boot_addr_i(32'h0000_0000),
      .mtvec_addr_i(32'h0000_0000),
      .dm_halt_addr_i(32'h0000_0100),
      .hart_id_i(32'b0),
      .dm_exception_addr_i(32'h0000_0100),
      .instr_req_o(instr_req),
      .instr_gnt_i(instr_gnt),
      .instr_rvalid_i(instr_rvalid),
      .instr_addr_o(instr_addr),
      .instr_rdata_i(instr_rdata),
      .data_req_o(cpu_data_req),
      .data_gnt_i(cpu_data_gnt),
      .data_rvalid_i(cpu_data_rvalid),
      .data_we_o(cpu_data_we),
      .data_be_o(cpu_data_be),
      .data_addr_o(cpu_data_addr),
      .data_wdata_o(cpu_data_wdata),
      .data_rdata_i(cpu_data_rdata),
      .irq_i(32'b0),
      .irq_ack_o(irq_ack),
      .irq_id_o(irq_id),
      .debug_req_i(1'b0),
      .debug_havereset_o(),
      .debug_running_o(),
      .debug_halted_o(),
      .fetch_enable_i(1'b1),
      .core_sleep_o()
  );
endmodule
