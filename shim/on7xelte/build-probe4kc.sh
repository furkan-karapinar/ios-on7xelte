#!/bin/sh
# Build the on7xelte colour-report variant of the 4 KiB MMU probe.
set -eu
cd "$(dirname "$0")"
mkdir -p out4kc
: "${CC:=gcc}"
: "${LD:=ld}"
: "${OBJCOPY:=objcopy}"
"${CC}" -c -ffreestanding -fno-builtin -fno-stack-protector -fno-pic -fno-pie -nostdlib \
    -fno-asynchronous-unwind-tables \
    -mgeneral-regs-only -march=armv8-a probe4kc.S -o out4kc/probe4kc.o
"${CC}" -c -ffreestanding -fno-builtin -fno-stack-protector -fno-pic -fno-pie -nostdlib \
    -fno-asynchronous-unwind-tables -Wall -Wextra -Werror \
    -mgeneral-regs-only -march=armv8-a -O2 mmu4k.c -o out4kc/mmu4k.o
"${CC}" -c -ffreestanding -fno-builtin -fno-stack-protector -fno-pic -fno-pie -nostdlib     -fno-asynchronous-unwind-tables -Wall -Wextra -Werror     -mgeneral-regs-only -march=armv8-a -O2 paint4k.c -o out4kc/paint4k.o
"${LD}" -static -T probe4k.ld --build-id=none out4kc/probe4kc.o out4kc/mmu4k.o out4kc/paint4k.o \
    -o out4kc/probe4kc.elf
"${OBJCOPY}" -O binary out4kc/probe4kc.elf out4kc/Image
python3 - <<'PY'
from pathlib import Path
import struct
p = Path("out4kc/Image").read_bytes()
assert len(p) < 0x200000
assert p[56:60] == b"ARMd"
assert struct.unpack_from("<Q", p, 8)[0] == 0x205000
assert struct.unpack_from("<Q", p, 16)[0] == 0
print(f"out4kc/Image: {len(p)} bytes; legacy Samsung Image header OK")
PY
