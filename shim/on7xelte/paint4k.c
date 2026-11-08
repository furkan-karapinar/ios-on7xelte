/* SPDX-License-Identifier: GPL-2.0-only
 *
 * on7xelte colour report for the 4 KiB MMU probe (probe4kc.S).
 *
 * TWRP cannot read the probe's RAM log: last_kmsg only copies text that was
 * written, and there is no /dev/mem or /proc/kcore. So the result is painted
 * into the S-Boot framebuffer (s3cfb.bootloaderfb=0x67000000, 1080x1920,
 * 32 bpp) and held for about 12 s before the recovery reset.
 *
 * Four horizontal bands, top to bottom:
 *   1 WHITE                 probe reached the report (EL1, MMU off at entry)
 *   2 GREEN / MAGENTA       FDT magic 0xd00dfeed valid / not valid
 *   3 GREEN / MAGENTA+bars  4 KiB MMU enabled / rejected (bar count = error)
 *     GREY                  MMU not attempted (FDT invalid)
 *   4 GREEN / GREY          this code is running with SCTLR_EL1.M=1 / M=0
 * Only green, white, grey and magenta are used, so a red/blue channel swap
 * in the panel format does not change the meaning.
 *
 * No peripheral register other than the framebuffer RAM is written here.
 * With the MMU on, mmu4k.c maps everything outside the Image as Device
 * memory, so these stores reach RAM directly in both states.
 */
#include <stdint.h>

#define FB_BASE   0x67000000UL
#define FB_WIDTH  1080U
#define FB_HEIGHT 1920U
#define BAND      (FB_HEIGHT / 4U)

#define WHITE   0xffffffffU
#define GREEN   0xff00ff00U
#define MAGENTA 0xffff00ffU
#define GREY    0xff808080U
#define BLACK   0xff000000U

static void fill_rows(unsigned y0, unsigned y1, uint32_t colour)
{
    volatile uint64_t *fb = (volatile uint64_t *)FB_BASE;
    uint64_t pair = ((uint64_t)colour << 32) | colour;
    for (unsigned i = y0 * FB_WIDTH / 2U; i < y1 * FB_WIDTH / 2U; ++i)
        fb[i] = pair;
}

static void bars(unsigned y0, unsigned y1, unsigned count)
{
    volatile uint32_t *fb = (volatile uint32_t *)FB_BASE;
    for (unsigned b = 0; b < count && b < 8U; ++b) {
        unsigned x0 = 60U + b * 120U;
        for (unsigned y = y0 + 60U; y < y1 - 60U; ++y)
            for (unsigned x = x0; x < x0 + 60U; ++x)
                fb[y * FB_WIDTH + x] = BLACK;
    }
}

static inline uint64_t sysreg_sctlr(void)
{
    uint64_t v;
    __asm__ volatile("mrs %0, SCTLR_EL1" : "=r" (v));
    return v;
}

static inline uint64_t counter(void)
{
    uint64_t v;
    __asm__ volatile("isb; mrs %0, CNTPCT_EL0" : "=r" (v) : : "memory");
    return v;
}

void on7_paint(volatile uint64_t *log)
{
    int64_t stage = (int64_t)log[10];
    int mmu_now = (int)(sysreg_sctlr() & 1U);

    fill_rows(0, BAND, WHITE);
    fill_rows(BAND, 2U * BAND, stage >= 3 ? GREEN : MAGENTA);
    if (stage == 4) {
        fill_rows(2U * BAND, 3U * BAND, GREEN);
    } else if (stage < 0) {
        fill_rows(2U * BAND, 3U * BAND, MAGENTA);
        bars(2U * BAND, 3U * BAND, (unsigned)(-stage));
    } else {
        fill_rows(2U * BAND, 3U * BAND, GREY);
    }
    fill_rows(3U * BAND, FB_HEIGHT, mmu_now ? GREEN : GREY);
    __asm__ volatile("dsb sy" : : : "memory");
    log[18] = 0x5041494e54ULL; /* "TNIAP": report painted */

    /* Hold ~12 s. The iteration cap keeps this finite if the counter is
     * stopped or CNTFRQ_EL0 was left at zero by S-Boot. */
    uint64_t freq = log[8] ? log[8] : 26000000ULL;
    uint64_t start = counter();
    for (uint64_t n = 0; n < 400000000ULL; ++n) {
        if (counter() - start >= 12ULL * freq)
            break;
    }
}
