// RV32I multi-cycle core, written from the RISC-V Unprivileged ISA
// specification (RV32I Base Integer Instruction Set, version 2.1).
//
// This is round one of a spec-to-RTL experiment. The design is deliberately
// the simplest organisation that is still a real core: one instruction at a
// time, a unified memory port, and no pipeline. Pipelining is round two, so
// that the workflow is measured on an easy design before a hard one.
//
// Memory protocol: assert `mem_req` with address, write enable, and byte
// enables; hold until `mem_gnt`; then wait for `mem_rvalid`. One transaction
// is outstanding at a time.
//
// `dbg_addr`/`dbg_data` expose an architectural register read port for
// verification. It is a real read port and is synthesised; it is declared in
// the experiment profile rather than hidden.

module rv32i_core #(
    parameter logic [31:0] RESET_PC = 32'h0000_0000
) (
    input  logic        clk,
    input  logic        rst_n,

    output logic        mem_req,
    output logic        mem_we,
    output logic [3:0]  mem_be,
    output logic [31:0] mem_addr,
    output logic [31:0] mem_wdata,
    input  logic        mem_gnt,
    input  logic        mem_rvalid,
    input  logic [31:0] mem_rdata,

    // Retirement observation for differential comparison.
    output logic        retire_valid,
    output logic [31:0] retire_pc,
    output logic [31:0] retire_instruction,
    output logic        halted,
    output logic        trap,
    output logic [31:0] trap_cause,

    input  logic [4:0]  dbg_addr,
    output logic [31:0] dbg_data

`ifdef RISCV_FORMAL
    ,
    // RISC-V Formal Interface. Present only under `RISCV_FORMAL`, so the
    // synthesizable core is byte-identical without it. Every signal is a
    // report about an instruction that has just retired; none of them feed
    // back into the design.
    output logic        rvfi_valid,
    output logic [63:0] rvfi_order,
    output logic [31:0] rvfi_insn,
    output logic        rvfi_trap,
    output logic        rvfi_halt,
    output logic        rvfi_intr,
    output logic [1:0]  rvfi_mode,
    output logic [1:0]  rvfi_ixl,
    output logic [4:0]  rvfi_rs1_addr,
    output logic [4:0]  rvfi_rs2_addr,
    output logic [31:0] rvfi_rs1_rdata,
    output logic [31:0] rvfi_rs2_rdata,
    output logic [4:0]  rvfi_rd_addr,
    output logic [31:0] rvfi_rd_wdata,
    output logic [31:0] rvfi_pc_rdata,
    output logic [31:0] rvfi_pc_wdata,
    output logic [31:0] rvfi_mem_addr,
    output logic [3:0]  rvfi_mem_rmask,
    output logic [3:0]  rvfi_mem_wmask,
    output logic [31:0] rvfi_mem_rdata,
    output logic [31:0] rvfi_mem_wdata
`endif
);
  typedef enum logic [2:0] {
    S_FETCH_REQ, S_FETCH_WAIT, S_EXEC, S_MEM_REQ, S_MEM_WAIT, S_HALT
  } state_e;

  state_e state_q;

  logic [31:0] pc_q;
  logic [31:0] instruction_q;
  logic [31:0] regs_q [0:31];
  logic        halted_q, trap_q;
  logic [31:0] trap_cause_q;
  logic        retire_q;
  logic [31:0] retire_pc_q, retire_instruction_q;

  // Latched load state, used when the response arrives.
  logic [4:0]  load_rd_q;
  logic [2:0]  load_funct3_q;
  logic [1:0]  load_offset_q;
  logic [31:0] next_pc_q;

  // --- instruction fields ------------------------------------------------
  logic [6:0] opcode;
  logic [4:0] rd, rs1, rs2;
  logic [2:0] funct3;
  logic [6:0] funct7;
  assign opcode = instruction_q[6:0];
  assign rd     = instruction_q[11:7];
  assign funct3 = instruction_q[14:12];
  assign rs1    = instruction_q[19:15];
  assign rs2    = instruction_q[24:20];
  assign funct7 = instruction_q[31:25];

  // x0 reads as zero regardless of what the array holds.
  logic [31:0] a, b;
  assign a = (rs1 == 5'd0) ? 32'd0 : regs_q[rs1];
  assign b = (rs2 == 5'd0) ? 32'd0 : regs_q[rs2];
  assign dbg_data = (dbg_addr == 5'd0) ? 32'd0 : regs_q[dbg_addr];

  // --- immediates, one per format ----------------------------------------
  logic signed [31:0] imm_i, imm_s, imm_b, imm_u, imm_j;
  assign imm_i = {{20{instruction_q[31]}}, instruction_q[31:20]};
  assign imm_s = {{20{instruction_q[31]}}, instruction_q[31:25], instruction_q[11:7]};
  assign imm_b = {{19{instruction_q[31]}}, instruction_q[31], instruction_q[7],
                  instruction_q[30:25], instruction_q[11:8], 1'b0};
  assign imm_u = {instruction_q[31:12], 12'd0};
  assign imm_j = {{11{instruction_q[31]}}, instruction_q[31], instruction_q[19:12],
                  instruction_q[20], instruction_q[30:21], 1'b0};

  // --- arithmetic --------------------------------------------------------
  logic [4:0]  shamt_r, shamt_i;
  assign shamt_r = b[4:0];
  assign shamt_i = instruction_q[24:20];

  logic signed [31:0] a_signed, b_signed;
  assign a_signed = a;
  assign b_signed = b;

  // Arithmetic shifts are computed in their own continuous assignments rather
  // than inside the ALU ternaries. In Verilog a ternary with one unsigned
  // branch makes the whole expression unsigned, which silently reinterprets a
  // signed operand and turns >>> into a logical shift. Giving each arithmetic
  // shift its own self-contained context keeps the operand signed.
  logic [31:0] sra_by_reg, sra_by_imm;
  assign sra_by_reg = a_signed >>> shamt_r;
  assign sra_by_imm = a_signed >>> shamt_i;

  logic [31:0] alu_rr, alu_ri;
  always_comb begin
    unique case (funct3)
      3'b000: alu_rr = (funct7[5]) ? (a - b) : (a + b);
      3'b001: alu_rr = a << shamt_r;
      3'b010: alu_rr = {31'd0, (a_signed < b_signed)};
      3'b011: alu_rr = {31'd0, (a < b)};
      3'b100: alu_rr = a ^ b;
      3'b101: alu_rr = (funct7[5]) ? sra_by_reg : (a >> shamt_r);
      3'b110: alu_rr = a | b;
      3'b111: alu_rr = a & b;
    endcase
  end

  always_comb begin
    unique case (funct3)
      3'b000: alu_ri = a + imm_i;
      3'b001: alu_ri = a << shamt_i;
      3'b010: alu_ri = {31'd0, (a_signed < imm_i)};
      3'b011: alu_ri = {31'd0, (a < imm_i)};   // immediate sign-extended, compared unsigned
      3'b100: alu_ri = a ^ imm_i;
      3'b101: alu_ri = (funct7[5]) ? sra_by_imm : (a >> shamt_i);
      3'b110: alu_ri = a | imm_i;
      3'b111: alu_ri = a & imm_i;
    endcase
  end

  logic branch_taken;
  always_comb begin
    unique case (funct3)
      3'b000: branch_taken = (a == b);
      3'b001: branch_taken = (a != b);
      3'b100: branch_taken = (a_signed < b_signed);
      3'b101: branch_taken = (a_signed >= b_signed);
      3'b110: branch_taken = (a < b);
      3'b111: branch_taken = (a >= b);
      default: branch_taken = 1'b0;
    endcase
  end

  // --- memory address and lane handling ----------------------------------
  logic [31:0] mem_address;
  logic [1:0]  mem_offset;
  assign mem_address = (opcode == 7'b0100011) ? (a + imm_s) : (a + imm_i);
  assign mem_offset  = mem_address[1:0];

  logic [3:0]  store_be;
  logic [31:0] store_data;
  always_comb begin
    unique case (funct3)
      3'b000: begin
        store_be   = 4'b0001 << mem_offset;
        store_data = b << (8 * mem_offset);
      end
      3'b001: begin
        store_be   = mem_offset[1] ? 4'b1100 : 4'b0011;
        store_data = b << (8 * mem_offset);
      end
      default: begin
        store_be   = 4'b1111;
        store_data = b;
      end
    endcase
  end

  // Branch and jump targets. B- and J-immediates encode multiples of two, so a
  // target can be 2 mod 4. RV32I without the C extension has IALIGN=32, and
  // such a target is an instruction-address-misaligned exception rather than a
  // legal jump. Formal verification found this missing; no amount of random
  // testing did, because the generator only ever produced aligned targets.
  logic [31:0] jal_target, jalr_target, branch_target;
  assign jal_target    = pc_q + imm_j;
  assign jalr_target   = (a + imm_i) & ~32'd1;
  assign branch_target = pc_q + imm_b;

  logic fetch_misaligned;
  always_comb begin
    unique case (opcode)
      7'b1101111: fetch_misaligned = (jal_target[1:0] != 2'b00);
      7'b1100111: fetch_misaligned = (jalr_target[1:0] != 2'b00);
      7'b1100011: fetch_misaligned = branch_taken && (branch_target[1:0] != 2'b00);
      default:    fetch_misaligned = 1'b0;
    endcase
  end

  // --- machine-mode control and status registers -------------------------
  //
  // Only the subset this core actually implements exists here. Registers the
  // specification defines but this design does not provide are decoded as
  // illegal rather than silently reading zero, so a program that depends on
  // one fails loudly instead of quietly getting the wrong answer.
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

  localparam logic [31:0] MISA_RV32I = 32'h4000_0100;   // MXL=1, extension I
  localparam int MSTATUS_MIE_BIT = 3, MSTATUS_MPIE_BIT = 7;

  logic [31:0] mstatus_q, mie_q, mtvec_q, mscratch_q;
  logic [31:0] mepc_q, mcause_q, mtval_q;
  logic [31:0] mcycle_q, mcycleh_q, minstret_q, minstreth_q;
  logic [31:0] mcounteren_q, mcountinhibit_q;

  logic [11:0] csr_address;
  assign csr_address = instruction_q[31:20];

  // Read value, and whether the address is implemented at all.
  logic [31:0] csr_rdata;
  logic        csr_known;
  always_comb begin
    csr_known = 1'b1;
    unique case (csr_address)
      CSR_MSTATUS:       csr_rdata = mstatus_q;
      CSR_MISA:          csr_rdata = MISA_RV32I;
      CSR_MIE:           csr_rdata = mie_q;
      CSR_MTVEC:         csr_rdata = mtvec_q;
      CSR_MCOUNTEREN:    csr_rdata = mcounteren_q;
      CSR_MSTATUSH:      csr_rdata = 32'd0;
      CSR_MCOUNTINHIBIT: csr_rdata = mcountinhibit_q;
      CSR_MSCRATCH:      csr_rdata = mscratch_q;
      CSR_MEPC:          csr_rdata = mepc_q;
      CSR_MCAUSE:        csr_rdata = mcause_q;
      CSR_MTVAL:         csr_rdata = mtval_q;
      CSR_MIP:           csr_rdata = 32'd0;      // nothing raises an interrupt
      CSR_MCYCLE,   CSR_CYCLE:     csr_rdata = mcycle_q;
      CSR_MCYCLEH,  CSR_CYCLEH:    csr_rdata = mcycleh_q;
      CSR_MINSTRET, CSR_INSTRET:   csr_rdata = minstret_q;
      CSR_MINSTRETH, CSR_INSTRETH: csr_rdata = minstreth_q;
      CSR_MVENDORID, CSR_MARCHID, CSR_MIMPID, CSR_MHARTID: csr_rdata = 32'd0;
      default: begin
        csr_rdata = 32'd0;
        csr_known = 1'b0;
      end
    endcase
  end

  // Operand: a register for the plain forms, the rs1 field as a 5-bit unsigned
  // immediate for the immediate forms.
  logic [31:0] csr_operand;
  assign csr_operand = funct3[2] ? {27'd0, rs1} : a;

  logic [31:0] csr_wdata;
  always_comb begin
    unique case (funct3[1:0])
      2'b01:   csr_wdata = csr_operand;               // csrrw
      2'b10:   csr_wdata = csr_rdata | csr_operand;   // csrrs
      default: csr_wdata = csr_rdata & ~csr_operand;  // csrrc
    endcase
  end

  // A set or clear whose source is x0 or a zero immediate performs no write,
  // so a read-only register may be read through them.
  logic csr_writes, csr_reads, csr_read_only, csr_illegal;
  assign csr_writes    = (funct3[1:0] == 2'b01) || (rs1 != 5'd0);
  assign csr_reads     = (funct3[1:0] != 2'b01) || (rd != 5'd0);
  assign csr_read_only = (csr_address[11:10] == 2'b11);
  assign csr_illegal   = !csr_known || (csr_writes && csr_read_only);

  // Reserved funct3 encodings within an otherwise valid opcode. Decoding one as
  // a neighbouring operation would silently compute a wrong answer rather than
  // fault, and nothing in the random corpus generates them, so this is checked
  // explicitly rather than left to chance.
  logic illegal_encoding;
  always_comb begin
    unique case (opcode)
      7'b1100111: illegal_encoding = (funct3 != 3'b000);
      7'b1100011: illegal_encoding = (funct3 == 3'b010) || (funct3 == 3'b011);
      7'b0000011: illegal_encoding = (funct3 == 3'b011) || (funct3 == 3'b110)
                                  || (funct3 == 3'b111);
      7'b0100011: illegal_encoding = (funct3 > 3'b010);
      default:    illegal_encoding = 1'b0;
    endcase
  end

  logic misaligned;
  always_comb begin
    unique case (funct3)
      3'b001, 3'b101: misaligned = mem_offset[0];              // halfword
      3'b010:         misaligned = (mem_offset != 2'b00);      // word
      default:        misaligned = 1'b0;                       // byte
    endcase
  end

  logic [31:0] load_result;
  logic [7:0]  load_byte;
  logic [15:0] load_half;
  assign load_byte = mem_rdata[8*load_offset_q +: 8];
  assign load_half = load_offset_q[1] ? mem_rdata[31:16] : mem_rdata[15:0];
  always_comb begin
    unique case (load_funct3_q)
      3'b000:  load_result = {{24{load_byte[7]}}, load_byte};
      3'b001:  load_result = {{16{load_half[15]}}, load_half};
      3'b010:  load_result = mem_rdata;
      3'b100:  load_result = {24'd0, load_byte};
      3'b101:  load_result = {16'd0, load_half};
      default: load_result = mem_rdata;
    endcase
  end

  // --- outputs -----------------------------------------------------------
  assign retire_valid       = retire_q;
  assign retire_pc          = retire_pc_q;
  assign retire_instruction = retire_instruction_q;
  assign halted             = halted_q;
  assign trap               = trap_q;
  assign trap_cause         = trap_cause_q;

  always_comb begin
    mem_req   = 1'b0;
    mem_we    = 1'b0;
    mem_be    = 4'b1111;
    mem_addr  = {pc_q[31:2], 2'b00};
    mem_wdata = 32'd0;
    if (state_q == S_FETCH_REQ) begin
      mem_req = 1'b1;
    end else if (state_q == S_MEM_REQ) begin
      mem_req   = 1'b1;
      mem_we    = (opcode == 7'b0100011);
      mem_be    = (opcode == 7'b0100011) ? store_be : 4'b1111;
      mem_addr  = {mem_address[31:2], 2'b00};
      mem_wdata = store_data;
    end
  end

  task automatic write_register(input logic [4:0] index, input logic [31:0] value);
    if (index != 5'd0) regs_q[index] <= value;
  endtask

  // Enter machine mode: record the cause and vector to mtvec. Exceptions
  // always use the base address; only interrupts use the vectored offset, and
  // this core raises none.
  task automatic enter_trap(input logic [31:0] cause, input logic [31:0] tval,
                            input logic [31:0] epc);
    mstatus_q <= {mstatus_q[31:8],
                  mstatus_q[MSTATUS_MIE_BIT],   // MPIE takes the old MIE
                  mstatus_q[6:4],
                  1'b0,                          // MIE clears on trap entry
                  mstatus_q[2:0]} | 32'h0000_1800;
    mepc_q <= epc & ~32'd3;
    mcause_q <= cause;
    mtval_q <= tval;
    pc_q <= mtvec_q & ~32'd3;
    trap_q <= 1'b1;
    trap_cause_q <= cause;
    retire_q <= 1'b1;
    state_q <= S_FETCH_REQ;
  endtask


  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state_q <= S_FETCH_REQ;
      pc_q <= RESET_PC;
      instruction_q <= 32'd0;
      halted_q <= 1'b0;
      trap_q <= 1'b0;
      trap_cause_q <= 32'd0;
      retire_q <= 1'b0;
      retire_pc_q <= 32'd0;
      retire_instruction_q <= 32'd0;
      load_rd_q <= 5'd0;
      load_funct3_q <= 3'd0;
      load_offset_q <= 2'd0;
      next_pc_q <= 32'd0;
      // mstatus resets to zero, MPP included. The Sail model does the same and
      // the certification suite compares against it; the specification leaves
      // most of these reset values to the implementation.
      mstatus_q <= 32'd0;
      mie_q <= 32'd0; mtvec_q <= 32'd0; mscratch_q <= 32'd0;
      mepc_q <= 32'd0; mcause_q <= 32'd0; mtval_q <= 32'd0;
      mcycle_q <= 32'd0; mcycleh_q <= 32'd0;
      minstret_q <= 32'd0; minstreth_q <= 32'd0;
      mcounteren_q <= 32'd0; mcountinhibit_q <= 32'd0;
      for (int i = 0; i < 32; i++) regs_q[i] <= 32'd0;
    end else begin
      retire_q <= 1'b0;

      // Counters. mcycle counts real clock cycles here; the reference model has
      // no cycles to count and advances it per retired instruction instead, so
      // the two disagree by construction and mcycle is kept out of differential
      // stimulus. minstret means the same thing in both.
      if (!mcountinhibit_q[0]) begin
        {mcycleh_q, mcycle_q} <= {mcycleh_q, mcycle_q} + 64'd1;
      end
      if (!mcountinhibit_q[2] && retire_q) begin
        {minstreth_q, minstret_q} <= {minstreth_q, minstret_q} + 64'd1;
      end

      unique case (state_q)
        S_FETCH_REQ: begin
          if (mem_gnt) state_q <= S_FETCH_WAIT;
        end

        S_FETCH_WAIT: begin
          if (mem_rvalid) begin
            instruction_q <= mem_rdata;
            state_q <= S_EXEC;
          end
        end

        S_EXEC: begin
          // Default sequential flow; overridden by branches and jumps below.
          next_pc_q <= pc_q + 32'd4;
          retire_pc_q <= pc_q;
          retire_instruction_q <= instruction_q;

          if (illegal_encoding) begin
            enter_trap(32'd2, instruction_q, pc_q);
          end else
          unique case (opcode)
            7'b0110111: begin                       // LUI
              write_register(rd, imm_u);
              pc_q <= pc_q + 32'd4;
              retire_q <= 1'b1;
              state_q <= S_FETCH_REQ;
            end
            7'b0010111: begin                       // AUIPC
              write_register(rd, pc_q + imm_u);
              pc_q <= pc_q + 32'd4;
              retire_q <= 1'b1;
              state_q <= S_FETCH_REQ;
            end
            7'b1101111: begin                       // JAL
              if (fetch_misaligned) begin
                enter_trap(32'd0, jal_target, pc_q);   // instruction address misaligned
              end else begin
                write_register(rd, pc_q + 32'd4);
                pc_q <= jal_target;
                retire_q <= 1'b1;
                state_q <= S_FETCH_REQ;
              end
            end
            7'b1100111: begin                       // JALR
              if (fetch_misaligned) begin
                enter_trap(32'd0, jalr_target, pc_q);   // instruction address misaligned
              end else begin
                write_register(rd, pc_q + 32'd4);
                pc_q <= jalr_target;
                retire_q <= 1'b1;
                state_q <= S_FETCH_REQ;
              end
            end
            7'b1100011: begin                       // branches
              if (fetch_misaligned) begin
                enter_trap(32'd0, branch_target, pc_q);   // instruction address misaligned
              end else begin
                pc_q <= branch_taken ? branch_target : (pc_q + 32'd4);
                retire_q <= 1'b1;
                state_q <= S_FETCH_REQ;
              end
            end
            7'b0010011: begin                       // register-immediate
              write_register(rd, alu_ri);
              pc_q <= pc_q + 32'd4;
              retire_q <= 1'b1;
              state_q <= S_FETCH_REQ;
            end
            7'b0110011: begin                       // register-register
              write_register(rd, alu_rr);
              pc_q <= pc_q + 32'd4;
              retire_q <= 1'b1;
              state_q <= S_FETCH_REQ;
            end
            7'b0001111: begin                       // FENCE: no visible state
              pc_q <= pc_q + 32'd4;
              retire_q <= 1'b1;
              state_q <= S_FETCH_REQ;
            end
            7'b0000011, 7'b0100011: begin           // loads and stores
              if (misaligned) begin
                // Cause 4 for a load, 6 for a store.
                enter_trap((opcode == 7'b0100011) ? 32'd6 : 32'd4,
                           mem_address, pc_q);
              end else begin
                load_rd_q <= rd;
                load_funct3_q <= funct3;
                load_offset_q <= mem_offset;
                state_q <= S_MEM_REQ;
              end
            end
            7'b1110011: begin                       // SYSTEM
              if (funct3 == 3'b000) begin
                unique case (instruction_q[31:20])
                  12'h000: enter_trap(32'd11, 32'd0, pc_q);      // ECALL from M
                  12'h001: enter_trap(32'd3, pc_q, pc_q);        // EBREAK
                  12'h302: begin                                 // MRET
                    mstatus_q <= {mstatus_q[31:8], 1'b1, mstatus_q[6:4],
                                  mstatus_q[MSTATUS_MPIE_BIT], mstatus_q[2:0]}
                                 | 32'h0000_1800;
                    pc_q <= mepc_q & ~32'd3;
                    retire_q <= 1'b1;
                    state_q <= S_FETCH_REQ;
                  end
                  12'h105: begin                                 // WFI: a nop here
                    pc_q <= pc_q + 32'd4;
                    retire_q <= 1'b1;
                    state_q <= S_FETCH_REQ;
                  end
                  default: enter_trap(32'd2, instruction_q, pc_q);
                endcase
              end else if (csr_illegal) begin
                enter_trap(32'd2, instruction_q, pc_q);
              end else begin
                if (csr_reads) write_register(rd, csr_rdata);
                if (csr_writes) begin
                  // WARL masking, inlined because only one process may drive
                  // the CSR state. MPP is writable but machine is the only
                  // implemented level, so supervisor and the reserved encoding
                  // read back as machine.
                  unique case (csr_address)
                    CSR_MSTATUS: mstatus_q <= {19'd0,
                                   ((csr_wdata[12:11] == 2'b00) ? 2'b00 : 2'b11),
                                   3'd0, csr_wdata[MSTATUS_MPIE_BIT], 3'd0,
                                   csr_wdata[MSTATUS_MIE_BIT], 3'd0};
                    CSR_MIE:           mie_q <= csr_wdata & 32'h0000_0888;
                    CSR_MTVEC:         mtvec_q <= {csr_wdata[31:2],
                                          (csr_wdata[1:0] < 2'd2) ? csr_wdata[1:0] : 2'd0};
                    CSR_MSCRATCH:      mscratch_q <= csr_wdata;
                    CSR_MEPC:          mepc_q <= csr_wdata & ~32'd3;
                    CSR_MCAUSE:        mcause_q <= csr_wdata;
                    CSR_MTVAL:         mtval_q <= csr_wdata;
                    CSR_MCOUNTEREN:    mcounteren_q <= csr_wdata;
                    CSR_MCOUNTINHIBIT: mcountinhibit_q <= csr_wdata & 32'h0000_0005;
                    CSR_MCYCLE:        mcycle_q <= csr_wdata;
                    CSR_MCYCLEH:       mcycleh_q <= csr_wdata;
                    CSR_MINSTRET:      minstret_q <= csr_wdata;
                    CSR_MINSTRETH:     minstreth_q <= csr_wdata;
                    default: ;                    // read-only or unimplemented
                  endcase
                end
                pc_q <= pc_q + 32'd4;
                retire_q <= 1'b1;
                state_q <= S_FETCH_REQ;
              end
            end
            default: enter_trap(32'd2, instruction_q, pc_q);
          endcase
        end

        S_MEM_REQ: begin
          if (mem_gnt) state_q <= S_MEM_WAIT;
        end

        S_MEM_WAIT: begin
          if (mem_rvalid) begin
            if (opcode == 7'b0000011) write_register(load_rd_q, load_result);
            pc_q <= next_pc_q;
            retire_q <= 1'b1;
            state_q <= S_FETCH_REQ;
          end
        end

        S_HALT: begin
          halted_q <= 1'b1;
        end

        default: state_q <= S_FETCH_REQ;
      endcase
    end
  end
`ifdef RISCV_FORMAL
  // --- RISC-V Formal Interface -------------------------------------------
  //
  // The core retires an instruction in S_EXEC, or in S_MEM_WAIT once a load or
  // store response arrives. A trapping instruction does not set retire_q,
  // because the differential testbench counts retire_q as work completed, but
  // the formal interface must still report it with rvfi_trap set. So the two
  // notions of "retired" are kept separate rather than merged.

  logic will_retire, will_trap;
  always_comb begin
    will_retire = 1'b0;
    will_trap   = 1'b0;
    if (state_q == S_EXEC) begin
      if (illegal_encoding) begin
        will_retire = 1'b1;
        will_trap   = 1'b1;
      end else
      unique case (opcode)
        7'b0110111, 7'b0010111, 7'b0010011, 7'b0110011, 7'b0001111:
          will_retire = 1'b1;
        7'b1101111, 7'b1100111, 7'b1100011: begin
          will_retire = 1'b1;
          will_trap   = fetch_misaligned;
        end
        7'b0000011, 7'b0100011: begin
          will_retire = misaligned;      // an aligned access retires in S_MEM_WAIT
          will_trap   = misaligned;
        end
        7'b1110011: begin
          will_retire = 1'b1;
          // ECALL, EBREAK, and an unsupported SYSTEM encoding trap; MRET, WFI,
          // and a legal CSR access do not.
          will_trap = (funct3 == 3'b000)
                      ? !((instruction_q[31:20] == 12'h302)
                          || (instruction_q[31:20] == 12'h105))
                      : csr_illegal;
        end
        default: begin
          will_retire = 1'b1;            // illegal instruction
          will_trap   = 1'b1;
        end
      endcase
    end else if (state_q == S_MEM_WAIT) begin
      will_retire = mem_rvalid;
    end
  end

  // Destination register and the value it receives.
  logic [4:0]  next_rd_addr;
  logic [31:0] next_rd_wdata;
  always_comb begin
    next_rd_addr  = 5'd0;
    next_rd_wdata = 32'd0;
    if (state_q == S_MEM_WAIT) begin
      if (opcode == 7'b0000011) begin
        next_rd_addr  = load_rd_q;
        next_rd_wdata = load_result;
      end
    end else if (!will_trap) begin
      unique case (opcode)
        7'b0110111: begin next_rd_addr = rd; next_rd_wdata = imm_u; end
        7'b0010111: begin next_rd_addr = rd; next_rd_wdata = pc_q + imm_u; end
        7'b1101111,
        7'b1100111: begin next_rd_addr = rd; next_rd_wdata = pc_q + 32'd4; end
        7'b0010011: begin next_rd_addr = rd; next_rd_wdata = alu_ri; end
        7'b0110011: begin next_rd_addr = rd; next_rd_wdata = alu_rr; end
        7'b1110011: begin
          if ((funct3 != 3'b000) && csr_reads) begin
            next_rd_addr = rd;
            next_rd_wdata = csr_rdata;
          end
        end
        default: ;
      endcase
    end
    // x0 absorbs its write, so the interface must report zero for both.
    if (next_rd_addr == 5'd0) next_rd_wdata = 32'd0;
  end

  // Where the program counter goes next.
  logic [31:0] next_pc_value;
  always_comb begin
    next_pc_value = pc_q + 32'd4;
    if (state_q == S_MEM_WAIT) begin
      next_pc_value = next_pc_q;
    end else if (will_trap) begin
      next_pc_value = mtvec_q & ~32'd3;
    end else begin
      unique case (opcode)
        7'b1101111: next_pc_value = jal_target;
        7'b1100111: next_pc_value = jalr_target;
        7'b1100011: next_pc_value = branch_taken ? branch_target : (pc_q + 32'd4);
        7'b1110011: begin
          if ((funct3 == 3'b000) && (instruction_q[31:20] == 12'h302)) begin
            next_pc_value = mepc_q & ~32'd3;      // MRET
          end
        end
        default: ;
      endcase
    end
  end

  // Which source registers the instruction actually reads.
  logic [4:0] next_rs1_addr, next_rs2_addr;
  always_comb begin
    next_rs1_addr = rs1;
    next_rs2_addr = rs2;
    unique case (opcode)
      7'b0110111, 7'b0010111, 7'b1101111: begin
        next_rs1_addr = 5'd0;
        next_rs2_addr = 5'd0;
      end
      7'b1100111, 7'b0010011, 7'b0000011: next_rs2_addr = 5'd0;
      7'b1110011: begin
        // The immediate CSR forms encode a zero-extended constant in the rs1
        // field, so no register is read; the plain SYSTEM instructions read
        // neither operand.
        next_rs1_addr = ((funct3 != 3'b000) && !funct3[2]) ? rs1 : 5'd0;
        next_rs2_addr = 5'd0;
      end
      default: ;
    endcase
  end

  // Byte lanes a load actually reads, mirroring the store byte enables.
  logic [3:0] load_mask;
  always_comb begin
    unique case (load_funct3_q)
      3'b000, 3'b100: load_mask = 4'b0001 << load_offset_q;
      3'b001, 3'b101: load_mask = load_offset_q[1] ? 4'b1100 : 4'b0011;
      default:        load_mask = 4'b1111;
    endcase
  end

  logic [63:0] order_q;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rvfi_valid <= 1'b0;
      order_q <= 64'd0;
      rvfi_order <= 64'd0;
      rvfi_insn <= 32'd0;
      rvfi_trap <= 1'b0;
      rvfi_rs1_addr <= 5'd0; rvfi_rs2_addr <= 5'd0;
      rvfi_rs1_rdata <= 32'd0; rvfi_rs2_rdata <= 32'd0;
      rvfi_rd_addr <= 5'd0; rvfi_rd_wdata <= 32'd0;
      rvfi_pc_rdata <= 32'd0; rvfi_pc_wdata <= 32'd0;
      rvfi_mem_addr <= 32'd0;
      rvfi_mem_rmask <= 4'd0; rvfi_mem_wmask <= 4'd0;
      rvfi_mem_rdata <= 32'd0; rvfi_mem_wdata <= 32'd0;
    end else begin
      rvfi_valid <= will_retire && !halted_q;
      if (will_retire && !halted_q) begin
        rvfi_order <= order_q;
        order_q <= order_q + 64'd1;
        rvfi_insn <= instruction_q;
        rvfi_trap <= will_trap;
        rvfi_rs1_addr <= next_rs1_addr;
        rvfi_rs2_addr <= next_rs2_addr;
        rvfi_rs1_rdata <= (next_rs1_addr == 5'd0) ? 32'd0 : regs_q[next_rs1_addr];
        rvfi_rs2_rdata <= (next_rs2_addr == 5'd0) ? 32'd0 : regs_q[next_rs2_addr];
        rvfi_rd_addr <= next_rd_addr;
        rvfi_rd_wdata <= next_rd_wdata;
        rvfi_pc_rdata <= pc_q;
        rvfi_pc_wdata <= next_pc_value;
        if (state_q == S_MEM_WAIT) begin
          rvfi_mem_addr <= {mem_address[31:2], 2'b00};
          rvfi_mem_rmask <= (opcode == 7'b0000011) ? load_mask : 4'd0;
          rvfi_mem_wmask <= (opcode == 7'b0100011) ? store_be : 4'd0;
          rvfi_mem_rdata <= mem_rdata;
          rvfi_mem_wdata <= store_data;
        end else begin
          rvfi_mem_addr <= 32'd0;
          rvfi_mem_rmask <= 4'd0;
          rvfi_mem_wmask <= 4'd0;
          rvfi_mem_rdata <= 32'd0;
          rvfi_mem_wdata <= 32'd0;
        end
      end
    end
  end

  assign rvfi_halt = halted_q;
  assign rvfi_intr = 1'b0;          // no interrupt support
  assign rvfi_mode = 2'b11;         // machine mode only
  assign rvfi_ixl  = 2'b01;         // XLEN = 32
`endif

endmodule
