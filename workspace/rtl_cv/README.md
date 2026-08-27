# CV32E40P final RTL integration

This directory contains the final candidate hardware. The earlier PicoRV32
integration under `workspace/rtl/` is retained as measured design history,
but is not used by `workspace/candidate.json`. The processor RTL is pinned to
OpenHW Group CV32E40P `cv32e40p_v1.8.3` at commit
`360d272898d81806be3377193870dbf83a3ea79f`.

`aisl_soc_cv.sv` preserves the firmware MMIO ABI while exposing independent
OBI instruction and data ports. The final simulation/synthesis boundary keeps
those independent ports and models a synchronous dual-port external SRAM: an
accepted OBI request receives its response one cycle later. The earlier
`aisl_soc.sv` single-port arbiter is retained as measured design-history RTL,
but is not part of the final source list. Both simulation and target-neutral
synthesis use `clock_gate_generic.sv`, whose always-on implementation is
functionally safe and synthesizable. A physical ASIC/FPGA integration may
replace it with the target technology's clock-gating cell.

CV32E40P's standard top does not expose RVFI. For simulator diagnostics only,
the local SoC observes the core event that increments architectural
`minstret`, plus its decode PC/instruction. These signals are guarded by
`ifndef SYNTHESIS`; the fields named `rvfi_*` retain simulator API
compatibility but are explicitly not a formal RVFI implementation.

`make` converts the complete synthesizable SystemVerilog design with pinned
`sv2v`, then runs target-neutral Yosys synthesis and emits the log plus JSON
and Verilog netlists under `build/`. The conversion defines `SYNTHESIS`, so no
diagnostic hierarchical references are present in the synthesized design.
