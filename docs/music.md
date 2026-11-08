# Music

Daytona USA '95's own recordings as the default race music, CCE's arcade
originals and remixes as choices, and DUSA's tracks where CCE plays one-off
music of its own. Design and listening notes: the music review of
2026-11-08 (user's choices).

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

Makefile DUSA_TRACKS, tools/mkdisc.py --from:

| Track | From | Plays |
|---|---|---|
| 2-18, 20, 23-31 | CCE's own | as CCE |
| 19 | DUSA 13, Sweat | Pounding Pavement '95's goal |
| 21 | DUSA 19, David Goes To Victory Lane | name entry and two-player result, looped (no code change: they play 21) |
| 22 | DUSA 17, Pounding Pavement (reprise) | Pounding Pavement '95's ending |
| 32 | DUSA 3 | the attract (patches/attract.s) |
| 33 | DUSA 2 | the attract's credits jingle |
| 34-37 | DUSA 6-9, the four songs | race; 37 also the replay and the staff roll (patches/music_tracks.patch) |
| 38-40 | DUSA 10-12 | goals |
| 41-43 | DUSA 14-16 | endings |

The four '95 songs are consecutive so a range of tracks can play them in
turn, as DUSA's long races do. Until the sound test gets DUSA's names, its
entries for The American Dream and Crash & Burrn play 37 and Sunset on the
DAYTONA Beach plays 21, what those places play now. Lack of Speed stays in 20 until DUSA's GAME
OVER comes with its on-screen letters. The disc runs 78:12, 1:46 short of
an 80-minute CD-R (mkdisc refuses a disc that doesn't fit).

CCE's root directory has a record per audio track, CDDA2 to CDDA31 (the
track's INDEX 01, its length from there at 2048 bytes a sector). The game
doesn't open them; mkdisc moves them with their tracks all the same.
