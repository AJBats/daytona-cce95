// Stick Lab's Saturn start-up, screen and pad, from the Tomb Raider project's
// standalone benchmarks (dspbench/platform.cpp, saturn/input.cpp), whose
// display layout the Saturn has proven: one layer, NBG0, a 512 x 256 15-bit
// bitmap in VRAM bank A that the CPU draws into, at 320 x 224.
#ifndef PLATFORM_H
#define PLATFORM_H

#include <stdint.h>

#define SCREEN_WIDTH    320
#define SCREEN_HEIGHT   224
#define PITCH           512     // pixels a line of the bitmap

// The 320-dot clock, the bitmap cleared and shown, the timer running.
void platformInit();

// Waits for the next vertical blank to start.
void waitVblankIn();

// The CPU's free-running timer: 16 bits, a tick every 8 cycles, 56,150
// ticks a frame on the 320-dot clock.
uint32_t ticks();
inline uint32_t ticksSince(uint32_t start)
{
    return (ticks() - start) & 0xFFFF;
}

// Waits n ticks of the timer.
void delayTicks(uint32_t n);

// The bitmap: 0 is transparent (the black back colour), RGB() colours show.
inline volatile uint16_t* pixelAt(int32_t x, int32_t y)
{
    return (volatile uint16_t*)0x25E00000 + y * PITCH + x;
}
void fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t colour);

// Port 1 through SMPC INTBACK, called once a frame inside the vertical blank
// (at least 300 us after it starts): takes the data of the request the call
// before made, and makes the next.
#define PAD_L       0x0008
#define PAD_Z       0x0010
#define PAD_Y       0x0020
#define PAD_X       0x0040
#define PAD_R       0x0080
#define PAD_B       0x0100
#define PAD_C       0x0200
#define PAD_A       0x0400
#define PAD_START   0x0800
#define PAD_UP      0x1000
#define PAD_DOWN    0x2000
#define PAD_LEFT    0x4000
#define PAD_RIGHT   0x8000

#define PAD_ID_NONE     0xFF    // nothing on port 1 (or a multitap)
#define PAD_ID_DIGITAL  0x02    // a standard pad, or a 3D pad switched to digital
#define PAD_ID_3D       0x16    // a 3D pad in analog mode: buttons, X, Y, R, L

struct Pad
{
    int32_t id;         // the peripheral ID: type << 4 | data bytes
    int32_t buttons;    // PAD_* bits held
    int32_t x;          // the first analog axis, 0 (left) to 255; -1 for none
};

void padRead(Pad& pad);

#endif
