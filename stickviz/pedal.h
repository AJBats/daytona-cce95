// The three pedal paths Stick Lab's PEDALS page compares, gas and brake,
// each run once a 30 Hz tick on the same trigger. Integers throughout, as the
// game's.
//
// Raw values are what the car keeps (gas +0x88, brake +0x98), resting at 56.
// The handling reads them as a pedal of 0-255 (CCE 0604D640 with
// patches/brake_pedal.patch, DUSA's scaling):
//   gas   (raw - 56) x 255 / 128, raw clamped to 56-184
//   brake (raw - 56) x 255 / 96,  raw clamped to 56-152
// A raw brake above 152 is still full brake, but it takes longer to fall.
#ifndef PEDAL_H
#define PEDAL_H

#include <stdint.h>

struct Pedal
{
    int32_t raw;
    int32_t target;     // the raw value it heads for
    int32_t phase;      // the gas's slow release: -1 on two ticks of three
};

#define PEDAL_REST      56
#define GAS_FULL        184
#define GAS_JUMP        160     // DUSA's button jumps to full from here
#define GAS_SLOW        176     // released from here up, -1 on two ticks of three
#define GAS_DROP        111     // released below this, back to rest at once
#define BRAKE_FULL      152     // pedal 255
#define BRAKE_STEP_TO   184     // the button adds while raw is up to this
#define BRAKE_TOP       191     // where the button stops from rest: 56 + 5 x 27

// The proposal's trigger travel: up to PEDAL_DEAD_ZONE is off, from
// PEDAL_FULL_TRIGGER on is the button held.
#define PEDAL_DEAD_ZONE     8
#define PEDAL_FULL_TRIGGER  248

inline int32_t clampTo(int32_t v, int32_t lo, int32_t hi)
{
    return v < lo ? lo : v > hi ? hi : v;
}

inline int32_t gasPedal(int32_t raw)
{
    return (clampTo(raw, PEDAL_REST, GAS_FULL) - PEDAL_REST) * 255 / 128;
}

inline int32_t brakePedal(int32_t raw)
{
    return (clampTo(raw, PEDAL_REST, BRAKE_FULL) - PEDAL_REST) * 255 / 96;
}

inline void pedalInit(Pedal& p)
{
    p.raw = p.target = PEDAL_REST;
    p.phase = 0;
}

// --- gas ----------------------------------------------------------------------

// DUSA's release at 30 Hz (patches/throttle.s): from 176 up, -1 on two ticks
// of three; below, raw / 24 off a tick, and under 111 back to rest.
inline void gasRelease(Pedal& p)
{
    if (p.raw >= GAS_SLOW)
    {
        p.phase = p.phase + 1 < 3 ? p.phase + 1 : 0;
        if (p.phase != 0) {
            p.raw--;
        }
        return;
    }
    p.raw -= (p.raw * 0x0AAB) >> 16;
    if (p.raw < GAS_DROP) {
        p.raw = PEDAL_REST;
    }
}

// A. DUSA's button (patches/throttle.s, the pad's gas): +7 a tick, full once
// it reaches 160; let go, DUSA's release.
inline void gasButtonTick(Pedal& p, bool pressed)
{
    if (!pressed)
    {
        p.target = PEDAL_REST;
        gasRelease(p);
        return;
    }
    p.target = GAS_FULL;
    if (p.raw > GAS_FULL)
        return;
    p.raw += 7;
    if (p.raw >= GAS_JUMP) {
        p.raw = GAS_FULL;
    }
}

// B. Circuit Edition's trigger, as the race runs it now (CCE 0603740E): half
// the trigger over rest, at once. A full trigger is 183, pedal 253.
inline void gasCceTick(Pedal& p, int32_t trigger)
{
    p.raw = p.target = (trigger >> 1) + PEDAL_REST;
}

// The proposal's target: the travel past the dead zone spread over rest to
// full, 56-184.
inline int32_t gasTarget(int32_t trigger)
{
    if (trigger <= PEDAL_DEAD_ZONE)
        return PEDAL_REST;
    if (trigger >= PEDAL_FULL_TRIGGER)
        return GAS_FULL;
    return PEDAL_REST + (trigger - PEDAL_DEAD_ZONE) * (GAS_FULL - PEDAL_REST)
        / (PEDAL_FULL_TRIGGER - PEDAL_DEAD_ZONE);
}

// C. The proposal: the trigger sets a target and the pedal moves toward it at
// DUSA's button rates. Up: +7 a tick, stopping at the target; from 160 up it
// jumps to the target, as the button jumps to full. Down: DUSA's release,
// stopping at the target. A full trigger is the button; a part trigger holds
// part of the pedal.
inline void gasNewTick(Pedal& p, int32_t trigger)
{
    p.target = gasTarget(trigger);
    if (p.raw < p.target)
    {
        p.raw += 7;
        if (p.raw >= GAS_JUMP || p.raw > p.target) {
            p.raw = p.target;
        }
    }
    else if (p.raw > p.target)
    {
        gasRelease(p);
        if (p.raw < p.target) {
            p.raw = p.target;
        }
    }
}

// --- brake --------------------------------------------------------------------

// DUSA's release at 30 Hz (patches/brake_pedal.s): keep 5/8 a tick, down to
// rest.
inline void brakeRelease(Pedal& p)
{
    int32_t quarter = p.raw >> 2;
    p.raw -= quarter;
    p.raw -= quarter >> 1;
    if (p.raw < PEDAL_REST) {
        p.raw = PEDAL_REST;
    }
}

// A. DUSA's button (patches/brake_pedal.s, the pad's brake): +27 a tick
// while raw is up to 184, so from rest 83, 110, 137, 164, 191 (full brake
// from the fourth tick); let go, DUSA's release.
inline void brakeButtonTick(Pedal& p, bool pressed)
{
    if (!pressed)
    {
        p.target = PEDAL_REST;
        brakeRelease(p);
        return;
    }
    p.target = BRAKE_TOP;
    if (p.raw <= BRAKE_STEP_TO) {
        p.raw += 27;
    }
}

// B. Circuit Edition's trigger, as the race runs it now (CCE 06037442): any
// touch is raw 88 plus half the trigger, at once. Through DUSA's scaling the
// lightest touch is a third of the brake and half a pull is all of it.
inline void brakeCceTick(Pedal& p, int32_t trigger)
{
    int32_t half = trigger >> 1;
    p.raw = p.target = half ? half + 32 + PEDAL_REST : PEDAL_REST;
}

// The proposal's target: the travel past the dead zone spread over rest to
// full brake, 56-152 (a full trigger is the button, BRAKE_TOP).
inline int32_t brakeTarget(int32_t trigger)
{
    if (trigger <= PEDAL_DEAD_ZONE)
        return PEDAL_REST;
    if (trigger >= PEDAL_FULL_TRIGGER)
        return BRAKE_TOP;
    return PEDAL_REST + (trigger - PEDAL_DEAD_ZONE) * (BRAKE_FULL - PEDAL_REST)
        / (PEDAL_FULL_TRIGGER - PEDAL_DEAD_ZONE);
}

// C. The proposal: +27 a tick up to the target, DUSA's release down to it.
// A full trigger is the button exactly, overshoot included, so its release
// takes as long as the button's.
inline void brakeNewTick(Pedal& p, int32_t trigger)
{
    if (trigger >= PEDAL_FULL_TRIGGER)
    {
        brakeButtonTick(p, true);
        return;
    }
    p.target = brakeTarget(trigger);
    if (p.raw < p.target)
    {
        p.raw += 27;
        if (p.raw > p.target) {
            p.raw = p.target;
        }
    }
    else if (p.raw > p.target)
    {
        brakeRelease(p);
        if (p.raw < p.target) {
            p.raw = p.target;
        }
    }
}

#endif
