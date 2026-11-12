# Open issues

This is the single list of known problems and unfinished work. Every Claude session on this project shares it. The details live in docs/ and in commit messages; this file says what's open and where to look.

- Give each issue one bullet under its area. Say what's wrong, who saw it, where and when, what's known, and what comes next.
- When a fix lands, move the issue to "Fixed, waiting on a check" and give the commit. Once the user has seen it work, move it to "Closed".
- Put work the user has asked for under "Planned", apart from the bugs.

Started 2026-11-10 from one session's notes. Other sessions add theirs.

## Picture

- **The player's car still flickers out in packs of CPU cars (1P).** First reported by Hassmaschine on Discord with beta.1, 2026-11-07 ("pretty random"). The user's Saturn recording of beta.1 (build/flicker_hw/rec1.mkv) caught it at 2:32 on Dinosaur Canyon, sliding onto the grass with sparks: the car and its sparks are gone for 4 frames, then half drawn for 5. The view sits at grass level there, so the camera clipping into the car is a candidate besides VDP1 running out of time. The user saw it again on the Saturn on 2026-11-10, with the build at 121d9a3. It is "way down", but still happens with many CPU cars close by. The race-time cut and the car effects drawn last are both on in 1P. The bar is plain CCE: on the Saturn, plain CCE flashes about 6 times in 70 s of Dinosaur Canyon. Next: find which course and moment, then compare with plain CCE there. See docs/performance.md.
- **Smoke covers the car's rear quarter in side-on spins.** Since 0e8fdcc, 1P races draw the car's smoke and sparks last. When a spin turns the car side-on, the smoke lies over its rear quarter (build/vdp1cost/spin_side.png). The user will judge it in game. See docs/performance.md, "Car effects drawn last".
- **Dropped frames (20 fps) on the Saturn.** Seen in the 2026-11-08 recordings:
  - Three Seven races, on the start/finish and gantry straights every lap. 06cdf4f stops the cut before the frame's deadline, but no Saturn race has been recorded since.
  - The attract's forest shot. This one isn't VDP1: turning brought VDP1 under budget there and the drops stayed.
- **Polygon glitches when rubbing other cars, and on the later tracks.** Reported by OlivusPrime on the Saturn with beta.1, 2026-11-08. PhuketJumboShrimpBro's video showed the track clipping too, in replays as well (Reddit, beta.1, 2026-11-08; nobody here has seen the video). Beta.1 had none of the VDP1 work, and nobody has checked current builds.

## Cameras

- **The victory sequence's camera goes under the road.** Seen three times:
  - Hassmaschine, Seaside, after 2nd place, 2026-11-07.
  - tk1sbiglove, "victory lanes", 2026-11-09.
  - The user, Three Seven, after 1st place, on the Saturn, 2026-11-10.

  It has never been fixed. Its neighbors were: the standing starts (5d00d70), the pit lane (61574c7), replays (de1a796) and CCE's demos (016c51f).

  What's known: CCE picks the ending's script at RACE.BIN 06030742, after the reset at 0603072A. The table is 0604F218 for courses 0, 1 and 4, and 0604F2B0 for courses 2 and 3. Nobody has traced it.

  Simplest fix: give the ending CCE's camera whole, as replays have (patches/camera.s, setup_select and chase_select). DUSA's own victory lane is the bigger plan; see Planned.
- **The pit lane sets DUSA's lens (0xA0) in replays too** (RACE.BIN 06038252, 06038378). Found by reading the code on 2026-11-08, after replays moved to CCE's camera (de1a796). Nobody has seen it on screen; the view would change while the car is in the pit lane. Next: watch a replay with a pit stop in it. See docs/conformance.md, "Camera: replays on CCE's camera".

## Two-player

- **The car flickers on player 2's screen.** The user saw it on 2026-11-10, in the first 2P test on the Saturn. Known so far:
  - **Our VDP1 measures mostly stay off in 2P.** The race-time cut and the effects drawn last are 1P only (src/vdp1x.c). Only the turned course quads apply, because they're in the course files.
  - **Our 2P cars are heavier than CCE's.** Each is DUSA's full body, 132 faces, against the 47-48 of CCE's 2P cars (docs/two_player.md, "The Gallop in 2P"). Each half of the screen draws both cars.
  - **Why player 2's screen:** probably because VDP1 draws player 2's half last. A frame that runs out of time then loses player 2's nearest polygons first, and those are their own car. Not confirmed yet.
  - **Plain CCE:** nobody knows yet whether it flickers in 2P.

  Next: measure plain CCE and ours in Mednafen over the same 2P race, and play a plain CCE 2P race on the Saturn.
- **Nobody has looked at the window reflection since it moved.** To make room for the replay camera, reflect_2p moved out of RACE.BIN into a race block in SCREEN.BIN (de1a796), then down to 06018800 (186d5fd). Mednafen showed it running for both players after the first move; the final move was checked by reading the code. The user's 2P test on the Saturn on 2026-11-10 (121d9a3) ran with it, but the reflection wasn't on the list to look at. Next: look at both cars' windows in a 2P race. See docs/two_player.md.

## Handling

- **The AI cars are passive.** tk1sbiglove, 2026-11-09: DUSA's cars crash into each other, hit you and spin, while ours "don't really do anything". Scraping them also slows you more than in DUSA. Seen in the fast-start recordings too (2026-11-09): DUSA's car ahead blocks its player about 2.3 s after GO, where CCE's cars pull away. Not started.
- **Rows 32-36 of the driving-model audit are open** (docs/driving_model.md):
  - the rolling-start handover on Three Seven
  - the flip's length and animation
  - the flip's side rules
  - the grass-climb grip event
  - the bog's halving rate
- **Manual downshifts don't start a drift.** tk1sbiglove (Reddit, 2026-11-09) put MT at "about 60%" of DUSA:
  - A downshift doesn't start a drift; you have to brake, where DUSA doesn't need it.
  - Dropping to 1st or 2nd skids and scrubs speed, instead of holding high revs through the drift.
  - Gears 1 and 2 are never needed, except Seaside's last corner.
  - On 2026-11-07 he'd said "70% OG, 30% CCE", that drifts engaged inconsistently, and that 3rd alone takes the Sonic-wall turn.

  He played MT on an analog pad (Yaba Sanshiro on a Retroid Pocket 6), which ran CCE's core on beta.1. Retest with the d-pad in both games first.
- **Corner comparisons are waiting on recordings.** The corners:
  - Three Seven's last left (PhuketJumboShrimpBro means to compare it with '95)
  - Seaside's green tunnel, right then right-left (PhuketJumboShrimpBro, the same)
  - the Seaside turn by the Jeffry statue (floaty to the user on the Saturn, 2026-11-08; the exact spot isn't found yet)
  - Dinosaur Canyon's last turn (PhuketJumboShrimpBro found power slides there "a little weird"; the user said it "maybe feels better" after the surfaces fix)

  PhuketJumboShrimpBro played beta.1 in AT on the 3D pad's analog, so his notes describe CCE's core, not ours. He also said the slipperiness is close to '95 and power sliding "can be dialed in more". Plan: the user records DUSA runs in Mednafen, and the same buttons replay in ours. That's the turn-3 method in docs/conformance.md.
- **The Arcade Racer wheel has never been driven.** It has been on DUSA's analog path since f4d9709 (patch 33), but no real or emulated wheel has tried it.
  - OlivusPrime plays an official Arcade Racer on the Saturn and found beta.1 "pretty close" to the original on it (Reddit, 2026-11-08). Beta.1 ran CCE's whole wheel path, so f4d9709 will feel different to him: full lock now comes at 63% of the wheel's turn instead of 38%. Ask him to retest.
  - Not known: which button brakes with CCE's wheel layout. The debugger can only fake the wheel with a digital pad; that found gas on B and C and gear changes on the paddles, but no brake.
  - The user can try a G29 through Mednafen's emulated wheel (ss.input.port1 wheel).
- **The 3D pad's triggers set the pedal at once while racing.** That's CCE's way; DUSA has no triggers. On the grid they step at DUSA's button rates since 5e6f2eb. Not decided: step them at DUSA's rates while racing too.
- **The analog triggers didn't work in Yaba Sanshiro.** tk1sbiglove, Reddit, 2026-11-07, on an Xbox Series X pad (Windows 11, the disc as CHD). He later played Yaba on a Retroid Pocket 6 with the triggers working, so it's probably Yaba's controller setup (its 3D pad mode). Next: find the Yaba setting and put it in the README.

## Sound and music

- **No engine sound in Yaba Sanshiro.** Reported by tk1sbiglove on 2026-11-07. The user confirmed it in Yaba 1.20.46, and it works on the Saturn and in Mednafen. Either fix Yaba (it's open source) or list it as a known issue in the README.
- **The start woosh has no reverb.** DUSA's woosh has a reverb tail 2-4 dB louder than ours; 71bcd9e sends ours dry. Found while matching it on 2026-11-09. See docs/tyre_sound.md, "The start woosh".
- **CCE's tire squeal in DUSA's gaps.** The user wants to try keeping CCE's slide loop where DUSA is silent. Tone 10 (DUSA car +0xB8 = 44) is still unidentified. See docs/tyre_sound.md.

## Presentation

- **Day and night races are untested** with our changes. The Japan CCE has a time-of-day choice for races.
- **Start on DUSA's title fades to black, then loads CCE's menu.** The user wants a crossfade, and it's deferred. Both programs rewrite every VDP2 register, and the menu uses every layer.
- **The Hornet's DUSA/CCE picker is hidden.** Left/right in car select works, but nothing on screen says so. Parked, because there's no place for a hint yet; arrows would clash with car select's own.
- **The hood's nose lettering reads as a red/yellow band when seen edge-on.** The user was offered dropping it from the hood only. See docs/hoods.md.

## Disc builder and release

- **The Linux builder is untested on a real desktop.** Still unchecked: the XDG portal file dialog, Flatpak browsers and snap Firefox. Waiting on the user's SteamOS test.
- **Untracked files in patcher/ui end up in the Windows app.** Tauri embeds the whole folder, so clipart/, sfx/roar_*.mp3 and sfx/thunder_*.mp3 go in too. Settle them before the next release, or move them aside for the build.
- **The release patch is still beta.1's.** The next release has to rerun `make release-patch`. It also has to run both builders end to end on the 43-track disc. Since 080b73d make_release_patch takes any of DUSA's tracks, and it built a patch with all five DUSA rips on 2026-11-08; neither builder has run with it.

## Planned

- **DUSA's victory lane sequence,** recorded from DUSA and played back the attract's way. The user is about 90% sure it's canned (2026-11-08): one fixed sequence under the announcer's "Welcome to victory lane!", whatever place you finished. DUSA runs it on a 1000-tick timer with the course's ending (DUSA tracks 14-16). Not decided: what the non-'95 choices' endings show. Since d9fb24c the '95 choices run CCE's ending scene for their songs' length (1000, 1110 and 1090 ticks; 1090 for Pounding Pavement '95). This would also replace the camera that goes under the road (see Cameras). Item 7 of the music95 docket.
- **GAME OVER with DUSA's letter dance,** timed to its jingle (DUSA track 18, started at APROG 06017106). The user, 2026-11-08: the jingle must not come without the dance, or "fans will riot". Plan: record the dance from DUSA, attract-style. Until then CCE's game over and Lack of Speed (track 20) stay. The jingle would take track 20's place on the disc (1:46 is left on an 80-minute CD-R), and Lack of Speed's name in the sound test (about 57 chars against its 43; 64 are free on the Sound page). Item 6 of the music95 docket.
- **The music choice at build time, in the disc builder.** tk1sbiglove asked for it; not decided.
- **Saving the Hornet's DUSA/CCE choice in the backup.** Offered, not yet asked for.
- **Victory Lane at the name entry, polished.** DUSA's David Goes To Victory Lane is short because DUSA's name entry ends on a 600-tick timer just as the song ends. CCE's name entry and 2P result have no such timer, so the song loops (080b73d). The user asked for the simple loop first (2026-11-08) and may want it polished.
- **Start Your Engines and Wait Coin: pinned** (the user, 2026-11-08). DUSA's menu songs are timed to its car and course select timers, so they'd loop awkwardly, and they'd pull in more of DUSA's screens.
- **Silver Ocean Causeway: no source.** tk1sbiglove asked about the "PC-exclusive CCE track" (Reddit, 2026-11-09). It's only in Daytona USA Deluxe for Windows (1997); no Saturn disc has it, so the builder has nothing to take it from.
- **Western CCE's songs: shelved.** OlivusPrime on Reddit, 2026-11-07: western CCE plays Funk Fair on National Park and Noisy Roars on Desert City, where the Japan disc has Noisy Roars and the Pounding Pavement remix. Funk Fair and Race to the Bass are only on the western discs, so the builder would need the player's western CCE as a third disc. The user shelved it on 2026-11-08, "in our back pocket". Room: Funk Fair with its jingles runs 5.3 minutes and Race to the Bass 4.9, against the 1:46 left on an 80-minute CD-R.

## Fixed, waiting on a check

- **The pit-stop camera under the road:** 61574c7, 2026-11-01. Measured on Three Seven only.
- **The standing starts' camera under the road** on Dinosaur Canyon and Seaside (Hassmaschine, Discord, 2026-11-07; probably OlivusPrime's "buggy starting cameras" too, Reddit, 2026-11-08). 5d00d70: the scripts played with the camera at our chase height while the blend assumed CCE's. Checked every frame in Mednafen against CCE; no tester has seen it since.
- **Start at course select also confirmed car select** (Hassmaschine, 2026-11-07). 5b7177c: Start now confirms one step per press, like A and C.
- **Dinosaur Canyon's tunnel had its shade and echo only in places** (Hassmaschine, 2026-11-07). 2d44928: the roof pieces keep CCE's outline on DUSA's ground. The echo itself stays as CCE has it (the user's call, 2026-11-07).
- **Touching a car mid-drift ended the slide and threw you forward** (OlivusPrime on the Saturn and tk1sbiglove, Reddit, 2026-11-07; tk1sbiglove blamed most of what AT lacks on it, 2026-11-09). CCE's contact set an impact timer that halves the slip every tick; DUSA's never does. Patch 27 (90727eb), on main since 317bb9d. Checked with breakpoint logs. The user drove the branch's disc on the Saturn on 2026-11-08, but contact wasn't on the list.
- **No gear changes or steering during a crash** (tk1sbiglove, 2026-11-09: '95 lets you shift). 3a8410e (patch 29): CCE zeroed the pad while the flip count was 32 or more. The pedals still hold through a crash, as in both games.
- **Uma's car-select picture was glitched** (tk1sbiglove, on Yaba Sanshiro, 2026-11-09). d83436c: the horses' picture cases skipped our palette restore.
- **The fast start** (PhuketJumboShrimpBro, Reddit, beta.1, 2026-11-08):
  - A grinding sound on the start line with gas and brake held: DUSA's brake squeal keyed on the grid. 3b0088f.
  - CCE's grid pedals moved three times as fast as DUSA's, so the fast-start window was in the wrong place. 4def1fd (patch 28), and 5e6f2eb for the analog triggers. Every measured launch matches DUSA in Mednafen.
  - DUSA's start woosh was missing (the user, 2026-11-09). 71bcd9e; its reverb is under Sound.

  The user has side-by-side recordings and the how-to (docs/conformance.md, "Patch 28"), and hasn't tried the trick yet.
- **Driving-model fixes with no feel test yet.** From the testers' handling reports and the per-tick audit: walls, surfaces and per-car traits (a1ba55a, 5b10670, ed48e94; the user drove them on the Saturn on 2026-11-08), then the spin-out speed loss, wheel re-centering, slipstream, automatic upshifts and top speed (8483f00), and the grip-loss countdown (695fbe3). Each was checked against DUSA's code, and the upshifts in Mednafen.
- **Start in the attract's demo goes to DUSA's title:** eb96f25, 2026-10-30.
- **The backup memory's messages in English:** f0ea69c.
- **The 3D pad's analog was too sensitive** (Hassmaschine, Discord, beta.1, 2026-11-07). Since ec4fe03 the 3D pad drives DUSA's handling, with Stick Lab's stick. No tester has tried it yet, and the Stick Lab disc (52f0499, `make stickviz`) hasn't been on the Saturn.
- **Replays' camera under the ground, a hall of mirrors** (the user, 2026-11-08; tk1sbiglove saw the camera go through the floor in replays too, 2026-11-09). de1a796: a replay takes CCE's camera whole, as 2P does, and B gets CCE's own chase. Checked in Mednafen with a forced replay. The user watched one real replay in Mednafen after a Three Seven race on 2026-11-08 and saw nothing wrong. Still to do together: all three views (A trackside, B chase, C overhead), and a replay on the Saturn. The pit-lane lens is under Cameras.
- **The rest of the '95 music** (080b73d, d9fb24c, 417e45d, 49e487e; docs/music.md). The user has heard a Three Seven race through, with its replay. Still to hear:
  - the other songs' goal jingles and endings, checked only in the tables
  - the name entry and the 2P result looping Victory Lane (no code change: they play track 21)
  - the staff roll playing Pounding Pavement '95 once
  - an Endurance race rolling through the chosen version's songs, checked in Mednafen
  - the sound test's 40 entries in game, checked in Mednafen; the user approved the lettering on a sheet
  - a beta.1 save, whose "(original)" choices should now play '95; nobody has loaded one

## Closed

The user has seen these work.

- **The race music was CCE's take on the arcade songs, not '95's.** fafling and manofstone17 on Discord, 2026-11-07. CCE's "(original)" tracks 23-25 are CCE's own recordings of the arcade arrangements, not DUSA's. Since 080b73d and d9fb24c the '95 songs, their goals and their endings are on the disc (tracks 34-43, with 19 and 22 for Pounding Pavement '95), they're the defaults on DUSA's three courses, and the arcade originals and CCE's remixes are choices. The user heard a Three Seven race on 2026-11-08: "everything sounded great".
- **The replay played The American Dream,** a CCE track that doesn't fit (the user, 2026-11-08). Replays and the staff roll play Pounding Pavement '95 since 080b73d. The user heard it in a replay on 2026-11-08: "a decent pick for replay but we'll see what fans say."
- **The game crashed to the Saturn's OS screen after a race** (the user, Mednafen, 2026-11-08, on the music95 branch). The new race block at 06019700 overwrote the main program's code that runs between races (060191A8 on). 186d5fd moved it to 06018800, in the main program's empty stretch. The user's next race finished fine the same day.
- **The band-clear skip limited to the race proper** (7417f79, to hide the replay camera's hall of mirrors) was reverted in 0959c3b at the user's request: the skip stays everywhere, and the replay camera was fixed instead (de1a796).
- **The sound test's new names looked cut out** (the user's review of the proposal sheets, 2026-11-08): neighbors' pixels, the A's crossbar in the V, a boxy outline, the A's tail on the V. The third sheet cut only each letter's own ink, learned the outline from CCE's own names and gave the V a point. The user approved it, and it went in with 49e487e.
