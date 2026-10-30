/* DUSA's title in place of the main menu's press-start page (docs/attract.md,
 * "The menu's press-start page"). Built by tools/menu_title.py into a blob
 * at LWRAM 0x00242300, after CCE's TITLED.BIN (the menu's screen file, read
 * to 0x220000 when the menu starts), and patches/menu_title.s points the
 * menu at its three entries.
 *
 * The menu (SLCT.BIN) shows its press-start page as state 3 of its title
 * (state byte 060418A2): the main menu's own screen (NBG0, CCE's background
 * and logo, 256 colours) with "Press Start Button" on NBG2 where the list
 * was. DUSA's title is two 16-colour layers at 352 x 224; the menu is
 * 704 x 448 (high resolution, interlaced), so each of DUSA's cells is drawn
 * as four here, each pixel as 2 x 2. The menu leaves NBG1 empty and VRAM
 * bank B0 unused, with access slots for NBG1 and NBG3 characters there and
 * for their maps in B1, so while the page is up:
 *   NBG1  DUSA's background (white stripes, the pale logo), 16 colours
 *   NBG3  DUSA's logo and PRESS START BUTTON, its plane two pages wide
 *         (the second blank) so the logo slides in from the left
 *   NBG0  (CCE's) and NBG2 (CCE's Press Start Button) hidden
 * with the characters doubled into B0 at 0x40000 and DUSA's palettes in
 * colour RAM palettes 32, 33 and 37 (put back after). The slide, the shake
 * and PRESS START's blink run from the VBlank-IN interrupt, as DUSA's title
 * and patches/title.s's do. With CCE's attract chosen (Options > Sound >
 * ATTRACT), the page stays CCE's. It shows at once, as DUSA's does, where the menu
 * faded its page in. Start (the menu goes on to the main menu, which draws
 * its own screen) or the timeout (the menu fades out and leaves) ends it. */
#include "menu_title_data.h"

#define VDP2 ((volatile unsigned short *)0x25F80000)
#define REG(off) VDP2[(off) / 2]
#define VRAM16(a) (*(volatile unsigned short *)(0x25E00000 + (a)))
#define VRAM32(a) (*(volatile unsigned int *)(0x25E00000 + (a)))
#define CRAM16(i) (*(volatile unsigned short *)(0x25F00000 + 2 * (i)))
#define VBL_VECTOR (*(void *volatile *)0x06000100)
#define ATTRACT_CHOICE (*(volatile unsigned char *)0x002FC3AB)  /* Options > Sound > ATTRACT: 1 CCE's */
#define FADE_STATE (*(volatile unsigned char *)0x0605397C)  /* the menu's colour offset fade: 1 in, 3 out, 0 none */
#define FADE_OFFSET (*(volatile short *)0x0605397E)

#define CHARS 0x40000           /* bank B0: the doubled characters */
#define CHAR_BASE 0x2000        /* their numbers (CHARS / 32), as PNCN's supplement gives them */
#define BG_MAP 0x6C000          /* NBG1's planes A and B, as the menu has them (pages 0x36, 0x37) */
#define LOGO_MAP 0x70000        /* NBG3: plane A pages 0x38-0x39, B 0x3A-0x3B (blank) */
#define PAL0 32                 /* DUSA's palette p at colour RAM palette PAL0 + p */
#define PS_ROW 23               /* PRESS START BUTTON: DUSA's NBG3 rows 23-24, from column 11 */
#define PS_COL 11
#define PS_W 22
#define PS_CHAR 556             /* its characters, after the title's */
#define PS_PAL 5

/* the menu's values of the registers the page changes (menu.vdp2 dumps) */
#define MENU_CHCTLA 0x1010
#define MENU_PNCN1 0xC008
#define MENU_PNCN3 0xC000
#define MENU_PLSZ 0x0000
#define MENU_MPN3 0x3534
#define MENU_PRINA 0x0302
#define MENU_PRINB 0x0405
#define MENU_CCCTL 0x000F

static const signed char shake[8] = {-8, 8, -4, 4, -2, 2, -1, 1};

volatile int on;                /* the page is up (read by the VBlank stub) */
volatile int t;                 /* DUSA's frames from the slide's start */
void *vbl_saved;                /* the VBlank-IN handler before ours */
static int ps_shown;
static unsigned short saved_cram[3 * 16];
static const unsigned char pals[3] = {0, 1, PS_PAL};

void title_vbl(void);

/* Each of DUSA's characters as four, top left, top right, bottom left,
 * bottom right: each pixel 2 x 2. */
static void double_chars(void)
{
    int c, q, r;
    for (c = 0; c < N_CHARS; c++) {
        const unsigned char *s = chars + 32 * c;
        for (q = 0; q < 4; q++) {
            unsigned int a = CHARS + 32 * (4 * c + q);
            for (r = 0; r < 8; r++) {
                const unsigned char *p = s + 4 * ((q >> 1) * 4 + (r >> 1)) + 2 * (q & 1);
                unsigned int v = 0;
                int k;
                for (k = 0; k < 2; k++) {
                    unsigned int hi = p[k] >> 4, lo = p[k] & 15;
                    v = v << 16 | (hi << 12 | hi << 8 | lo << 4 | lo);
                }
                VRAM32(a + 4 * r) = v;
            }
        }
    }
}

/* A 16-colour cell (palette p, character n of the doubled ones) at a map
 * page pair: columns 0-63 in the first page, 64-127 in the second. */
static void put(unsigned int map, int row, int col, int p, int n)
{
    VRAM16(map + ((col >> 6) << 13) + 2 * (row * 64 + (col & 63))) = p << 12 | n;
}

/* DUSA's cell v (palette in bits 12-15, character below) at its row r,
 * column c, as four cells. */
static void put4(unsigned int map, int r, int c, unsigned int v)
{
    int q, n = 4 * (v & 0xFFF), p = v >> 12;
    for (q = 0; q < 4; q++)
        put(map, 2 * r + (q >> 1), 2 * c + (q & 1), p, n + q);
}

static void clear(unsigned int a, int bytes)
{
    for (; bytes > 0; bytes -= 4, a += 4)
        VRAM32(a) = 0;
}

static void press_start(int shown)
{
    int r, c;
    for (r = 0; r < 2; r++)
        for (c = 0; c < PS_W; c++)
            put4(LOGO_MAP, PS_ROW + r, PS_COL + c, shown ? PS_PAL << 12 | (PS_CHAR + r * PS_W + c) : 0);
    ps_shown = shown;
}

/* Called in place of the menu's draw of its Press Start Button (06034CC2)
 * as its title goes to the press-start page. */
void title_on(void)
{
    int i, r, c;
    ((void (*)(void))0x06034CC2)();
    if (ATTRACT_CHOICE)             /* CCE's attract chosen: CCE's page, as it shipped */
        return;
    double_chars();
    clear(BG_MAP, 0x4000);
    clear(LOGO_MAP, 0x8000);
    for (r = 0; r < H; r++)
        for (c = 0; c < W; c++) {
            put4(BG_MAP, r, c, bg_map[r * W + c]);
            if (logo_map[r * W + c])
                put4(LOGO_MAP, r, c, logo_map[r * W + c]);
        }
    for (i = 0; i < 3; i++)
        for (c = 0; c < 16; c++) {
            if (!on)                /* the menu's own, kept for after */
                saved_cram[16 * i + c] = CRAM16(16 * (PAL0 + pals[i]) + c);
            CRAM16(16 * (PAL0 + pals[i]) + c) = palettes[16 * i + c];
        }
    ps_shown = 0;
    t = 0;
    REG(0x28) = MENU_CHCTLA & ~0x3000;      /* NBG1 16 colours */
    REG(0x32) = MENU_PNCN1 | PAL0 >> 4 << 5;
    REG(0x36) = MENU_PNCN3 | PAL0 >> 4 << 5 | (CHAR_BASE >> 12) << 2;
    REG(0x3A) = MENU_PLSZ | 1 << 6;         /* NBG3's planes two pages wide */
    REG(0x4C) = (LOGO_MAP / 0x2000 + 2) << 8 | LOGO_MAP / 0x2000;
    REG(0x4E) = (LOGO_MAP / 0x2000 + 2) << 8 | LOGO_MAP / 0x2000;
    REG(0x94) = 672;                        /* the logo off to the left */
    REG(0x96) = 0;
    REG(0xEC) = MENU_CCCTL & ~0xA;          /* no blending for NBG1 and NBG3 */
    REG(0xF8) = MENU_PRINA & 0xFF00;        /* NBG0 hidden */
    REG(0xFA) = MENU_PRINB & 0xFF00;        /* NBG2 hidden */
    FADE_STATE = 0;                         /* no fade in: DUSA's title shows at once */
    FADE_OFFSET = 0;
    REG(0x114) = 0;
    REG(0x116) = 0;
    REG(0x118) = 0;
    if (VBL_VECTOR != (void *)title_vbl) {
        vbl_saved = VBL_VECTOR;
        VBL_VECTOR = (void *)title_vbl;
    }
    on = 1;
}

static void off(void)
{
    int i, c;
    if (!on)
        return;
    on = 0;
    if (VBL_VECTOR == (void *)title_vbl)
        VBL_VECTOR = vbl_saved;
    for (i = 0; i < 3; i++)
        for (c = 0; c < 16; c++)
            CRAM16(16 * (PAL0 + pals[i]) + c) = saved_cram[16 * i + c];
    clear(BG_MAP, 0x4000);
    REG(0x28) = MENU_CHCTLA;
    REG(0x32) = MENU_PNCN1;
    REG(0x36) = MENU_PNCN3;
    REG(0x3A) = MENU_PLSZ;
    REG(0x4C) = MENU_MPN3;
    REG(0x4E) = MENU_MPN3;
    REG(0x94) = 0;
    REG(0x96) = 0;
    REG(0xEC) = MENU_CCCTL;
    REG(0xF8) = MENU_PRINA;
    REG(0xFA) = MENU_PRINB;
}

/* In place of the menu's call to set up the main menu (0602A800), once
 * Start on the page has played out: the main menu draws its own screen. */
void title_menu(void)
{
    off();
    ((void (*)(void))0x0602A800)();
}

/* In place of the menu's call as it leaves after the timeout (06005876), the
 * page faded out: the VBlank handler back before the next program loads
 * over this one. */
void title_leave(void)
{
    if (on && VBL_VECTOR == (void *)title_vbl)
        VBL_VECTOR = vbl_saved;
    on = 0;
    ((void (*)(void))0x06005876)();
}

/* A frame of DUSA's title (patches/title.s's title_vbl, each step doubled):
 * the slide from 336 pixels to the left, 16 a frame, the shake, PRESS START
 * blinking from frame 64, 4 frames on, 4 off. */
void title_frame(void)
{
    int x, k = t;
    if (k < 22)
        x = 2 * (336 - 16 * k);
    else if (k < 31)
        x = k == 22 ? 0 : 2 * shake[k - 23];
    else if (k < 63)
        x = -2 * (k & 1);
    else
        x = 0;
    REG(0x94) = x & 0x7FF;
    if (k >= 64) {
        int shown = (k - 63) & 4 ? 0 : 1;
        if (shown != ps_shown)
            press_start(shown);
    }
    t = k + 1;
}

/* VBlank-IN: a frame of the title while the page is up, then the menu's
 * handler. */
__asm__(
    "    .text\n"
    "    .global _title_vbl\n"
    "    .align 2\n"
    "_title_vbl:\n"
    "    mov.l   r0,@-r15\n"
    "    mov.l   r1,@-r15\n"
    "    mov.l   r2,@-r15\n"
    "    mov.l   r3,@-r15\n"
    "    mov.l   r4,@-r15\n"
    "    mov.l   r5,@-r15\n"
    "    mov.l   r6,@-r15\n"
    "    mov.l   r7,@-r15\n"
    "    sts.l   pr,@-r15\n"
    "    sts.l   macl,@-r15\n"
    "    sts.l   mach,@-r15\n"
    "    mov.l   1f,r0\n"
    "    mov.l   @r0,r0\n"
    "    tst     r0,r0\n"
    "    bt      2f\n"
    "    mov.l   3f,r0\n"
    "    jsr     @r0\n"
    "    nop\n"
    "2:\n"
    "    lds.l   @r15+,mach\n"
    "    lds.l   @r15+,macl\n"
    "    lds.l   @r15+,pr\n"
    "    mov.l   @r15+,r7\n"
    "    mov.l   @r15+,r6\n"
    "    mov.l   @r15+,r5\n"
    "    mov.l   @r15+,r4\n"
    "    mov.l   @r15+,r3\n"
    "    mov.l   @r15+,r2\n"
    "    mov.l   @r15+,r1\n"
    "    mov.l   4f,r0\n"
    "    mov.l   @r0,r0\n"
    "    jmp     @r0\n"
    "    mov.l   @r15+,r0\n"
    "    .align 2\n"
    "1:  .long   _on\n"
    "3:  .long   _title_frame\n"
    "4:  .long   _vbl_saved\n"
);

/* the entries, at the blob's start (patches/menu_title.s) */
__asm__(
    "    .section .text.entry,\"ax\"\n"
    "    .global _entries\n"
    "_entries:\n"
    "    mov.l   5f,r0\n"
    "    jmp     @r0\n"
    "    nop\n"
    "    nop\n"
    "    mov.l   6f,r0\n"
    "    jmp     @r0\n"
    "    nop\n"
    "    nop\n"
    "    mov.l   7f,r0\n"
    "    jmp     @r0\n"
    "    nop\n"
    "    .align 2\n"
    "5:  .long   _title_on\n"
    "6:  .long   _title_menu\n"
    "7:  .long   _title_leave\n"
    "    .text\n"
);
