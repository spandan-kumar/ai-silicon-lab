// RV32I five-stage pipelined core, written from the same specification.
//
// Round two of the spec-to-RTL experiment. The instruction set is identical to
// the multi-cycle core, so the reference model, stimulus, and comparison are
// unchanged; only the microarchitecture is harder. That is the point. A
// workflow tuned on an easy design is only shown to be better when it is
// applied to a design whose bugs it has not already seen.
//
// Stages: IF, ID, EX, MEM, WB. Forwarding from EX/MEM and MEM/WB into EX.
// Load-use hazards stall one cycle. Branches and jumps resolve in EX and flush
// the two instructions behind them.
//
// Harvard memories, both single-cycle: instruction fetch is combinational and
// data access completes in the MEM stage. This keeps the memory system out of
// the way of the pipeline logic under test.

module rv32i_pipe #(
    parameter logic [31:0] RESET_PC = 32'h0000_0000
) (
    input  logic        clk,
    input  logic        rst_n,

    output logic [31:0] imem_addr,
    input  logic [31:0] imem_rdata,

    output logic        dmem_req,
    output logic        dmem_we,
    output logic [3:0]  dmem_be,
    output logic [31:0] dmem_addr,
    output logic [31:0] dmem_wdata,
    input  logic [31:0] dmem_rdata,

    output logic        retire_valid,
    output logic [31:0] retire_pc,
    output logic [31:0] retire_instruction,
    output logic        halted,
    output logic        trap,
    output logic [31:0] trap_cause,

    input  logic [4:0]  dbg_addr,
    output logic [31:0] dbg_data
);
  // --- architectural state ------------------------------------------------
  logic [31:0] regs_q [0:31];
  logic [31:0] pc_q;
  logic        halted_q, trap_q;
  logic [31:0] trap_cause_q;

  assign dbg_data = (dbg_addr == 5'd0) ? 32'd0 : regs_q[dbg_addr];
  assign halted = halted_q;
  assign trap = trap_q;
  assign trap_cause = trap_cause_q;

  // --- pipeline registers -------------------------------------------------
  logic        id_valid_q;
  logic [31:0] id_pc_q, id_instruction_q;

  logic        ex_valid_q;
  logic [31:0] ex_pc_q, ex_instruction_q, ex_a_q, ex_b_q;

  logic        mem_valid_q;
  logic [31:0] mem_pc_q, mem_instruction_q, mem_result_q, mem_store_q;

  logic        wb_valid_q;
  logic [31:0] wb_pc_q, wb_instruction_q, wb_result_q;

  logic        retire_valid_q;
  logic [31:0] retire_pc_q, retire_instruction_q;
  assign retire_valid = retire_valid_q;
  assign retire_pc = retire_pc_q;
  assign retire_instruction = retire_instruction_q;

  // --- decode helpers, applied per stage ----------------------------------
  function automatic logic [6:0] f_opcode(input logic [31:0] w);
    f_opcode = w[6:0];
  endfunction
  function automatic logic [4:0] f_rd(input logic [31:0] w);
    f_rd = w[11:7];
  endfunction
  function automatic logic [2:0] f_funct3(input logic [31:0] w);
    f_funct3 = w[14:12];
  endfunction
  function automatic logic [4:0] f_rs1(input logic [31:0] w);
    f_rs1 = w[19:15];
  endfunction
  function automatic logic [4:0] f_rs2(input logic [31:0] w);
    f_rs2 = w[24:20];
  endfunction
  function automatic logic f_writes_reg(input logic [31:0] w);
    unique case (w[6:0])
      7'b0110111, 7'b0010111, 7'b1101111, 7'b1100111,
      7'b0000011, 7'b0010011, 7'b0110011: f_writes_reg = 1'b1;
      default: f_writes_reg = 1'b0;
    endcase
  endfunction
  function automatic logic f_is_load(input logic [31:0] w);
    f_is_load = (w[6:0] == 7'b0000011);
  endfunction
  function automatic logic f_is_store(input logic [31:0] w);
    f_is_store = (w[6:0] == 7'b0100011);
  endfunction

  function automatic logic [31:0] f_imm_i(input logic [31:0] w);
    f_imm_i = {{20{w[31]}}, w[31:20]};
  endfunction
  function automatic logic [31:0] f_imm_s(input logic [31:0] w);
    f_imm_s = {{20{w[31]}}, w[31:25], w[11:7]};
  endfunction
  function automatic logic [31:0] f_imm_b(input logic [31:0] w);
    f_imm_b = {{19{w[31]}}, w[31], w[7], w[30:25], w[11:8], 1'b0};
  endfunction
  function automatic logic [31:0] f_imm_u(input logic [31:0] w);
    f_imm_u = {w[31:12], 12'd0};
  endfunction
  function automatic logic [31:0] f_imm_j(input logic [31:0] w);
    f_imm_j = {{11{w[31]}}, w[31], w[19:12], w[20], w[30:21], 1'b0};
  endfunction

  // --- writeback (computed first; ID reads the forwarded value) -----------
  logic        wb_writes;
  logic [4:0]  wb_rd;
  assign wb_writes = wb_valid_q && f_writes_reg(wb_instruction_q)
                     && (f_rd(wb_instruction_q) != 5'd0);
  assign wb_rd = f_rd(wb_instruction_q);

  // --- instruction fetch --------------------------------------------------
  logic stall, flush;
  assign imem_addr = pc_q;

  // --- decode -------------------------------------------------------------
  logic [4:0] id_rs1, id_rs2;
  assign id_rs1 = f_rs1(id_instruction_q);
  assign id_rs2 = f_rs2(id_instruction_q);

  // Register read with writeback bypass: an instruction in WB writes the file
  // this cycle, so ID must see the new value rather than the stale one.
  logic [31:0] id_a, id_b;
  always_comb begin
    id_a = (id_rs1 == 5'd0) ? 32'd0 : regs_q[id_rs1];
    if (wb_writes && (wb_rd == id_rs1) && (id_rs1 != 5'd0)) id_a = wb_result_q;
    id_b = (id_rs2 == 5'd0) ? 32'd0 : regs_q[id_rs2];
    if (wb_writes && (wb_rd == id_rs2) && (id_rs2 != 5'd0)) id_b = wb_result_q;
  end

  // Load-use hazard: the value is not available until the load reaches WB, so
  // the dependent instruction waits one cycle in ID.
  logic load_use_hazard;
  assign load_use_hazard = ex_valid_q && f_is_load(ex_instruction_q)
                           && (f_rd(ex_instruction_q) != 5'd0)
                           && id_valid_q
                           && (((f_rd(ex_instruction_q) == id_rs1) && (id_rs1 != 5'd0))
                               || ((f_rd(ex_instruction_q) == id_rs2) && (id_rs2 != 5'd0)));

  // --- execute ------------------------------------------------------------
  logic [4:0] ex_rs1, ex_rs2;
  assign ex_rs1 = f_rs1(ex_instruction_q);
  assign ex_rs2 = f_rs2(ex_instruction_q);

  logic        mem_writes;
  logic [4:0]  mem_rd;
  assign mem_writes = mem_valid_q && f_writes_reg(mem_instruction_q)
                      && (f_rd(mem_instruction_q) != 5'd0);
  assign mem_rd = f_rd(mem_instruction_q);

  // Forwarding. MEM is checked before WB so the most recent producer wins.
  logic [31:0] ex_a, ex_b;
  always_comb begin
    ex_a = ex_a_q;
    if (mem_writes && (mem_rd == ex_rs1) && (ex_rs1 != 5'd0)) ex_a = mem_result_q;
    else if (wb_writes && (wb_rd == ex_rs1) && (ex_rs1 != 5'd0)) ex_a = wb_result_q;

    ex_b = ex_b_q;
    if (mem_writes && (mem_rd == ex_rs2) && (ex_rs2 != 5'd0)) ex_b = mem_result_q;
    else if (wb_writes && (wb_rd == ex_rs2) && (ex_rs2 != 5'd0)) ex_b = wb_result_q;
  end

  logic signed [31:0] ex_a_signed, ex_b_signed;
  assign ex_a_signed = ex_a;
  assign ex_b_signed = ex_b;
  logic signed [31:0] ex_imm_i_signed;
  assign ex_imm_i_signed = f_imm_i(ex_instruction_q);

  logic [4:0] ex_shamt_r, ex_shamt_i;
  assign ex_shamt_r = ex_b[4:0];
  assign ex_shamt_i = ex_instruction_q[24:20];

  logic [31:0] ex_sra_r, ex_sra_i;
  assign ex_sra_r = ex_a_signed >>> ex_shamt_r;
  assign ex_sra_i = ex_a_signed >>> ex_shamt_i;

  logic [2:0] ex_funct3;
  logic       ex_funct7_5;
  assign ex_funct3 = f_funct3(ex_instruction_q);
  assign ex_funct7_5 = ex_instruction_q[30];

  logic [31:0] ex_alu;
  always_comb begin
    unique case (f_opcode(ex_instruction_q))
      7'b0110111: ex_alu = f_imm_u(ex_instruction_q);
      7'b0010111: ex_alu = ex_pc_q + f_imm_u(ex_instruction_q);
      7'b1101111, 7'b1100111: ex_alu = ex_pc_q + 32'd4;
      7'b0000011: ex_alu = ex_a + f_imm_i(ex_instruction_q);
      7'b0100011: ex_alu = ex_a + f_imm_s(ex_instruction_q);
      7'b0010011: begin
        unique case (ex_funct3)
          3'b000: ex_alu = ex_a + ex_imm_i_signed;
          3'b001: ex_alu = ex_a << ex_shamt_i;
          3'b010: ex_alu = {31'd0, (ex_a_signed < ex_imm_i_signed)};
          3'b011: ex_alu = {31'd0, (ex_a < f_imm_i(ex_instruction_q))};
          3'b100: ex_alu = ex_a ^ f_imm_i(ex_instruction_q);
          3'b101: ex_alu = ex_funct7_5 ? ex_sra_i : (ex_a >> ex_shamt_i);
          3'b110: ex_alu = ex_a | f_imm_i(ex_instruction_q);
          3'b111: ex_alu = ex_a & f_imm_i(ex_instruction_q);
        endcase
      end
      7'b0110011: begin
        unique case (ex_funct3)
          3'b000: ex_alu = ex_funct7_5 ? (ex_a - ex_b) : (ex_a + ex_b);
          3'b001: ex_alu = ex_a << ex_shamt_r;
          3'b010: ex_alu = {31'd0, (ex_a_signed < ex_b_signed)};
          3'b011: ex_alu = {31'd0, (ex_a < ex_b)};
          3'b100: ex_alu = ex_a ^ ex_b;
          3'b101: ex_alu = ex_funct7_5 ? ex_sra_r : (ex_a >> ex_shamt_r);
          3'b110: ex_alu = ex_a | ex_b;
          3'b111: ex_alu = ex_a & ex_b;
        endcase
      end
      default: ex_alu = 32'd0;
    endcase
  end

  logic ex_branch_taken;
  always_comb begin
    unique case (ex_funct3)
      3'b000: ex_branch_taken = (ex_a == ex_b);
      3'b001: ex_branch_taken = (ex_a != ex_b);
      3'b100: ex_branch_taken = (ex_a_signed < ex_b_signed);
      3'b101: ex_branch_taken = (ex_a_signed >= ex_b_signed);
      3'b110: ex_branch_taken = (ex_a < ex_b);
      3'b111: ex_branch_taken = (ex_a >= ex_b);
      default: ex_branch_taken = 1'b0;
    endcase
  end

  logic        ex_redirect;
  logic [31:0] ex_target;
  always_comb begin
    ex_redirect = 1'b0;
    ex_target = 32'd0;
    if (ex_valid_q) begin
      unique case (f_opcode(ex_instruction_q))
        7'b1101111: begin
          ex_redirect = 1'b1;
          ex_target = ex_pc_q + f_imm_j(ex_instruction_q);
        end
        7'b1100111: begin
          ex_redirect = 1'b1;
          ex_target = (ex_a + f_imm_i(ex_instruction_q)) & ~32'd1;
        end
        7'b1100011: begin
          ex_redirect = ex_branch_taken;
          ex_target = ex_pc_q + f_imm_b(ex_instruction_q);
        end
        default: ;
      endcase
    end
  end

  logic ex_is_system;
  assign ex_is_system = ex_valid_q && (f_opcode(ex_instruction_q) == 7'b1110011);

  // --- memory stage -------------------------------------------------------
  logic [1:0] mem_offset;
  logic [2:0] mem_funct3;
  assign mem_offset = mem_result_q[1:0];
  assign mem_funct3 = f_funct3(mem_instruction_q);

  logic [3:0]  mem_store_be;
  logic [31:0] mem_store_data;
  always_comb begin
    unique case (mem_funct3)
      3'b000: begin
        mem_store_be = 4'b0001 << mem_offset;
        mem_store_data = mem_store_q << (8 * mem_offset);
      end
      3'b001: begin
        mem_store_be = mem_offset[1] ? 4'b1100 : 4'b0011;
        mem_store_data = mem_store_q << (8 * mem_offset);
      end
      default: begin
        mem_store_be = 4'b1111;
        mem_store_data = mem_store_q;
      end
    endcase
  end

  assign dmem_req = mem_valid_q && (f_is_load(mem_instruction_q) || f_is_store(mem_instruction_q));
  assign dmem_we = mem_valid_q && f_is_store(mem_instruction_q);
  assign dmem_be = mem_store_be;
  assign dmem_addr = {mem_result_q[31:2], 2'b00};
  assign dmem_wdata = mem_store_data;

  logic [7:0]  mem_load_byte;
  logic [15:0] mem_load_half;
  assign mem_load_byte = dmem_rdata[8*mem_offset +: 8];
  assign mem_load_half = mem_offset[1] ? dmem_rdata[31:16] : dmem_rdata[15:0];

  logic [31:0] mem_load_result;
  always_comb begin
    unique case (mem_funct3)
      3'b000:  mem_load_result = {{24{mem_load_byte[7]}}, mem_load_byte};
      3'b001:  mem_load_result = {{16{mem_load_half[15]}}, mem_load_half};
      3'b010:  mem_load_result = dmem_rdata;
      3'b100:  mem_load_result = {24'd0, mem_load_byte};
      3'b101:  mem_load_result = {16'd0, mem_load_half};
      default: mem_load_result = dmem_rdata;
    endcase
  end

  logic [31:0] mem_writeback_value;
  assign mem_writeback_value = f_is_load(mem_instruction_q) ? mem_load_result : mem_result_q;

  // --- control ------------------------------------------------------------
  assign stall = load_use_hazard;
  assign flush = ex_redirect;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      pc_q <= RESET_PC;
      id_valid_q <= 1'b0; id_pc_q <= 32'd0; id_instruction_q <= 32'd0;
      ex_valid_q <= 1'b0; ex_pc_q <= 32'd0; ex_instruction_q <= 32'd0;
      ex_a_q <= 32'd0; ex_b_q <= 32'd0;
      mem_valid_q <= 1'b0; mem_pc_q <= 32'd0; mem_instruction_q <= 32'd0;
      mem_result_q <= 32'd0; mem_store_q <= 32'd0;
      wb_valid_q <= 1'b0; wb_pc_q <= 32'd0; wb_instruction_q <= 32'd0; wb_result_q <= 32'd0;
      retire_valid_q <= 1'b0; retire_pc_q <= 32'd0; retire_instruction_q <= 32'd0;
      halted_q <= 1'b0; trap_q <= 1'b0; trap_cause_q <= 32'd0;
      for (int i = 0; i < 32; i++) regs_q[i] <= 32'd0;
    end else begin
      // Writeback commits before anything else this cycle.
      if (wb_writes) regs_q[wb_rd] <= wb_result_q;
      retire_valid_q <= wb_valid_q;
      retire_pc_q <= wb_pc_q;
      retire_instruction_q <= wb_instruction_q;

      if (!halted_q) begin
        // MEM -> WB
        wb_valid_q <= mem_valid_q;
        wb_pc_q <= mem_pc_q;
        wb_instruction_q <= mem_instruction_q;
        wb_result_q <= mem_writeback_value;

        // EX -> MEM
        mem_valid_q <= ex_valid_q && !ex_is_system;
        mem_pc_q <= ex_pc_q;
        mem_instruction_q <= ex_instruction_q;
        mem_result_q <= ex_alu;
        mem_store_q <= ex_b;

        // ID -> EX
        if (stall) begin
          ex_valid_q <= 1'b0;               // bubble
          ex_instruction_q <= 32'd0;
        end else begin
          ex_valid_q <= id_valid_q && !flush;
          ex_pc_q <= id_pc_q;
          ex_instruction_q <= id_instruction_q;
          ex_a_q <= id_a;
          ex_b_q <= id_b;
        end

        // IF -> ID
        if (flush) begin
          id_valid_q <= 1'b0;
          id_instruction_q <= 32'd0;
          pc_q <= ex_target;
        end else if (!stall) begin
          id_valid_q <= 1'b1;
          id_pc_q <= pc_q;
          id_instruction_q <= imem_rdata;
          pc_q <= pc_q + 32'd4;
        end

        // A system instruction stops the machine once everything ahead of it
        // has retired. Stopping at EX would discard in-flight instructions.
        if (ex_is_system) begin
          trap_q <= 1'b1;
          trap_cause_q <= ex_instruction_q[20] ? 32'd3 : 32'd11;
          halted_q <= 1'b1;
        end
      end else begin
        // Drain what is already past EX so their writebacks still land.
        wb_valid_q <= mem_valid_q;
        wb_pc_q <= mem_pc_q;
        wb_instruction_q <= mem_instruction_q;
        wb_result_q <= mem_writeback_value;
        mem_valid_q <= 1'b0;
      end
    end
  end

`ifdef AISL_ASSERTIONS
  // Equivalence obligation.
  //
  // Mutation testing removed `mem_valid_q` from the MEM forwarding condition
  // and no test could tell the difference. The raw condition -- an invalid MEM
  // entry that names a destination register -- does occur, 5787 times over 420
  // programs, on every flush and during the post-halt drain. What never occurs
  // is that condition together with a valid EX instruction reading that
  // register: zero occurrences over 820 programs. The reason is structural,
  // since a flush places the squashed instruction in MEM in the same cycle that
  // EX holds a bubble.
  //
  // That makes the mutant equivalent rather than a gap in the stimulus. This
  // assertion turns the judgement into a property that is re-checked on every
  // run, so it fails loudly if a later microarchitectural change makes the
  // conjunction reachable and the forwarding guard load-bearing again.
  always_ff @(posedge clk) begin
    if (rst_n) begin
      assert (!(!mem_valid_q && f_writes_reg(mem_instruction_q)
                && (f_rd(mem_instruction_q) != 5'd0) && ex_valid_q
                && ((f_rd(mem_instruction_q) == ex_rs1)
                    || (f_rd(mem_instruction_q) == ex_rs2))))
        else $error("an invalid MEM entry was visible to a valid EX instruction");
    end
  end
`endif

endmodule
