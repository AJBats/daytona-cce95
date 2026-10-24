# Sound lab: DUSA's car sounds, part by part

A live debugger setup that plays one part of the car sound at a time, with
the music, crowd, narrator and effects off. Built 2026-10-24 to find out,
by ear and from the code, what DUSA's car sound is made of, and then what
CCE95's port is missing or gets wrong. The code side of each part is in
[engine_sound.md](engine_sound.md).

## What each part sounds like (DUSA, Time Lap, Three Seven)

The user's notes from the solos, with what the code says beside them.

| part | heard | code |
|---|---|---|
| L0 | "odd, I would never have called this the main rev": a low-frequency base rev that only kicks in past a certain speed | sample A, the lowest-pitched layer; level near silent at low revs, full from ~4,200 rpm |
| L1 | higher pitch, but empty without the other parts; doesn't kick in until higher revs | sample B, an octave above L0; quiet below ~3,500 rpm, then as loud as L0 |
| L2 | a little engine sound on each gear change, quieter from gear 1 to 3; nothing in 4th | sample C; full from ~2,500 rpm, fades out between ~4,500 and ~5,600 rpm, so each upshift drops the revs back into it |
| L3 | the top end | sample A an octave up; audible from ~6,000 rpm to the limiter |
| L4-5 (idle) | cuts off quickly as you gain speed; comes back as the revs fall to idle, even following the 2-to-1 downshift hiccup, just barely | sample D, two detuned copies; alone only at v 1 (stopped or crawling), fading out by ~4,400 rpm |
| slip | only while the tyres slide, pitching up the more they slide | channel 1, slip level 1-7 from car +0x5C |
| brake | what it says on the tin: no amount of gentle braking avoided it, 1:1 with braking | channel 2, brake pedal > 200 of 255 while moving; on the keyboard the pedal is 0 or 255, so every press counts |
| peel-out | an entry sound and an exit sound; also fires on braking | tone 16, from the wheelspin timer car +0x166 |

Before the solos, from the full mix: the idle seemed to start only once the
car had stopped (the code agrees: below ~1,880 rpm every rev layer is off
and the idle plays alone), and when Mednafen's sound glitched a second rev
could be heard layered on the main one (L1 and L3 are both a second rev).

### Peel-out from a dead stop

With every sound on: peel-out entry, then engine only while the tyres
spin, then peel-out exit, then normal driving. The gap is DUSA's own, not
the lab. The exit comes as the tyres finally grip and the rpm starts to
rise for real in 1st, which is expected.

### Slip: port faithfully

The user's call: the slip sound is "a pure win" over CCE's tyre slip
effect, simply better player feedback, and one to port faithfully. It is
its own signal, not braking and not 1:1 with the tyre smoke: it plays
whenever the tyres slide, which can happen apart from either.

### Other sounds met on the way

- Crowd: with the music off, the grandstand crowd on Three Seven loops
  audibly (tone 17).
- Narrator: muted for the solos (program 3).
- Wall hits and scrapes: heard during the L3 solo, but they are sound
  effects, not engine (program 0, wall scrapes tones 19/20, a wall hit
  tone 57).
- Drones (CCE95 Arcade, 2026-10-23): passing drones make only a whoosh, no
  engine sound.

## Earlier comparisons (2026-10-23)

- DUSA's engine in CCE95, first listen: "very similar".
- Vanilla CCE's 1P engine is similar to DUSA's but not the same; the clear
  difference was a low rumble balanced far too loud. CCE95 fixed that ("yup
  that was it"). Possibly CCE95 plays the engine rev a little quieter than
  DUSA: hard to tell.
- Gear changes: no blips heard.
- 2P: vanilla CCE and CCE95 sound the same (CCE95 keeps CCE's 2P engine).
- DUSA's tyre screeches and peel-outs are far richer than CCE's: more
  varied, better feedback about what the wheels are doing, maybe a big
  part of why DUSA feels the way it does.

2026-10-24: something still doesn't sound right with CCE95's engine. That is
what the CCE95 lab is for.

## Emulator caveats

- Mednafen has an old sound bug that fires now and then; when it does,
  DUSA's engine doesn't play right. Restart the emulator.
- build/states/dusa_ta_racing.mcs (saved 2026-10-22) carries that bug.
  At load, SCSP slots 0-2 hold engine layers 0, 1 and 3 keyed off, while
  the driver still counts them as playing. The driver keys a layer on
  only when v enters its range, so from this state only layers 2, 4 and 5
  play until the car has stopped (v 1) and revs up again. The lab's forced
  re-evaluation doesn't change that; it's the same with no lab at all.
  Takes from this state are sound only from the first standstill on.
- build/states/dusa_ta_standing.mcs is clean: the drag take replayed from
  dusa_ta_racing.mcs to frame 1880 (stopped, just before the launch; the
  car struct matches the lab's replay byte for byte), with the timer and
  lap nops but no cave, so they are in its code. At load the idle pair is
  keyed (slots 28-29) and nothing else, as it should be at a standstill.
- Once, mid-lab, Mednafen ran at ~100 fps with no sound at all; another
  restart brought back silence; a cold boot fixed it. A plain boot into
  the attract mode is a quick check that audio works.
- In the lab, pausing the game brings the music back: the lab writes its
  settings each car tick, and the car tick stops while paused.
- DUSA's Time Lap has a countdown like Arcade, and a lap counts on every
  crossing of the line, either way. The lab freezes both.

## The DUSA lab

The debugger's pokes only reach work RAM, so the lab is a code cave the
SH-2 runs each car tick, which writes sound RAM and the SCSP for it.

| piece | where |
|---|---|
| cave | WRAM-L 0029F000: writes each (address, byte) pair of the table at 0029F100 until a zero address, then jumps to 0602F7EA (the car-tick sound routine) |
| hook | call literals 06009254 and 0600DFAC -> 0029F000 |
| resend | poke trigger at 0602F7EA: 0605DF94 = 0, 0605DF98 = 0 (the last engine and slip messages), so they are sent every tick; the table sets 25A04E07 / 25A04E17 = FF (the driver's last v; never 0, or a drop to 0 is ignored and the voice sticks) |
| engine layer k off | 25A04652 + 12k (vmin) = 80; on: 02 05 03 48 01 01 |
| slip / brake off | 25A0469E / 25A046AE = 80; on: 01 |
| a tone off | tone table 25A0322C + 16t + 0xD (attack rate) = 00; on: 1F (tone 16: 0B) |
| music off | 25B00217 = 1F, 25B00237 = 0F (CD-DA level, slots 16/17); on: 9F, 8F |
| timer | nop (0009) at 0600930E |
| laps | nop at 0600D9F0, 0600DB80, 0600DB92; set 06063F24 and 06078B1C to 1 before the first crossing, or the race ends there |

Tone groups: peel-out 16; crowd 17; unidentified 10 (car +0xB8 = 44);
narrator 25-35, 37-60; effects 6-9, 11-15, 18-24, 36.

Re-poke everything after a load_state (the state restores work RAM). To
leave the lab, write every original value, let a tick run, then point
the literals back at 0602F7EA and clear the poke trigger.

## The CCE95 lab

Same idea, on CCE95's car-tick sound routine 06030AFA (RACE.BIN, which
writes rpm, throttle, km/h and gear to 25A06F00 every tick).

| piece | where |
|---|---|
| cave | WRAM-L 00210000 (zero during a race), table at 00210100, then jumps to 06030AFA |
| hook | call literals 060287B4, 06028C3C, 06034338 -> 00210000 |
| engine layer k off | its 35 level bytes, sound RAM 7F007 + 0x80k (one per 256 rpm), all FF; on: the values engine_convert.py wrote |
| music off | 25B00217 = 1F, 25B00237 = 0F; on: DF, CF (CCE plays CD-DA at effect level 6, DUSA at 4) |
| every other sound off | each layer record of tone banks 1 (19900) and 2 (3CE00), 69 in all: +23 (IMXL) and +24 (DISDL/DIPAN) = 0 |

The area map at sound RAM 0500 lists what the race sound file loaded:
tone banks 0 (B000, the engine), 1 (19900) and 2 (3CE00), the engine
tables (type 4, 7F000), and the rest. A tone bank starts with word offsets:
mixer, VL, PEG, PLFO, then one per voice ((mixer - 8) / 2 voices). A voice
is a 4-byte header (byte 2 = layers - 1) and 0x20-byte layer records: +0/+1
note range, +2 slot registers 0-5, +20 LFO, +22 DSP send (ISEL/IMXL), +24
direct send (DISDL/DIPAN, EFSDL/EFPAN).

## Recordings and spectra

tools/soundlab.py does all of the above from the command line: `live` and
`mix` drive the MCP-run emulator, `record` starts its own Mednafen (the
user's settings at sound volume 0, so it is silent but still records),
installs the lab after the state loads, plays an input script and writes a
WAV plus a per-frame trace of the car sound inputs. tools/sound_compare.py
lines the WAV up with the trace (Saturn frames are 1/59.83 s) and compares
DUSA with CCE95 by engine value v.

The sweep both games drive (build/snd/sweep_dusa.txt, sweep_cce.txt; DUSA
pad C = accelerate, B = brake, CCE95 the other way round): from the
rolling start at ~300 km/h, brake for 6 s, idle 2 s, full throttle 17 s,
coast 5 s; no steering, so both cars end up along the wall. States:
build/states/dusa_ta_racing.mcs (Time Lap) and cce95_refl_5000.mcs (Time
Attack, the build before the engine mix change). build/snd/record_all.sh
records L0, L1, L2, L3, idle and the whole engine for both games into
build/snd/wav.

A save state carries the sound RAM it was made with, so a state from
before a sound change plays the old sound. cce95_engine_5000.mcs is the
race at frame 5000 (cce_start_auto_script.txt, fixed clock, no
frameskip) on the build with the engine mix change. It isn't the same
moment as cce95_refl_5000.mcs, which was made with frameskip on, so
takes from the old state don't replay on it.

### Takes: the player's own drive

`soundlab.py play <game> <state>` starts an audible emulator; `take start
<state> [mix]` reloads the state with the lab and logs the buttons; `take
stop <script>` writes them as an input script. `record` then replays the
script frame for frame (fixed clock) in silent emulators, one per part.

- Make takes only in a `play` emulator. The input trace counts drawn
  frames, and an emulator with frameskip on (the MCP one runs the user's
  cfg, `video.frameskip 1`) drops drawn frames under load. Its take then
  replays early from the first dropped frame on, and the replay drives
  into walls the player never touched. soundlab's own emulators run with
  frameskip off, and `take start` refuses the MCP one.
- The first two takes (2026-10-24, build/snd/take_dusa.txt and
  take_cce.txt) were made with frameskip on and lost 1 (DUSA) and 2
  (CCE95) frames before their first button. take_dusa_sync.txt and
  take_cce_sync.txt are shifted by that, and their replays end on the
  exact car position the drives did.
- In DUSA a replay through a pause can depend on the mix. The donut take
  (build/snd/take_dusa_donut.txt) replayed exactly with the take's own mix,
  the engine solo and the peel solo, but the brake solo left the drive at
  the first unpause. So recordings start from a state saved after the
  opening pause, made by replaying the take with the lab in the take's own
  mix and checked against that faithful replay: dusa_donut_1900.mcs and
  take_dusa_donut_1900.txt. Every part replayed from it follows the drive
  to the end. That state has the take's mix in its sound RAM (crowd,
  narrator and sfx muted), so the lab reads them as off and can't turn
  them back on from it.
- Each recording gets its own Mednafen home. Mednafen rewrites its cfg
  on exit, so with a shared home a starting emulator read a half-written
  cfg: an error dialog, or a recording playing out loud.

tools/take_compare.py lines the two drives up on the events they share:
launch (the gas press held longest), lift, brake and stop. Time between
events is stretched, so DUSA's 25.6 s drag and CCE95's 25.2 s drag line up.
It stops at the closing pause (DUSA's lab lets the music back in while
paused), writes take_<part>.png and prints level and spectral centroid per
phase.

The drag-race takes (a standing start held flat for a lap, then hard
braking to a stop), recorded whole in build/snd/drag. CCE95 runs with
`nolp gain3.5`, and cce95_engine_shipped.wav is the build as it is. The
clip_*.wav files are just the drag, from 1 s before the launch to the
closing pause. The first 16.5 s of the DUSA take are bugged (see the
caveat above); the drag starts 32 s in.

| whole engine | DUSA dB | CCE95 dB | DUSA Hz | CCE95 Hz |
|---|---|---|---|---|
| idle, last second before launch | 62.1 | 61.8 | 178 | 182 |
| launch, first 5 s | 63.0 | 63.4 | 1003 | 973 |
| drag, last 5 s | 63.3 | 63.1 | 1208 | 1313 |
| braking to the stop | 62.5 | 62.6 | 758 | 775 |
| stopped | 61.6 | 62.2 | 203 | 177 |

Each layer (L0-L3, idle) is within 1 dB in every phase where it plays,
and the L2 bursts and idle hand-offs land at the same points of the drive.
The rpm curves are the same shape, with two differences:
- DUSA's rpm overshoots to 10,800 in the launch wheelspin and to 9,200
  on the lift, where CCE95 stops at 8,500.
- CCE95 shifts into 4th a little earlier in the drag.
The one spectral difference is the drag centroid, about 100 Hz brighter in
CCE95 (L1 alone: 2294 vs 2413 Hz).
