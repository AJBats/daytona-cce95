Daytona USA Ultimate disc builder for Linux, version {version}
https://github.com/AJBats/daytona-cce95

Daytona USA Ultimate is a mod of Daytona USA Circuit Edition for the Sega
Saturn. It keeps Circuit Edition's five courses and two-player mode, and
swaps in the handling, car, road surface and sounds from the original
Saturn Daytona USA. This program builds the disc from your own copies of
both games. No game data is included.


WHAT YOU NEED

- A 64-bit (x86-64) Linux PC or a Steam Deck in Desktop Mode. There's
  nothing to install: the builder is a single file.
- A web browser. The builder opens in a window of its own, drawn by your
  browser. It works best with Chrome, Chromium, Edge, Brave, Vivaldi or
  Firefox, installed normally or from Flathub. With any other browser it
  opens as a tab.
- Rips of your two discs, each as a .cue file and its .bin tracks. A .zip
  of a rip works too.
    - Daytona USA - Circuit Edition (Japan), GS-9100. It has to be this
      release, the one that lets you choose the time of day. No other
      version of Circuit Edition will work, and that includes Championship
      Circuit Edition from the US and Europe.
    - Daytona USA, the original Saturn release. The USA, European and
      Japanese discs all work.
  The builder checks every track against known-good rips of the retail
  discs, and it will refuse a rip that's off by a few samples. To get one
  that passes, use a ripper that corrects for your drive's read offset,
  such as redumper.
- About 650 MB of free space for the disc.


HOW TO USE IT

1. Extract this folder somewhere you can save files, like your home
   folder.
2. Open "daytona-usa-ultimate-builder" from your file manager, or run
   ./daytona-usa-ultimate-builder in a terminal.
3. Click each cover to pick the rip for that game, then press COMBINE.
4. The disc is written to a "Daytona USA Ultimate" folder next to the
   builder, as a .cue file and its tracks. You can play it in an emulator,
   or on a real Saturn with an ODE such as the Satiator.

The builder stops when you close its window.


IF IT WON'T START

- Your file manager opens the file as text, or asks what to do with it:
  choose "Run" or "Execute". If it still won't run, right-click it, open
  Properties, and turn on "Allow executing file as program" (or "Is
  executable"). In a terminal: chmod +x daytona-usa-ultimate-builder
- No window appears: run it from a terminal. It prints the address of its
  page, which you can open in any browser on the same computer. If you
  have no browser (a Steam Deck may not come with one), get Chrome or
  Firefox from Discover.
- Clicking a cover asks you to type a path: your desktop has no file
  dialog the builder can use. Type the full path of the .cue or .zip, like
  /home/you/Games/Daytona USA (USA)/Daytona USA (USA).cue
- Without a window at all, the terminal can do the whole job:
    ./daytona-usa-ultimate-builder --build <Circuit Edition .cue> <Daytona USA .cue> <output folder>


BETA NOTES

- I've tested it on a real Saturn with a Satiator. I haven't tried other
  ODEs, the Saroo or a burned disc.
- It will boot on a PAL Saturn, but the game is made for 60 Hz and will
  probably run slow at 50 Hz. I haven't tested that either.

If you run into a problem, please open an issue:
https://github.com/AJBats/daytona-cce95/issues
