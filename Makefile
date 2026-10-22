PY      := .venv/bin/python
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

# Patched CCE image: byte patches from patches/*.patch applied to extracted files
disc: extract
	$(PY) tools/apply_patches.py extracted/cce build/cce_files $(PATCHES)
	$(PY) tools/mkdisc.py "$(CCE_CUE)" build/cce_files build/disc

test:
	$(PY) tools/test_cdimage.py "$(CCE)"
