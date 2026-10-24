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

CCE's own sounds (tyres, collisions, narrator, crowd) are not muted yet.
