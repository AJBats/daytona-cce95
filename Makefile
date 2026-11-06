ifeq ($(OS),Windows_NT)
PY      := .venv/Scripts/python.exe
else
PY      := .venv/bin/python
endif
ER      := external_resources
DUSA    := $(ER)/Daytona USA (USA)/Daytona USA (USA) (Track 01).bin
CCE_CUE := $(ER)/Daytona USA - Circuit Edition (Japan)/Daytona USA - Circuit Edition (Japan).cue
# DUSA's attract song (its track 3) and credits jingle (track 2) become tracks 32 and 33
DUSA_CUE := $(ER)/Daytona USA (USA)/Daytona USA (USA).cue
CCE     := $(ER)/Daytona USA - Circuit Edition (Japan)/Daytona USA - Circuit Edition (Japan) (Track 01).bin

.PHONY: all extract disc test clean-disc attract-vis release-patch release

all: disc

extract: extracted/dusa/MANIFEST.txt extracted/cce/MANIFEST.txt

extracted/dusa/MANIFEST.txt:
	$(PY) tools/extract.py "$(DUSA)" extracted/dusa

extracted/cce/MANIFEST.txt:
	$(PY) tools/extract.py "$(CCE)" extracted/cce

PATCHES := $(sort $(wildcard patches/*.patch))

# Patched CCE image: byte patches from patches/*.patch applied to extracted
# files, the player car rebuilt from DUSA's (tools/car_convert.py), its
# car-select picture rendered from it (tools/car_pictures.py),
# DUSA's engine and tyre sounds in the 1P race sound files (tools/engine_convert.py),
# DUSA's ground (or ground made DUSA's way) under every course (tools/col_convert.py)
# and DUSA's title, camera work and cars in the attract (tools/build_attract.py,
# tools/title_convert.py), with CCE's own attract as a choice in Options
# (tools/options_attract.py), DUSA's title on the main menu's press-start
# page too (tools/menu_title.py), the name entry's pictures of the cars
# on DUSA's body (tools/name_pictures.py) and their hoods in the in-car
# view (tools/hoods.py)
disc: extract build/attract/dusa_cars.npz
	$(PY) tools/apply_patches.py extracted/cce build/cce_files $(PATCHES)
	$(PY) tools/car_convert.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/car_pictures.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/engine_convert.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/col_convert.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/build_attract.py extracted/dusa build/attract build/cce_files
	$(PY) tools/title_convert.py extracted/dusa extracted/cce build/cce_files build/attract/attract.bin build/attract/cars.blk
	$(PY) tools/options_attract.py extracted/cce build/cce_files
	$(PY) tools/menu_title.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/name_pictures.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/hoods.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/mkdisc.py "$(CCE_CUE)" build/cce_files build/disc --append "$(DUSA_CUE)" 3 2

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

# The disc builder players download (patcher/): the built disc as changes to the two
# discs it's made from (tools/make_release_patch.py), then the builder with that inside.
# The builder also takes the other Redump dumps of DUSA found here (zips, file names
# without spaces).
DUSA_DUMPS ?= $(wildcard external_resources/dusa_dumps/*.zip)
release-patch: disc
	$(PY) tools/make_release_patch.py "$(CCE_CUE)" "$(DUSA_CUE)" build/disc build/release/ultimate.patch $(foreach z,$(DUSA_DUMPS),"$(z)")

release: release-patch
	cargo build --release --manifest-path patcher/src-tauri/Cargo.toml
