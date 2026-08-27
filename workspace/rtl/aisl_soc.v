// AI Silicon Lab RV32IM SoC
//
// The core is the pinned upstream PicoRV32 source included below.  Defining
// RISCV_FORMAL enables its synthesizable RVFI retirement interface; FORMAL is
// deliberately not defined, so no formal-only assertions are instantiated.
`define RISCV_FORMAL
`include "vendor/picorv32/picorv32.v"

module aisl_soc (
	input wire clk,
	input wire resetn,

	// External 64 MiB byte-addressed memory window: 0x00000000-0x03ffffff.
	output wire        mem_valid,
	output wire        mem_instr,
	input  wire        mem_ready,
	output wire [31:0] mem_addr,
	output wire [31:0] mem_wdata,
	output wire [ 3:0] mem_wstrb,
	input  wire [31:0] mem_rdata,

	// Run configuration, exposed to firmware through read-only MMIO.
	input wire [31:0] cfg_frame_count,
	input wire [31:0] cfg_frame_warmup,
	input wire [31:0] cfg_input_count,
	input wire [31:0] cfg_wad_size,
	input wire [31:0] cfg_skill,
	input wire [31:0] cfg_episode,
	input wire [31:0] cfg_map,

	// Observable MMIO side effects and latched run state.
	output reg        uart_tx_valid,
	output reg [ 7:0] uart_tx_data,
	output reg        event_valid,
	output reg [31:0] event_code,
	output reg        frame_capture_valid,
	output reg        status_booted,
	output reg        status_doom_started,
	output reg        status_finished,
	output reg        status_failed,
	output reg [31:0] frame_address,
	output reg [31:0] frame_index,
	output reg [31:0] stat_simulation_frames,
	output reg [31:0] stat_game_tics,
	output reg [31:0] stat_captured_frames,
	output reg [31:0] stat_exit_code,

	output wire        trap,

	// PicoRV32 native execution trace.
	output wire        trace_valid,
	output wire [35:0] trace_data,

	// RVFI retirement trace used by the deterministic simulator hash.
	output wire        rvfi_valid,
	output wire [63:0] rvfi_order,
	output wire [31:0] rvfi_insn,
	output wire        rvfi_trap,
	output wire        rvfi_halt,
	output wire        rvfi_intr,
	output wire [ 1:0] rvfi_mode,
	output wire [ 1:0] rvfi_ixl,
	output wire [ 4:0] rvfi_rs1_addr,
	output wire [ 4:0] rvfi_rs2_addr,
	output wire [31:0] rvfi_rs1_rdata,
	output wire [31:0] rvfi_rs2_rdata,
	output wire [ 4:0] rvfi_rd_addr,
	output wire [31:0] rvfi_rd_wdata,
	output wire [31:0] rvfi_pc_rdata,
	output wire [31:0] rvfi_pc_wdata,
	output wire [31:0] rvfi_mem_addr,
	output wire [ 3:0] rvfi_mem_rmask,
	output wire [ 3:0] rvfi_mem_wmask,
	output wire [31:0] rvfi_mem_rdata,
	output wire [31:0] rvfi_mem_wdata
);
	localparam [31:0] MMIO_BASE = 32'h1000_0000;

	wire        cpu_mem_valid;
	wire        cpu_mem_instr;
	wire        cpu_mem_ready;
	wire [31:0] cpu_mem_addr;
	wire [31:0] cpu_mem_wdata;
	wire [ 3:0] cpu_mem_wstrb;
	wire [31:0] cpu_mem_rdata;

	wire external_memory_select = cpu_mem_addr[31:26] == 6'b000000;
	wire mmio_select = cpu_mem_addr[31:8] == MMIO_BASE[31:8];
	wire mmio_transfer = cpu_mem_valid && cpu_mem_ready && mmio_select;
	wire mmio_write = mmio_transfer && |cpu_mem_wstrb;

	reg [31:0] mmio_rdata;

	assign mem_valid = cpu_mem_valid && external_memory_select;
	assign mem_instr = cpu_mem_instr;
	assign mem_addr = cpu_mem_addr;
	assign mem_wdata = cpu_mem_wdata;
	assign mem_wstrb = cpu_mem_wstrb;

	assign cpu_mem_ready = external_memory_select ? mem_ready :
		mmio_select ? cpu_mem_valid : 1'b0;
	assign cpu_mem_rdata = external_memory_select ? mem_rdata : mmio_rdata;

	always @* begin
		mmio_rdata = 32'b0;
		case (cpu_mem_addr[7:0])
			8'h08: mmio_rdata = frame_address;
			8'h0c: mmio_rdata = frame_index;
			8'h10: mmio_rdata = cfg_frame_count;
			8'h14: mmio_rdata = cfg_frame_warmup;
			8'h18: mmio_rdata = cfg_input_count;
			8'h1c: mmio_rdata = cfg_wad_size;
			8'h20: mmio_rdata = cfg_skill;
			8'h24: mmio_rdata = cfg_episode;
			8'h28: mmio_rdata = cfg_map;
			default: mmio_rdata = 32'b0;
		endcase
	end

	function [31:0] merge_write;
		input [31:0] old_value;
		input [31:0] new_value;
		input [ 3:0] write_strobe;
		begin
			merge_write = old_value;
			if (write_strobe[0]) merge_write[ 7: 0] = new_value[ 7: 0];
			if (write_strobe[1]) merge_write[15: 8] = new_value[15: 8];
			if (write_strobe[2]) merge_write[23:16] = new_value[23:16];
			if (write_strobe[3]) merge_write[31:24] = new_value[31:24];
		end
	endfunction

	always @(posedge clk) begin
		if (!resetn) begin
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
			uart_tx_valid <= 1'b0;
			event_valid <= 1'b0;
			frame_capture_valid <= 1'b0;

			if (mmio_write) begin
				case (cpu_mem_addr[7:0])
					8'h00: begin
						uart_tx_valid <= 1'b1;
						uart_tx_data <= cpu_mem_wdata[7:0];
					end
					8'h04: begin
						event_valid <= 1'b1;
						event_code <= cpu_mem_wdata;
						case (cpu_mem_wdata)
							32'h0000_0001: status_booted <= 1'b1;
							32'h0000_0002: status_doom_started <= 1'b1;
							32'h0000_0003: frame_capture_valid <= 1'b1;
							32'h0000_0004: status_finished <= 1'b1;
							32'h0000_dead: status_failed <= 1'b1;
							default: begin end
						endcase
					end
					8'h08: frame_address <= merge_write(frame_address, cpu_mem_wdata, cpu_mem_wstrb);
					8'h0c: frame_index <= merge_write(frame_index, cpu_mem_wdata, cpu_mem_wstrb);
					8'h30: stat_simulation_frames <= merge_write(stat_simulation_frames, cpu_mem_wdata, cpu_mem_wstrb);
					8'h34: stat_game_tics <= merge_write(stat_game_tics, cpu_mem_wdata, cpu_mem_wstrb);
					8'h38: stat_captured_frames <= merge_write(stat_captured_frames, cpu_mem_wdata, cpu_mem_wstrb);
					8'h3c: stat_exit_code <= merge_write(stat_exit_code, cpu_mem_wdata, cpu_mem_wstrb);
					default: begin end
				endcase
			end
		end
	end

	wire [31:0] unused_eoi;
	wire [63:0] unused_rvfi_csr_mcycle_rmask;
	wire [63:0] unused_rvfi_csr_mcycle_wmask;
	wire [63:0] unused_rvfi_csr_mcycle_rdata;
	wire [63:0] unused_rvfi_csr_mcycle_wdata;
	wire [63:0] unused_rvfi_csr_minstret_rmask;
	wire [63:0] unused_rvfi_csr_minstret_wmask;
	wire [63:0] unused_rvfi_csr_minstret_rdata;
	wire [63:0] unused_rvfi_csr_minstret_wdata;

	picorv32 #(
		.ENABLE_COUNTERS(1),
		.ENABLE_COUNTERS64(1),
		.ENABLE_REGS_16_31(1),
		.ENABLE_REGS_DUALPORT(1),
		.LATCHED_MEM_RDATA(0),
		.TWO_STAGE_SHIFT(0),
		.BARREL_SHIFTER(1),
		.COMPRESSED_ISA(0),
		.CATCH_MISALIGN(1),
		.CATCH_ILLINSN(1),
		.ENABLE_PCPI(0),
		.ENABLE_MUL(0),
		.ENABLE_FAST_MUL(1),
		.ENABLE_DIV(1),
		.ENABLE_IRQ(0),
		.ENABLE_TRACE(1),
		.REGS_INIT_ZERO(0),
		.PROGADDR_RESET(32'h0000_0000),
		.STACKADDR(32'h01ff_f000)
	) cpu (
		.clk(clk),
		.resetn(resetn),
		.trap(trap),

		.mem_valid(cpu_mem_valid),
		.mem_instr(cpu_mem_instr),
		.mem_ready(cpu_mem_ready),
		.mem_addr(cpu_mem_addr),
		.mem_wdata(cpu_mem_wdata),
		.mem_wstrb(cpu_mem_wstrb),
		.mem_rdata(cpu_mem_rdata),

		.mem_la_read(),
		.mem_la_write(),
		.mem_la_addr(),
		.mem_la_wdata(),
		.mem_la_wstrb(),

		.pcpi_valid(),
		.pcpi_insn(),
		.pcpi_rs1(),
		.pcpi_rs2(),
		.pcpi_wr(1'b0),
		.pcpi_rd(32'b0),
		.pcpi_wait(1'b0),
		.pcpi_ready(1'b0),

		.irq(32'b0),
		.eoi(unused_eoi),

		.rvfi_valid(rvfi_valid),
		.rvfi_order(rvfi_order),
		.rvfi_insn(rvfi_insn),
		.rvfi_trap(rvfi_trap),
		.rvfi_halt(rvfi_halt),
		.rvfi_intr(rvfi_intr),
		.rvfi_mode(rvfi_mode),
		.rvfi_ixl(rvfi_ixl),
		.rvfi_rs1_addr(rvfi_rs1_addr),
		.rvfi_rs2_addr(rvfi_rs2_addr),
		.rvfi_rs1_rdata(rvfi_rs1_rdata),
		.rvfi_rs2_rdata(rvfi_rs2_rdata),
		.rvfi_rd_addr(rvfi_rd_addr),
		.rvfi_rd_wdata(rvfi_rd_wdata),
		.rvfi_pc_rdata(rvfi_pc_rdata),
		.rvfi_pc_wdata(rvfi_pc_wdata),
		.rvfi_mem_addr(rvfi_mem_addr),
		.rvfi_mem_rmask(rvfi_mem_rmask),
		.rvfi_mem_wmask(rvfi_mem_wmask),
		.rvfi_mem_rdata(rvfi_mem_rdata),
		.rvfi_mem_wdata(rvfi_mem_wdata),
		.rvfi_csr_mcycle_rmask(unused_rvfi_csr_mcycle_rmask),
		.rvfi_csr_mcycle_wmask(unused_rvfi_csr_mcycle_wmask),
		.rvfi_csr_mcycle_rdata(unused_rvfi_csr_mcycle_rdata),
		.rvfi_csr_mcycle_wdata(unused_rvfi_csr_mcycle_wdata),
		.rvfi_csr_minstret_rmask(unused_rvfi_csr_minstret_rmask),
		.rvfi_csr_minstret_wmask(unused_rvfi_csr_minstret_wmask),
		.rvfi_csr_minstret_rdata(unused_rvfi_csr_minstret_rdata),
		.rvfi_csr_minstret_wdata(unused_rvfi_csr_minstret_wdata),

		.trace_valid(trace_valid),
		.trace_data(trace_data)
	);
endmodule
