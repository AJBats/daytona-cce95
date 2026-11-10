# Open issues

This is the single list of known problems and unfinished work. Every Claude session on this project shares it. The details live in docs/ and in commit messages; this file says what's open and where to look.

- Give each issue one bullet under its area. Say what's wrong, who saw it, where and when, what's known, and what comes next.
- When a fix lands, move the issue to "Fixed, waiting on a check" and give the commit. Delete it once the user has seen it work.
- Put work the user has asked for under "Planned", apart from the bugs.

Started 2026-11-10 from one session's notes. Other sessions add theirs.

## Picture

- **The player's car still flickers out in packs of CPU cars (1P).** The user saw it on the Saturn on 2026-11-10, with the build at 121d9a3. It is "way down", but still happens with many CPU cars close by. The race-time cut and the car effects drawn last are both on in 1P. The bar is plain CCE: on the Saturn, plain CCE flashes about 6 times in 70 s of Dinosaur Canyon. Next: find which course and moment, then compare with plain CCE there. See docs/performance.md.
- **Smoke covers the car's rear quarter in side-on spins.** Since 0e8fdcc, 1P races draw the car's smoke and sparks last. When a spin turns the car side-on, the smoke lies over its rear quarter (build/vdp1cost/spin_side.png). The user will judge it in game. See docs/performance.md, "Car effects drawn last".
- **Dropped frames (20 fps) on the Saturn.** Seen in the 2026-11-08 recordings:
  - Three Seven races, on the start/finish and gantry straights every lap. 06cdf4f stops the cut before the frame's deadline, but no Saturn race has been recorded since.
  - The attract's forest shot. This one isn't VDP1: turning brought VDP1 under budget there and the drops stayed.
- **Polygon glitches when rubbing other cars, and on the later tracks.** Reported by OlivusPrime on the Saturn with beta.1, 2026-11-08. Beta.1 had none of the VDP1 work, and nobody has checked current builds.

## Cameras

- **The victory sequence's camera goes under the road.** Seen three times:
  - Hassmaschine, Seaside, after 2nd place, 2026-11-07.
  - tk1sbiglove, "victory lanes", 2026-11-09.
  - The user, Three Seven, after 1st place, on the Saturn, 2026-11-10.

  It has never been fixed. Its neighbors were: the standing starts (5d00d70), the pit lane (61574c7), replays (de1a796) and CCE's demos (016c51f).

  What's known: CCE picks the ending's script at RACE.BIN 06030742, after the reset at 0603072A. The table is 0604F218 for courses 0, 1 and 4, and 0604F2B0 for courses 2 and 3. Nobody has traced it.

  Simplest fix: give the ending CCE's camera whole, as replays have (patches/camera.s, setup_select and chase_select). DUSA's own victory lane is the bigger plan; see Planned.
- **Replays:**
  - Nobody has watched a real replay (not a forced one) since de1a796.
  - The pit lane sets DUSA's lens, 0xA0, in replays too (06038252, 06038378).

  See docs/conformance.md, "Camera: replays on CCE's camera".

## Two-player

- **The car flickers on player 2's screen.** The user saw it on 2026-11-10, in the first 2P test on the Saturn. Known so far:
  - **Our VDP1 measures mostly stay off in 2P.** The race-time cut and the effects drawn last are 1P only (src/vdp1x.c). Only the turned course quads apply, because they're in the course files.
  - **Our 2P cars are heavier than CCE's.** Each is DUSA's full body, 132 faces, against the 47-48 of CCE's 2P cars (docs/two_player.md, "The Gallop in 2P"). Each half of the screen draws both cars.
  - **Why player 2's screen:** probably because VDP1 draws player 2's half last. A frame that runs out of time then loses player 2's nearest polygons first, and those are their own car. Not confirmed yet.
  - **Plain CCE:** nobody knows yet whether it flickers in 2P.

  Next: measure plain CCE and ours in Mednafen over the same 2P race, and play a plain CCE 2P race on the Saturn.

## Handling

- **The AI cars are passive.** tk1sbiglove, 2026-11-09: DUSA's cars crash into each other, hit you and spin, while ours "don't really do anything". Scraping them also slows you more than in DUSA. Not started.
- **Rows 32-36 of the driving-model audit are open** (docs/driving_model.md):
  - the rolling-start handover on Three Seven
  - the flip's length and animation
  - the flip's side rules
  - the grass-climb grip event
  - the bog's halving rate
- **Manual downshifts don't start a drift.** tk1sbiglove, 2026-11-09, who put MT at "about 60%". He played MT on an analog pad, which ran CCE's core on beta.1. Retest with the d-pad in both games first.
- **Corner comparisons are waiting on recordings.** The corners:
  - Three Seven's last left
  - Seaside's green tunnel (right, then right-left)
  - the Seaside turn by the Jeffry statue (floaty to the user; the exact spot isn't found yet)
  - Dinosaur Canyon's last turn

  Plan: the user records DUSA runs in Mednafen, and the same buttons replay in ours. That's the turn-3 method in docs/conformance.md.
- **The Arcade Racer wheel has never been driven.** It has been on DUSA's analog path since f4d9709 (patch 33), but no real or emulated wheel has tried it.

## Sound and music

- **No engine sound in Yaba Sanshiro.** Reported by tk1sbiglove on 2026-11-07. The user confirmed it in Yaba 1.20.46, and it works on the Saturn and in Mednafen. Either fix Yaba (it's open source) or list it as a known issue in the README.
- **Not heard yet** (docs/music.md):
  - the name entry and the 2P result looping Victory Lane
  - the staff roll
  - the goal and ending jingles for each song choice
  - the sound test, in game
- **CCE's tire squeal in DUSA's gaps.** The user wants to try keeping CCE's slide loop where DUSA is silent. Tone 10 (DUSA car +0xB8 = 44) is still unidentified. See docs/tyre_sound.md.

## Presentation

- **Day and night races are untested** with our changes. The Japan CCE has a time-of-day choice for races.
- **Start on DUSA's title fades to black, then loads CCE's menu.** The user wants a crossfade, and it's deferred. Both programs rewrite every VDP2 register, and the menu uses every layer.
- **The Hornet's DUSA/CCE picker is hidden.** Left/right in car select works, but nothing on screen says so. Parked, because there's no place for a hint yet; arrows would clash with car select's own.
- **The hood's nose lettering reads as a red/yellow band when seen edge-on.** The user was offered dropping it from the hood only. See docs/hoods.md.

## Disc builder and release

- **The Linux builder is untested on a real desktop.** Still unchecked: the XDG portal file dialog, Flatpak browsers and snap Firefox. Waiting on the user's SteamOS test.
- **Untracked files in patcher/ui end up in the Windows app.** Tauri embeds the whole folder, so clipart/, sfx/roar_*.mp3 and sfx/thunder_*.mp3 go in too. Settle them before the next release, or move them aside for the build.
- **The release patch is still beta.1's.** The next release has to rerun `make release-patch`. It also has to run both builders end to end on the 43-track disc.

## Planned

- **DUSA's victory lane sequence:** recorded from DUSA and played back the attract's way. The user is about 90% sure it's canned.
- **GAME OVER with DUSA's letter dance,** timed to its jingle. CCE's game over stays until then.
- **The music choice at build time, in the disc builder.** tk1sbiglove asked for it; not decided.
- **Saving the Hornet's DUSA/CCE choice in the backup.** Offered, not yet asked for.

## Fixed, waiting on a check

- **The pit-stop camera under the road:** 61574c7, 2026-11-01. Measured on Three Seven only.
- **Start in the attract's demo goes to DUSA's title:** eb96f25, 2026-10-30.
- **The backup memory's messages in English:** f0ea69c.
- **The 3D pad's analog was too sensitive** (Hassmaschine). Since ec4fe03 the 3D pad drives DUSA's handling, with Stick Lab's stick. No tester has tried it yet.
