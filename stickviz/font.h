// The 8 x 8 font the CPU draws with (libyaul's, see font.cpp), from the Tomb
// Raider project's saturn/font.h.
#ifndef FONT_H
#define FONT_H

#include <stdint.h>

// 8 x 8 glyphs of printable ASCII, FONT8_FIRST on: a byte a row from the top,
// bit 0 the leftmost pixel.
#define FONT8_FIRST ' '
#define FONT8_COUNT 95
extern const uint8_t gFont8[FONT8_COUNT][8];

#endif
