// The three steering paths Stick Lab compares, each run once a 30 Hz tick
// (every other frame, as the race runs) on the same input. Integers
// throughout; '/' truncates toward zero, as C's does and as the game's
// divisions do. Negative steer is left.
#ifndef STEER_H
#define STEER_H

#include <stdint.h>

enum Handling { SLOW, NORMAL, QUICK };

struct Path
{
    int32_t steer;
    int32_t target;
    int32_t wheel;      // the front wheels' angle, in steer units x 256
};

// The d-pad's divisor and the new stick's: a tick closes 1/div of the gap to
// the target (CCE 060370A0 with patches/steering.patch).
static const int32_t kPadDivisor[3] = { 14, 10, 6 };
// Circuit Edition's own analog path (CCE 06037364) as it shipped
// (patches/steering.patch makes SLOW 24 and NORMAL at once): at most this
// much a tick; 0 follows the stick at once.
static const int32_t kCceStep[3] = { 12, 24, 0 };

#define PAD_TARGET      112     // full lock, d-pad
#define NEW_DEAD_ZONE   8       // |stick X - 128| under this is centre
#define NEW_FULL_TILT   127     // |stick X - 128| at full lock

// 1. The d-pad (the game's tuned path): toward -112 while LEFT is held,
// +112 while RIGHT is (LEFT first if both are), from 0 if the steer points
// the other way; nothing held centres at once.
inline void dpadTick(Path& p, bool left, bool right, int32_t handling)
{
    if (left)
    {
        p.target = -PAD_TARGET;
        if (p.steer > 0) {
            p.steer = 0;
        }
    }
    else if (right)
    {
        p.target = PAD_TARGET;
        if (p.steer < 0) {
            p.steer = 0;
        }
    }
    else
    {
        p.target = 0;
        p.steer = 0;
        return;
    }
    p.steer += (p.target - p.steer) / kPadDivisor[handling];
}

// 2. Circuit Edition's analog path: stick X clamped to 3..252, less 128
// (-125..124), followed at most kCceStep a tick.
inline void cceStickTick(Path& p, int32_t x, int32_t handling)
{
    int32_t v = x < 3 ? 3 : x > 252 ? 252 : x;
    p.target = v - 1 - 127;
    int32_t step = kCceStep[handling];
    if (step == 0)
    {
        p.steer = p.target;
        return;
    }
    int32_t gap = p.target - p.steer;
    p.steer += gap > step ? step : gap < -step ? -step : gap;
}

// 3. The proposal: stick X less 128, a dead zone of 8 around the centre, the
// rest scaled so full tilt (128 +- 127) is the d-pad's +-112, then the
// d-pad's easing toward it, back to the centre too. Easing back toward the
// centre moves at least 1 a tick, where the division alone would stop up to
// div - 1 short of it; outward it stops where the d-pad does, so full tilt
// still matches the d-pad.
inline void newStickTick(Path& p, int32_t x, int32_t handling)
{
    int32_t offset = x - 128;
    int32_t tilt = offset < 0 ? -offset : offset;
    if (tilt > NEW_FULL_TILT) {
        tilt = NEW_FULL_TILT;
    }
    int32_t magnitude = tilt < NEW_DEAD_ZONE ? 0
        : (tilt - NEW_DEAD_ZONE) * PAD_TARGET / (NEW_FULL_TILT - NEW_DEAD_ZONE);
    p.target = offset < 0 ? -magnitude : magnitude;
    int32_t gap = p.target - p.steer;
    int32_t step = gap / kPadDivisor[handling];
    bool inward = (p.steer > 0 && gap < 0) || (p.steer < 0 && gap > 0);
    if (step == 0 && inward) {
        step = gap < 0 ? -1 : 1;
    }
    p.steer += step;
}

// The front wheels follow the steer as DUSA's do, halving the gap each
// 20 Hz tick: 1 - 0.5^(2/3) = 0.370 of it each 30 Hz tick.
inline void wheelTick(Path& p)
{
    p.wheel += (p.steer * 256 - p.wheel) * 370 / 1000;
}

#endif
