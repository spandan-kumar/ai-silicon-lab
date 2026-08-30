`timescale 1ns/1ps

module tb_obi_wishbone_bridge;
  logic clk = 1'b0;
  logic resetn = 1'b0;
  logic enable = 1'b0;
  logic obi_req = 1'b0;
  logic obi_gnt;
  logic obi_rvalid;
  logic obi_we = 1'b0;
  logic [3:0] obi_be = 4'b1111;
  logic [31:0] obi_addr = 32'b0;
  logic [31:0] obi_wdata = 32'b0;
  logic [31:0] obi_rdata;
  logic [29:0] wb_adr;
  logic [31:0] wb_dat_w;
  logic [31:0] wb_dat_r = 32'b0;
  logic [3:0] wb_sel;
  logic wb_cyc;
  logic wb_stb;
  logic wb_we;
  logic [2:0] wb_cti;
  logic [1:0] wb_bte;
  logic wb_ack = 1'b0;
  logic wb_err = 1'b0;

  always #5 clk = ~clk;

  aisl_obi_wishbone_bridge dut (
      .clk,
      .resetn,
      .enable,
      .obi_req,
      .obi_gnt,
      .obi_rvalid,
      .obi_we,
      .obi_be,
      .obi_addr,
      .obi_wdata,
      .obi_rdata,
      .wb_adr,
      .wb_dat_w,
      .wb_dat_r,
      .wb_sel,
      .wb_cyc,
      .wb_stb,
      .wb_we,
      .wb_cti,
      .wb_bte,
      .wb_ack,
      .wb_err
  );

  task automatic step;
    @(posedge clk);
    #1;
  endtask

  initial begin
    repeat (2) step();
    resetn = 1'b1;
    enable = 1'b1;
    step();

    // Read: the OBI byte address is remapped into LiteX's word-addressed
    // 0x4000_0000 main-RAM window.
    obi_addr = 32'h0200_0040;
    obi_req = 1'b1;
    #1;
    if (!obi_gnt) $fatal(1, "read request was not granted");
    step();
    obi_req = 1'b0;
    if (!wb_cyc || !wb_stb || wb_we) $fatal(1, "bad Wishbone read request");
    if (wb_adr != 30'h1080_0010) $fatal(1, "bad remapped read address");
    if (wb_cti != 3'b000 || wb_bte != 2'b00) $fatal(1, "bad classic-cycle tags");

    wb_dat_r = 32'hc001_d00d;
    wb_ack = 1'b1;
    step();
    wb_ack = 1'b0;
    if (!obi_rvalid || obi_rdata != 32'hc001_d00d) $fatal(1, "bad read response");
    step();
    if (obi_rvalid || wb_cyc) $fatal(1, "response did not return to idle");

    // Byte-masked write.
    obi_addr = 32'h0000_0104;
    obi_wdata = 32'h1234_5678;
    obi_be = 4'b0101;
    obi_we = 1'b1;
    obi_req = 1'b1;
    #1;
    if (!obi_gnt) $fatal(1, "write request was not granted");
    step();
    obi_req = 1'b0;
    if (!wb_cyc || !wb_we || wb_sel != 4'b0101) $fatal(1, "bad Wishbone write control");
    if (wb_dat_w != 32'h1234_5678 || wb_adr != 30'h1000_0041) $fatal(1, "bad Wishbone write payload");
    wb_ack = 1'b1;
    step();
    wb_ack = 1'b0;
    if (!obi_rvalid) $fatal(1, "write completion did not produce OBI rvalid");
    step();

    // A paused bridge must not accept new work.
    enable = 1'b0;
    obi_req = 1'b1;
    #1;
    if (obi_gnt) $fatal(1, "disabled bridge granted a request");
    step();
    if (wb_cyc) $fatal(1, "disabled bridge started a Wishbone cycle");

    // Disabling after acceptance must not strand an in-flight transaction.
    enable = 1'b1;
    #1;
    if (!obi_gnt) $fatal(1, "request was not granted after re-enable");
    step();
    obi_req = 1'b0;
    enable = 1'b0;
    if (!wb_cyc) $fatal(1, "accepted transaction disappeared after pause");
    wb_err = 1'b1;
    step();
    wb_err = 1'b0;
    if (!obi_rvalid || obi_rdata != 32'b0) $fatal(1, "Wishbone error completion was not deterministic");
    step();

    $display("OBI/Wishbone bridge verification passed");
    $finish;
  end
endmodule
