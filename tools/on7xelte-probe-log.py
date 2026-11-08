#!/usr/bin/env python3
"""Decode the probe4k record from a /proc/last_kmsg copy pulled in TWRP.

probe4k.S writes a 4 KiB record at PA 0x469ff000, the last page of the
Exynos Snapshot log_kernel region. sec_debug copies that region to
/proc/last_kmsg on the next boot, but it may rotate the ring, so this tool
searches for the "A5XNU001" magic instead of trusting offset 0x1ff000.
Host-side only.
"""
import struct
import sys
from pathlib import Path

MAGIC = b"A5XNU001"
STAGES = {
    1: "girdi: EL1, MMU kapali, log sayfasi yazildi",
    2: "CPU kimlik registerlari okundu",
    3: "FDT (0xd00dfeed) gecerli",
    4: "4 KiB MMU acildi ve calisti",
}


def main():
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} last_kmsg.bin")
    data = Path(sys.argv[1]).read_bytes()
    hits = [i for i in range(len(data)) if data.startswith(MAGIC, i)]
    if not hits:
        print(f"{MAGIC.decode()} bulunamadi ({len(data)} bayt). Probe calismadi"
              " ya da RAM soguk resetle silindi.")
        return 1
    for off in hits:
        rec = data[off:off + 104].ljust(104, b"\0")
        q = struct.unpack_from("<13Q", rec)
        stage = q[10]
        print(f"kayit offset {off:#x} (beklenen 0x1ff000)")
        print(f"  CurrentEL      {q[1]:#x}  (EL{(q[1] >> 2) & 3})")
        print(f"  SCTLR_EL1      {q[2]:#x}")
        print(f"  FDT            {q[3]:#x}")
        print(f"  _start         {q[4]:#x}")
        print(f"  MPIDR_EL1      {q[5]:#x}")
        print(f"  ID_AA64MMFR0   {q[6]:#x}")
        print(f"  ID_AA64PFR0    {q[7]:#x}")
        print(f"  CNTFRQ_EL0     {q[8]} Hz")
        print(f"  FDT ilk kelime {q[9]:#x}")
        print(f"  asama          {stage:#x}  {STAGES.get(stage, 'MMU reddetti (hata kodu)')}")
        if stage == 4:
            print(f"  TCR_EL1        {q[11]:#x}")
            print(f"  SCTLR_EL1 son  {q[12]:#x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
