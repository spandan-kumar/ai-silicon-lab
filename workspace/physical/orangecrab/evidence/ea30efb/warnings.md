# Synthesis warning investigation

Yosys reported exactly three undriven-wire warnings, all in the pinned
management-only `VexRiscv_Min.v`, and then reported zero problems after
flattening and technology mapping.

- `IBusSimplePlugin_rspJoin_fetchRsp_isRvc` only propagates through RVC
  metadata. This VexRiscv build compiles the BIOS for `rv32i2p0`, and the
  metadata chain has no consumer in the synthesized top-level netlist.
- `CsrPlugin_mtvec_mode[1:0]` only feeds `CsrPlugin_xtvec_mode`, which has no
  consumer in this minimal core. `CsrPlugin_mtvec_base` remains separately
  implemented and supplies the direct-mode trap address used by the BIOS.

Neither warning symbol exists in the final flattened netlist, and the final
Yosys `check` result is `Found and reported 0 problems.` These signals belong
to the LiteX DDR-management CPU, not the experiment's CV32E40P Doom CPU.

ABC also prints two mapping notices: the mapped AIG has internal fanout in
zero complex flops and one carry, and one network is combinational. They are
not Yosys `check` failures. The mapped design proceeds through strict nextpnr
place-and-route and final timing analysis successfully.
