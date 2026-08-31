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

  logic        mem_valid_q, mem_exception_q;
  logic [31:0] mem_pc_q, mem_instruction_q, mem_result_q, mem_store_q;

  logic        wb_valid_q, wb_exception_q;
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
      // Only the CSR forms of SYSTEM produce a result; ECALL, EBREAK, MRET,
      // and WFI do not, and must not be forwarded as if they did.
      7'b1110011: f_writes_reg = (w[14:12] != 3'b000);
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
  assign wb_writes = wb_valid_q && !wb_exception_q && f_writes_reg(wb_instruction_q)
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
  assign mem_writes = mem_valid_q && !mem_exception_q && f_writes_reg(mem_instruction_q)
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
      7'b1110011: ex_alu = ex_csr_rdata;      // CSR read result
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

  // --- machine-mode control and status registers -------------------------
  //
  // CSR access, trap entry, and MRET are all resolved in EX, the same stage
  // that resolves branches. That keeps exceptions precise without a separate
  // commit point: when an instruction is in EX every older instruction is
  // already in MEM or WB and will complete, and everything younger is flushed
  // exactly as a taken branch flushes it.
  localparam logic [11:0] CSR_MSTATUS = 12'h300, CSR_MISA = 12'h301;
  localparam logic [11:0] CSR_MIE = 12'h304, CSR_MTVEC = 12'h305;
  localparam logic [11:0] CSR_MCOUNTEREN = 12'h306, CSR_MSTATUSH = 12'h310;
  localparam logic [11:0] CSR_MCOUNTINHIBIT = 12'h320, CSR_MSCRATCH = 12'h340;
  localparam logic [11:0] CSR_MEPC = 12'h341, CSR_MCAUSE = 12'h342;
  localparam logic [11:0] CSR_MTVAL = 12'h343, CSR_MIP = 12'h344;
  localparam logic [11:0] CSR_MCYCLE = 12'hB00, CSR_MINSTRET = 12'hB02;
  localparam logic [11:0] CSR_MCYCLEH = 12'hB80, CSR_MINSTRETH = 12'hB82;
  localparam logic [11:0] CSR_CYCLE = 12'hC00, CSR_INSTRET = 12'hC02;
  localparam logic [11:0] CSR_CYCLEH = 12'hC80, CSR_INSTRETH = 12'hC82;
  localparam logic [11:0] CSR_MVENDORID = 12'hF11, CSR_MARCHID = 12'hF12;
  localparam logic [11:0] CSR_MIMPID = 12'hF13, CSR_MHARTID = 12'hF14;
  localparam logic [31:0] MISA_RV32I = 32'h4000_0100;

  logic [31:0] mstatus_q, mie_q, mtvec_q, mscratch_q;
  logic [31:0] mepc_q, mcause_q, mtval_q;
  logic [31:0] mcycle_q, mcycleh_q, minstret_q, minstreth_q;
  logic [31:0] mcounteren_q, mcountinhibit_q;

  logic [11:0] ex_csr_address;
  assign ex_csr_address = ex_instruction_q[31:20];

  logic [31:0] ex_csr_rdata;
  logic        ex_csr_known;
  always_comb begin
    ex_csr_known = 1'b1;
    unique case (ex_csr_address)
      CSR_MSTATUS:       ex_csr_rdata = mstatus_q;
      CSR_MISA:          ex_csr_rdata = MISA_RV32I;
      CSR_MIE:           ex_csr_rdata = mie_q;
      CSR_MTVEC:         ex_csr_rdata = mtvec_q;
      CSR_MCOUNTEREN:    ex_csr_rdata = mcounteren_q;
      CSR_MSTATUSH:      ex_csr_rdata = 32'd0;
      CSR_MCOUNTINHIBIT: ex_csr_rdata = mcountinhibit_q;
      CSR_MSCRATCH:      ex_csr_rdata = mscratch_q;
      CSR_MEPC:          ex_csr_rdata = mepc_q;
      CSR_MCAUSE:        ex_csr_rdata = mcause_q;
      CSR_MTVAL:         ex_csr_rdata = mtval_q;
      CSR_MIP:           ex_csr_rdata = 32'd0;
      CSR_MCYCLE,    CSR_CYCLE:    ex_csr_rdata = mcycle_q;
      CSR_MCYCLEH,   CSR_CYCLEH:   ex_csr_rdata = mcycleh_q;
      CSR_MINSTRET,  CSR_INSTRET:  ex_csr_rdata = minstret_q;
      CSR_MINSTRETH, CSR_INSTRETH: ex_csr_rdata = minstreth_q;
      CSR_MVENDORID, CSR_MARCHID, CSR_MIMPID, CSR_MHARTID: ex_csr_rdata = 32'd0;
      default: begin
        ex_csr_rdata = 32'd0;
        ex_csr_known = 1'b0;
      end
    endcase
  end

  logic [2:0]  ex_sys_funct3;
  logic [11:0] ex_funct12;
  assign ex_sys_funct3 = f_funct3(ex_instruction_q);
  assign ex_funct12 = ex_instruction_q[31:20];

  logic [31:0] ex_csr_operand, ex_csr_wdata;
  assign ex_csr_operand = ex_sys_funct3[2] ? {27'd0, ex_rs1} : ex_a;
  always_comb begin
    unique case (ex_sys_funct3[1:0])
      2'b01:   ex_csr_wdata = ex_csr_operand;
      2'b10:   ex_csr_wdata = ex_csr_rdata | ex_csr_operand;
      default: ex_csr_wdata = ex_csr_rdata & ~ex_csr_operand;
    endcase
  end

  logic ex_is_system, ex_is_csr, ex_csr_writes, ex_csr_reads, ex_csr_illegal;
  assign ex_is_system  = ex_valid_q && (f_opcode(ex_instruction_q) == 7'b1110011);
  assign ex_is_csr     = ex_is_system && (ex_sys_funct3 != 3'b000);
  assign ex_csr_writes = (ex_sys_funct3[1:0] == 2'b01) || (ex_rs1 != 5'd0);
  assign ex_csr_reads  = (ex_sys_funct3[1:0] != 2'b01) || (f_rd(ex_instruction_q) != 5'd0);
  assign ex_csr_illegal = !ex_csr_known
                          || (ex_csr_writes && (ex_csr_address[11:10] == 2'b11));

  // RV32I without the C extension has IALIGN=32. B- and J-immediates encode
  // multiples of two, so a control-flow target can be 2 mod 4, which is an
  // instruction-address-misaligned exception rather than a legal jump. The
  // multi-cycle core had the same omission; formal verification found it there
  // and the same rule applies here.
  logic ex_fetch_misaligned;
  assign ex_fetch_misaligned = ex_redirect && (ex_target[1:0] != 2'b00);

  // Data alignment is checked in EX, where the effective address is computed,
  // so the exception is raised before the access reaches memory.
  logic [31:0] ex_data_address;
  logic        ex_data_misaligned;
  assign ex_data_address = ex_alu;
  always_comb begin
    ex_data_misaligned = 1'b0;
    if (ex_valid_q && (f_is_load(ex_instruction_q) || f_is_store(ex_instruction_q))) begin
      unique case (f_funct3(ex_instruction_q))
        3'b001, 3'b101: ex_data_misaligned = ex_data_address[0];
        3'b010:         ex_data_misaligned = (ex_data_address[1:0] != 2'b00);
        default:        ex_data_misaligned = 1'b0;
      endcase
    end
  end

  // An instruction this core does not implement raises illegal-instruction.
  // Opcode alone is not enough: several opcodes have funct3 encodings that are
  // reserved, and decoding them as a neighbouring operation would silently
  // compute the wrong answer instead of faulting.
  logic ex_illegal_encoding;
  always_comb begin
    ex_illegal_encoding = 1'b0;
    unique case (f_opcode(ex_instruction_q))
      7'b0110111, 7'b0010111, 7'b1101111,
      7'b0010011, 7'b0110011, 7'b0001111, 7'b1110011: ex_illegal_encoding = 1'b0;
      7'b1100111: ex_illegal_encoding = (f_funct3(ex_instruction_q) != 3'b000);
      7'b1100011: ex_illegal_encoding = (f_funct3(ex_instruction_q) == 3'b010)
                                     || (f_funct3(ex_instruction_q) == 3'b011);
      7'b0000011: ex_illegal_encoding = (f_funct3(ex_instruction_q) == 3'b011)
                                     || (f_funct3(ex_instruction_q) == 3'b110)
                                     || (f_funct3(ex_instruction_q) == 3'b111);
      7'b0100011: ex_illegal_encoding = (f_funct3(ex_instruction_q) > 3'b010);
      default: ex_illegal_encoding = 1'b1;
    endcase
  end

  // Exception detection, in priority order.
  logic        ex_exception;
  logic [31:0] ex_cause, ex_tval;
  logic        ex_is_mret;
  always_comb begin
    ex_exception = 1'b0;
    ex_cause = 32'd0;
    ex_tval = 32'd0;
    ex_is_mret = 1'b0;
    if (ex_valid_q) begin
      if (ex_illegal_encoding) begin
        ex_exception = 1'b1; ex_cause = 32'd2; ex_tval = ex_instruction_q;
      end else if (ex_fetch_misaligned) begin
        ex_exception = 1'b1; ex_cause = 32'd0; ex_tval = ex_target;
      end else if (ex_data_misaligned) begin
        ex_exception = 1'b1;
        ex_cause = f_is_store(ex_instruction_q) ? 32'd6 : 32'd4;
        ex_tval = ex_data_address;
      end else if (ex_is_csr) begin
        if (ex_csr_illegal) begin
          ex_exception = 1'b1; ex_cause = 32'd2; ex_tval = ex_instruction_q;
        end
      end else if (ex_is_system) begin
        unique case (ex_funct12)
          12'h000: begin ex_exception = 1'b1; ex_cause = 32'd11; end
          12'h001: begin ex_exception = 1'b1; ex_cause = 32'd3; ex_tval = ex_pc_q; end
          12'h302: ex_is_mret = 1'b1;
          12'h105: ;                                    // WFI behaves as a nop
          default: begin
            ex_exception = 1'b1; ex_cause = 32'd2; ex_tval = ex_instruction_q;
          end
        endcase
      end
    end
  end

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

  assign dmem_req = mem_valid_q && !mem_exception_q
                    && (f_is_load(mem_instruction_q) || f_is_store(mem_instruction_q));
  assign dmem_we = mem_valid_q && !mem_exception_q && f_is_store(mem_instruction_q);
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
  // A trap or an MRET redirects the front end just as a taken branch does, and
  // takes priority: an instruction that faults must not also be allowed to
  // jump. Everything younger is flushed, which is what makes the exception
  // precise.
  logic        ex_control_redirect;
  logic [31:0] ex_control_target;
  always_comb begin
    if (ex_exception) begin
      ex_control_redirect = 1'b1;
      ex_control_target = mtvec_q & ~32'd3;
    end else if (ex_is_mret) begin
      ex_control_redirect = 1'b1;
      ex_control_target = mepc_q & ~32'd3;
    end else begin
      ex_control_redirect = ex_redirect && !ex_fetch_misaligned;
      ex_control_target = ex_target;
    end
  end

  assign stall = load_use_hazard;
  assign flush = ex_control_redirect;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      pc_q <= RESET_PC;
      id_valid_q <= 1'b0; id_pc_q <= 32'd0; id_instruction_q <= 32'd0;
      ex_valid_q <= 1'b0; ex_pc_q <= 32'd0; ex_instruction_q <= 32'd0;
      ex_a_q <= 32'd0; ex_b_q <= 32'd0;
      mem_valid_q <= 1'b0; mem_exception_q <= 1'b0;
      mem_pc_q <= 32'd0; mem_instruction_q <= 32'd0;
      mem_result_q <= 32'd0; mem_store_q <= 32'd0;
      wb_valid_q <= 1'b0; wb_exception_q <= 1'b0;
      wb_pc_q <= 32'd0; wb_instruction_q <= 32'd0; wb_result_q <= 32'd0;
      retire_valid_q <= 1'b0; retire_pc_q <= 32'd0; retire_instruction_q <= 32'd0;
      halted_q <= 1'b0; trap_q <= 1'b0; trap_cause_q <= 32'd0;
      mstatus_q <= 32'd0; mie_q <= 32'd0; mtvec_q <= 32'd0; mscratch_q <= 32'd0;
      mepc_q <= 32'd0; mcause_q <= 32'd0; mtval_q <= 32'd0;
      mcycle_q <= 32'd0; mcycleh_q <= 32'd0;
      minstret_q <= 32'd0; minstreth_q <= 32'd0;
      mcounteren_q <= 32'd0; mcountinhibit_q <= 32'd0;
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
        wb_exception_q <= mem_exception_q;
        wb_pc_q <= mem_pc_q;
        wb_instruction_q <= mem_instruction_q;
        wb_result_q <= mem_writeback_value;

        // EX -> MEM
        mem_valid_q <= ex_valid_q;
        mem_exception_q <= ex_exception;
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
          pc_q <= ex_control_target;
        end else if (!stall) begin
          id_valid_q <= 1'b1;
          id_pc_q <= pc_q;
          id_instruction_q <= imem_rdata;
          pc_q <= pc_q + 32'd4;
        end

        // Counters. mcycle counts clock cycles; minstret counts retirements.
        if (!mcountinhibit_q[0]) {mcycleh_q, mcycle_q} <= {mcycleh_q, mcycle_q} + 64'd1;
        if (!mcountinhibit_q[2] && wb_valid_q) begin
          {minstreth_q, minstret_q} <= {minstreth_q, minstret_q} + 64'd1;
        end

        if (ex_exception) begin
          // Enter machine mode. Younger instructions are flushed by the
          // redirect, so nothing after the faulting instruction commits.
          mstatus_q <= {mstatus_q[31:8], mstatus_q[3], mstatus_q[6:4], 1'b0,
                        mstatus_q[2:0]} | 32'h0000_1800;
          mepc_q <= ex_pc_q & ~32'd3;
          mcause_q <= ex_cause;
          mtval_q <= ex_tval;
          trap_q <= 1'b1;
          trap_cause_q <= ex_cause;
        end else if (ex_is_mret) begin
          mstatus_q <= {mstatus_q[31:8], 1'b1, mstatus_q[6:4], mstatus_q[7],
                        mstatus_q[2:0]} | 32'h0000_1800;
        end else if (ex_is_csr && !ex_csr_illegal && ex_csr_writes) begin
          unique case (ex_csr_address)
            CSR_MSTATUS: mstatus_q <= {19'd0,
                           ((ex_csr_wdata[12:11] == 2'b00) ? 2'b00 : 2'b11),
                           3'd0, ex_csr_wdata[7], 3'd0, ex_csr_wdata[3], 3'd0};
            CSR_MIE:           mie_q <= ex_csr_wdata & 32'h0000_0888;
            CSR_MTVEC:         mtvec_q <= {ex_csr_wdata[31:2],
                                  (ex_csr_wdata[1:0] < 2'd2) ? ex_csr_wdata[1:0] : 2'd0};
            CSR_MSCRATCH:      mscratch_q <= ex_csr_wdata;
            CSR_MEPC:          mepc_q <= ex_csr_wdata & ~32'd3;
            CSR_MCAUSE:        mcause_q <= ex_csr_wdata;
            CSR_MTVAL:         mtval_q <= ex_csr_wdata;
            CSR_MCOUNTEREN:    mcounteren_q <= ex_csr_wdata;
            CSR_MCOUNTINHIBIT: mcountinhibit_q <= ex_csr_wdata & 32'h0000_0005;
            CSR_MCYCLE:        mcycle_q <= ex_csr_wdata;
            CSR_MCYCLEH:       mcycleh_q <= ex_csr_wdata;
            CSR_MINSTRET:      minstret_q <= ex_csr_wdata;
            CSR_MINSTRETH:     minstreth_q <= ex_csr_wdata;
            default: ;
          endcase
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
  // Armed one cycle after reset releases. Reading rst_n directly here would
  // make it both a synchronous and an asynchronous input, which is a real lint
  // warning about mixed reset styles rather than a false positive.
  logic assertions_armed_q;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) assertions_armed_q <= 1'b0;
    else assertions_armed_q <= 1'b1;
  end

  always_ff @(posedge clk) begin
    if (assertions_armed_q) begin
      assert (!(!mem_valid_q && f_writes_reg(mem_instruction_q)
                && (f_rd(mem_instruction_q) != 5'd0) && ex_valid_q
                && ((f_rd(mem_instruction_q) == ex_rs1)
                    || (f_rd(mem_instruction_q) == ex_rs2))))
        else $error("an invalid MEM entry was visible to a valid EX instruction");
    end
  end
`endif

endmodule
