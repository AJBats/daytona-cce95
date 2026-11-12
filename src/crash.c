/* A crash screen for players' reports, after Tomb Raider Saturn's (its
 * saturn/crash.cpp). tools/crash.py builds this and src/crash_entry.s into
 * DAYTONA/CRASH.BIN, which patches/crash.s loads at boot, after CCE's init,
 * to CRASH_AT: a stretch of the zeros CCE's main program carries before its
 * code at 060191A8, which nothing else uses.
 *
 * The screen comes up in a solid colour for the kind of crash:
 *   red      the main CPU took an exception
 *   magenta  the second CPU took an exception
 *   blue     the game stood still: CCE's main loop (its frame count
 *            06011F84) didn't move for FROZEN VBlanks while no file was
 *            loading (06011FB8 is 0 through every load)
 * and shows the build, the game's state, the CPU's registers and the code
 * addresses on its stack, for a photo. It stays up until the reset.
 *
 * The exceptions are the SH-2's four: an illegal instruction (vector 4),
 * one in a delay slot (6), an address error (9) and a DMA address error
 * (10), on both CPUs (vector tables at 06000000 and 06000400). CCE has its
 * own handlers for 4 and 9 (0600735C: a line of text on whatever layer is
 * up, then back to the same fault); ours replace them.
 *
 * The SH-2 shifts by a variable only in a library call, and the blob has
 * little room, so every shift here is by a constant. */

#include "crash_version.h"      /* CRASH_VERSION, from tools/crash.py */

/* src/crash_entry.s's frame on the stack, 21 words from the stack pointer
 * up: MACH, MACL, GBR, R0-R13, PR, R14, PC, SR. R15 as it was is past it. */

/* the second CPU's crash: its frame's address (0 until then) and the vector */
unsigned crash_slave[2];
unsigned crash_max_still;       /* the longest stand-still seen, for tests */
static unsigned last_beat, still;

#define THRU 0x20000000         /* the cache-through mirror: what the other CPU wrote */
#define FROZEN 600              /* VBlanks: 10 s at 60 Hz */
#define BEAT (*(volatile unsigned *)0x06011F84)         /* CCE's main loop: +1 a frame */
#define IDLE (*(volatile unsigned char *)0x06011FB8)    /* 0 while a file loads */

void crash_m4(void), crash_m6(void), crash_m9(void), crash_m10(void);
void crash_s4(void), crash_s6(void), crash_s9(void), crash_s10(void);
void crash_vbl_entry(void);
#define MASTER_VBR ((void *volatile *)0x06000000)
#define SLAVE_VBR ((void *volatile *)(0x06000400 | THRU))

static void vectors(void)
{
    MASTER_VBR[4] = crash_m4;
    MASTER_VBR[6] = crash_m6;
    MASTER_VBR[9] = crash_m9;
    MASTER_VBR[10] = crash_m10;
    SLAVE_VBR[4] = crash_s4;
    SLAVE_VBR[6] = crash_s6;
    SLAVE_VBR[9] = crash_s9;
    SLAVE_VBR[10] = crash_s10;
}

/* patches/crash.s, once CRASH.BIN is in place: the vectors, and our VBlank
 * in front of CCE's (060054D4 put CCE's there; the attract and the title
 * take the vector later and give back what they found). */
void crash_init(void)
{
    vectors();
    MASTER_VBR[0x40] = crash_vbl_entry;
}

/* ---- the screen ---- */

#define VDP2(off) (*(volatile unsigned short *)(0x25F80000 + (off)))
#define VRAM ((volatile unsigned short *)0x25E00000)
#define PITCH 512
#define RGB(r, g, b) (0x8000 | (b) << 10 | (g) << 5 | (r))

/* With every VDP2 register from RAMCTL on cleared first (every layer,
 * window, scroll, colour calculation and offset off, sprites hidden at
 * priority 0): NBG0 alone, a 512 x 256 bitmap of 15-bit colour at VRAM 0,
 * as Tomb Raider's screen. Bank A's first four slots read it, the CPU has
 * the rest. */
static const unsigned short setup[][2] = {
    {0x0E, 0x0300},             /* RAMCTL: banks A0, A1, B0, B1 */
    {0x10, 0x4444}, {0x12, 0xEEEE}, {0x14, 0x4444}, {0x16, 0xEEEE},
    {0x18, 0xEEEE}, {0x1A, 0xEEEE}, {0x1C, 0xEEEE}, {0x1E, 0xEEEE},
    {0x20, 0x0001},             /* BGON: NBG0 */
    {0x28, 0x0032},             /* CHCTLA: NBG0 15-bit, bitmap 512 x 256 */
    {0x78, 1}, {0x7C, 1},       /* NBG0 zoom 1 */
    {0xF8, 7},                  /* PRINA: NBG0 at priority 7 */
};

/* A 3 x 5 font from '+' to 'Z', rows from the top, 3 bits a row */
#define FIRST '+'
static const unsigned short font['Z' + 1 - FIRST] = {
    ['+' - FIRST] = 0x05D0, ['-' - FIRST] = 0x01C0, ['.' - FIRST] = 0x0002, ['/' - FIRST] = 0x12A4,
    ['0' - FIRST] = 0x7B6F, 0x2C97, 0x73E7, 0x73CF, 0x5BC9, 0x79CF, 0x79EF, 0x7249, 0x7BEF, 0x7BCF,
    [':' - FIRST] = 0x0410,
    ['A' - FIRST] = 0x2BED, 0x6BAE, 0x3923, 0x6B6E, 0x79A7, 0x79A4, 0x396B, 0x5BED, 0x7497, 0x126A, 0x5BAD,
    0x4927, 0x5FED, 0x6B6D, 0x2B6A, 0x6BA4, 0x2B73, 0x6BAD, 0x388E, 0x7492, 0x5B6F, 0x5B6A, 0x5BFD, 0x5AAD,
    0x5A92, 0x72A7,
};

/* at twice its size, in cells of 8 x 12, with a margin for the TV's
 * overscan: 36 columns, 17 rows */
#define ORIGIN (VRAM + 8 * PITCH + 16)
static volatile unsigned short *line, *pen;

static void ch(unsigned c)
{
    unsigned g = c - FIRST <= 'Z' - FIRST ? font[c - FIRST] : 0;
    volatile unsigned short *p = pen;
    int x, y;

    for (y = 0; y < 5; y++, p += 2 * PITCH - 6)
        for (x = 0; x < 3; x++, p += 2, g <<= 1)
            if (g & 0x4000)
                p[0] = p[1] = p[PITCH] = p[PITCH + 1] = 0xFFFF;
    pen += 8;
}

static void str(const char *s)
{
    while (*s)
        ch(*s++);
}

static void hex(unsigned v, int digits)    /* 2 or 8 */
{
    if (digits == 2)
        v <<= 24;
    while (digits--) {
        ch("0123456789ABCDEF"[v >> 28]);
        v <<= 4;
    }
}

static void next_row(void)
{
    pen = line += 12 * PITCH;
}

/* The text: ~ and a letter print a word: A-U the frame's (MACH, MACL, GBR,
 * R0-R13, PR, R14, PC, SR), V the stack pointer, W CCE's frame count; ^ and a
 * digit a byte of the game's state, @ the kind of crash, # the code
 * addresses on the stack, | starts the next row. */
static const char text[] =
    "DAYTONA USA ULTIMATE CRASHED.|"
    "PLEASE TAKE A PHOTO OF THIS SCREEN|"
    "FOR GITHUB.COM/AJBATS/DAYTONA-CCE95|"
    CRASH_VERSION "|"
    "@|"
    "GAME ^0 ^1 ^2 ^3 ^4 ~W|"
    "PC ~T PR ~R GB ~C|"
    "SR ~U SP ~V|"
    "R0  ~D ~E ~F|"
    "R3  ~G ~H ~I|"
    "R6  ~J ~K ~L|"
    "R9  ~M ~N ~O|"
    "R12 ~P ~Q ~S|"
    "CALLS #";

/* the program flow's program (0601927A), the game mode, the course, the
 * attract's demo, the replay flag */
static const unsigned char *const game[5] = {
    (void *)0x06019A21, (void *)0x002FC233, (void *)0x06054920, (void *)0x0601335C, (void *)0x06054923,
};

static const char *const kinds[] = {
    "MAIN CPU: ", "2ND CPU: ", "FROZE FOR 10 S",
    "ILLEGAL INSTRUCTION", "ILLEGAL DELAY SLOT", "ADDRESS ERROR", "DMA ADDRESS ERROR",
};

static int code(unsigned w)
{
    return !(w & 1) && ((w >= 0x06004000 && w < 0x06060000)        /* CCE's programs, our blocks */
                        || (w >= 0x00242300 && w < 0x00250000)     /* src/menu_title.c */
                        || (w >= 0x002E2780 && w < 0x002F0000));   /* src/attract.c */
}

/* kind 0: the main CPU's exception, 1: the second CPU's, 2: frozen.
 * From src/crash_entry.s for the main CPU's exceptions, else crash_vbl. */
__attribute__((noreturn))
void crash_report(const volatile unsigned *f, unsigned sp, unsigned vector, int kind)
{
    static const unsigned short backs[3] = {RGB(20, 0, 0), RGB(20, 0, 20), RGB(0, 0, 20)};
    const char *t;
    unsigned i, n, top, w;

    for (i = 0; i < 3; i++)
        *(volatile unsigned *)(0x25FE0010 + i * 0x20) = 0;     /* SCU DMA off: none rewrites VDP2 */
    for (i = 0x0E; i < 0x120; i += 2)
        VDP2(i) = 0;
    for (i = 0; i < sizeof setup / sizeof setup[0]; i++)
        VDP2(setup[i][0]) = setup[i][1];
    /* TVMD: display on, 224 lines, and the width the clock is set for, the
     * BIOS's note of it at 06000324: 1 352 dots (CCE's), 0 320. The other
     * width on this clock is a picture the TV can't hold. */
    VDP2(0x00) = 0x8000 | (*(volatile unsigned *)0x06000324 & 1);
    w = backs[kind] * 0x10001;
    for (i = 0; i < PITCH * 224 / 2; i++)
        ((volatile unsigned *)VRAM)[i] = w;

    pen = line = ORIGIN;
    for (t = text; *t; t++) {
        switch (*t) {
        case '|':
            next_row();
            break;
        case '~':
            w = *++t - 'A';
            hex(w < 21 ? f[w] : w == 21 ? sp : BEAT, 8);
            break;
        case '^':
            hex(*game[*++t - '0'], 2);
            break;
        case '@':
            str(kinds[kind]);
            if (kind < 2)
                str(kinds[vector == 4 ? 3 : vector == 6 ? 4 : vector == 9 ? 5 : 6]);
            break;
        case '#':       /* nearest first: the return addresses among them are the calls that led here */
            top = sp <= 0x06001000 ? 0x06001000 : sp <= 0x06002000 ? 0x06002000 : sp + 1024;
            if (sp & 3 || !((sp >= 0x06000000 && sp < 0x06100000) || (sp >= 0x00200000 && sp < 0x00300000)))
                top = sp;
            for (n = 0; sp < top && n < 12; sp += 4) {
                w = *(volatile unsigned *)(sp | (kind == 1 ? THRU : 0));
                if (code(w)) {
                    if (n && n % 3 == 0) {
                        next_row();
                        pen += 6 * 8;
                    }
                    hex(w, 8), ch(' ');
                    n++;
                }
            }
            break;
        default:
            ch(*t);
        }
    }
    for (;;)
        ;
}

/* src/crash_entry.s's VBlank-IN, before CCE's handler, interrupts masked */
void crash_vbl(const unsigned *f)
{
    unsigned beat = BEAT;
    volatile unsigned *slave = (volatile unsigned *)((unsigned)crash_slave | THRU);

#ifdef CRASH_TEST
    /* make disc CRASH_TEST=...: about a minute after boot, CRASH_TEST goes
     * over the main loop's count (0600529E), to crash on a Saturn */
    if (beat == 1600) {
        *(volatile unsigned short *)(0x0600529E | THRU) = CRASH_TEST;
        *(volatile unsigned *)0x4600529C = 0;           /* its line out of the cache */
    }
#endif
    if (slave[0])
        crash_report((const volatile unsigned *)(slave[0] | THRU), slave[0] + 84, slave[1], 1);
    if (beat != last_beat || !IDLE) {
        last_beat = beat;
        still = 0;
        return;
    }
    if (++still > crash_max_still)
        crash_max_still = still;
    if (still >= FROZEN)
        crash_report(f, (unsigned)(f + 21), 0, 2);
}
