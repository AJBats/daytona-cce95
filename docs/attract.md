# Attract mode: DUSA vs CCE

The user's goal (2026-10-24): CCE95's attract like DUSA's, with DUSA's sound
and camera work. It should open at once on the Daytona theme and DUSA's
opening shot (CCE fades in), and end with DUSA's DAYTONA USA logo sliding
in with a crash shake. Start there fades into CCE's main menu (today CCE's
title crossfades in over its demo).

## Survey (2026-10-25, boot with no input, frame = 1/60 s)

Screenshots every second and around each transition, audio recorded, CD
Block commands traced (scratchpad attract/).

DUSA:

| frames | |
|---|---|
| 360-660 | Saturn logo, SEGA licence |
| 720-1244 | black (loading); CD track 3 starts ~1.9 s before the cut |
| 1248 | hard cut to the demo: a sky shot tilting down onto Three Seven's straight as the rolling-start pack comes at the camera |
| 1248-4008 | demo race, trackside and chase cameras, PRESS START BUTTON, AM2 logo top right, ranking table scrolling over it from 2280 |
| 4010, 4012 | one black frame, one green frame |
| 4014-4034 | white striped title background at once; a pale ghost of the logo in place; the black DAYTONA USA logo slides in from the left |
| 4034-4040 | arrival shake (doubled letters) |
| 4078- | PRESS START BUTTON blinks; the title holds to ~4600 |
| 4620-5280 | white credits: SEGA, AM2, SEGA SPORTS; CD track 2 (9 s jingle) from ~4520 |
| 5340- | the next demo, Dinosaur Canyon, with its own ranking; the cycle goes on |

DUSA's attract music is its CD track 3 (57 s; the recording matches it at
0.99 from 18.8 s to 75.8 s, so it carries on under the logo and title);
track 2 is a 9 s jingle at the credits. Neither is on CCE's disc (best
match against all 30 CCE audio tracks: 0.29).

CCE:

| frames | |
|---|---|
| 360-1980 | Saturn logo, SEGA licence, SEGA SPORTS, trademark notice; silent from ~540 |
| 2090-2100 | the race start plays CD track 18 (94 s) |
| 2100-2150 | fade in from black to a trackside shot of the pack mid-race; the song comes in at 2131, mid-fade |
| 2160-6720 | demo race on Three Seven: ranking table from the first frame, high and overhead cameras; track 18 under the race sounds |
| 6720-6900 | the DAYTONA USA CIRCUIT EDITION title crossfades in over the still-running demo |
| 6900- | title with Press Start Button; track 18 plays on (80 s in at 6800) and fades out by itself at its end |

Music level, fitting each recording to its CD track sample by sample in
2 s windows: DUSA's track 3 at gain 0.42 (the track explains 96% of the
recording's power), CCE's track 18 at 0.41 (90%; CCE's demo race is a
little louder). Both tracks open with 2 s of silence, so a play command
is heard 2 s later.

## The opening (patches/attract.s)

make disc appends DUSA's track 3 as track 32 and track 2 as track 33
(tools/mkdisc.py --append). The attract demo plays track 32 in place of
18. CCE's fade-in is held black until the CD drive is playing audio, then
the colour offsets go to their targets in one call (the fade engine's
state 2), so the demo appears on a hard cut.

Measured from boot with no input (CCE95's frames moved by the appended
tracks, so they aren't vanilla's):

| | DUSA | CCE95 |
|---|---|---|
| song's play command | 1230-1240 | 2090-2100 |
| first beat (track 2.0 s) | 1245 | 2147 |
| hard cut | 1248 | 2146 |
| music gain | 0.42 | 0.40 |

Open: the song is 56 s and CCE's demo runs 76 s, so the music stops at
about 5390, 22 s before the title. It comes right when the demo takes
DUSA's length (46 s, the song carrying on under the logo and title).
