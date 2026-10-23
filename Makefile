ifeq ($(OS),Windows_NT)
PY      := .venv/Scripts/python.exe
else
PY      := .venv/bin/python
endif
ER      := external_resources
DUSA    := $(ER)/Daytona USA (USA)/Daytona USA (USA) (Track 01).bin
CCE_CUE := $(ER)/Daytona USA - Circuit Edition (Japan)/Daytona USA - Circuit Edition (Japan).cue
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
# DUSA's engine sound in the 1P race sound files (tools/engine_convert.py)
disc: extract
	$(PY) tools/apply_patches.py extracted/cce build/cce_files $(PATCHES)
	$(PY) tools/car_convert.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/engine_convert.py extracted/dusa extracted/cce build/cce_files
	$(PY) tools/mkdisc.py "$(CCE_CUE)" build/cce_files build/disc

test:
	$(PY) tools/test_cdimage.py "$(CCE)"
