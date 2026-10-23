# daytona-cce95

Daytona USA Circuit Edition, with the feel of the original Saturn Daytona USA.

https://github.com/user-attachments/assets/3cd164af-e87e-4776-865a-485d1c2815b0

No game data is included: you need your own copies of both discs.

## Building

Requires Python 3 and `make`.

1. Put the disc images in `external_resources/`:
   - `Daytona USA (USA)/Daytona USA (USA) (Track 01).bin`
   - `Daytona USA - Circuit Edition (Japan)/Daytona USA - Circuit Edition (Japan).cue`
     and its `(Track 01).bin`
2. `python3 -m venv .venv`
3. `make disc`

Output: `build/disc/cce.cue`.

## Contents

- `patches/`: one byte patch per change, each with a header explaining it
- `tools/`: patching, disc building and analysis tools
- `docs/`: how both games' driving code works, and how each patch was tested
