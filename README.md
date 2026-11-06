

https://github.com/user-attachments/assets/efa8b612-5a3d-4eed-aaa9-9d564f8baff2

# Daytona USA Ultimate

<p align="center"><img src="patcher/ui/art/ultimate.jpg" alt="Daytona USA Ultimate cover" width="480"></p>

This is a mod of Daytona USA Circuit Edition for the Sega Saturn. It keeps
Circuit Edition's five courses and two-player mode, and swaps in the
handling, car, road surface and sounds from the original Saturn Daytona USA.

**This is a beta.** The mod is complete and you can play all of it, but some
parts haven't had much testing. The [beta notes](#beta-notes) say which.

No game data is included. You build the disc yourself from your own copies
of both games, using the disc builder described under
[Getting it](#getting-it).

## What's different

### Handling and camera

The car drives just like it does in Daytona USA, and the camera follows it
the same way! Watch all three games take turn 3 of Three Seven Speedway
with the exact same button presses, from the same spot at the same speed.
Ultimate slides through on Daytona USA's line, while Circuit Edition's car
runs wide and smacks the wall.

![The same inputs through turn 3: Circuit Edition, Ultimate and Daytona USA](docs/readme/handling.webp)

### Cars

All eight cars now race with the classic Daytona USA body! The Hornet keeps
its original paint, and the other seven get brand new liveries in the
Daytona USA style, inspired by their Circuit Edition looks. Pick automatic
or manual and you get a different paint job, for 14 new liveries in all!
You'll see them in car select, on the name entry screen and from the in-car
view too.

![Car select: Circuit Edition's cars above, Ultimate's below](docs/readme/cars.png)

### Road surface

No more rocking through the banked turns! Circuit Edition rebuilt its
banking out of small patches that don't line up, and the car rocks back and
forth as it crosses them. Ultimate drives on Daytona USA's ground on the
three original courses, and Circuit Edition's two extra courses get all-new
ground built the same way. The track looks the same as ever, but you'll
feel it in the banking!

![Turn 1's ground in both games, and how far the car leans on it](docs/readme/road_surface.png)

### Engine and tire sounds

It sounds like Daytona USA too! The engine and the tire squeal are the ones
you remember from the original. Hear them through turn 3 again, with the
music, crowd and announcer muted so nothing gets in the way. Circuit
Edition goes first, then Ultimate, then Daytona USA. Turn your sound on for
this one!

https://github.com/user-attachments/assets/2fed5d19-1d48-43ca-b55b-60a1d5fdcb87

### Attract mode and title screen

Daytona USA's title screen is back, and so is its attract mode! Leave the
game alone and the original demo plays, song and camera work included,
across all three of Daytona USA's courses. You can switch back to Circuit
Edition's attract mode any time with Options > Sound > ATTRACT.

https://github.com/user-attachments/assets/d05e6607-a084-4dff-b7e8-08b329be97cb

![The title screen: Circuit Edition's and Ultimate's](docs/readme/title.png)

### Circuit Edition's cars are still there

In car select, press left or right on any of the eight cars to swap between
Ultimate's version and the Circuit Edition original, model and paint
together. Race whichever one you like!

![Car select: left and right on the Hornet](docs/readme/hornet.webp)

### Also!

- Two-player supported!
- Circuit Edition's handling option applied to Daytona USA's driving model,
  for never before seen car handling options!
- The disc is region free and boots on any Saturn.

## Getting it

1. Download the disc builder from [Releases](https://github.com/AJBats/daytona-cce95/releases).
   It's a Windows program.
2. Rip your two discs to .cue/.bin. The builder also takes a .zip of a rip.
   - **Daytona USA - Circuit Edition (Japan)**, GS-9100. It has to be this
     release, the one that lets you choose the time of day. No other
     version of Circuit Edition will work, and that includes Championship
     Circuit Edition from the US and Europe.
   - **Daytona USA**, the original Saturn release. The USA, European and
     Japanese discs all work.

   The builder checks every track against known-good rips of the retail
   discs, and it will refuse a rip that's off by a few samples. To get one
   that passes, use a ripper that corrects for your drive's read offset,
   such as redumper or DiscImageCreator.
3. Run the builder. Click each cover to pick the rip for that game, or drop
   the files on the window, then press COMBINE.
4. The disc is written to a `Daytona USA Ultimate` folder next to the
   builder, as a .cue file and its tracks. You can play it in an emulator,
   or on a real Saturn with an ODE such as the Satiator.

## Beta notes

- I've tested it on a real Saturn with a Satiator. I haven't tried other
  ODEs, the Saroo or a burned disc.
- It will boot on a PAL Saturn, but the game is made for 60 Hz and will
  probably run slow at 50 Hz. I haven't tested that either.

If you run into a problem, please open an issue.

## Building from source

You need Python 3 and `make`.

1. Put rips of your two discs in `external_resources/`, each with its .cue
   and all of its tracks:
   - `Daytona USA (USA)/Daytona USA (USA).cue`
   - `Daytona USA - Circuit Edition (Japan)/Daytona USA - Circuit Edition (Japan).cue`
2. Create the virtual environment with `python3 -m venv .venv`, then
   install the packages with
   `.venv/bin/pip install numpy pillow opencv-python-headless`
   (`.venv\Scripts\pip` on Windows).
3. Run `make disc`. The disc comes out at `build/disc/cce.cue`.

The liveries are drawn with fonts that come with Windows (Impact, Arial
Black, Franklin Gothic Heavy Italic and Segoe UI), so the disc has to be
built on Windows.

`make release` builds the disc builder, with the patch from the disc you
just built inside it. The builder lives in `patcher/` and is a Tauri app,
so you need Rust for this step. If you want it to accept Daytona USA discs
from the other regions too, put zipped rips of them in
`external_resources/dusa_dumps/`, and replace the spaces in their file
names with underscores.

## What's in the repo

- `patches/`: one byte patch per change, each with a header that explains it
- `tools/`: the patching, disc building and analysis tools
- `docs/`: how the driving code works in both games, and how each patch
  was tested
- `patcher/`: the disc builder
