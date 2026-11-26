# Code caves and free memory

A code cave is space in one of CCE's programs that a patch takes for its
own code or data because CCE no longer uses it: a dead function, or a
function our patches have bypassed. A cave is only safe if nothing that
still runs reaches into it. This page explains how that went wrong, how the
build now checks it, and how to find space safely.

## What went wrong

The old test for a cave was "nothing branches to it or points at it". On
the SH-2 that misses three ways in:

- **Shared literal pools.** The compiler puts one pool of 32-bit constants
  after a group of functions, and every function in the group loads from it
  with `mov.l @(disp,PC)`. When the last function is dead, the pool after
  it can still be live, because its live neighbours read from it.
- **Pointers.** A function can be live through its address alone: a task
  another function starts, an entry in a table of handlers, a case in a
  `jmp` through a table of addresses. If the pointer itself sits inside the
  "dead" range, a check that skips the range never sees it.
- **Tables reached with `mova`.** Switch tables (`braf`, `bsrf`) and data
  tables have no pointer to each entry. A patch over the tail of a table
  breaks the cases it doesn't see.

Each instance found (2026-11-25):

- **0602C92A-0602CA13**, used by patches/sector_fallback.s and
  patches/car_choice.s. The "dead" function is the two-player delay task
  that 0602C7C4 starts, and its pool (0602C99C-0602CA07) is shared with
  0602C764, 0602C7C4 and 0602C854. As a result:
  - 06051BA4, the race-state byte CCE sets at each sector-4 crossing,
    stayed 0.
  - The two-player DELAY countdown read garbage addresses and could crash.
- **060375D0**, in patches/grid_pedals.s's rewrite of the grid pedal
  functions. The gear keys' step before them (06037580) loaded the GEAR 1
  key's offset, 0x1C, from their pool. With a manual gearbox and direct
  gear keys, the GEAR 1 test read a garbage address.
- **0603E64C-0603E653**, in patches/car_job.s's use of the slave's copy of
  the car draw. The routine both CPUs now run loads two flags' addresses
  from there (0603E5D6, 0603E5D8). It got code bytes instead, so the
  per-car step 0603EE48 never ran. That step advances the car's +22/+24
  words, which the draw copies. It only runs when 06052A05 is set, which
  wasn't the case in a 1P Arcade race. The header also called
  0603E654-0603E683 free, but 0603E654-0603E65B are live too.
- **0603E448-0603E453**, earlier (docs/performance.md): patches/vdp1x.s's
  cave covered literals the live AI code loads. A longer stub there froze
  the attract.

All four were fixed:

- sector_fallback's code and car_choice's TEX load moved to 0603C6A0, a
  function nothing reaches.
- 06037580 takes 0x1C as an immediate (`mov #28`).
- car_job's literals avoid 0603E64C-0603E65B.
- vdp1x's cave stops before 0603E448.

Every cave in the SH-2 programs, 56 declared with the moved ones, now
passes the check below.
A hand scan of the sound driver (SDDRVS.TSK) found no 68000 code reading
the bytes our driver patches change. One branch lands on a hook
tyre_sound_drv.s made on purpose: 19EA branches to the `bsr` at 1A0A.

## The check: tools/cave_check.py

`make disc` runs `cave_check.py check extracted/cce build/cce_files` before
it makes the disc, and stops on a finding. For each SH-2 program a patch
changes (DAYTONA/0, RACE.BIN, SLCT.BIN, NAME.BIN, BKUP.BIN, RESULT2P.BIN),
it compares the shipped bytes with CCE's.

**Live code** is found statically, so rare paths count as much as common
ones: two-player options, manual-gear keys, link races. The check traces
every path of every reached function, starting from:

- the program's entry;
- `bsr` targets, and `jsr` or `jmp` through a literal, plus any `add #n`
  after it;
- switch tables reached by `mova` with `braf` or `bsrf`, bounded by their
  compare, or read until the cases end;
- `jmp` through a table of code addresses;
- literals whose value is code and isn't used as a data address;
- aligned words anywhere that point at code;
- addresses that other programs name: the overlays naming DAYTONA/0, and
  our own blocks (the attract, the VDP1 pass, the crash screen, the race
  block) naming CCE's functions.

The shipped program is traced twice: as it ships, and as the attract's CCE
choice puts some of CCE's bytes back at run time (title_convert.py's
CCE_SWITCH). Code live in either trace counts as live.

Checked against Mednafen's code log over two laps of Three Seven: every
instruction that ran in RACE.BIN is in the trace. That is 16,013 in plain
CCE and 16,152 in ours.

**Rules.** The build fails when live code that we left unchanged:

1. reaches into a declared cave. That means loading a literal there,
   branching there (directly, or through a literal or table entry we left
   alone), holding a pointer there, falling through into it, or being named
   there by another of CCE's programs;
2. loads a literal whose bytes a patch changed, where the change is more
   than literals. That is a pool under new code. A patch line made only of
   loaded literals is a deliberate tuning or repointed call and passes; 151
   do;
3. would run our code placed where CCE's own trace finds dead code, with no
   `.cave` declaring that space. A new cave has to be declared so that
   rule 1 covers it.

**Declaring a cave.** Put `.cave <first> <last>` in the patch's .s,
inclusive, next to the `.org` it covers. tools/mkpatch.py writes it into
the .patch as `#!cave <disc path> <first> <last>`; a hand-written .patch
writes that line itself. Declare the space the patch claims. Bytes inside
it that must stay CCE's (a live literal) split it into two caves; see
car_job.s and grip_filter.s.

## Finding space for new code

1. `cave_check.py free extracted/cce build/cce_files DAYTONA/RACE.BIN 64`
   lists whole functions, or runs of zeros, that:
   - neither CCE's program nor ours executes or loads;
   - nothing points into;
   - no patch writes.

   Add Mednafen code-log dumps (`cdl_start 06000000 06100000`, play, then
   `cdl_dump x.cdl`) taken while that program was loaded. Anything they saw
   run or read is then left out too.
2. `cave_check.py refs extracted/cce build/cce_files DAYTONA/RACE.BIN
   <first> <last>` lists everything in either program that reaches into a
   range.
3. Read the function. Then declare the cave with `.cave` and build. The
   check covers the whole declared range from then on, including the part
   still unused.

## What it doesn't cover

- **RAM.** Space our code takes in work RAM, VRAM and sound RAM isn't in any
  file, so this check can't see it. An inventory (2026-11-25) graded each
  claim by its evidence. These rest on the least:
  - RESULT2P.BIN's tail at 0609B000, with the zero padding the bigger file
    now writes over 06099E20-0609AFFF.
  - The name-entry and two-player result buffers at 00279000-00288FFF.
  - National Park's second VDP1 run for the VDP1 pass. It is never checked
    at run time.
  - The tyre mailboxes at sound RAM 6F10-6F14 and 6F30-6F34.
  - 002FC3A9-002FC3AB, found only by a search for literals.
  - 06015140-060191A7, under the VDP1 pass, the race block and the crash
    screen. No measurement covered Link, XBAND, Time Attack, Endurance or
    the records, ranking or ending screens.
  - Options' characters in VDP2 VRAM. A sibling claim on the Sound page was
    already wrong (GitHub #13).

  A code log of plain CCE (cdl_start on 06000000 or 00200000) through each
  mode would settle them.
- **Data inside the programs.** Rule 1 only sees tables reached through a
  literal or `mova`. A table read through a pointer CCE builds at run time
  wouldn't show.
- **The sound driver.** It is 68000 code, and only a hand scan covers it.
