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

.PHONY: all extract disc test clean-disc

all: disc

extract: extracted/dusa/MANIFEST.txt extracted/cce/MANIFEST.txt

extracted/dusa/MANIFEST.txt:
	$(PY) tools/extract.py "$(DUSA)" extracted/dusa

extracted/cce/MANIFEST.txt:
	$(PY) tools/extract.py "$(CCE)" extracted/cce

PATCHES := $(sort $(wildcard patches/*.patch))

# Patched CCE image: byte patches from patches/*.patch applied to extracted
# files, the player car rebuilt from DUSA's (tools/car_convert.py) and
# DUSA's engine and tyre sounds in the 1P race sound files (tools/engine_convert.py),
# DUSA's ground (or ground made DUSA's way) under every course (tools/col_convert.py)
# and DUSA's title and camera work in the attract (tools/build_attract.py,
# tools/title_convert.py)
disc: extract
	$(PY) tools/apply_patches.py extracted/cce build/cce_files $(PATCHES)
	$(PY) tools/car_convert.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/engine_convert.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/col_convert.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/build_attract.py extracted/dusa build/attract
	$(PY) tools/title_convert.py extracted/dusa extracted/cce build/cce_files build/attract/attract.bin
	$(PY) tools/mkdisc.py "$(CCE_CUE)" build/cce_files build/disc --append "$(DUSA_CUE)" 3 2

test:
	$(PY) tools/test_cdimage.py "$(CCE)"
