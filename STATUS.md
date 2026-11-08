# on7xelte (Exynos 7870) — iOS Port Status

Hedef: XNU/iOS'u Samsung Galaxy J7 Prime (SM-G610F, `on7xelte`, Exynos 7870) üzerinde çalıştırmak.

**Temel (donor):** a5xelte = Galaxy A5 **2016** (SM-A510F, Exynos **7580**), `nickdemon22/ios-a51` reposundaki
A5XELTE serisi (upstream: `orhunnx/ios-a5xelte`). Repo `ios-a10`'dan klonlandı ama aktif build yolu artık
tamamen a5xelte serisi; A10/SWEET'e özel dosyalar `donor-a10*/` klasörlerinde referans olarak duruyor.

Bütün 7870 adresleri WSL `~/j7prime-kernels/kernel_Exynos7870/` kaynağından:
`arch/arm64/boot/dts/exynos7870.dtsi`, `exynos7870-on7xelte_common.dtsi`,
`drivers/soc/samsung/pwrcal/S5E7870/S5E7870-{sfrbase,pmusfr,cmusfr,cmu}.h/.c`,
`drivers/staging/samsung/sec_reboot.c`.

## Durum (2026-11-08, branch `on7xelte/fix-7870-addresses`)

| Parça | Durum |
|---|---|
| `xnu/patches/` | ios-a51'in 0001–0123 serisiyle birebir aynı (126 dosya). Tek fark: 0118/0120'de A5 tuş/dokunmatik kodu varsayılan olarak kapalı |
| `.github/workflows/xnu.yml` | ios-a51'in A5XELTE workflow'u (macos-14, `MACHINE_CONFIG=A5XELTE`) |
| `tools/mkadt_a5xelte.py` + `tools/mkadt.py` | a51 sürümü; GIC 7870'e göre düzeltildi. ADT üretimi test edildi (9500 bayt) |
| `shim/on7xelte/` | a5xelte shim'i; 7870 PMU/CMU/ekran gücü adresleri düzeltildi. WSL'de `aarch64-linux-gnu-gcc 15.2` ile `-Werror` derlendi: `outxnu/Image` 9760 B, `out4k/Image` 20480 B, Samsung header OK |
| XNU build | Repo: github.com/furkan-karapinar/ios-on7xelte (public). CI `macos-15`'e taşındı (macos-14 kaldırıldı). İlk çalıştırma GitHub hesabındaki **fatura kilidi** yüzünden başlamadı |
| Donanım testi | ✅ probe4k + probe4kc (2026-11-08): EL1 girişi, geçerli FDT, 4 KiB MMU açık yürütme ve framebuffer 0x67000000 çıktısı telefonda doğrulandı |

## 7580 → 7870 adres düzeltmeleri

| Ne | a5xelte (7580) | on7xelte (7870) | Kaynak |
|---|---|---|---|
| GIC dist/cpu | `0x10C01000/0x10C02000` | `0x104E1000/0x104E2000` | exynos7870.dtsi `gic@104E0000` |
| PMU (reset, INFORM2/3) | `0x10460000` | `0x10480000` (SWRESET +0x400, INFORM2/3 +0x808/+0x80C) | S5E7870-sfrbase.h, pmusfr.h |
| Ekran güç bloğu | `0x10464080` | `0x10484020` (`PMU_DISPAUD_CONFIGURATION`, status +4) | pmusfr.h |
| MIF CMU | `0x10430000` (7870'te DREX0_PF_SECURE!) | `0x10460000` | sfrbase.h |
| Ekran CMU | `0x14870000` | `0x148D0000` (`CMU_DISPAUD`) | sfrbase.h |
| Ekran saat kapıları | 7580 offset'leri | MIF +0x870/874/878; DISPAUD +0x800/810/814/81C/820/824/828 | S5E7870-cmu.c `CLK_GATE` |
| eMMC, DECON, DSIM, SYSMMU | `0x13540000`, `0x14830000`, `0x14800000`, `0x14860000` | aynı | exynos7870.dtsi |
| Sanal timer | INTID 27 | INTID 27 (PPI 11) | exynos7870.dtsi |
| CPU MPIDR | 0–3, 0x100–0x103 | aynı | exynos7870.dtsi |
| Recovery reboot sihirli değerleri | INFORM2=0x12345678, INFORM3=0x12345674 | aynı | sec_reboot.c |

## Telefondan doğrulananlar (2026-11-08, adb + /proc/last_kmsg)

Cihaz: SM-G610F, bootloader **G610FDDU1CSB3**, `warranty_bit=1` (KNOX zaten atmış), Android 11 custom ROM
("Marvel OS M31-R Port", 3.18.140 SIMPLE-KERNEL). Magisk uygulaması kurulu ama adb shell'de `su` yok (root yok).
Shell kullanıcısı `log` grubunda, bu yüzden `/proc/last_kmsg` root olmadan okunabiliyor.

- **Framebuffer `0x67000000` ✅** — S-Boot `s3cfb.bootloaderfb=0x67000000` veriyor; panel TD4300 FHD 1080×1920, "LCD ON UBOOT".
- **Log sayfası `0x469ff000` ✅** — Exynos Snapshot düzeni: `log_kernel` 0x46800000 + 0x200000. `sec_debug` bunu bir sonraki
  açılışta `/proc/last_kmsg`'e kopyalıyor (2 MB). 0x469ff000 son sayfa → last_kmsg offset **0x1FF000**.
  Diğer bölgeler: log_kevents 0x46000000 (8 MB), log_platform 0x46A00000 (4 MB), log_pstore/ramoops 0x46E00000 (32 KB).
- **Boot çekirdeği MPIDR 0** ✅ (Linux: `CPU: 0 MPIDR: 80000000`).
- **Partition'lar:** BOOT p10, RECOVERY p11, EFS p3, SYSTEM p21, USERDATA p25 (A5: SYSTEM p20, USERDATA p23).
  XNU patch'leri GPT **adıyla** seçiyor, sorun yok. A5'in host tarafındaki `a5xelte-log-pull.sh` p20'yi sabit kullanıyor; J7'de p20 = RESERVED2, **kullanmayın**.
- **Linux CMA alanları** 0x80000000–0x8A000000 aralığında (sadece Linux'a ait, XNU açılışında boş).
- Recovery'de TWRP olup olmadığı **bilinmiyor**.
- **DSIM davranışı** — `display_console.c` 7580 DSIM sırasını kullanıyor (ör. fazladan RX kelimesi). 7870 DSIM IP'si benzer, test edilmedi.
- **RAM** — ADT 0x80000000'den başlayan 512 MB veriyor (J7: bank0 0x40000000–0x7E400000, bank1 0x80000000–0xFFFFFFFF; MFC carve-out 0xAE600000/0xAE800000). İlk boot için güvenli alt küme.

## İlk donanım testi: probe4k (2026-11-08)

- `candidates/probe4k-boot.img` (SHA-256 `1aef6507…dcb4df`) BOOT p10'a yazıldı ve geri okunarak doğrulandı. Ardından `adb reboot` yapıldı.
- Telefon 24 saniye içinde **kendiliğinden TWRP'ye** döndü. cmdline'da `bootmode=2` ve `sec_debug.reset_reason=7` (RR_R) vardı.
  Probe'da reset koduna giden her yol EL1'de ve MMU kapalıyken geçiyor, aksi halde `halt` ile donuyor. BOOT'ta Linux da yok. Buradan çıkanlar:
  - S-Boot imzasız ARMd/0x205000 imajını kabul ediyor.
  - Giriş EL1'de ve MMU kapalı.
  - PMU_ALIVE `0x10480000` ve INFORM2/3 + SWRESET sırası 7870'te çalışıyor.
- **0x469FF000'deki kayıt okunamadı.**
  - `sec_debug_save_last_kmsg()` buffer dolu değilse yalnızca `head..curr` metnini kopyalıyor (bu testte 255 KB). Bu yüzden son sayfa `/proc/last_kmsg`'e girmiyor.
  - TWRP'de `/dev/mem` ve `/proc/kcore` da yok.
  - Sonuç: FDT kontrolü ve 4 KiB MMU aşaması doğrulanamadı.
- Bu yüzden sonucu ekrana basan ikinci bir probe yazıldı: probe4kc (`paint4k.c`).

## İkinci donanım testi: probe4kc renkli rapor (2026-11-08) ✅

- `candidates/probe4kc-boot.img` (SHA-256 `48ea88aa…25637e`) BOOT p10'a yazıldı ve geri okunarak doğrulandı.
- Telefon **39 saniyede** TWRP'ye döndü (probe4k'da 24 sn). Aradaki yaklaşık 15 sn, ekrana boyama ve 12 sn'lik beklemeye denk geliyor; CNTPCT sayacı da çalışıyor.
- Kullanıcının gördüğü: en üstte ekranın yaklaşık dörtte biri **beyaz**, geri kalan üç bant **yeşil**.
  - FDT geçerli: S-Boot cihaz ağacını x0'da veriyor (S-Boot log'u 0x48000000 diyor).
  - `a5_enable_4k()` başarılı: 4 KiB granül, 32-bit VA, L1/L2/L3 tabloları.
  - Rapor kodu SCTLR_EL1.M=1 iken, yani MMU ve cache açıkken çalıştı.
  - Bant 4 yalnızca yeşil ya da gri olabiliyor ve yeşil göründü. Yani yeşil/mor kanal karışması yok; panel formatı 0xAARRGGBB'yi doğru gösteriyor.
- **Framebuffer 0x67000000 S-Boot'tan sonra hâlâ ekranda taranıyor.** Ekrana yazmak için DECON veya DSIM'e dokunmak gerekmiyor.
- A5'te XNU'nun ilk kontrol noktası da buydu (MMU açık talimat yürütme). J7 bu noktaya ulaştı.

## Sıradaki adım

XNU'nun kendisi. `xnu.yml` workflow'u GitHub macOS runner'ında çalıştırılmalı (push gerekli). Çıkan Mach-O, `mkpayload.py` ve `xnu_boot` shim ile BOOT'a paketlenir.

## J7 Prime'a özel donanım (A5'ten farklı, sürücü yazılmalı)

- **Tuşlar:** Power GPA0-0, Vol- GPA2-1, Vol+ GPA2-0, Home GPA1-7 (A5: hepsi GPA2'de). A5 tuş kodu kapalı (`a5keys=1` ile açılır, ama J7'de yanlış pinleri okur).
- **Dokunmatik:** Synaptics, I2C `0x13840000`, adres 0x70, IRQ GPC3-2. Dokunmatik tuşlar Melfas MIP4 @ I2C `0x13850000`, IRQ GPA1-4. A5 dokunmatik/PMIC kodu kapalı (`a5touchprobe=1` ile açılır, açmayın: 7870'te DREX secure ve GIC bölgelerini okur).
- **PMIC:** S2MPU05 (A5: S2MPU03). Patch 0121/0122 A5 PMIC'ine özel.

## Sıradaki adımlar

1. ~~Framebuffer ve log adreslerini doğrula~~ ✅
2. ~~TWRP doğrula, yedek al~~ ✅ TWRP 3.7.0 var. 24 partition yedeği (BOOT, RECOVERY, EFS, bootloader alanları, GPT) SHA-256 eşleşmeli olarak
   `j7prime-2016-sources/backup-on7xelte-2026-11-08/` klasöründe (git dışında). BOOT formatı: `ANDROID!`, page 2048,
   kernel text_offset 0x80000, DTBH (dt_size 370688), sonda SEANDROIDENFORCE; A5'teki BOOT p10 + DTBH düzeniyle aynı.
3. Shim'i yeniden derlemek için (WSL): `cd shim/on7xelte && CC=aarch64-linux-gnu-gcc LD=aarch64-linux-gnu-ld OBJCOPY=aarch64-linux-gnu-objcopy sh build-xnu-boot.sh`
4. GitHub'a push et → `xnu` workflow'unu çalıştır (macOS runner'da XNU derlenir).
5. J7'ye özel tuş/dokunmatik sürücüsü (yukarıdaki pinler).

## Notlar

- `MACHINE_CONFIG=A5XELTE` adı patch'lerin içinde geçtiği için şimdilik korunuyor; yeniden adlandırmak tüm seride değişiklik gerektirir.
- iOS userland kapalı kaynak; IPSW'den çekilir ve git'e konmaz.
