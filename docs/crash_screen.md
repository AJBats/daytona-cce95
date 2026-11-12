# The crash screen

Players had nothing to report but "it crashed" (GitHub #4). Since
2026-11-12 a crash shows a screen to photograph, after Tomb Raider
Saturn's. The code is src/crash.c and src/crash_entry.s, built by
tools/crash.py into DAYTONA/CRASH.BIN; patches/crash.s loads it at boot.

## What it catches

| Colour | When |
|---|---|
| Red | The main CPU took an exception: an illegal instruction, one in a delay slot, an address error or a DMA address error (vectors 4, 6, 9, 10). |
| Magenta | The second CPU took one of the same. It stops, and the main CPU's next VBlank draws the screen from the second CPU's stack. |
| Blue | The game stood still: CCE's main loop count (06011F84) didn't move for 600 VBlanks (10 s at 60 Hz) while no file was loading (06011FB8 is 0 through every load). |

The longest stand-still measured in Mednafen is 10 VBlanks. That covers boot, all of the attract, the menus, a 1P race with a pause, a time-out, the results, and a 2P race with its pause and exit. The game pauses through the main loop, so a pause never counts.

Not caught:
- a reset to the Saturn's own menu: the BIOS has taken over, so nothing of ours runs
- a hang with VBlank-IN interrupts stopped or masked, since the watchdog lives in VBlank-IN
- the sound CPU

The screen replaces CCE's own handlers for vectors 4 and 9 (0600735C). Those printed a line of text on whatever layer was up, then returned to the same fault. CCE also set vector 5 for "ILLEGAL SLOT", a vector the SH-2 never uses.

## Reading a photo

```
DAYTONA USA ULTIMATE CRASHED.
PLEASE TAKE A PHOTO OF THIS SCREEN
FOR GITHUB.COM/AJBATS/DAYTONA-CCE95
1.0.0-BETA.2 1A2B3C4                <- version (patcher/src-tauri/Cargo.toml) and commit, + if the tree had changes
MAIN CPU: ADDRESS ERROR             <- or 2ND CPU: ..., or FROZE FOR 10 S
GAME pp mm cc dd rr tttttttt        <- program (06019A21), game mode (002FC233), course (06054920),
                                       attract demo (0601335C), replay (06054923), main loop count
PC ........ PR ........ GB ........
SR ........ SP ........             <- SP as it was before the exception
R0  ........ ........ ........      <- R0-R14
...
CALLS ........ ........ ........    <- code addresses on the stack, nearest first
```

- **For an exception,** PC is the faulting instruction, or close to it for an address error.
- **For a freeze,** PC and the registers are where the main CPU was standing when VBlank-IN interrupted it.
- **The calls** are every stack word that looks like a code address:
  - 06004000-0605FFFF: CCE's programs and our blocks
  - 00242300-0024FFFF: src/menu_title.c
  - 002E2780-002EFFFF: src/attract.c

  Each is either a saved return address, so a caller, or a stale value, so take them as leads. A routine saves PR before it calls on, so the first address is usually the faulting routine's caller.
- **Which program a PC is in:**
  - 06005200-06019A1F: the kernel (DAYTONA/0)
  - 06028000 and up: the overlay that's loaded; the program byte says which, and RACE.BIN is the race
  - 06015140-0601641B: tools/vdp1x.py's block
  - 06018700-06018993: tools/race_block.py's block
  - 06018A00-060191A7: the crash screen itself

## Where it lives

- **CRASH_AT = 06018A00, up to 060191A8.** This is in the zeros the main program's image carries before its code at 060191A8. The race block sits below it, from 06018700, after vdp1x's work areas.
  - A canary through the attract, the menus, Options with a save, a 1P and a 2P race found nothing else writing 06018A94-060191A8.
  - The old race block's stretch, from 06018A00, is ours now that the block has moved.
- **Room: 1960 bytes.** The blob is about 1900, which is why the font is 3 x 5 and the text a template. CCE clears this stretch at boot, so the blob can't come with the main program.
- **Loading.** patches/crash.s hooks CCE's init call (0600521A) from a dead load routine at 06005950. The steps:
  1. It runs the init, then reads CRASH.BIN through the kernel's load (060058B4) into 00200000. The init has just cleared that memory, and it is the replay buffer later.
  2. It copies the blob to CRASH_AT and clears the scratch again.
  3. It purges the blob's cache lines and calls crash_init.
  4. crash_init writes the master's vectors (VBR 06000000) and the slave's (06000400, cache-through), and puts crash_vbl_entry in front of CCE's VBlank-IN (06005568). The attract's and the title's VBlank handlers chain in front of it and give it back.

## Testing it in Mednafen

Force each kind of crash from a state in the attract:
- **Red:** poke `FF FF` at 0600529E, the main loop's count.
- **Blue:** poke `AF FE` there, a branch to itself.
- **Magenta:** 06045BDC is run by both CPUs, so the main CPU drew red first. Instead, poke crash_slave (the second word, then the first, from `tools/crash.py`'s printout) with a vector and a stack address.

**Boot in one run.** Stepping a boot 300 frames at a time hung it at the trademark screen, at main loop count 382 with VBlank-IN dead. That happened on discs with and without the crash screen. The same disc passed booting in one run, or with a pause at 1200: it's the debugger's pauses.
