#!/usr/bin/env python3
import os
import re
from pathlib import Path

from migen import Cat, ClockSignal, If, Instance, ResetSignal, Signal

from litex.gen import LiteXModule
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc import SoCCore
from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import CSRStatus, CSRStorage

from litedram.modules import MT41K64M16
from litedram.phy import ECP5DDRPHY

from litex_boards.platforms import gsd_orangecrab
from litex_boards.targets.gsd_orangecrab import _CRGSDRAM


ROOT = Path(__file__).resolve().parents[3]
CONVERTED_RTL = Path(
    os.environ.get(
        "AISL_CONVERTED_RTL",
        ROOT / "workspace" / "rtl_cv" / "build" / "aisl_soc.v",
    )
)
BRIDGE_RTL = Path(
    os.environ.get(
        "AISL_BRIDGE_RTL",
        Path(__file__).resolve().parent / "rtl" / "aisl_obi_wishbone_bridge.sv",
    )
)
MAIN_RAM_BASE = 0x4000_0000


class OBIWishboneBridge(LiteXModule):
    def __init__(self, platform):
        self.req = Signal()
        self.gnt = Signal()
        self.rvalid = Signal()
        self.we = Signal()
        self.be = Signal(4)
        self.addr = Signal(32)
        self.wdata = Signal(32)
        self.rdata = Signal(32)
        self.enable = Signal()
        self.resetn = Signal()

        self.wishbone = wishbone.Interface(
            data_width=32,
            address_width=32,
            addressing="word",
        )

        platform.add_source(str(BRIDGE_RTL))
        wb = self.wishbone
        self.specials += Instance(
            "aisl_obi_wishbone_bridge",
            p_WB_BASE_ADDR=MAIN_RAM_BASE,
            i_clk=ClockSignal("sys"),
            i_resetn=self.resetn,
            i_enable=self.enable,
            i_obi_req=self.req,
            o_obi_gnt=self.gnt,
            o_obi_rvalid=self.rvalid,
            i_obi_we=self.we,
            i_obi_be=self.be,
            i_obi_addr=self.addr,
            i_obi_wdata=self.wdata,
            o_obi_rdata=self.rdata,
            o_wb_adr=wb.adr,
            o_wb_dat_w=wb.dat_w,
            i_wb_dat_r=wb.dat_r,
            o_wb_sel=wb.sel,
            o_wb_cyc=wb.cyc,
            o_wb_stb=wb.stb,
            o_wb_we=wb.we,
            o_wb_cti=wb.cti,
            o_wb_bte=wb.bte,
            i_wb_ack=wb.ack,
            i_wb_err=wb.err,
        )


class DDRInitStatus(LiteXModule):
    """BIOS-written result of LiteDRAM training and its destructive memtest."""

    def __init__(self):
        # LiteDRAM's sdram_init() detects these exact CSR names and writes them
        # before and after training. Keeping the state outside AISLControl lets
        # the host distinguish "BIOS still working" from a tested DDR failure.
        self.init_done = CSRStorage(1, reset=0, name="init_done")
        self.init_error = CSRStorage(1, reset=0, name="init_error")


class AISLControl(LiteXModule):
    def __init__(self):
        self.run = CSRStorage(1, name="run", description="Release the CV32E40P after memory loading.")
        self.memory_ready = CSRStorage(
            1,
            name="memory_ready",
            description="Host acknowledgement that DDR calibration and image loading passed.",
        )
        self.capture_ack = CSRStorage(
            1,
            name="capture_ack",
            description="Any write releases a framebuffer capture pause.",
        )
        self.frame_count = CSRStorage(32, reset=120, name="frame_count")
        self.frame_warmup = CSRStorage(32, reset=64, name="frame_warmup")
        self.input_count = CSRStorage(32, reset=10, name="input_count")
        self.wad_size = CSRStorage(32, reset=28_795_076, name="wad_size")
        self.skill = CSRStorage(32, reset=1, name="skill")
        self.episode = CSRStorage(32, reset=1, name="episode")
        self.map = CSRStorage(32, reset=1, name="map")

        self.state = CSRStatus(
            8,
            name="state",
            description="booted, Doom-started, finished, failed, trap, capture-pending, run, memory-ready.",
        )
        self.frame_address = CSRStatus(32, name="frame_address")
        self.frame_index = CSRStatus(32, name="frame_index")
        self.simulation_frames = CSRStatus(32, name="simulation_frames")
        self.game_tics = CSRStatus(32, name="game_tics")
        self.captured_frames = CSRStatus(32, name="captured_frames")
        self.exit_code = CSRStatus(32, name="exit_code")
        self.uart_last = CSRStatus(8, name="uart_last")
        self.uart_count = CSRStatus(32, name="uart_count")
        self.execution_cycles = CSRStatus(
            64,
            name="execution_cycles",
            description="CV32E40P clock cycles excluding host framebuffer-capture pauses.",
        )
        self.capture_pause_cycles = CSRStatus(
            64,
            name="capture_pause_cycles",
            description="Clock cycles spent paused for host framebuffer capture.",
        )

        self.status_booted = Signal()
        self.status_doom_started = Signal()
        self.status_finished = Signal()
        self.status_failed = Signal()
        self.trap = Signal()
        self.frame_capture_valid = Signal()
        self.uart_valid = Signal()
        self.uart_data = Signal(8)

        self.capture_pending = Signal(reset=0)
        self.cpu_resetn = Signal()
        self.bridge_enable = Signal()
        uart_last = Signal(8)
        uart_count = Signal(32)
        execution_cycles = Signal(64)
        capture_pause_cycles = Signal(64)
        terminal = Signal()

        self.comb += [
            self.cpu_resetn.eq(self.run.storage & self.memory_ready.storage),
            self.bridge_enable.eq(self.cpu_resetn & ~self.capture_pending),
            terminal.eq(self.status_finished | self.status_failed | self.trap),
            self.state.status.eq(Cat(
                self.status_booted,
                self.status_doom_started,
                self.status_finished,
                self.status_failed,
                self.trap,
                self.capture_pending,
                self.run.storage,
                self.memory_ready.storage,
            )),
            self.uart_last.status.eq(uart_last),
            self.uart_count.status.eq(uart_count),
            self.execution_cycles.status.eq(execution_cycles),
            self.capture_pause_cycles.status.eq(capture_pause_cycles),
        ]

        self.sync += [
            If(
                ~self.cpu_resetn,
                self.capture_pending.eq(0),
                uart_last.eq(0),
                uart_count.eq(0),
                execution_cycles.eq(0),
                capture_pause_cycles.eq(0),
            ).Else(
                If(
                    self.frame_capture_valid,
                    self.capture_pending.eq(1),
                ).Elif(
                    self.capture_ack.re,
                    self.capture_pending.eq(0),
                ),
                If(
                    self.uart_valid,
                    uart_last.eq(self.uart_data),
                    uart_count.eq(uart_count + 1),
                ),
                If(
                    ~terminal,
                    If(
                        self.capture_pending,
                        capture_pause_cycles.eq(capture_pause_cycles + 1),
                    ).Else(
                        execution_cycles.eq(execution_cycles + 1),
                    ),
                ),
            )
        ]


class AISLOrangeCrabSoC(SoCCore):
    def __init__(self, device="85F", sys_clk_freq=48e6):
        platform = gsd_orangecrab.Platform(revision="0.2", device=device, toolchain="trellis")
        platform.add_extension(gsd_orangecrab.feather_serial)

        self.crg = _CRGSDRAM(platform, sys_clk_freq, with_usb_pll=False, with_dfu_rst=True)
        SoCCore.__init__(
            self,
            platform,
            sys_clk_freq,
            ident="AI Silicon Lab CV32E40P Doom target",
            ident_version=False,
            cpu_type="vexriscv",
            cpu_variant="minimal",
            integrated_rom_size=0x10000,
            integrated_sram_size=0x8000,
            # A pure UARTBone link leaves no console TX FIFO for BIOS output to
            # fill before DDR training. The VexRiscv is management-only; Doom
            # executes on the separately instantiated CV32E40P RTL below.
            uart_name="uartbone",
            uart_baudrate=1_000_000,
            with_timer=True,
        )
        self.add_config("BIOS_NO_PROMPT")
        self.add_config("BIOS_NO_CRC")
        self.add_config("BIOS_NO_BOOT")

        ddram_pads = platform.request("ddram")
        self.ddrphy = ECP5DDRPHY(
            pads=ddram_pads,
            sys_clk_freq=sys_clk_freq,
            dm_remapping={0: 1, 1: 0},
            cmd_delay=100,
        )
        self.ddrphy.settings.rtt_nom = "disabled"
        self.comb += [
            ddram_pads.vccio.eq(0b111111),
            ddram_pads.gnd.eq(0),
            self.crg.stop.eq(self.ddrphy.init.stop),
            self.crg.reset.eq(self.ddrphy.init.reset),
        ]
        self.add_sdram(
            "sdram",
            phy=self.ddrphy,
            module=MT41K64M16(sys_clk_freq, "1:2"),
            l2_cache_size=8192,
        )
        self.ddrctrl = DDRInitStatus()

        if not CONVERTED_RTL.is_file():
            raise FileNotFoundError(f"generate the converted CV32E40P RTL first: {CONVERTED_RTL}")
        platform.add_source(str(CONVERTED_RTL))

        self.aisl_control = control = AISLControl()
        self.instr_bridge = instr = OBIWishboneBridge(platform)
        self.data_bridge = data = OBIWishboneBridge(platform)
        self.bus.add_master(name="aisl_instr", master=instr.wishbone)
        self.bus.add_master(name="aisl_data", master=data.wishbone)

        self.comb += [
            instr.resetn.eq(control.cpu_resetn),
            instr.enable.eq(control.bridge_enable),
            instr.we.eq(0),
            instr.be.eq(0b1111),
            instr.wdata.eq(0),
            data.resetn.eq(control.cpu_resetn),
            data.enable.eq(control.bridge_enable),
        ]

        self.specials += Instance(
            "aisl_soc_cv",
            i_clk=ClockSignal("sys"),
            i_resetn=control.cpu_resetn,
            o_instr_req=instr.req,
            i_instr_gnt=instr.gnt,
            i_instr_rvalid=instr.rvalid,
            o_instr_addr=instr.addr,
            i_instr_rdata=instr.rdata,
            o_data_req=data.req,
            i_data_gnt=data.gnt,
            i_data_rvalid=data.rvalid,
            o_data_we=data.we,
            o_data_be=data.be,
            o_data_addr=data.addr,
            o_data_wdata=data.wdata,
            i_data_rdata=data.rdata,
            i_cfg_frame_count=control.frame_count.storage,
            i_cfg_frame_warmup=control.frame_warmup.storage,
            i_cfg_input_count=control.input_count.storage,
            i_cfg_wad_size=control.wad_size.storage,
            i_cfg_skill=control.skill.storage,
            i_cfg_episode=control.episode.storage,
            i_cfg_map=control.map.storage,
            o_uart_tx_valid=control.uart_valid,
            o_uart_tx_data=control.uart_data,
            o_frame_capture_valid=control.frame_capture_valid,
            o_status_booted=control.status_booted,
            o_status_doom_started=control.status_doom_started,
            o_status_finished=control.status_finished,
            o_status_failed=control.status_failed,
            o_frame_address=control.frame_address.status,
            o_frame_index=control.frame_index.status,
            o_stat_simulation_frames=control.simulation_frames.status,
            o_stat_game_tics=control.game_tics.status,
            o_stat_captured_frames=control.captured_frames.status,
            o_stat_exit_code=control.exit_code.status,
            o_trap=control.trap,
        )


def main():
    from litex.build.parser import LiteXArgumentParser

    parser = LiteXArgumentParser(
        platform=gsd_orangecrab.Platform,
        description="AI Silicon Lab CV32E40P Doom target for OrangeCrab r0.2.",
    )
    parser.add_target_argument("--device", default="85F", choices=["25F", "45F", "85F"])
    parser.add_target_argument("--sys-clk-freq", default=48e6, type=float)
    args = parser.parse_args()

    soc = AISLOrangeCrabSoC(device=args.device, sys_clk_freq=args.sys_clk_freq)
    builder_args = dict(parser.builder_argdict)
    builder_args["bios_console"] = "disable"
    builder = Builder(soc, **builder_args)
    if args.build:
        builder.build(**parser.toolchain_argdict)
        csr_csv = Path(builder.csr_csv)
        contents = csr_csv.read_text(encoding="utf-8")
        contents = re.sub(
            r"^(# Auto-generated by LiteX \([^\n]+\)) on [^\n]+$",
            r"\1; generation timestamp normalized",
            contents,
            count=1,
            flags=re.MULTILINE,
        )
        csr_csv.write_text(contents, encoding="utf-8")
    if args.load:
        bitstream = Path(builder.get_bitstream_filename(mode="sram"))
        if not bitstream.is_file():
            raise FileNotFoundError(f"build the gateware before programming: {bitstream}")
        programmer = soc.platform.create_programmer()
        programmer.load_bitstream(str(bitstream))


if __name__ == "__main__":
    main()
