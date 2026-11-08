#!/usr/bin/env python3
"""Build the minimal Apple Device Tree that the on7xelte xnu needs to boot.

Port of mkadt-a10.py to the Samsung Galaxy J7 Prime (SM-G610F, Exynos 7870).
Every MMIO address comes from the Exynos 7870 kernel source
(arch/arm64/boot/dts/exynos7870.dtsi + exynos7870-on7xelte_common.dtsi).

Usage:
  mkadt-on7xelte.py OUT.adt [--dump] [--qemu] [--boot-core 0x0]

--qemu switches the boot-core reg to 0 for the QEMU virt board.

on7xelte (Exynos 7870) facts:
  - SoC Exynos 7870, 8x Cortex-A53 (homogeneous, no big.LITTLE);
  - eMMC host DW-MMC0 at 0x13540000, DT IRQ 245 (INTID 277 = 245 + 32);
  - GIC-400 at GICD 0x104E1000 / GICC 0x104E2000;
  - virtual timer: PPI 11 -> INTID 27, CNTFRQ 26 MHz (oscclk 26000000);
  - framebuffer 0x67000000, 1080x1920, stride 4320 (SBOOT leaves it up);
  - RAM (exynos7870-on7xelte_common.dtsi):
      bank 1  0x40000000 + 0x3E400000  (996 MiB; framebuffer 0x67000000 here)
      bank 2  0x80000000 + 0x80000000  (2 GiB)
    Total 3 GiB. Kernel window TBD (measure on hardware, like the A10 did).
"""

import hashlib, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402

# Kernel-managed RAM.  TODO(measure): the A10 used bank 2 only; for the 7870
# the framebuffer (0x67000000) sits in bank 1, so the kernel window is likely
# bank 2 (0x80000000..0x100000000).  These values are a first guess and MUST
# be verified against the live FDT / dmesg on hardware before first boot.
PHYS_BASE = 0x80000000
MEM_SIZE = 0x7f000000		# 2 GiB minus 1 MiB panic log (guess)
# Panic log buffer, carved off the TOP of the dram range.
PANIC_LOG_SIZE = 0x100000
# /arm-io children are relative to this; Exynos peripherals start at 0x10000000.
SOC_BASE = 0x01000000

# GIC-400 (GICv2): exynos7870.dtsi:273.
GICC, GICC_SIZE = 0x104E2000, 0x1000
GICD, GICD_SIZE = 0x104E1000, 0x1000
GICC_QEMU, GICD_QEMU = 0x08010000, 0x08000000
# fbcon: bootloader_fb 0x67000000, panel 1080x1920 (resolution = <1080 1920>).
FB, FB_SIZE = 0x67000000, 0x800000
FB_W, FB_H, FB_STRIDE = 1080, 1920, 1080 * 4
# Exynos DW-MMC 0 hosts the soldered eMMC.  DT interrupts = <0 245 0>;
# XNU wants the GIC INTID, i.e. 245 + 32 = 277.
DWMMC0, DWMMC0_SIZE = 0x13540000, 0x2000
DWMMC0_IRQ = 277
# Synthetic ECID, NOT the phone's: 'on7' header word, fixed tail.
ON7_ECID = 0x6f6e370000000001
TIMEBASE = 26000000		# CNTFRQ at boot, oscclk 26000000
VTIMER_INTID = 27		# FDT timer: type1 PPI 11 (virtual) -> INTID 27
# Masked MPIDR (Aff1<<8 | Aff0) of the boot core.  TODO(measure): the A10 was
# 0x0 (first A73).  The 7870 is all A53; measure MPIDR_EL1 on hardware.
BOOT_CORE_PHYS_ID = 0x0
BOOT_MANIFEST_HASH = hashlib.sha384(b'on7xelte boot manifest').digest()

# The real D22AP tree provides /product; kept out of git.
D22AP_ADT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
			 'research', 'd22ap.adt')


def d22ap_product(path=D22AP_ADT):
    """/product properties of the real D22AP tree, without the syscfg
    placeholders iBoot would fill in and the node bookkeeping."""
    if not os.path.exists(path):
        print(f'note: {path} missing, no /product node (fine for first boot)',
              file=sys.stderr)
        return None
    for c in adt.parse(open(path, 'rb').read())[0].children:
        if dict((k, v) for k, f, v in c.props).get('name') == b'product\0':
            return [(k, v) for k, f, v in c.props
                    if not f and k not in ('name', 'AAPL,phandle')]
    raise SystemExit(f'{path}: no /product node')


u32 = lambda *v: struct.pack('<%dI' % len(v), *v)
u64 = lambda *v: struct.pack('<%dQ' % len(v), *v)
cstr = lambda s: s.encode() + b'\0'


def node(name, props=(), children=()):
    n = adt.Node()
    n.props = [('name', 0, cstr(name))] + [(k, 0, v) for k, v in props]
    n.children = list(children)
    return n


def arg_value(flag):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 >= len(sys.argv):
            raise SystemExit(f'{flag} needs a value')
        return sys.argv[i + 1]
    return None


def build():
    qemu = '--qemu' in sys.argv
    boot_core = arg_value('--boot-core')
    boot_core = int(boot_core, 0) if boot_core else BOOT_CORE_PHYS_ID
    panic_base = PHYS_BASE + MEM_SIZE
    gicc, gicd = (GICC_QEMU, GICD_QEMU) if qemu else (GICC, GICD)
    if qemu:
        boot_core = 0
    gicc_rel, gicd_rel = gicc - SOC_BASE, gicd - SOC_BASE

    seed = os.urandom(64)
    phandle = iter(range(1, 1000))
    ph = lambda: ('AAPL,phandle', u32(next(phandle)))

    chosen = node('chosen', [
        ph(),
        ('dram-base', u64(PHYS_BASE)),
        ('dram-size', u64(MEM_SIZE)),
        ('random-seed', seed),
        ('debug-enabled', u32(1)),
        ('embedded-panic-log-size', u32(PANIC_LOG_SIZE)),
        ('firmware-version', cstr('on7xelte-shim')),
        ('system-firmware-version', cstr('on7xelte-shim')),
        ('boot-manifest-hash', BOOT_MANIFEST_HASH),
        ('crypto-hash-method', cstr('sha2-384')),
        ('display-scale', u32(3)),
        ('unique-chip-id', struct.pack('<Q', ON7_ECID)),
        ('chip-id', u32(0x8015)),
        ('certificate-production-status', u32(0)),
        ('effective-production-status-ap', u32(0)),
        ('certificate-security-mode', u32(1)),
        ('effective-security-mode-sep', u32(1)),
    ], [
        node('memory-map', [ph()]),
        node('asmb', [ph(), ('lp-sip0', u64(0x6f)), ('lp-sip1', u32(1))]),
    ])

    cpus = node('cpus', [ph(), ('#address-cells', u32(1)),
                         ('#size-cells', u32(0))], [
        node('cpu0', [
            ph(),
            ('device_type', cstr('cpu')),
            ('compatible', cstr('arm,cortex-a53') + cstr('ARM,v8')),
            ('reg', u32(boot_core)),	# MPIDR Aff1:Aff0, not logical
            ('cpu-id', u32(0)),
            ('cluster-id', u32(0)),
            ('cluster-type', u32(0)),
            ('die-cluster-id', u32(0)),
            ('cluster-core-id', u32(0)),
            ('l2-cache-id', u32(0)),
            ('l3-cache-id', u32(0)),
            ('state', cstr('running')),
            ('timebase-frequency', u32(TIMEBASE)),
            ('clock-frequency', u32(1600000000)),
            ('bus-frequency', u32(100000000)),
            ('memory-frequency', u32(1600000000)),
            ('peripheral-frequency', u32(TIMEBASE)),
            ('fixed-frequency', u32(TIMEBASE)),
        ]),
    ])

    gic = node('gic', [
        ph(),
        ('compatible', cstr('arm,gic-v2')),
        ('interrupt-controller', b''),
        ('virtual-timer-intid', u32(VTIMER_INTID)),
        ('reg', u64(gicc_rel, GICC_SIZE, gicd_rel, GICD_SIZE)),
    ])

    emmc = node('dwmmc0', [
        ph(),
        ('compatible', cstr('samsung,exynos-dw-mshc')),
        ('reg', u64(DWMMC0 - SOC_BASE, DWMMC0_SIZE)),
        ('interrupt', u32(DWMMC0_IRQ)),
        ('bus-width', u32(8)),
        ('non-removable', u32(1)),
    ])

    arm_io = node('arm-io', [
        ph(),
        ('device_type', cstr('on7xelte-io')),
        ('compatible', cstr('sweet-io') + cstr('arm-io')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
        ('ranges', u64(0, SOC_BASE, 0x100000000 - SOC_BASE)),
    ], [
        gic,
        emmc,
        node('wdt', [ph(), ('no-pmu', u32(1))]),
        node('disp0', [
            ph(),
            ('device_type', cstr('display-subsystem')),
            ('compatible', cstr('sweet,display')),
            ('canvas-width', u32(FB_W)),
            ('canvas-height', u32(FB_H)),
        ]),
    ])

    fbcon = node('sweet-fbcon', [
        ph(),
        ('reg', u64(FB, FB_SIZE)),
        ('width', u32(FB_W)),
        ('height', u32(FB_H)),
        ('stride', u32(FB_STRIDE)),
    ])

    defaults = node('defaults', [ph(), ('no-effaceable-storage', u32(1))])

    buttons = node('buttons', [
        ph(),
        ('button-names', cstr('volup') + cstr('voldown') + cstr('hold')),
        ('home-button-type', u32(2)),
        ('opposed-power-vol-buttons', u32(1)),
    ])

    pram = node('pram', [ph(),
                         ('reg', u64(panic_base) + u64(PANIC_LOG_SIZE))])

    product_props = d22ap_product()
    product = [node('product', [ph()] + product_props)] if product_props \
        else []

    return node('device-tree', [
        ph(),
        ('compatible', cstr('D22AP') + cstr('iPhone10,3') + cstr('samsung,on7xelte')
         + cstr('exynos7870') + cstr('AppleARM')),
        ('model', cstr('iPhone10,3')),
        ('target-type', cstr('D22')),
        ('target-sub-type', cstr('D22AP')),
        ('manufacturer', cstr('Apple Inc.')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
    ], [chosen, defaults, cpus, arm_io, fbcon, buttons, pram] + product)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    root = build()
    blob = adt.serialize(root)
    open(sys.argv[1], 'wb').write(blob)
    if '--dump' in sys.argv:
        adt.dump(adt.parse(blob)[0])
    print(f'{sys.argv[1]}: {len(blob)} bytes', file=sys.stderr)
