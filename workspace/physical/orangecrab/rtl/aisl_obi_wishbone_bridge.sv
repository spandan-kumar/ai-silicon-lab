`timescale 1ns/1ps

module aisl_obi_wishbone_bridge #(
    parameter logic [31:0] WB_BASE_ADDR = 32'h4000_0000
) (
    input  logic        clk,
    input  logic        resetn,
    input  logic        enable,

    input  logic        obi_req,
    output logic        obi_gnt,
    output logic        obi_rvalid,
    input  logic        obi_we,
    input  logic [ 3:0] obi_be,
    input  logic [31:0] obi_addr,
    input  logic [31:0] obi_wdata,
    output logic [31:0] obi_rdata,

    output logic [29:0] wb_adr,
    output logic [31:0] wb_dat_w,
    input  logic [31:0] wb_dat_r,
    output logic [ 3:0] wb_sel,
    output logic        wb_cyc,
    output logic        wb_stb,
    output logic        wb_we,
    output logic [ 2:0] wb_cti,
    output logic [ 1:0] wb_bte,
    input  logic        wb_ack,
    input  logic        wb_err
);
  logic        busy;
  logic [29:0] wb_adr_q;
  logic [31:0] wb_dat_w_q;
  logic [ 3:0] wb_sel_q;
  logic        wb_we_q;

  assign obi_gnt = resetn && enable && !busy && obi_req;

  assign wb_adr   = wb_adr_q;
  assign wb_dat_w = wb_dat_w_q;
  assign wb_sel   = wb_sel_q;
  assign wb_we    = wb_we_q;
  assign wb_cyc   = busy;
  assign wb_stb   = busy;
  assign wb_cti   = 3'b000;
  assign wb_bte   = 2'b00;

  always_ff @(posedge clk or negedge resetn) begin
    if (!resetn) begin
      busy       <= 1'b0;
      wb_adr_q   <= 30'b0;
      wb_dat_w_q <= 32'b0;
      wb_sel_q   <= 4'b0;
      wb_we_q    <= 1'b0;
      obi_rvalid <= 1'b0;
      obi_rdata  <= 32'b0;
    end else begin
      obi_rvalid <= 1'b0;

      if (busy) begin
        if (wb_ack || wb_err) begin
          busy       <= 1'b0;
          obi_rvalid <= 1'b1;
          obi_rdata  <= wb_err ? 32'b0 : wb_dat_r;
        end
      end else if (enable && obi_req) begin
        busy       <= 1'b1;
        wb_adr_q   <= obi_addr[31:2] + WB_BASE_ADDR[31:2];
        wb_dat_w_q <= obi_wdata;
        wb_sel_q   <= obi_be;
        wb_we_q    <= obi_we;
      end
    end
  end
endmodule
