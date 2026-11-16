// Stick Lab: the game's controller paths side by side on the Saturn, driven
// by the pad on port 1, to feel and see how each behaves before the game
// changes. Two pages; START switches between them.
//
// STEERING (steer.h): the d-pad, CCE stick and new stick paths, which the
// d-pad and a 3D pad's stick drive all at once. On screen (320 x 224): the
// HANDLING setting, the pad's ID, raw stick X and d-pad; a graph of the last
// 4 seconds of each path's steer (one sample a tick, the newest at the right;
// up is right, solid lines the steer, dots the target, dashes the front
// wheels' angle); each path's steer, target and front-wheel angle. X / Y / Z
// pick SLOW / NORMAL / QUICK, L / R step slower / quicker; A / B / C show or
// hide the paths. With an Arcade Racer wheel on port 1, path B is the game's
// wheel path instead of the CCE stick, always shown (the wheel's B is the
// gas), and the d-pad and new stick start hidden: neither drives the car with
// a wheel.
//
// PEDALS (pedal.h): DUSA's button, CCE's trigger and the new trigger, the gas
// from a 3D pad's R trigger and the brake from its L, as the game's 3D pad
// layouts have them, all three driven at once (the button is pressed while
// the trigger is past the dead zone). A graph each of the last 4 seconds of
// the pedal as the handling reads it, 0 at the bottom to 255 at the top, with
// the trigger as dots; each path's pedal and raw values. A / B / C show or
// hide the paths. A pad without triggers presses them with R and L, as a
// full trigger.

#include "font.h"
#include "hw.h"
#include "pedal.h"
#include "platform.h"
#include "steer.h"

#define WHITE       RGB(31, 31, 31)
#define GREY        RGB(17, 17, 17)
#define FRAME       RGB(9, 9, 9)
#define CENTRE      RGB(13, 13, 13)
#define LOCK_LINE   RGB(10, 10, 10)
#define SECOND_LINE RGB(8, 8, 8)
#define TRIGGER_DOT RGB(26, 26, 26)

enum { PATH_A, PATH_B, PATH_C, PATHS };
enum { DPAD = PATH_A, CCE = PATH_B, NEW = PATH_C };                     // steering
enum { BUTTON = PATH_A, CCE_TRIGGER = PATH_B, NEW_TRIGGER = PATH_C };   // pedals

static const char* const kSteerNames[PATHS] = { "A D-PAD", "B CCE STICK", "C NEW STICK" };
static const char* const kPedalNames[PATHS] = { "A BUTTON", "B CCE TRIG", "C NEW TRIG" };
static const uint16_t kLineColour[PATHS] = { RGB(31, 31, 0), RGB(31, 8, 31), RGB(0, 31, 31) };
static const uint16_t kTargetColour[PATHS] = { RGB(16, 16, 0), RGB(16, 4, 16), RGB(0, 16, 16) };
static const uint16_t kWheelColour[PATHS] = { RGB(22, 22, 8), RGB(22, 8, 22), RGB(8, 22, 22) };
static const uint16_t kTriggerColour[PATHS] = { TRIGGER_DOT, TRIGGER_DOT, TRIGGER_DOT };
// rows each line takes from its value's: A's sits one above the others', so
// where it and C agree both show
static const int32_t kLineOffset[PATHS] = { -1, 0, 0 };
// drawn last on top
static const int32_t kDrawOrder[PATHS] = { PATH_B, PATH_C, PATH_A };

static const char* const kHandlingNames[3] = { "SLOW", "NORMAL", "QUICK" };
static const uint16_t kHandlingColour[3] = { RGB(8, 31, 8), WHITE, RGB(31, 16, 0) };

// INTBACK goes 300 us or more into the vertical blank: 12 lines in, as the
// Tomb Raider project's pad reading does
#define INTBACK_DELAY   2600    // timer ticks, 775 us on the 320-dot clock
// the graphs draw until this long after a frame's vertical blank starts:
// 82% of a frame of 56,150 ticks, the rest a margin for the last column
#define DRAW_TICKS      46000

// --- text -------------------------------------------------------------------

static void drawGlyph(int32_t x, int32_t y, char c, uint16_t colour, int32_t scale)
{
    const uint8_t* rows = (c >= FONT8_FIRST && c < FONT8_FIRST + FONT8_COUNT) ? gFont8[c - FONT8_FIRST] : gFont8[0];
    for (int32_t row = 0; row < 8; row++)
    {
        for (int32_t sy = 0; sy < scale; sy++)
        {
            volatile uint16_t* p = pixelAt(x, y + row * scale + sy);
            for (int32_t col = 0; col < 8; col++)
            {
                uint16_t pixel = (rows[row] >> col) & 1 ? colour : 0;
                for (int32_t sx = 0; sx < scale; sx++) {
                    *p++ = pixel;
                }
            }
        }
    }
}

static void drawText(int32_t x, int32_t y, const char* text, uint16_t colour, int32_t scale = 1)
{
    for (; *text; text++, x += 8 * scale) {
        drawGlyph(x, y, *text, colour, scale);
    }
}

// Text that changes: only the characters that differ from what's shown are
// drawn again, padded with spaces to its width.
struct Field
{
    int16_t x, y;
    int16_t scale, width;
    uint16_t colour;
    char shown[20];
};

static void fieldSet(Field& f, const char* text, uint16_t colour)
{
    bool recolour = colour != f.colour;
    f.colour = colour;
    for (int32_t i = 0; i < f.width; i++)
    {
        char c = *text ? *text++ : ' ';
        if (c != f.shown[i] || recolour)
        {
            drawGlyph(f.x + i * 8 * f.scale, f.y, c, colour, f.scale);
            f.shown[i] = c;
        }
    }
}

static constexpr Field field(int32_t x, int32_t y, int32_t scale, int32_t width)
{
    return { (int16_t)x, (int16_t)y, (int16_t)scale, (int16_t)width, 0, {} };
}

static char* put(char* p, const char* s)
{
    while (*s) {
        *p++ = *s++;
    }
    *p = 0;
    return p;
}

// value right-aligned in width characters
static char* putInt(char* p, int32_t value, int32_t width)
{
    char digits[12];
    int32_t n = 0;
    uint32_t v = value < 0 ? -value : value;
    do
    {
        digits[n++] = '0' + v % 10;
        v /= 10;
    } while (v);
    if (value < 0) {
        digits[n++] = '-';
    }
    for (int32_t i = n; i < width; i++) {
        *p++ = ' ';
    }
    while (n) {
        *p++ = digits[--n];
    }
    *p = 0;
    return p;
}

static char* putHex2(char* p, int32_t value)
{
    const char* hex = "0123456789ABCDEF";
    *p++ = hex[(value >> 4) & 15];
    *p++ = hex[value & 15];
    *p = 0;
    return p;
}

// --- the graphs ---------------------------------------------------------------

#define SAMPLES     120     // 4 seconds of ticks
#define GW          (SAMPLES * 2)
#define GH_MAX      112
#define HISTORY     (SAMPLES + 1)   // and the one before the oldest shown, where its line starts
#define NO_ROW      0xFF

// a tick of a graph's paths as rows: each path's line, and its dot (drawn in
// even columns) and dash (odd columns) where it has them
struct Sample
{
    uint8_t line[PATHS];
    uint8_t dot[PATHS];
    uint8_t dash[PATHS];
};

struct Graph
{
    int16_t x, y, h;                // its top left on screen, its rows
    const uint16_t* dotColour;
    const uint16_t* dashColour;
    bool dotsAlways;                // dots drawn whether or not their path is
    uint16_t (*background)(int32_t x, int32_t y);
    const bool* shown;              // the paths drawn
    Sample history[HISTORY];
    int32_t newest;
    uint16_t bg[GW][GH_MAX];        // columns with nothing drawn
    uint16_t onScreen[GW][GH_MAX];  // what VRAM holds
    int16_t drawnTop[GW], drawnBottom[GW];  // rows drawn over the background, per column
    uint64_t key[GW][PATHS];        // what each column was drawn from (graphColumn)
};

static void graphSetup(Graph& g, int32_t x, int32_t y, int32_t h, const uint16_t* dotColour,
                       const uint16_t* dashColour, bool dotsAlways, uint16_t (*background)(int32_t, int32_t),
                       const bool* shown, const Sample& rest)
{
    g.x = x;
    g.y = y;
    g.h = h;
    g.dotColour = dotColour;
    g.dashColour = dashColour;
    g.dotsAlways = dotsAlways;
    g.background = background;
    g.shown = shown;
    for (int32_t s = 0; s < HISTORY; s++) {
        g.history[s] = rest;
    }
    g.newest = 0;
}

static void graphPush(Graph& g, const Sample& s)
{
    g.newest = (g.newest + 1) % HISTORY;
    g.history[g.newest] = s;
}

// The empty graph and its frame on screen; every column is drawn again from
// its history.
static void graphShow(Graph& g)
{
    for (int32_t x = 0; x < GW; x++)
    {
        for (int32_t y = 0; y < g.h; y++)
        {
            uint16_t c = g.background(x, y);
            g.bg[x][y] = g.onScreen[x][y] = c;
            *pixelAt(g.x + x, g.y + y) = c;
        }
        g.drawnTop[x] = g.h;
        g.drawnBottom[x] = -1;
        for (int32_t p = 0; p < PATHS; p++) {
            g.key[x][p] = ~0ull;
        }
    }
    fillRect(g.x - 1, g.y - 1, GW + 2, 1, FRAME);
    fillRect(g.x - 1, g.y + g.h, GW + 2, 1, FRAME);
    fillRect(g.x - 1, g.y, 1, g.h, FRAME);
    fillRect(g.x + GW, g.y, 1, g.h, FRAME);
}

struct Span
{
    int32_t top, bottom;
    uint16_t colour;
};

// One column: sample x / 2's lines from the sample before it, with the dots
// in even columns and the dashes in odd ones. Unless the rows it's drawn from
// have changed, nothing to do; otherwise what it shows now against what VRAM
// holds, writing only the pixels that differ, inside the rows drawn before or
// now.
static void graphColumn(Graph& g, int32_t x)
{
    int32_t i = x / 2;
    const Sample& now = g.history[(g.newest - (SAMPLES - 1 - i) + HISTORY) % HISTORY];
    const Sample& before = g.history[(g.newest - (SAMPLES - i) + HISTORY) % HISTORY];
    bool odd = x & 1;

    Span spans[2 * PATHS];
    int32_t count = 0;
    uint64_t* key = g.key[x];
    bool same = true;
    for (int32_t p = 0; p < PATHS; p++)
    {
        uint64_t k = g.shown[p] ? 1ull << 48 | (uint64_t)before.line[p] << 32 | (uint64_t)now.line[p] << 24 : 0;
        if (odd)
        {
            if (g.shown[p] && now.dash[p] != NO_ROW)
            {
                int32_t a = before.dash[p] != NO_ROW ? before.dash[p] : now.dash[p], b = now.dash[p];
                k |= 1ull << 16 | (uint64_t)a << 8 | b;
                spans[count++] = { a < b ? a : b, a < b ? b : a, g.dashColour[p] };
            }
        }
        else if ((g.shown[p] || g.dotsAlways) && now.dot[p] != NO_ROW)
        {
            k |= 1ull << 16 | now.dot[p];
            spans[count++] = { now.dot[p], now.dot[p], g.dotColour[p] };
        }
        same = same && k == key[p];
        key[p] = k;
    }
    if (same)
        return;

    for (int32_t n = 0; n < PATHS; n++)
    {
        int32_t p = kDrawOrder[n];
        if (g.shown[p])
        {
            int32_t a = before.line[p], b = now.line[p];
            int32_t top = (a < b ? a : b) + kLineOffset[p];
            int32_t bottom = (a < b ? b : a) + kLineOffset[p] + 1;
            spans[count++] = { top, bottom, kLineColour[p] };
        }
    }

    int32_t top = g.h, bottom = -1;
    for (int32_t s = 0; s < count; s++)
    {
        top = spans[s].top < top ? spans[s].top : top;
        bottom = spans[s].bottom > bottom ? spans[s].bottom : bottom;
    }
    int32_t from = top < g.drawnTop[x] ? top : g.drawnTop[x];
    int32_t to = bottom > g.drawnBottom[x] ? bottom : g.drawnBottom[x];
    g.drawnTop[x] = top;
    g.drawnBottom[x] = bottom;

    uint16_t column[GH_MAX];
    for (int32_t y = from; y <= to; y++) {
        column[y] = g.bg[x][y];
    }
    for (int32_t s = 0; s < count; s++)
    {
        for (int32_t y = spans[s].top; y <= spans[s].bottom; y++) {
            column[y] = spans[s].colour;
        }
    }
    uint16_t* screen = g.onScreen[x];
    for (int32_t y = from; y <= to; y++)
    {
        if (column[y] != screen[y])
        {
            screen[y] = column[y];
            *pixelAt(g.x + x, g.y + y) = column[y];
        }
    }
}

// a dotted line a second back from the newest sample, 2, 3
static bool secondLine(int32_t x, int32_t y)
{
    int32_t back = SAMPLES - 1 - x / 2;
    return (x & 1) == 0 && back > 0 && back % 30 == 0 && (y & 3) == 0;
}

// --- the steering graph -------------------------------------------------------

#define STEER_GY    44
#define STEER_GH    112

// A steer value's row: up is right, 7/16 of a row a unit (+-125 fits)
static int32_t steerRow(int32_t value)
{
    int32_t row = STEER_GH / 2 - value * 7 / 16;
    return row < 1 ? 1 : row > STEER_GH - 2 ? STEER_GH - 2 : row;
}

static uint16_t steerBackground(int32_t x, int32_t y)
{
    if (y == STEER_GH / 2)
        return CENTRE;
    if ((y == steerRow(HANDLING_LOCK) || y == steerRow(-HANDLING_LOCK)) && (x & 7) < 4)
        return LOCK_LINE;
    return secondLine(x, y) ? SECOND_LINE : 0;
}

// --- the pedal graphs ---------------------------------------------------------

#define GAS_GY      40
#define BRAKE_GY    118
#define PEDAL_GH    64

// A pedal value's row: 0 at the bottom, 255 at the top
static int32_t pedalRow(int32_t value)
{
    return PEDAL_GH - 2 - clampTo(value, 0, 255) * (PEDAL_GH - 3) / 255;
}

static uint16_t pedalBackground(int32_t x, int32_t y)
{
    if (y == pedalRow(0))
        return CENTRE;
    if (y == pedalRow(255) && (x & 7) < 4)
        return LOCK_LINE;
    if (y == pedalRow(128) && (x & 7) == 0)
        return SECOND_LINE;
    return secondLine(x, y) ? SECOND_LINE : 0;
}

// --- the state ----------------------------------------------------------------

enum Page { STEERING, PEDALS };

static Pad gPad = { PAD_ID_NONE, 0, -1, -1, -1 };
static Path gPaths[PATHS];
static Pedal gGas[PATHS], gBrake[PATHS];
static int32_t gGasTrigger, gBrakeTrigger;
static bool gSteerShown[PATHS] = { true, true, true };
static bool gPedalShown[PATHS] = { true, true, true };
static Graph gSteerGraph, gGasGraph, gBrakeGraph;

// --- the screen ---------------------------------------------------------------

#define INFO_X      168
#define PANEL_Y     160
#define PANEL_W     104
#define VALUE_X     (8 + GW + 8)    // right of the graphs

static Field gHandlingField = field(8, 17, 3, 6);
static Field gIdField = field(INFO_X, 8, 1, 18);
static Field gStickField = field(INFO_X, 18, 1, 18);
static Field gDpadField = field(INFO_X, 28, 1, 18);
static Field gNameFields[PATHS], gSteerFields[PATHS], gDetailFields[PATHS];

static Field gTriggerField = field(INFO_X, 18, 1, 18);
static Field gPedalNameFields[PATHS], gRawFields[PATHS];
static Field gGasFields[PATHS + 1], gBrakeFields[PATHS + 1];   // each path's pedal, then the trigger

static void fieldReset(Field& f)
{
    f.colour = 0;
    for (int32_t i = 0; i < f.width; i++) {
        f.shown[i] = 0;
    }
}

static void steeringShow()
{
    drawText(8, 8, "HANDLING", GREY);
    graphShow(gSteerGraph);

    // the graph's captions, beside the lines they name
    int32_t cx = VALUE_X;
    drawText(cx, STEER_GY + steerRow(PAD_TARGET) - 4, "RIGHT", GREY);
    drawText(cx, STEER_GY + STEER_GH / 2 - 4, "0", GREY);
    drawText(cx, STEER_GY + steerRow(-PAD_TARGET) - 4, "LEFT", GREY);
    drawText(cx, STEER_GY + 13, "LINE:", GREY);
    drawText(cx, STEER_GY + 22, "STEER", GREY);
    drawText(cx, STEER_GY + 31, "DASH:", GREY);
    drawText(cx, STEER_GY + 40, "WHEEL", GREY);
    drawText(cx, STEER_GY + 64, "DOTS:", GREY);
    drawText(cx, STEER_GY + 74, "TARGET", GREY);
    drawText(cx, STEER_GY + 84, "GRID:", GREY);
    drawText(cx, STEER_GY + 93, "1 S", GREY);

    Field* fields[] = { &gHandlingField, &gIdField, &gStickField, &gDpadField };
    for (Field* f : fields) {
        fieldReset(*f);
    }
    for (int32_t p = 0; p < PATHS; p++)
    {
        int32_t x = 8 + p * PANEL_W;
        gNameFields[p] = field(x, PANEL_Y, 1, 12);
        gSteerFields[p] = field(x, PANEL_Y + 10, 2, 4);
        gDetailFields[p] = field(x, PANEL_Y + 28, 1, 12);
    }
    drawText(8, 199, "X Y Z or L R: HANDLING  A B C: SHOW", GREY);
    drawText(8, 208, "T target  W wheel  START: PEDALS", GREY);
}

static void pedalsShow()
{
    drawText(8, 8, "PEDALS", WHITE, 2);
    drawText(INFO_X, 28, "DOTS: THE TRIGGER", GREY);
    graphShow(gGasGraph);
    graphShow(gBrakeGraph);
    drawText(VALUE_X, GAS_GY + 2, "GAS", WHITE);
    drawText(VALUE_X, BRAKE_GY + 2, "BRAKE", WHITE);

    fieldReset(gIdField);
    fieldReset(gTriggerField);
    for (int32_t p = 0; p <= PATHS; p++)
    {
        int32_t dy = p < PATHS ? 14 + p * 10 : 46;
        gGasFields[p] = field(VALUE_X, GAS_GY + dy, 1, 5);
        gBrakeFields[p] = field(VALUE_X, BRAKE_GY + dy, 1, 5);
    }
    for (int32_t p = 0; p < PATHS; p++)
    {
        int32_t x = 8 + p * PANEL_W;
        gPedalNameFields[p] = field(x, 188, 1, 12);
        gRawFields[p] = field(x, 198, 1, 12);
    }
    drawText(8, 210, "R GAS L BRAKE  ABC: SHOW  START: STEER", GREY);
}

static void pageShow(Page page)
{
    fillRect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0);
    if (page == STEERING) {
        steeringShow();
    } else {
        pedalsShow();
    }
}

static void padIdText(const Pad& pad, Field& f)
{
    char text[24];
    if (pad.id == PAD_ID_NONE) {
        put(text, "NO PAD ON PORT 1");
    }
    else
    {
        char* p = putHex2(put(text, "PAD "), pad.id);
        put(p, pad.id == PAD_ID_DIGITAL ? " DIGITAL" : pad.id == PAD_ID_3D ? " 3D ANALOG"
               : pad.id == PAD_ID_WHEEL ? " WHEEL" : pad.x >= 0 ? " ANALOG" : "");
    }
    fieldSet(f, text, WHITE);
}

// The steering page's text: the setting, the pad and each path's numbers.
static void steeringText(const Pad& pad, int32_t handling)
{
    char text[24];
    fieldSet(gHandlingField, kHandlingNames[handling], kHandlingColour[handling]);
    padIdText(pad, gIdField);

    char* p = put(text, "STICK X ");
    if (pad.x >= 0) {
        putInt(p, pad.x, 3);
    } else {
        put(p, "---");
    }
    fieldSet(gStickField, text, WHITE);

    bool left = pad.buttons & PAD_LEFT, right = pad.buttons & PAD_RIGHT;
    put(text, left && right ? "D-PAD LEFT+RIGHT" : left ? "D-PAD LEFT" : right ? "D-PAD RIGHT" : "D-PAD -");
    fieldSet(gDpadField, text, WHITE);

    for (int32_t k = 0; k < PATHS; k++)
    {
        uint16_t colour = gSteerShown[k] ? kLineColour[k] : GREY;
        fieldSet(gNameFields[k], k == CCE && pad.id == PAD_ID_WHEEL ? "B WHEEL" : kSteerNames[k], colour);
        putInt(text, gPaths[k].steer, 4);
        fieldSet(gSteerFields[k], text, colour);
        p = putInt(put(text, "T"), gPaths[k].target, 4);
        putInt(put(p, " W"), gPaths[k].wheel / 256, 4);
        fieldSet(gDetailFields[k], text, colour);
    }
}

// The pedal page's text: the pad, the triggers and each path's pedals.
static void pedalsText(const Pad& pad)
{
    static const char kLetter[PATHS + 1] = { 'A', 'B', 'C', 'T' };
    char text[24];
    padIdText(pad, gIdField);

    if (pad.r >= 0) {
        putInt(put(putInt(put(text, "TRIG R "), pad.r, 3), "  L "), pad.l, 3);
    } else {
        put(text, "NO TRIGGERS: R L");
    }
    fieldSet(gTriggerField, text, WHITE);

    for (int32_t k = 0; k <= PATHS; k++)
    {
        uint16_t colour = k == PATHS ? TRIGGER_DOT : gPedalShown[k] ? kLineColour[k] : GREY;
        text[0] = kLetter[k];
        text[1] = 0;
        putInt(text + 1, k < PATHS ? gasPedal(gGas[k].raw) : gGasTrigger, 4);
        fieldSet(gGasFields[k], text, colour);
        putInt(text + 1, k < PATHS ? brakePedal(gBrake[k].raw) : gBrakeTrigger, 4);
        fieldSet(gBrakeFields[k], text, colour);
    }
    for (int32_t k = 0; k < PATHS; k++)
    {
        uint16_t colour = gPedalShown[k] ? kLineColour[k] : GREY;
        fieldSet(gPedalNameFields[k], kPedalNames[k], colour);
        putInt(putInt(put(text, "RAW"), gGas[k].raw, 4), gBrake[k].raw, 4);
        fieldSet(gRawFields[k], text, colour);
    }
}

// --- the tick -----------------------------------------------------------------

// The buttons pressed since the last tick: the setting and the paths shown.
static void handleButtons(int32_t pressed, int32_t& handling, bool wheel, Page page)
{
    bool* shown = page == STEERING ? gSteerShown : gPedalShown;
    if (page == STEERING)
    {
        if (wheel) {
            pressed &= ~PAD_B;  // the gas: the wheel line stays shown
        }
        if (pressed & PAD_X) {
            handling = SLOW;
        }
        if (pressed & PAD_Y) {
            handling = NORMAL;
        }
        if (pressed & PAD_Z) {
            handling = QUICK;
        }
        if ((pressed & PAD_L) && handling > SLOW) {
            handling--;
        }
        if ((pressed & PAD_R) && handling < QUICK) {
            handling++;
        }
    }
    if (pressed & PAD_A) {
        shown[PATH_A] = !shown[PATH_A];
    }
    if (pressed & PAD_B) {
        shown[PATH_B] = !shown[PATH_B];
    }
    if (pressed & PAD_C) {
        shown[PATH_C] = !shown[PATH_C];
    }
}

static void steeringTick(int32_t handling)
{
    int32_t x = gPad.x >= 0 ? gPad.x : 128;     // a stick that isn't there is centred
    dpadTick(gPaths[DPAD], gPad.buttons & PAD_LEFT, gPad.buttons & PAD_RIGHT, handling);
    if (gPad.id == PAD_ID_WHEEL) {
        wheelSteerTick(gPaths[CCE], x);
    } else {
        cceStickTick(gPaths[CCE], x, handling);
    }
    newStickTick(gPaths[NEW], x, handling);

    Sample s;
    for (int32_t p = 0; p < PATHS; p++)
    {
        wheelTick(gPaths[p]);
        s.line[p] = steerRow(gPaths[p].steer);
        s.dot[p] = steerRow(gPaths[p].target);
        s.dash[p] = steerRow(gPaths[p].wheel / 256);
    }
    graphPush(gSteerGraph, s);
}

static void pedalsTick()
{
    // a pad without triggers: R and L pressed are a full trigger
    gGasTrigger = gPad.r >= 0 ? gPad.r : (gPad.buttons & PAD_R) ? 255 : 0;
    gBrakeTrigger = gPad.l >= 0 ? gPad.l : (gPad.buttons & PAD_L) ? 255 : 0;
    gasButtonTick(gGas[BUTTON], gGasTrigger > PEDAL_DEAD_ZONE);
    gasCceTick(gGas[CCE_TRIGGER], gGasTrigger);
    gasNewTick(gGas[NEW_TRIGGER], gGasTrigger);
    brakeButtonTick(gBrake[BUTTON], gBrakeTrigger > PEDAL_DEAD_ZONE);
    brakeCceTick(gBrake[CCE_TRIGGER], gBrakeTrigger);
    brakeNewTick(gBrake[NEW_TRIGGER], gBrakeTrigger);

    Sample gas, brake;
    for (int32_t p = 0; p < PATHS; p++)
    {
        gas.line[p] = pedalRow(gasPedal(gGas[p].raw));
        brake.line[p] = pedalRow(brakePedal(gBrake[p].raw));
        gas.dot[p] = brake.dot[p] = gas.dash[p] = brake.dash[p] = NO_ROW;
    }
    gas.dot[0] = pedalRow(gGasTrigger);
    brake.dot[0] = pedalRow(gBrakeTrigger);
    graphPush(gGasGraph, gas);
    graphPush(gBrakeGraph, brake);
}

static void graphsInit()
{
    Sample steerRest, pedalRest;
    for (int32_t p = 0; p < PATHS; p++)
    {
        steerRest.line[p] = steerRest.dot[p] = steerRest.dash[p] = steerRow(0);
        pedalRest.line[p] = pedalRow(0);
        pedalRest.dot[p] = pedalRest.dash[p] = NO_ROW;
        pedalInit(gGas[p]);
        pedalInit(gBrake[p]);
    }
    pedalRest.dot[0] = pedalRow(0);
    graphSetup(gSteerGraph, 8, STEER_GY, STEER_GH, kTargetColour, kWheelColour, false, steerBackground,
               gSteerShown, steerRest);
    graphSetup(gGasGraph, 8, GAS_GY, PEDAL_GH, kTriggerColour, kTriggerColour, true, pedalBackground,
               gPedalShown, pedalRest);
    graphSetup(gBrakeGraph, 8, BRAKE_GY, PEDAL_GH, kTriggerColour, kTriggerColour, true, pedalBackground,
               gPedalShown, pedalRest);
}

// The pad is read every frame and the paths tick every other one. The
// graphs' columns are drawn in whatever time each frame has left, from where
// the last frame stopped, so a busy graph never holds the next tick back.
// Both pages' paths tick whichever is shown.
int main()
{
    platformInit();
    graphsInit();
    Page page = STEERING;
    pageShow(page);

    int32_t handling = NORMAL;
    int32_t held = 0, pressed = 0;
    int32_t column = 0, columnsLeft = 0;
    bool wheelSeen = false;
    for (uint32_t frame = 0;; frame++)
    {
        waitVblankIn();
        uint32_t frameStart = ticks();
        delayTicks(INTBACK_DELAY);
        padRead(gPad);
        pressed |= gPad.buttons & ~held;
        held = gPad.buttons;
        bool wheel = gPad.id == PAD_ID_WHEEL;
        if (wheel && !wheelSeen)
        {
            gSteerShown[DPAD] = gSteerShown[NEW] = false;
            gSteerShown[CCE] = true;
            wheelSeen = true;
        }
        if ((frame & 1) == 0 && (pressed & PAD_START))
        {
            page = page == STEERING ? PEDALS : STEERING;
            pageShow(page);
            column = 0;
        }
        Graph* graphs[2] = { &gSteerGraph, nullptr };
        if (page == PEDALS)
        {
            graphs[0] = &gGasGraph;
            graphs[1] = &gBrakeGraph;
        }
        int32_t graphCount = page == PEDALS ? 2 : 1;
        if ((frame & 1) == 0)
        {
            handleButtons(pressed, handling, wheel, page);
            pressed = 0;
            steeringTick(handling);
            pedalsTick();
            if (page == STEERING) {
                steeringText(gPad, handling);
            } else {
                pedalsText(gPad);
            }
            columnsLeft = GW * graphCount;
        }
        while (columnsLeft > 0 && ticksSince(frameStart) < DRAW_TICKS)
        {
            graphColumn(*graphs[column / GW], column % GW);
            column = column + 1 < GW * graphCount ? column + 1 : 0;
            columnsLeft--;
        }
    }
}
