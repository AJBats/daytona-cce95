/* The course's textured quads, made cheaper for VDP1 once the race has built
 * a frame's list (docs/performance.md, "Race-time quads"). Built by
 * tools/vdp1x.py into a block of SCREEN.BIN, which CCE's block loader copies
 * to work RAM 06015140 at every race start (the attract loads other files);
 * patches/vdp1x.s runs it at the race frame's last call while the block's
 * first word is 'VX'.
 *
 * Then the list (at 0601B000, VDP1's command table in two areas, each with
 * its count of slots used and its limit) is whole: every command built and
 * linked into the depth order, VDP1 to start on it at the next frame
 * change. One pass over it looks up each textured quad by its texture. A
 * texture with strips (copies of its columns, 8 or 16 wide) and a quad
 * that's dear and partly off the screen: the quad is cut into pieces by
 * strip and band of rows, the pieces wholly off the screen left out (VDP1
 * steps every pixel of a line that crosses the screen's edge); the first
 * piece takes the quad's place, the rest go at its area's end, linked on
 * from it and back to where it went (src/vdp1x_core.c).
 * tools/vdp1x_eval.py chose the textures, per course, from lap logs;
 * tools/vdp1x.py placed their copies in the course's free VDP1 VRAM.
 *
 * The pass costs the master SH-2 time every frame, so it does no more than
 * that: drawing each quad turned whichever way is cheaper (copies of
 * textures turned a quarter) took as long again and saved VDP1 little in
 * the frames that overrun; the course files' quads are turned where that
 * pays on the whole (tools/turn_quads.py).
 *
 * The copies are made on the race's first frame from the textures in VRAM,
 * each checked against its sum first, in VRAM that must be all zero then
 * (the tail of the player car's texture file, and more on National Park).
 * A sign at the free VRAM's start, checked each frame, finds VRAM loaded
 * again under the copies (they're made again). Off in two-player races
 * (CCE's camera and split screen) and in the attract. */

#define VX_API static
#include "vdp1x_core.c"
#include "vdp1x_data.h"

#define LIST ((unsigned short *)0x0601B000)
#define AREA1 ((volatile unsigned short *)0x06057888)   /* slots used, limit: slots 0 on */
#define AREA2 ((volatile unsigned short *)0x06057C88)   /* the same from slot 0xC00 (06021000) */
#define USER_CLIP (LIST + 0xD00 / 2)    /* the race list's clip window and local origin */
#define LOCAL (LIST + 0xD20 / 2)
#define VRAM16(a) (*(volatile unsigned short *)(0x25C00000 + (a)))
#define VRAM32(a) (*(volatile unsigned int *)(0x25C00000 + (a)))
#define COURSE (*(volatile unsigned char *)0x06054920)
#define DEMO (*(volatile unsigned char *)0x0601335C)    /* the attract's demo, 0 in races */
#define MODE (*(volatile unsigned char *)0x002FC233)    /* 2 in two-player */
#define SIGN 0x5658

typedef struct {
    unsigned short srca, size;          /* the texture as the course's quads draw it */
    unsigned short strips, step;        /* its strips, and how far apart (in 8 bytes) */
    unsigned short sw, cut;             /* their width, its cutting's index */
} vx_tex;

/* State, loaded with the block at every race start (initialised, so in .data: tools/vdp1x.py builds
   with -fno-zero-initialized-in-bss); the work areas after the block aren't loaded. The block may
   also come back over a cache holding the last race's state, so nothing here is trusted over the
   sign in VRAM. */
static int vx_count = 0;
static unsigned char vx_state = 0;      /* 0: to make the copies, 1: on, 2: off */
static unsigned char vx_course = 0xFF;
static unsigned short vx_seen = 0;      /* off: the word at the sign's place then */
static vx_tex vx_texs[VX_MAX_TEX];
static vx_cutting vx_cutting_list[VX_MAX_TEX];
static unsigned char vx_hit[1024];      /* by srca & 1023: 0 none, the texture's index + 1, or 255 several */
static unsigned char vx_buf[VX_BUF] __attribute__((aligned(4)));
static vx_piece vx_pieces[VX_MAX_PIECES] __attribute__((aligned(4)));

/* the strips: each a texture sw wide and h high, one after the other */
static void vx_strip_copy(unsigned int at, int w, int h, int sw)
{
    int k, y, i;
    for (k = 0; k < w; k += sw)
        for (y = 0; y < h; y++) {
            const unsigned short *p = (const unsigned short *)(vx_buf + y * (w >> 1) + (k >> 1));
            for (i = 0; i < sw >> 2; i++) {
                VRAM16(at) = p[i];
                at += 2;
            }
        }
}

/* The copies for the course, from its textures in VRAM, into its free VRAM (all zero, or off) */
static void vx_setup(void)
{
    const unsigned int *f;
    const unsigned short *e;
    unsigned int a, i, sum;
    vx_course = COURSE;
    vx_count = 0;
    for (i = 0; i < sizeof vx_hit; i++) vx_hit[i] = 0;
    if (vx_course >= VX_COURSES) {
        vx_state = 2;
        return;
    }
    f = vx_free[vx_course];
    if (VRAM16(f[0]) != SIGN || VRAM16(f[0] + 2) != vx_course)  /* else this course's copies already */
        for (i = 0; i < 4; i += 2)
            for (a = f[i]; a < f[i] + f[i + 1]; a += 4)
                if (VRAM32(a)) {
                    vx_state = 2;
                    vx_seen = VRAM16(f[0]);
                    return;
                }
    for (e = vx_list + 5 * vx_first[vx_course]; e < vx_list + 5 * vx_first[vx_course + 1]; e += 5) {
        int w = (e[1] >> 8) * 8, h = e[1] & 0xFF, n = w * h / 2;
        vx_tex *t = vx_texs + vx_count;
        for (a = 0, sum = 0; a < (unsigned int)n; a += 2) {
            unsigned short v = VRAM16(e[0] * 8 + a);
            *(unsigned short *)(vx_buf + a) = v;
            sum += v;
        }
        if ((sum & 0xFFFF) != e[4] || !vx_cutting_of(vx_cutting_list + vx_count, w, h, e[3], VX_BAND))
            continue;                           /* not the texture the list was made for */
        t->srca = e[0], t->size = e[1], t->strips = e[2], t->sw = e[3];
        t->step = (unsigned short)(e[3] * h >> 4), t->cut = (unsigned short)vx_count;
        vx_strip_copy(t->strips * 8, w, h, t->sw);
        vx_hit[e[0] & 1023] = vx_hit[e[0] & 1023] ? 255 : (unsigned char)(vx_count + 1);
        vx_count++;
    }
    VRAM16(f[0]) = SIGN;
    VRAM16(f[0] + 2) = vx_course;
    vx_state = 1;
}

static const vx_tex *vx_search(unsigned int srca)
{
    int lo = 0, hi = vx_count;
    while (lo < hi) {
        int mid = (lo + hi) >> 1;
        if (vx_texs[mid].srca < srca) lo = mid + 1;
        else hi = mid;
    }
    return vx_texs + (lo < vx_count ? lo : 0);
}

/* The quad cut into pieces from its texture's strips: the first in its place, linked on to the rest at
   the area's end, the last linked to where the quad went (each command's words as longs: control and
   link, draw mode and colour, texture and size, the corners; its gouraud table unused). Unless it isn't
   worth cutting or the area has no room. The quad jumps to its link or on to the next command
   (0x1000 or 0 in its control word, vx_area). */
static __attribute__((noinline)) void vx_cut(unsigned int *cmd, const vx_tex *t, volatile unsigned short *area,
                                             const short *scr)
{
    unsigned int at = area[0], head = cmd[0], mode = cmd[1], i, j, last;
    int n = vx_grid((const short *)cmd + 6, vx_cutting_list + t->cut, (head >> 20) & 3, scr, VX_MIN_CUT,
                    vx_pieces, VX_MAX_PIECES);
    if (n < 0 || at + 4 * (n - 1) > area[1]) return;
    if (n == 0) {
        cmd[0] = head | 0x40000000;             /* not drawn, its jump kept */
        return;
    }
    /* where the quad went: its link, or (near-clipped pieces CCE chains by place) the command after it */
    last = head & 0x70000000 ? head
         : (head & 0xFFFF0000) | 0x10000000 | (((unsigned char *)cmd - (unsigned char *)LIST) / 8 + 4);
    for (i = 0; i < (unsigned int)n; i++) {
        unsigned int *p = i ? (unsigned int *)(LIST + 4 * (at + 4 * (i - 1))) : cmd;
        const vx_piece *q = vx_pieces + i;
        const unsigned int *c = (const unsigned int *)q->c;
        if (i == (unsigned int)n - 1) p[0] = last;                      /* on to where the quad went */
        else if (i) p[0] = head & 0x8FFF0000;                           /* on to the next piece */
        else p[0] = (head & 0x8FFF0000) | 0x10000000 | at;              /* the first: on to the rest */
        p[1] = mode;
        p[2] = ((t->strips + q->strip * t->step + ((q->row * t->sw) >> 4)) << 16) | ((t->sw >> 3) << 8) | q->rows;
        for (j = 0; j < 4; j++) p[3 + j] = c[j];
    }
    if (n > 1) area[0] = (unsigned short)(at + 4 * (n - 1));
}

static void vx_area(volatile unsigned short *area, unsigned int first, const short *scr)
{
    unsigned short *cmd = LIST + 4 * first, *end = LIST + 4 * area[0];
    for (; cmd < end; cmd += 16) {
        unsigned int k;
        const vx_tex *t;
        if ((cmd[0] & 0x600F) != 0x0002) continue;     /* drawn, a textured quad, jumping on or to its link */
        k = vx_hit[cmd[4] & 1023];
        if (!k) continue;
        t = k == 255 ? vx_search(cmd[4]) : vx_texs + k - 1;
        if (t->srca != cmd[4] || t->size != cmd[5] || (cmd[2] & 0x34)) continue;  /* 16 colours, no gouraud */
        if (vx_estimate((const short *)cmd + 6) < VX_MIN_CUT) continue;           /* most, before the call */
        vx_cut((unsigned int *)cmd, t, area, scr);
    }
}

/* The race frame's list, whole: copies made, kept, or made again when VRAM was loaded again under them;
   then the pass over both areas */
void vx_frame(void)
{
    const unsigned int *f;
    short scr[4];
    if (MODE == 2 || DEMO || COURSE >= VX_COURSES) return;
    f = vx_free[COURSE];
    if (vx_state == 2 && VRAM16(f[0]) == vx_seen) return;
    if (vx_state != 1 || COURSE != vx_course || VRAM16(f[0]) != SIGN || VRAM16(f[0] + 2) != vx_course)
        vx_setup();
    if (vx_state != 1 || !vx_count || (USER_CLIP[0] & 0x400F) != 8 || (LOCAL[0] & 0x400F) != 10) return;
    scr[0] = (short)(USER_CLIP[6] - LOCAL[6]), scr[1] = (short)(USER_CLIP[7] - LOCAL[7]);
    scr[2] = (short)(USER_CLIP[10] - LOCAL[6]), scr[3] = (short)(USER_CLIP[11] - LOCAL[7]);
    vx_area(AREA1, 0, scr);
    vx_area(AREA2, 0xC00, scr);
}

/* The block's start: VX_MAGIC's word, then the way in from patches/vdp1x.s, which leaves PR the race
   frame's and goes on (here, after the pass) to the frame's last call as it was. */
__asm__(
    "    .section .text.entry,\"ax\"\n"
    "    .global _vx_block\n"
    "_vx_block:\n"
    "    .word   0x5658\n"
    "    sts.l   pr,@-r15\n"
    "    mov.l   1f,r1\n"
    "    jsr     @r1\n"
    "    nop\n"
    "    lds.l   @r15+,pr\n"
    "    mov.l   2f,r1\n"
    "    jmp     @r1\n"
    "    nop\n"
    "    .p2align 2\n"
    "1:  .long   _vx_frame\n"
    "2:  .long   0x0603C8F8\n"
    "    .text\n");
