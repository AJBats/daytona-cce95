Daytona USA Ultimate disc builder, version {version}
https://github.com/AJBats/daytona-cce95

Daytona USA Ultimate is a mod of Daytona USA Circuit Edition for the Sega
Saturn. It keeps Circuit Edition's five courses and two-player mode, and
swaps in the handling, car, road surface and sounds from the original
Saturn Daytona USA. This program builds the disc from your own copies of
both games. No game data is included.


WHAT YOU NEED

- Windows 10 or 11, 64-bit.
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
  such as redumper or DiscImageCreator.
- About 700 MB of free space for the disc.


HOW TO USE IT

1. Unzip this somewhere you can save files, like your Documents folder.
2. Run "Daytona USA Ultimate Builder.exe".
3. Click each cover to pick the rip for that game, or drop the files on
   the window, then press COMBINE. CONFIGURE, next to COMBINE, chooses the
   race music: Saturn Daytona USA's versions of The King of Speed, Let's
   Go Away and Sky High (the default), or Circuit Edition's arcade
   originals.
4. The disc is written to a "Daytona USA Ultimate" folder next to the
   builder, as a .cue file and its tracks. You can play it in an emulator,
   or on a real Saturn with an ODE such as the Satiator.


IF IT WON'T START

- "Windows protected your PC": the builder isn't signed, so Windows warns
  about it. Click "More info", then "Run anyway".
- Nothing happens: the builder needs Microsoft's WebView2 Runtime. Windows
  11 comes with it, and so do most Windows 10 PCs. If yours doesn't, get
  the Evergreen Runtime from
  https://developer.microsoft.com/microsoft-edge/webview2/


BETA NOTES

- Players ran beta 1 on a real Saturn from a Satiator, a Saroo, a Fenrir
  and a burned disc, and on a MiSTer. Beta 2's disc ran past 66 minutes,
  too long for the MiSTer, the Fenrir and burned discs. Beta 2.1's runs
  under 63 minutes, shorter than beta 1's. Nobody has tried 2.1 on a
  MiSTer, a Fenrir or a burned disc yet.
- It boots on a PAL Saturn, but the game is made for 60 Hz: at 50 Hz it
  runs about 17% slower, with black bars at the top and bottom. A PAL
  Saturn with a 50/60 Hz switch set to 60 Hz, or a Japanese or US Saturn,
  runs it at full speed.
- The Yaba Sanshiro emulator plays no engine sound. Mednafen and real
  hardware do.

If you run into a problem, please open an issue:
https://github.com/AJBats/daytona-cce95/issues

If the builder turned down a disc or stopped with an error, please attach
its log to your issue: the file "Daytona USA Ultimate Builder log.txt" in
the builder's folder. The error message shows where it is too, and its
"show" link opens that folder.

If the game crashes or freezes, a red, blue or purple screen full of
numbers comes up. Please take a photo of the whole screen and attach it to
your issue, and say what you were doing when it happened. Those numbers
tell me where the game went wrong.
