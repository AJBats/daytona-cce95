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

#define PAD_TARGET      112     // the d-pad's target
// The handling reads the steer through DUSA's scaling (CCE 0604D580 with
// patches/steering.patch): (|steer| - 5) * 255 / 150, the steer clamped to
// 80. Under 6 doesn't turn the car, and past 80 turns it no further: 80 is
// full lock, whatever the d-pad's target.
#define HANDLING_FIRST  5
#define HANDLING_LOCK   80
#define NEW_DEAD_ZONE   8       // |stick X - 128| up to this is centre

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

// 3. The proposal: stick X less 128, a dead zone of 8 around the centre, and
// the rest, up to the 3D pad's last value (128 +- 127, reached well before
// the stick meets its gate), spread over the steer the handling turns by:
// the first count past the dead zone is 6, the first that turns the car, and
// full tilt is 80, full lock. Outward the steer takes the d-pad's own steps
// toward its target (1/div of the gap to 112) and stops at the stick's, so a
// flick turns the wheel no faster than the d-pad does and every target is
// reached; toward the centre it follows the stick at once, as the d-pad (and
// DUSA's, 0603000E) drops to 0 when let go, the stick's own spring setting
// the pace. Across the centre it goes through 0 first, as the d-pad does
// when the other direction is pressed.
inline void newStickTick(Path& p, int32_t x, int32_t handling)
{
    int32_t offset = x - 128;
    int32_t tilt = offset < 0 ? -offset : offset;
    // 5 and 5/8 of the tilt past the dead zone, rounded up: 6 at the first
    // count past it, 80 from 127 (X 255 or 1) on; patches/stick.s's sums
    int32_t magnitude = tilt <= NEW_DEAD_ZONE ? 0
        : HANDLING_FIRST + (5 * (tilt - NEW_DEAD_ZONE) + 7) / 8;
    p.target = offset < 0 ? -magnitude : magnitude;
    if ((p.steer > 0 && p.target < 0) || (p.steer < 0 && p.target > 0)) {
        p.steer = 0;
    }
    int32_t size = p.steer < 0 ? -p.steer : p.steer;
    if (magnitude <= size) {
        p.steer = p.target;
        return;
    }
    int32_t padTarget = offset < 0 ? -PAD_TARGET : PAD_TARGET;
    p.steer += (padTarget - p.steer) / kPadDivisor[handling];
    if ((p.steer < 0 ? -p.steer : p.steer) > magnitude) {
        p.steer = p.target;
    }
}

// The front wheels follow the steer as the handling reads it (clamped to
// full lock, 80; patches/wheel_filter.s filters the scaled steer CCE
// 0604D580 makes) the way DUSA's do, halving the gap each 20 Hz tick:
// 1 - 0.5^(2/3) = 0.370 of it each 30 Hz tick.
inline void wheelTick(Path& p)
{
    int32_t felt = p.steer > HANDLING_LOCK ? HANDLING_LOCK
        : p.steer < -HANDLING_LOCK ? -HANDLING_LOCK : p.steer;
    p.wheel += (felt * 256 - p.wheel) * 370 / 1000;
}

#endif
