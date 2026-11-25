# The security ring test

A Saturn disc must end before the CD block's disc check reads its security
ring (tools/mkdisc.py, RING_CAP), or MiSTer, the Fenrir and burned discs
boot it as a music CD (beta 2, OPEN_ISSUES). Mednafen, the Satiator and the
Saroo never run that check, so they can't show it. Ymir can: with CD Block
LLE it runs the CD block's own SH-1 firmware, and its drive answers ring
data only past the image's end (libs/ymir-core/src/ymir/hw/cdblock/cd_drive.cpp,
`m_currFAD > toc.GetEndFrameAddress()`), the rule MiSTer's drive follows
(Main_MiSTer support/saturn/saturncdd.cpp, `lba >= toc.end`).

## Setup

- tools/ymir (gitignored): Ymir's Windows release (v0.4.1, x86_64 AVX2)
  with its profile in tools/ymir/profile, started as
  `ymir-sdl3.exe -p tools/ymir/profile -d <cue>`.
- profile/roms/ipl: the BIOS from Mednafen's firmware folder.
  profile/roms/cdb: the CD block ROMs 1.05 and 1.06, converted from
  MiSTer-devel/Saturn_MiSTer rtl/cdb105.mif and cdb106.mif (64 KB each,
  32-bit words big-endian). Ymir doesn't know their hashes but takes them.
- Ymir.toml: `[CDBlock] UseLLE = true, OverrideROM = true, ROMPath =
  'cdb106.bin'` (or cdb105.bin); `PreferredRegionOrder` Japan first, so
  region-free discs use the Japanese BIOS, whose clock is already set.
- profile/state/updates/.onboarded skips the update question.
- A fresh profile's BIOS asks for the date first: six presses right
  (Ymir's key D) reach 決定, then C (key L). Keys reach Ymir as window
  messages (WM_KEYDOWN) while it isn't focused.

A disc that passes shows the SEGA license screen and then CCE's attract; one
that fails shows the BIOS's CD player with the disc's track count and time.
The test discs need their files beside the cue: Ymir takes no absolute paths
in FILE lines.

## 2026-11-25

| Disc | Tracks | Ends at FAD | 1.06 | 1.05 |
|---|---|---|---|---|
| retail CCE (Japan) | 31 | 277,345 | boots | |
| beta 1 | 33 | 284,831 | boots | |
| beta 2, from beta 2's own builder | 43 | 352,063 | CD player | CD player |
| 2.1, MUSIC=95 | 34 | 281,940 | boots | boots |
| 2.1, MUSIC=original | 34 | 278,497 | boots | boots |
| 2.1 + silence to 50 sectors before the ring | 35 | 299,250 | boots | boots |
| 2.1 + silence to 100 sectors past its start | 35 | 299,400 | boots | |
| 2.1 + silence past every ring sector | 35 | 318,000 | CD player | CD player |
| 2.1 + nine short silent tracks | 43 | 284,640 | boots | boots |
| 2.1 release builder: USA DUSA, '95 music | 34 | 281,940 | boots | boots |
| 2.1 release builder: Japan DUSA, arcade originals | 34 | 278,498 | boots | |
| 2.1 release builder: Europe DUSA, '95 music | 34 | 281,936 | boots | |

The release builder's discs (1.0.0-beta.2.1, Windows) match `make disc`'s
track for track where the DUSA rip is the USA one; with the Japan and Europe
rips their DUSA tracks are those rips' own, as the builder checks. The Linux
builder's arcade-originals disc matches `make disc MUSIC=original`'s.

With Ymir's HLE CD block, beta 2 boots: the failure is the firmware's check.
The firmware reads the ring at FAD 299,300 + 0-12 x 1470, chosen at random,
so a disc ending between there and about 317,000 boots some of the time (the
299,400 disc booted once); one ending before 299,300 always gets ring data,
and one past every candidate never does. Neither the track count (43) nor
anything else in beta 2's layout matters, only where the disc ends.

The Fenrir is a separate case: its own menu refused beta 2 ("failed to
load") before the Saturn ever checked, so its limit is its own and Ymir
can't show it. Beta 2.1 is inside what beta 1 proved on it in length (62:37
against 63:17), its cue (3,915 bytes, against beta 1's 3,570 and beta 2's
4,950) is smaller than retail CCE's Redump cue (4,097), and it has one
track more than beta 1 (34 against 33).
