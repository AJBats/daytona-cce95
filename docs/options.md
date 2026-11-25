# The disc's options

Choices the player makes in the disc builder (its CONFIGURE button) that change
what goes on the disc. The default disc is what `make disc` builds; each option
is a Make variable, and the builder gets every other value as changes from the
default disc.

| Option | Make | Values | What changes |
|---|---|---|---|
| music | `MUSIC` | `95` (default), `original` | tracks 23-31: Daytona USA '95's The King of Speed, Let's Go Away and Sky High with their goals and endings, or CCE's arcade originals of them (docs/music.md) |

## Why music is an option

Beta 2 carried both versions of the three songs, 78 minutes, and that disc
booted as a music CD on a MiSTer and failed on the Fenrir: the Saturn's CD
block reads the security ring from LBA 299,150 (66:28) on, and drive
emulators answer only past the image's end (tools/mkdisc.py). One version fits
with room to spare: 62:37 with '95's, 61:51 with the originals. CCE's remixes
stay on the disc either way.

## Building one

`make disc MUSIC=original` builds into build/cce_files_music_original and
build/disc_music_original, so the default disc stays where it is. A value
other than the default can bring:

- patches applied after patches/*.patch: patches/options/music_original.patch
  (the originals' ending scene length);
- its own arguments to the tools: tools/options_sound.py names the disc's
  version on the Sound page;
- its own tracks: the Makefile's DUSA_TRACKS.

## In the builder

`make release-patch` builds the default disc and one disc per other value,
each with the other options at their defaults, and tools/make_release_patch.py
stores each value as what differs from the default disc: the data track's
changed bytes (MUSIC=original: 15,406 bytes in 13 sectors, the volume size,
the CDDA records, the ending ticks and the Sound page's names and their
chars, as each version draws only the names it lists) with that
disc's SHA-1, and the tracks that come from elsewhere. It refuses options
that change the same bytes or tracks, and any disc past mkdisc's RING_CAP.

The builder (patcher/core/src/builder.rs) rebuilds the default data track,
checks it, writes the chosen values' bytes and those sectors' EDC and ECC,
and checks the SHA-1 when one option is off its default. Each audio track
takes its INDEX lines from the disc it comes from. The log names the options
of every build.

The page (patcher/ui) lists the options from one table, OPTIONS in app.js:
a row each under its section's heading, with a dropdown of its values (the
first the default); the list scrolls when it outgrows the window, and the
CONFIGURE button says how many options are off their defaults. A new option
is a row there, with the same ids and values as the patch. The page
remembers the choices between runs. Without the window:
`--build <cce> <dusa> <folder> --option music=original`.

## Checked

2026-11-24, both discs in Mednafen: the race on Three Seven asks for track 23,
on Sea-Side 25, on National Park 5; the replay 22; beta 2's choices 9 and 11
play 23 and 25; Endurance runs 22-25 from the chosen song (2-7 for CCE's own);
the Sound page names the disc's version, its BGM test steps past 9-11, wraps
from 0 to 33, and plays 8, 26 and 34 for entries 13, 18 and 30. The builder's
command line made both discs from the rips, the '95 one identical to `make
disc`'s track for track, the originals one (from Daytona USA (Japan)) with the
same data track and Circuit Edition tracks as `make disc MUSIC=original`.

2026-11-25, the security ring: both discs, and the 2.1 release builder's,
boot in Ymir running the CD block's own firmware, where beta 2 drops to the
CD player as it did on MiSTer (docs/ring_test.md).
