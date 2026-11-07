// Stick Lab: the three steering paths of steer.h side by side on the Saturn,
// driven by the pad on port 1 (the d-pad and a 3D pad's stick drive all three
// at once), to feel and see how each behaves before the game changes.
//
// On screen (320 x 224): the HANDLING setting, the pad's ID, raw stick X and
// d-pad; a graph of the last 4 seconds of each path's steer (one sample a
// tick, the newest at the right; up is right, solid lines the steer, dots
// the target); each path's steer, target and front-wheel angle.
//
// X / Y / Z pick SLOW / NORMAL / QUICK, L / R step slower / quicker; A / B / C
// show or hide the d-pad, CCE stick and new stick paths on the graph.

#include "font.h"
#include "hw.h"
#include "platform.h"
#include "steer.h"

#define WHITE       RGB(31, 31, 31)
#define GREY        RGB(17, 17, 17)
#define FRAME       RGB(9, 9, 9)
#define CENTRE      RGB(13, 13, 13)
#define LOCK_LINE   RGB(10, 10, 10)
#define SECOND_LINE RGB(8, 8, 8)

enum { DPAD, CCE, NEW, PATHS };

static const char* const kPathNames[PATHS] = { "A D-PAD", "B CCE STICK", "C NEW STICK" };
static const uint16_t kSteerColour[PATHS] = { RGB(31, 31, 0), RGB(31, 8, 31), RGB(0, 31, 31) };
static const uint16_t kTargetColour[PATHS] = { RGB(16, 16, 0), RGB(16, 4, 16), RGB(0, 16, 16) };
// rows each steer line takes from its value's: the d-pad's sits one above the
// others', so where it and the new stick agree both show
static const int32_t kLineOffset[PATHS] = { -1, 0, 0 };
// drawn last on top
static const int32_t kDrawOrder[PATHS] = { CCE, NEW, DPAD };

static const char* const kHandlingNames[3] = { "SLOW", "NORMAL", "QUICK" };
static const uint16_t kHandlingColour[3] = { RGB(8, 31, 8), WHITE, RGB(31, 16, 0) };

// INTBACK goes 300 us or more into the vertical blank: 12 lines in, as the
// Tomb Raider project's pad reading does
#define INTBACK_DELAY   2600    // timer ticks, 775 us on the 320-dot clock
// the graph draws until this long after a frame's vertical blank starts:
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

static void drawText(int32_t x, int32_t y, const char* text, uint16_t colour)
{
    for (; *text; text++, x += 8) {
        drawGlyph(x, y, *text, colour, 1);
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

// --- the graph ----------------------------------------------------------------

#define GX          8       // its top left on screen
#define GY          44
#define SAMPLES     120     // 4 seconds of ticks
#define GW          (SAMPLES * 2)
#define GH          112
#define HISTORY     (SAMPLES + 1)   // and the one before the oldest shown, where its line starts

// A steer value's row: up is right, 7/16 of a row a unit (+-125 fits)
static int32_t rowOf(int32_t value)
{
    int32_t row = GH / 2 - value * 7 / 16;
    return row < 1 ? 1 : row > GH - 2 ? GH - 2 : row;
}

// a tick of each path, as the rows its steer and target take
struct Sample
{
    uint8_t steerRow[PATHS];
    uint8_t targetRow[PATHS];
};

static Sample gHistory[HISTORY];
static int32_t gNewest;
static bool gShown[PATHS] = { true, true, true };

static uint16_t gBackground[GW][GH];    // columns of the graph with nothing drawn
static uint16_t gOnScreen[GW][GH];      // what VRAM holds
static int16_t gDrawnTop[GW], gDrawnBottom[GW];     // rows drawn over the background, per column
static uint32_t gColumnKey[GW][PATHS];  // what each column was drawn from (graphColumn)

static uint16_t background(int32_t x, int32_t y)
{
    if (y == GH / 2)
        return CENTRE;
    if ((y == rowOf(PAD_TARGET) || y == rowOf(-PAD_TARGET)) && (x & 7) < 4)
        return LOCK_LINE;
    // a dotted line a second back from the newest sample, 2, 3
    int32_t back = SAMPLES - 1 - x / 2;
    if ((x & 1) == 0 && back > 0 && back % 30 == 0 && (y & 3) == 0)
        return SECOND_LINE;
    return 0;
}

static void graphInit()
{
    for (int32_t s = 0; s < HISTORY; s++)
    {
        for (int32_t p = 0; p < PATHS; p++) {
            gHistory[s].steerRow[p] = gHistory[s].targetRow[p] = rowOf(0);
        }
    }
    for (int32_t x = 0; x < GW; x++)
    {
        for (int32_t y = 0; y < GH; y++)
        {
            uint16_t c = background(x, y);
            gBackground[x][y] = gOnScreen[x][y] = c;
            *pixelAt(GX + x, GY + y) = c;
        }
        gDrawnTop[x] = GH;
        gDrawnBottom[x] = -1;
        for (int32_t p = 0; p < PATHS; p++) {
            gColumnKey[x][p] = ~0u;
        }
    }
    // a frame around it
    fillRect(GX - 1, GY - 1, GW + 2, 1, FRAME);
    fillRect(GX - 1, GY + GH, GW + 2, 1, FRAME);
    fillRect(GX - 1, GY, 1, GH, FRAME);
    fillRect(GX + GW, GY, 1, GH, FRAME);
}

struct Span
{
    int32_t top, bottom;
    uint16_t colour;
};

// One column: sample x / 2's line from the sample before it, and its target
// dot in even columns. Unless the rows it's drawn from have changed, nothing
// to do; otherwise what it shows now against what VRAM holds, writing only
// the pixels that differ, inside the rows drawn before or now.
static void graphColumn(int32_t x)
{
    int32_t i = x / 2;
    const Sample& now = gHistory[(gNewest - (SAMPLES - 1 - i) + HISTORY) % HISTORY];
    const Sample& before = gHistory[(gNewest - (SAMPLES - i) + HISTORY) % HISTORY];

    uint32_t* key = gColumnKey[x];
    bool same = true;
    for (int32_t p = 0; p < PATHS; p++)
    {
        uint32_t k = gShown[p] ? 1u << 24 | before.steerRow[p] << 16 | now.steerRow[p] << 8
            | ((x & 1) ? 0xFF : now.targetRow[p]) : 0;
        same = same && k == key[p];
        key[p] = k;
    }
    if (same)
        return;

    Span spans[2 * PATHS];
    int32_t count = 0;
    if ((x & 1) == 0)
    {
        for (int32_t p = 0; p < PATHS; p++)
        {
            if (gShown[p])
            {
                int32_t row = now.targetRow[p];
                spans[count++] = { row, row, kTargetColour[p] };
            }
        }
    }
    for (int32_t k = 0; k < PATHS; k++)
    {
        int32_t p = kDrawOrder[k];
        if (gShown[p])
        {
            int32_t a = before.steerRow[p], b = now.steerRow[p];
            int32_t top = (a < b ? a : b) + kLineOffset[p];
            int32_t bottom = (a < b ? b : a) + kLineOffset[p] + 1;
            spans[count++] = { top, bottom, kSteerColour[p] };
        }
    }

    int32_t top = GH, bottom = -1;
    for (int32_t s = 0; s < count; s++)
    {
        top = spans[s].top < top ? spans[s].top : top;
        bottom = spans[s].bottom > bottom ? spans[s].bottom : bottom;
    }
    int32_t from = top < gDrawnTop[x] ? top : gDrawnTop[x];
    int32_t to = bottom > gDrawnBottom[x] ? bottom : gDrawnBottom[x];
    gDrawnTop[x] = top;
    gDrawnBottom[x] = bottom;

    uint16_t column[GH];
    for (int32_t y = from; y <= to; y++) {
        column[y] = gBackground[x][y];
    }
    for (int32_t s = 0; s < count; s++)
    {
        for (int32_t y = spans[s].top; y <= spans[s].bottom; y++) {
            column[y] = spans[s].colour;
        }
    }
    uint16_t* screen = gOnScreen[x];
    for (int32_t y = from; y <= to; y++)
    {
        if (column[y] != screen[y])
        {
            screen[y] = column[y];
            *pixelAt(GX + x, GY + y) = column[y];
        }
    }
}

// --- the screen ---------------------------------------------------------------

#define INFO_X      168
#define PANEL_Y     160
#define PANEL_W     104

static Field gHandlingField = { 8, 17, 3, 6, 0, {} };
static Field gIdField = { INFO_X, 8, 1, 18, 0, {} };
static Field gStickField = { INFO_X, 18, 1, 18, 0, {} };
static Field gDpadField = { INFO_X, 28, 1, 18, 0, {} };
static Field gNameFields[PATHS], gSteerFields[PATHS], gDetailFields[PATHS];

static void screenInit()
{
    drawText(8, 8, "HANDLING", GREY);
    graphInit();

    // the graph's captions, beside the lines they name
    int32_t cx = GX + GW + 8;
    drawText(cx, GY + rowOf(PAD_TARGET) - 4, "RIGHT", GREY);
    drawText(cx, GY + GH / 2 - 4, "0", GREY);
    drawText(cx, GY + rowOf(-PAD_TARGET) - 4, "LEFT", GREY);
    drawText(cx, GY + 22, "LINE:", GREY);
    drawText(cx, GY + 32, "STEER", GREY);
    drawText(cx, GY + 72, "DOTS:", GREY);
    drawText(cx, GY + 82, "TARGET", GREY);

    for (int32_t p = 0; p < PATHS; p++)
    {
        int16_t x = 8 + p * PANEL_W;
        gNameFields[p] = { x, PANEL_Y, 1, 12, 0, {} };
        gSteerFields[p] = { x, PANEL_Y + 10, 2, 4, 0, {} };
        gDetailFields[p] = { x, PANEL_Y + 28, 1, 12, 0, {} };
    }
    drawText(8, 199, "X Y Z or L R: HANDLING  A B C: SHOW", GREY);
    drawText(8, 208, "big steer  T target  W wheel  grid 1 s", GREY);
}

// The text: the setting, the pad and each path's numbers.
static void textUpdate(const Pad& pad, int32_t handling, const Path* paths)
{
    char text[24];
    fieldSet(gHandlingField, kHandlingNames[handling], kHandlingColour[handling]);

    if (pad.id == PAD_ID_NONE) {
        put(text, "NO PAD ON PORT 1");
    }
    else
    {
        char* p = putHex2(put(text, "PAD "), pad.id);
        put(p, pad.id == PAD_ID_DIGITAL ? " DIGITAL" : pad.id == PAD_ID_3D ? " 3D ANALOG" : pad.x >= 0 ? " ANALOG" : "");
    }
    fieldSet(gIdField, text, WHITE);

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
        uint16_t colour = gShown[k] ? kSteerColour[k] : GREY;
        fieldSet(gNameFields[k], kPathNames[k], colour);
        putInt(text, paths[k].steer, 4);
        fieldSet(gSteerFields[k], text, colour);
        p = putInt(put(text, "T"), paths[k].target, 4);
        putInt(put(p, " W"), paths[k].wheel / 256, 4);
        fieldSet(gDetailFields[k], text, colour);
    }
}

// --- the tick -----------------------------------------------------------------

// The buttons pressed since the last tick: the setting and the paths shown.
static void handleButtons(int32_t pressed, int32_t& handling)
{
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
    if (pressed & PAD_A) {
        gShown[DPAD] = !gShown[DPAD];
    }
    if (pressed & PAD_B) {
        gShown[CCE] = !gShown[CCE];
    }
    if (pressed & PAD_C) {
        gShown[NEW] = !gShown[NEW];
    }
}

static Pad gPad = { PAD_ID_NONE, 0, -1 };
static Path gPaths[PATHS];

// The three paths a tick on, from the pad as last read (a stick that isn't
// there is centred).
static void __attribute__((noinline)) tick(int32_t handling)
{
    int32_t x = gPad.x >= 0 ? gPad.x : 128;
    dpadTick(gPaths[DPAD], gPad.buttons & PAD_LEFT, gPad.buttons & PAD_RIGHT, handling);
    cceStickTick(gPaths[CCE], x, handling);
    newStickTick(gPaths[NEW], x, handling);

    gNewest = (gNewest + 1) % HISTORY;
    for (int32_t p = 0; p < PATHS; p++)
    {
        wheelTick(gPaths[p]);
        gHistory[gNewest].steerRow[p] = rowOf(gPaths[p].steer);
        gHistory[gNewest].targetRow[p] = rowOf(gPaths[p].target);
    }
}

// The pad is read every frame and the paths tick every other one. The
// graph's columns are drawn in whatever time each frame has left, from where
// the last frame stopped, so a busy graph never holds the next tick back.
int main()
{
    platformInit();
    screenInit();

    int32_t handling = NORMAL;
    int32_t held = 0, pressed = 0;
    int32_t column = 0, columnsLeft = 0;
    for (uint32_t frame = 0;; frame++)
    {
        waitVblankIn();
        uint32_t frameStart = ticks();
        delayTicks(INTBACK_DELAY);
        padRead(gPad);
        pressed |= gPad.buttons & ~held;
        held = gPad.buttons;
        if ((frame & 1) == 0)
        {
            handleButtons(pressed, handling);
            pressed = 0;
            tick(handling);
            textUpdate(gPad, handling, gPaths);
            columnsLeft = GW;
        }
        while (columnsLeft > 0 && ticksSince(frameStart) < DRAW_TICKS)
        {
            graphColumn(column);
            column = column + 1 < GW ? column + 1 : 0;
            columnsLeft--;
        }
    }
}
