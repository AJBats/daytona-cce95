# Music

Daytona USA '95's own recordings as the default race music, CCE's remixes
as choices, and DUSA's tracks where CCE plays one-off music of its own.
The disc has room for one version of The King of Speed, Let's Go Away and
Sky High: '95's, or CCE's arcade originals when the player picks them in
the disc builder (docs/options.md). Design and listening notes: the music
review of 2026-11-08 (user's choices).

## What the discs hold

CCE (Japan) plays its music from CD tracks by number (the play command's
position type 2, track and index; 06007A74 and 06007A98 loop a track,
06007AF8 plays it once). Its sound test (SLCT.BIN, names 0603F860, tracks
0603FCF8) lists all 30:

| CCE track | What | Where CCE plays it |
|---|---|---|
| 2-7 | The King of Speed, Let's Go Away, Sky High (remixes), The Noisy Roars of Wilderness, Pounding Pavement (remix), the Medley | race, BGM index 0-5 |
| 8-12 | goal jingles of 2-6 | at the finish, by the song chosen |
| 13-17 | endings of 2-6 | the race's ending scene |
| 18 | Sons of Angels | the attract (ATTRACT : CCE) |
| 19 | The American Dream | the replay, looped (RACE.BIN 0602950A) |
| 20 | Lack of Speed | time up (RACE.BIN 06028456, 0602849A, 06034962) |
| 21 | Sunset on the DAYTONA Beach | name entry (NAME.BIN 0602A0FC) and two-player result (RESULT2P.BIN 0602801E), looped |
| 22 | Crash & Burrn | staff roll (ENDING.BIN 06028092), once |
| 23-25 | The King of Speed, Let's Go Away, Sky High (original): CCE's arcade versions | race, BGM index 6-8 |
| 26-28 | goal jingles of 23-25 | |
| 29-31 | endings of 23-25 | |

DUSA (APROG.BIN's music test, 0605D2B8: track = entry + 2):

| DUSA track | What | Where DUSA plays it |
|---|---|---|
| 2 | SEGA LOGO | boot; the attract's credits |
| 3 | Let's Go Away (Advertise theme) | the attract |
| 4, 5 | Wait Coin, Start Your Engines | menu loops (timed to the arcade's menu timers) |
| 6-8 | The King of Speed, Let's Go Away, Sky High | race: course + 6 |
| 9 | Pounding Pavement | only in the longest race setting, where the CD runs on from the course's song through 6-9 and loops (06018B28); its karaoke mix (22) on Three Seven in karaoke mode |
| 10-12 | Breakdown, Raggin', Check It Out! | goal: course + 10 |
| 13 | Sweat | music test only (a fourth course's goal) |
| 14-16 | Rolling Start, The Dream of Daytona, Can You Fly? | the victory lane ending: course + 14 (timer 1000) |
| 17 | Pounding Pavement (reprise) | music test only (a fourth course's ending) |
| 18 | G,A,M,E,O,V,E,R | game over, with the letters' dance on screen |
| 19 | David Goes To Victory Lane | name entry (state 27, its 600-tick timer) |
| 20-22 | karaoke mixes of 7, 8, 9 | karaoke mode |

CCE's "original" versions are CCE's own recordings of the arcade
arrangements: they follow DUSA's note for note, but no 1 s window of one
matches DUSA's recording (r 0.1-0.2, against 0.8-0.97 for DUSA's karaoke
mixes of the same recordings). CCE's Pounding Pavement remix is the same
song as DUSA's (chroma 0.86), another recording (r 0.23).

## Our disc

Makefile DUSA_TRACKS (by MUSIC), tools/mkdisc.py --from:

| Track | From | Plays |
|---|---|---|
| 2-18, 20 | CCE's own | as CCE |
| 19 | DUSA 13, Sweat | Pounding Pavement '95's goal |
| 21 | DUSA 19, David Goes To Victory Lane | name entry and two-player result, looped (no code change: they play 21) |
| 22 | DUSA 9, Pounding Pavement '95 | race, the replay (patches/music_tracks.patch) and the staff roll (CCE's own 22) |
| 23-25 | DUSA 6-8, or CCE's arcade originals (MUSIC=original) | race: The King of Speed, Let's Go Away, Sky High |
| 26-28 | DUSA 10-12, or CCE's | their goals |
| 29-31 | DUSA 14-16, or CCE's | their endings |
| 32 | DUSA 3 | the attract (patches/attract.s) |
| 33 | DUSA 2 | the attract's credits jingle |
| 34 | DUSA 17, Pounding Pavement (reprise) | Pounding Pavement '95's ending |

With MUSIC=original, 23-31 are CCE's own tracks in their own places. Pounding
Pavement '95 in 22, right before the other three, lets a range of tracks
play the four in turn as DUSA's long races do (Endurance, below). Lack of
Speed stays in 20 until DUSA's GAME OVER comes with its on-screen letters.

The disc runs 62:37 with '95's songs and 61:51 with the originals. It has
to end well before 66:28 (LBA 299,150), where the Saturn's CD block starts
looking for the security ring: drive emulators (MiSTer, the Fenrir) answer
with ring data only past the image's end, so beta 2's 78-minute disc, both
versions of the three songs on it, booted as a music CD on a MiSTer.
mkdisc refuses a disc past 66:13.

## The BGM choices

Options > Sound picks a song per course (a byte each at 002FC3A2, 4 bits
each in the backup). The race takes the song, its goal jingle and its
ending from tables by that choice (patches/bgm_tables.s):

| Choice | Song | Goal | Ending | Ending scene, ticks |
|---|---|---|---|---|
| 0-4 | CCE's remixes, Noisy Roars, Pounding Pavement (remix): 2-6 | 8-12 | 13-17 | 1140, 990, 990, 1020, 960 |
| 5 | DAYTONA USA Medley: 7 | the course's | the course's | 1200 |
| 6-8 | The King of Speed, Let's Go Away, Sky High, the disc's version: 23-25 | 26-28 | 29-31 | '95: 1000, 1110, 1090; originals: 990 (patches/options/music_original.patch) |
| 9-11 | the same as 6-8 | | | |
| 12 | Pounding Pavement '95: 22 | 19 | 34 | 1090 |

The jingles follow the song chosen, as CCE's do; DUSA ties them to the
course, and on DUSA's three courses with their '95 songs the pairs are
DUSA's own. The defaults stay 6 7 8 3 4 (patches/original_music.patch).
Beta 2 had both versions on its disc, '95's as 6-8 and the originals as
9-11; now 9-11 are 6-8 again, in the page's names too, so any save plays
the version the disc carries. Beta 1's 6-8 were CCE's originals: those
saves get the disc's version as well. The CCE choices (0-5) stay what they
were. The ending scene runs about 30 ticks a second of its song, as CCE's
own do.

The page draws a choice by its name box (tools/options_sound.py): the '95
songs by their bare names, the remixes' pictures cut before " (remix)";
"(original)" stays CCE's arcade versions, "(remix)" CCE's. Left and right
on a course row step through the disc's version first, then CCE's (6 7 8
12 0 1 2 3 4 5, around; 9-11 step as 6-8).

## The sound test

Options > Sound's BGM TEST plays every track the game plays: 34 entries,
31 shown (tools/options_sound.py, patches/bgm_menu.s):

| Entries | What | Tracks |
|---|---|---|
| 0-12 | the 13 BGM choices, by choice number; left and right step past 9-11, which are 6-8 again | as above |
| 13-17 | CCE's goal jingles | 8-12 |
| 18-21 | the disc's three goals ('95: Breakdown, Raggin', Check It Out!), then Sweat | 26, 27, 28, 19 |
| 22-26 | CCE's endings | 13-17 |
| 27-30 | the disc's three endings ('95: Rolling Start, The Dream of Daytona, Can You Fly?), then Pounding Pavement (reprise) | 29, 30, 31, 34 |
| 31-33 | Sons of Angels, Lack of Speed, David Goes To Victory Lane | 18, 20, 21 |

The names of the disc's version are '95's or the originals' (CCE's own
pictures), whichever the disc carries. CCE's entries for The American
Dream, Sunset on the DAYTONA Beach and Crash & Burrn are gone with their
tracks. The page's names are pictures;
DUSA's titles are drawn in CCE's lettering (tools/sound_names.py): letters
cut from CCE's own names, five made from others (I, V, F, !, ?), CCE's
spacing, and the dark plate drawn as CCE drew its plain-style names, each
pixel by the ink around it. Pounding Pavement (reprise) is CCE's Pounding
Pavement (remix) picture with its last word redrawn. Their chars take the
places of the names the disc's list leaves out (the three dropped ones,
and on the '95 disc the originals' nine) and VRAM free past the page's
chars (0x1F0E0 to 0x20000). Until 2026-11-25 they also took VRAM 0x8380
to 0xA000, which the S.E. test's entries from "Seven laps to go" on load
their own names into: the announcer's lines near the end of the list came
up scrambled (GitHub #13). Checked in Mednafen (2026-11-08, with 40
entries): all names drawn, the page right again after KEY CONFIG, and
OPT.DAT's appended block in work RAM untouched through the Options pages.
Checked 2026-11-24 on both discs: right from 6 steps 7, 8, 12, 13 and left
back, the row wraps from 0 to 33, entries 13, 18 and 30 play 8, 26 and 34,
and the names are the disc's version's. Checked 2026-11-25 on both discs:
all 31 BGM test names and all S.E. test names drawn whole.

## Endurance

CCE's ARCADE > GAME MODE (002FC234: NORMAL, GRANDPRIX, ENDURANCE; 80 laps
of Three Seven in Endurance) loops the one song in every mode. DUSA loops
it in its first two race lengths and, in its longest, runs on from the
course's song through its four and loops them (06018B28: a seek to the
course's song, then a play of tracks 6-9 with the pickup left where it is,
mode 0x8F). In an Endurance race the song now does the same through the
chosen song's version (src/race_block.s, patches/endurance.s): 22-25 for
Pounding Pavement '95 and the disc's other three (from the chosen song to
25, then round from 22: DUSA's order), CCE's own 2-7. On a disc with the
arcade originals the run is those three and Pounding Pavement '95. Normal
and Grand Prix loop the song as before. Checked in Mednafen (2026-11-08,
the tracks then 34-37): an Endurance race on Three Seven seeks to the song
and plays the run at mode 0x8F, and 5 minutes in, after The King of Speed,
Let's Go Away '95 plays (r 0.75 against DUSA's track 7, 0.2 against the
others). 2026-11-24 on both discs: the run 22-25 from 23 by default, from
22 for Pounding Pavement '95, 2-7 from 5 for Noisy Roars.

## The CDDA records

CCE's root directory has a record per audio track, CDDA2 to CDDA31 (the
track's INDEX 01, its length from there at 2048 bytes a sector). The game
doesn't open them; mkdisc moves them with their tracks all the same.
