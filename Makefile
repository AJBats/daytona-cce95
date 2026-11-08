ifeq ($(OS),Windows_NT)
PY      := .venv/Scripts/python.exe
else
PY      := .venv/bin/python
endif
ER      := external_resources
DUSA    := $(ER)/Daytona USA (USA)/Daytona USA (USA) (Track 01).bin
CCE_CUE := $(ER)/Daytona USA - Circuit Edition (Japan)/Daytona USA - Circuit Edition (Japan).cue
DUSA_CUE := $(ER)/Daytona USA (USA)/Daytona USA (USA).cue
# DUSA's tracks on our disc, our slot=DUSA's track (docs/music.md): Pounding Pavement's
# goal and ending, and Victory Lane at the name entry, in place of CCE's American Dream,
# Sunset on the DAYTONA Beach and Crash & Burrn (19, 21, 22); the attract song and the
# credits jingle (32, 33); the four '95 songs (34-37), goals (38-40) and endings (41-43)
DUSA_TRACKS := 19=13 21=19 22=17 32=3 33=2 34=6 35=7 36=8 37=9 38=10 39=11 40=12 41=14 42=15 43=16
CCE     := $(ER)/Daytona USA - Circuit Edition (Japan)/Daytona USA - Circuit Edition (Japan) (Track 01).bin

.PHONY: all extract disc test clean-disc attract-vis release-patch release release-zip stickviz probe-cce

all: disc

extract: extracted/dusa/MANIFEST.txt extracted/cce/MANIFEST.txt

extracted/dusa/MANIFEST.txt:
	$(PY) tools/extract.py "$(DUSA)" extracted/dusa

extracted/cce/MANIFEST.txt:
	$(PY) tools/extract.py "$(CCE)" extracted/cce

PATCHES := $(sort $(wildcard patches/*.patch))

# The disc and the files it is built from. make disc PROBE=1 builds a test disc
# instead, in build/disc_probe: patches/probe/vdp1_late.s tints the picture red
# while the frame on screen was cut short (VDP1 out of time), in the cave
# attract_load uses, so that one and attract_choice stay out.
FILES := build/cce_files
DISC_OUT := build/disc
ifdef PROBE
PATCHES := $(filter-out patches/attract_choice.patch patches/attract_load.patch,$(PATCHES)) patches/probe/vdp1_late.patch
FILES := build/cce_files_probe
DISC_OUT := build/disc_probe
endif

# Patched CCE image: byte patches from patches/*.patch applied to extracted
# files, course quads turned for VDP1 (tools/turn_quads.py) and turned or cut
# as the race draws them (tools/vdp1x.py, a block of SCREEN.BIN), the
# two-player window reflection in another (tools/reflect_2p.py), the player car
# rebuilt from DUSA's (tools/car_convert.py), its
# car-select picture rendered from it (tools/car_pictures.py),
# DUSA's engine and tyre sounds in the 1P race sound files (tools/engine_convert.py),
# DUSA's ground (or ground made DUSA's way) under every course (tools/col_convert.py)
# and DUSA's title, camera work and cars in the attract (tools/build_attract.py,
# tools/title_convert.py), with CCE's own attract as a choice in Options and
# the BGM list with DUSA's '95 songs (tools/options_sound.py), DUSA's title on the main menu's press-start
# page too (tools/menu_title.py), the name entry's pictures of the cars
# on DUSA's body (tools/name_pictures.py) and their hoods in the in-car
# view (tools/hoods.py), and the backup-memory messages in English
# (tools/backup_messages.py). The car and its pictures take minutes and
# their inputs rarely change: tools/cached.py writes back what they made last
# time while nothing they read has changed.
disc: extract build/attract/dusa_cars.npz
	$(PY) tools/apply_patches.py extracted/cce $(FILES) $(PATCHES)
	$(PY) tools/turn_quads.py extracted/cce $(FILES)
	$(PY) tools/vdp1x.py extracted/cce $(FILES)
	$(PY) tools/reflect_2p.py extracted/cce $(FILES)
	$(PY) tools/cached.py tools/car_convert.py extracted/dusa extracted/cce $(FILES)
	$(PY) tools/cached.py tools/car_pictures.py extracted/dusa extracted/cce $(FILES)
	$(PY) tools/engine_convert.py extracted/dusa extracted/cce $(FILES)
	$(PY) tools/col_convert.py extracted/dusa extracted/cce $(FILES)
	$(PY) tools/build_attract.py extracted/dusa build/attract $(FILES)
	$(PY) tools/title_convert.py extracted/dusa extracted/cce $(FILES) build/attract/attract.bin build/attract/cars.blk
	$(PY) tools/options_sound.py extracted/cce $(FILES)
	$(PY) tools/menu_title.py extracted/dusa extracted/cce $(FILES)
	$(PY) tools/cached.py tools/name_pictures.py extracted/dusa extracted/cce $(FILES)
	$(PY) tools/hoods.py extracted/dusa extracted/cce $(FILES)
	$(PY) tools/backup_messages.py extracted/cce $(FILES)
	$(PY) tools/mkdisc.py "$(CCE_CUE)" $(FILES) $(DISC_OUT) --from "$(DUSA_CUE)" $(DUSA_TRACKS)

# DUSA's attract cars, recorded once from DUSA running in the debugger (about a minute)
build/attract/dusa_cars.npz:
	$(PY) tools/attract_record.py $@

# The course blocks on screen through DUSA's demos (tools/attract_vis.py), recorded
# from a disc built with CCE's own choice of blocks (COURSE_LISTS=0), then the disc
# again with them (several minutes). Again when the attract's camera changes.
export COURSE_LISTS
attract-vis:
	$(MAKE) disc COURSE_LISTS=0
	$(PY) tools/attract_vis.py build/attract/course_vis.npz
	$(MAKE) disc

test:
	$(PY) tools/test_cdimage.py "$(CCE)"

# Stick Lab (stickviz/main.cpp): a program of its own on a disc of its own, to feel and
# see the d-pad, CCE stick and new stick steering paths on the Saturn with a 3D Control
# Pad: build/stickviz/disc/stickviz.cue. Its header is CCE's (tools/mkiso.py).
stickviz:
	$(PY) stickviz/build.py build/stickviz
	$(PY) tools/mkiso.py "$(CCE)" build/stickviz/disc stickviz --title "STICK LAB" --load 06004000 0MAIN.BIN=build/stickviz/0MAIN.BIN

# Unmodified CCE with only the VDP1 probe (patches/probe/vdp1_late.s): its own frames
# cut short turn red too, to compare with ours. build/disc_vprobe
probe-cce: extract
	$(PY) tools/apply_patches.py extracted/cce build/cce_files_vprobe patches/probe/vdp1_late.patch
	$(PY) tools/mkdisc.py "$(CCE_CUE)" build/cce_files_vprobe build/disc_vprobe

# The disc builder players download (patcher/): the built disc as changes to the two
# discs it's made from (tools/make_release_patch.py), then the builder with that inside.
# The builder also takes rips of DUSA's other regions found here (zips, file names
# without spaces).
DUSA_DUMPS ?= $(wildcard external_resources/dusa_dumps/*.zip)
release-patch: disc
	$(PY) tools/make_release_patch.py "$(CCE_CUE)" "$(DUSA_CUE)" build/disc build/release/ultimate.patch $(foreach z,$(DUSA_DUMPS),"$(z)")

release: release-patch
	cargo build --release --manifest-path patcher/src-tauri/Cargo.toml

# The zip for GitHub's Releases: the builder and patcher/README.txt, named for the
# version in patcher/src-tauri/Cargo.toml (keep tauri.conf.json's the same)
release-zip: release
	$(PY) tools/release_zip.py patcher/src-tauri/target/release/daytona-ultimate.exe patcher/README.txt patcher/src-tauri/Cargo.toml build/release
