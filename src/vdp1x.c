/* The course's textured quads, made cheaper for VDP1 as the race builds a
 * frame's list (docs/performance.md, "Race-time quads" and "Cutting as CCE
 * builds the list"). Built by
 * tools/vdp1x.py into a block of SCREEN.BIN, which CCE's block loader copies
 * to work RAM 06015140 at every race start (the attract loads other files);
 * patches/vdp1x.s comes in while the block's first word is 'VX'.
 *
 * The list (at 0601B000, VDP1's command table in two areas, each with its
 * count of slots used and its limit) is built a polygon at a time: its
 * commands written at the area's end, then linked into the list for its
 * depth. Between the two, a course polygon whose texture has strips (copies
 * of its columns, 8 or 16 wide; tools/vdp1x.py marks those polygons in the
 * course's model) comes here (vx_emit). A quad that's dear and partly off
 * the screen is cut into pieces by strip and band of rows, the pieces wholly
 * off the screen left out (VDP1 steps every pixel of a line that crosses the
 * screen's edge), all in the quad's place at the area's end, and linked in
 * as the polygon (src/vdp1x_core.c). The car effects' smoke and sparks come
 * here too (marked in their model), to be left out after a late frame.
 * Every other polygon costs CCE a test of its attribute.
 * tools/vdp1x_eval.py chose the textures, per course, from lap logs;
 * tools/vdp1x.py placed their copies in the course's free VDP1 VRAM.
 *
 * At the race frame's last call (vx_frame), with the list whole: the copies
 * checked, and whether the next frame's car effects stay out. Drawing each
 * quad turned whichever way is cheaper (copies of textures turned a quarter)
 * took the master SH-2 long and saved VDP1 little in the frames that
 * overrun; the course files' quads are turned where that pays on the whole
 * (tools/turn_quads.py).
 *
 * The copies are made on the race's first frame from the textures in VRAM,
 * each checked against its sum first, in VRAM nothing in the race uses: the
 * tail of the player car's texture file, all zero then (or off), and on
 * National Park a run the attract may have left its pictures in.
 * A sign at the free VRAM's start, checked each frame, finds VRAM loaded
 * again under the copies (they're made again). Off in two-player races
 * (CCE's camera and split screen) and in the attract. */

#define VX_API static
#include "vdp1x_core.c"
#include "vdp1x_data.h"

#define LIST ((unsigned short *)0x0601B000)
#define USER_CLIP (LIST + 0xD00 / 2)    /* the race list's clip window and local origin */
#define LOCAL (LIST + 0xD20 / 2)
#define VRAM16(a) (*(volatile unsigned short *)(0x25C00000 + (a)))
#define VRAM32(a) (*(volatile unsigned int *)(0x25C00000 + (a)))
#define COURSE (*(volatile unsigned char *)0x06054920)
#define DEMO (*(volatile unsigned char *)0x0601335C)    /* the attract's demo, 0 in races */
#define MODE (*(volatile unsigned char *)0x002FC233)    /* 2 in two-player */
#define FRC_HI (*(volatile unsigned char *)0xFFFFFE12)  /* the free-running timer, phi/128: its high byte latches its low */
#define FRC_LO (*(volatile unsigned char *)0xFFFFFE13)
#define LATE (*(volatile unsigned char *)0x0603E438)    /* patches/vdp1x.s: 1 when VDP1 ran late with the last list */
#define SIGN 0x5658
#define FX_HOLD 30                      /* frames the car effects stay out after a late frame */
#define FX 254                          /* vx_hit's mark for a car effect */

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
static unsigned char vx_live = 0;       /* the next frame's quads may be cut: copies there, a 1P race */
unsigned char vx_fx_out = 0;            /* the next frames' car effects left out, after a late frame (the emit entry reads it too) */
static short vx_scr[4];                 /* the screen (xmin, ymin, xmax, ymax) from the local origin */
static unsigned char vx_course = 0xFF;
static unsigned short vx_seen = 0;      /* off: the word at the sign's place then */
static unsigned char vx_fx_hold = 0;    /* frames left with the car effects out */
static unsigned short vx_fx[VX_EFFECTS];    /* the course's car effects found in VRAM (srca, 0 none) */
static vx_tex vx_texs[VX_MAX_TEX];
static vx_cutting vx_cutting_list[VX_MAX_TEX];
static unsigned char vx_hit[1024];      /* by srca & 1023: 0 none, the texture's index + 1, FX a car effect, or 255 several */
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
    /* The first run is the tail of the player car's texture file, all zero when the race loaded it
       (another car's file, CCE's Hornet's, fills it); this course's copies there already will do. The
       second (National Park's) nothing in a race loads or draws, but the attract leaves its pictures
       there, so it isn't checked. */
    if (VRAM16(f[0]) != SIGN || VRAM16(f[0] + 2) != vx_course)
        for (a = f[0]; a < f[0] + f[1]; a += 4)
            if (VRAM32(a)) {
                vx_state = 2;
                vx_seen = VRAM16(f[0]);
                return;
            }
    for (e = vx_list + 4 * vx_first[vx_course]; e < vx_list + 4 * vx_first[vx_course + 1]; e += 4) {
        int w = (e[1] >> 8) * 8, h = e[1] & 0xFF, n = w * h / 2, sw = w & 15 ? 8 : 16;  /* tools/vdp1x_eval.py */
        vx_tex *t = vx_texs + vx_count;
        for (a = 0, sum = 0; a < (unsigned int)n; a += 2) {
            unsigned short v = VRAM16(e[0] * 8 + a);
            *(unsigned short *)(vx_buf + a) = v;
            sum += v;
        }
        if ((sum & 0xFFFF) != e[3] || !vx_cutting_of(vx_cutting_list + vx_count, w, h, sw, VX_BAND))
            continue;                           /* not the texture the list was made for */
        t->srca = e[0], t->size = e[1], t->strips = e[2], t->sw = (unsigned short)sw;
        t->step = (unsigned short)(sw * h >> 4), t->cut = (unsigned short)vx_count;
        vx_strip_copy(t->strips * 8, w, h, t->sw);
        vx_hit[e[0] & 1023] = vx_hit[e[0] & 1023] ? 255 : (unsigned char)(vx_count + 1);
        vx_count++;
    }
    for (i = 0; i < VX_EFFECTS; i++) {
        e = vx_effects[vx_course] + 3 * i;
        for (a = 0, sum = 0; a < 2u * e[1]; a += 2) sum += VRAM16(e[0] * 8 + a);
        vx_fx[i] = (sum & 0xFFFF) == e[2] ? e[0] : 0;
        if (vx_fx[i])
            vx_hit[e[0] & 1023] = vx_hit[e[0] & 1023] ? 255 : FX;
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

/* A CUT_DIAG this long or more on the command's diagonal A-C, x and y together: all but 24 of the 3,158 quads
   worth cutting over the lap logs, so only those are looked up further */
#define CUT_DIAG 96

/* The command's texture with strips, when it's a drawn quad (jumping on or to its link) with the strips'
   texture, size and colour mode (16 colours, no gouraud), long enough to be worth trying */
static const vx_tex *vx_cuttable(const unsigned short *cmd)
{
    unsigned int k, srca = cmd[4];
    const vx_tex *t;
    if ((cmd[0] & 0x600F) != 0x0002 || !(k = vx_hit[srca & 1023]) || k == FX) return 0;
    if (vx_abs((short)cmd[6] - (short)cmd[10]) + vx_abs((short)cmd[7] - (short)cmd[11]) < CUT_DIAG) return 0;
    t = k == 255 ? vx_search(srca) : vx_texs + k - 1;
    return t->srca == srca && t->size == cmd[5] && !(cmd[2] & 0x34) ? t : 0;
}

/* Slots first to last into the list for depth, as 06045E06 links a polygon: the depth's list (a first and a
   last slot in the table at work + 32, by depth / 1024, none while the first is 0) gets them at its end */
static void vx_link(unsigned char *work, unsigned int depth, unsigned int first, unsigned int last)
{
    unsigned short *d = (unsigned short *)(*(unsigned char **)(work + 32) + ((depth >> 10) & ~7u));
    if (d[0]) LIST[4 * d[1] + 1] = (unsigned short)first;
    else d[0] = (unsigned short)first;
    d[1] = (unsigned short)last;
}

#define GROUP 3                         /* a polygon's commands, at most (CCE's clip to its guard band) */

VX_INLINE int vx_is_fx(unsigned int srca)
{
    int i;
    for (i = 0; i < VX_EFFECTS; i++)
        if (srca == vx_fx[i]) return 1;
    return 0;
}

/* A marked polygon's commands, written but not linked (patches/vdp1x.s): ctx the list area's context (GBR:
   the polygon's attribute at +128, the area's slots used and limit at +0x88, the polygon's slots at +155),
   work CCE's polygon work area (r14), depth the polygon's.

   A car effect's polygon (bit 15) while the effects are out (VDP1 was late with the last list, LATE, set
   as this frame's work began, or with one of the FX_HOLD before it): left out, neither linked nor counted
   (1).

   A course polygon (bit 14): each of its quads worth cutting is cut, every piece and command in the
   polygon's place at the area's end in order, jumping on to the next (each command's words as longs:
   control and link, draw mode and colour, texture and size, the corners, the gouraud table); the last
   jumps as the polygon's last did. Linked and counted here (1), or none cut, or no room: back to CCE as
   they are (0). */
#ifdef VX_PROFILE
static int vx_emit_cut(unsigned char *ctx, unsigned char *work, unsigned int depth);
static int vx_elapsed(void);
/* Test builds (VDP1X_CFLAGS=-DVX_PROFILE): this frame's calls, polygons handled here, timer ticks in all calls
   and in those (summed from each call's ends, so unbiased over many), calls turned away by vx_cuttable and by
   vx_grid, ticks in vx_grid and in writing and linking the pieces; then the last frame's (+8), for the
   debugger */
unsigned short vx_prof[16];
#define PROF(i) (vx_prof[i]++)
#define PROF_T0 int pt0 = vx_elapsed()
#define PROF_T(i) (vx_prof[i] += (unsigned short)(vx_elapsed() - pt0))

int vx_emit(unsigned char *ctx, unsigned char *work, unsigned int depth)
{
    int t0 = vx_elapsed(), r = vx_emit_cut(ctx, work, depth);
    unsigned short ticks = (unsigned short)(vx_elapsed() - t0);
    vx_prof[0]++, vx_prof[1] += (unsigned short)r, vx_prof[2] += ticks;
    if (r) vx_prof[3] += ticks;
    return r;
}

static int vx_emit_cut(unsigned char *ctx, unsigned char *work, unsigned int depth)
#else
#define PROF(i)
#define PROF_T0
#define PROF_T(i)
int vx_emit(unsigned char *ctx, unsigned char *work, unsigned int depth)
#endif
{
    volatile unsigned short *area = (volatile unsigned short *)(ctx + 0x88);
    unsigned int first = area[0], n = ctx[155] >> 2, i, j, k, at, way, used = 0, total = 0, cut = 0;
    unsigned int group[GROUP][8];
    const vx_tex *t[GROUP];
    int np[GROUP];
    if (DEMO || MODE == 2 || n - 1 >= GROUP) return 0;
    if (ctx[128] & 0x80) {
        const unsigned short *cmd = LIST + 4 * first;
        unsigned int srca = cmd[4];
        k = vx_hit[srca & 1023];
        return (vx_fx_out || LATE) && (cmd[0] & 0x600F) == 0x0002 && (k == FX || (k == 255 && vx_is_fx(srca)));
    }
    if (!vx_live) return 0;
    for (i = 0; i < n; i++) {
        const unsigned short *cmd = LIST + 4 * (first + 4 * i);
        np[i] = -1;
        if ((t[i] = vx_cuttable(cmd)) != 0) {
            PROF_T0;
            np[i] = vx_grid((const short *)cmd + 6, vx_cutting_list + t[i]->cut, (cmd[0] >> 4) & 3, vx_scr,
                            VX_MIN_CUT, vx_pieces + used, VX_MAX_PIECES - used);
            PROF_T(6);
            if (np[i] < 0) PROF(5);
        } else PROF(4);
        if (np[i] >= 0) used += np[i], total += np[i], cut = 1;
        else total++;
    }
    if (!cut || first + 4 * total > area[1]) return 0;
    PROF_T0;
    for (i = 0; i < n; i++)
        for (j = 0; j < 8; j++) group[i][j] = ((const unsigned int *)(LIST + 4 * (first + 4 * i)))[j];
    way = group[n - 1][0] & 0x70000000;
    for (i = 0, at = first, used = 0; i < n; i++) {
        unsigned int head = group[i][0] & 0x8FFF0000;
        if (np[i] < 0) {
            unsigned int *p = (unsigned int *)(LIST + 4 * at);
            for (j = 0; j < 8; j++) p[j] = group[i][j];
            p[0] = head;
            at += 4;
            continue;
        }
        for (k = 0; k < (unsigned int)np[i]; k++, at += 4) {
            unsigned int *p = (unsigned int *)(LIST + 4 * at);
            const vx_piece *q = vx_pieces + used + k;
            const unsigned int *c = (const unsigned int *)q->c;
            const vx_tex *x = t[i];
            p[0] = head;
            p[1] = group[i][1];
            p[2] = ((x->strips + q->strip * x->step + ((q->row * x->sw) >> 4)) << 16) | ((x->sw >> 3) << 8) | q->rows;
            for (j = 0; j < 4; j++) p[3 + j] = c[j];
            p[7] = group[i][7];
        }
        used += np[i];
    }
    if (at == first) return 1;                  /* wholly off the screen: nothing drawn */
    ((unsigned int *)(LIST + 4 * (at - 4)))[0] |= way;
    vx_link(work, depth, first, at - 4);
    area[0] = (unsigned short)at;
    PROF_T(7);
    return 1;
}

#ifdef VX_PROFILE
/* Ticks of the timer since the frame's work began (the race zeroes it then, 0600730A from 06028170) */
static int vx_elapsed(void)
{
    unsigned int hi = FRC_HI, lo = FRC_LO;
    return (int)((hi << 8) | lo);
}
#endif

/* The race frame's list, whole: copies made, kept, or made again when VRAM was loaded again under them,
   for the next frame's quads.

   The polygon CCE draws first over the screen's bottom 42 rows, in colour 0 (clearing them), is left
   out: the course covers those rows in the race.

   After a frame VDP1 didn't finish in time, the car effects (tire smoke and sparks: big sprites, already
   coming and going) are left out of the next FX_HOLD frames, so those lose them instead of the list's
   end, the nearest things and the player's car. */
void vx_frame(void)
{
    const unsigned int *f;
    unsigned short *band = LIST + 0x40 / 2;
#ifdef VX_PROFILE
    {
        int i;
        for (i = 0; i < 8; i++) vx_prof[8 + i] = vx_prof[i], vx_prof[i] = 0;
    }
#endif
    vx_live = vx_fx_out = 0;
    if (MODE == 2 || DEMO || COURSE >= VX_COURSES) return;
    f = vx_free[COURSE];
    if (vx_state == 2 && VRAM16(f[0]) == vx_seen) return;
    if (vx_state != 1 || COURSE != vx_course || VRAM16(f[0]) != SIGN || VRAM16(f[0] + 2) != vx_course)
        vx_setup();
    if (vx_state != 1 || (USER_CLIP[0] & 0x400F) != 8 || (LOCAL[0] & 0x400F) != 10) return;
    if (band[0] == 0x0004 && band[3] == 0 && band[6] == 0 && band[7] == 182 && band[13] == 223) band[0] |= 0x4000;
    vx_scr[0] = (short)(USER_CLIP[6] - LOCAL[6]), vx_scr[1] = (short)(USER_CLIP[7] - LOCAL[7]);
    vx_scr[2] = (short)(USER_CLIP[10] - LOCAL[6]), vx_scr[3] = (short)(USER_CLIP[11] - LOCAL[7]);
    vx_live = vx_count > 0;
    if (LATE) vx_fx_hold = FX_HOLD;
    else if (vx_fx_hold) vx_fx_hold--;
    vx_fx_out = vx_fx_hold != 0;
}

/* The block's start: VX_MAGIC's word, then the way in at the race frame's last call from patches/vdp1x.s,
   which leaves PR the race frame's and goes on (here, after vx_frame) to that call as it was. At +28
   (tools/vdp1x.py checks), the way in from CCE's polygon tail for a marked polygon: r0 its depth, the polygon
   routine's PR on the stack; the polygon linked and counted by vx_emit, or by that tail's own steps here.
   A car effect's polygon goes straight on unless the effects are out. A course polygon of one command CCE
   found wholly on the screen (it turned VDP1's pre-clipping off: bit 11 of the draw mode, 060469F4),
   shorter than CUT_DIAG across or estimated under VX_MIN_CUT cycles (vx_estimate's sum) has nothing to cut,
   and goes straight on: nearly every marked polygon, kept out of vx_emit's code and data, which miss the
   caches between polygons (about 1,000 cycles a call that cuts nothing). */
#define VX_STR2(x) #x
#define VX_STR(x) VX_STR2(x)
/* vx_edge in d: the longer axis between the command's corners at the offsets (xp, yp) and (xq, yq); r0, r7 */
#define VX_EDGE(xp, yp, xq, yq, d) \
    "    mov.w   @(" #xp ",r1),r0\n" \
    "    mov     r0,r7\n" \
    "    mov.w   @(" #xq ",r1),r0\n" \
    "    sub     r0,r7\n" \
    "    cmp/pz  r7\n" \
    "    bt      11f\n" \
    "    neg     r7,r7\n" \
    "11: mov.w   @(" #yp ",r1),r0\n" \
    "    mov     r0," #d "\n" \
    "    mov.w   @(" #yq ",r1),r0\n" \
    "    sub     r0," #d "\n" \
    "    cmp/pz  " #d "\n" \
    "    bt      12f\n" \
    "    neg     " #d "," #d "\n" \
    "12: cmp/ge  r7," #d "\n" \
    "    bt      13f\n" \
    "    mov     r7," #d "\n" \
    "13:\n"
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
    "    .global _vx_emit_entry\n"
    "_vx_emit_entry:\n"
    "    mov     r0,r6\n"
    "    mov.b   @(128,gbr),r0\n"
    "    cmp/pz  r0\n"
    "    bt      1f\n"
#ifdef VX_FX_LAST
    /* test builds: a car effect always drawn, linked nearest of all (after the cars, before the map's
       markers), so a late VDP1 loses the nearest smoke instead of the player's car */
    "    bra     4f\n"
    "    mov     #0,r6\n"
#else
    "    mov.l   7f,r1\n"
    "    mov.b   @r1,r0\n"
    "    mov.l   10f,r1\n"
    "    mov.b   @r1,r2\n"
    "    or      r2,r0\n"
    "    tst     r0,r0\n"
    "    bt      4f\n"
    "    bra     2f\n"
    "    nop\n"
#endif
    "1:\n"
#ifdef VX_POLYID
    /* test builds: the polygon's record (r8, just past it) / 4 in each of its commands' gouraud word */
    "    mov.w   @(136,gbr),r0\n"
    "    mov.l   6f,r4\n"
    "    extu.w  r0,r0\n"
    "    shll2   r0\n"
    "    shll    r0\n"
    "    add     r0,r4\n"
    "    mov.b   @(155,gbr),r0\n"
    "    shlr2   r0\n"
    "    mov     r0,r2\n"
    "    mov     r8,r3\n"
    "    shlr2   r3\n"
    "15: mov     r3,r0\n"
    "    mov.w   r0,@(28,r4)\n"
    "    dt      r2\n"
    "    bf/s    15b\n"
    "    add     #32,r4\n"
#endif
    "    mov.b   @(155,gbr),r0\n"
    "    cmp/eq  #4,r0\n"
    "    bf      2f\n"
    "    mov.w   @(136,gbr),r0\n"
    "    mov.l   6f,r1\n"
    "    extu.w  r0,r0\n"
    "    shll2   r0\n"
    "    shll    r0\n"
    "    add     r0,r1\n"
    "    mov.b   @(4,r1),r0\n"
    "    tst     #8,r0\n"
    "    bf      4f\n"
    "    mov.w   @(12,r1),r0\n"
    "    mov     r0,r2\n"
    "    mov.w   @(20,r1),r0\n"
    "    sub     r0,r2\n"
    "    cmp/pz  r2\n"
    "    bt      8f\n"
    "    neg     r2,r2\n"
    "8:  mov.w   @(14,r1),r0\n"
    "    mov     r0,r3\n"
    "    mov.w   @(22,r1),r0\n"
    "    sub     r0,r3\n"
    "    cmp/pz  r3\n"
    "    bt      9f\n"
    "    neg     r3,r3\n"
    "9:  add     r3,r2\n"
    "    mov     #" VX_STR(CUT_DIAG) ",r0\n"
    "    cmp/ge  r0,r2\n"
    "    bf      4f\n"
    VX_EDGE(12, 14, 24, 26, r2)
    VX_EDGE(16, 18, 20, 22, r3)
    VX_EDGE(12, 14, 16, 18, r4)
    VX_EDGE(24, 26, 20, 22, r5)
    "    cmp/ge  r3,r2\n"
    "    bt      14f\n"
    "    mov     r3,r2\n"
    "14: add     #1,r2\n"
    "    add     r5,r4\n"
    "    add     #2,r4\n"
    "    mulu.w  r2,r4\n"
    "    sts     macl,r4\n"
    "    shlr    r4\n"
    "    mov     #" VX_STR(VX_LINE) ",r0\n"
    "    mulu.w  r2,r0\n"
    "    sts     macl,r0\n"
    "    add     r0,r4\n"
    "    mov.l   20f,r0\n"
    "    cmp/hs  r0,r4\n"
    "    bf      4f\n"
    "2:  mov.l   r6,@-r15\n"
    "    stc     gbr,r4\n"
    "    mov     r14,r5\n"
    "    mov.l   3f,r1\n"
    "    jsr     @r1\n"
    "    nop\n"
    "    tst     r0,r0\n"
    "    bt/s    4f\n"
    "    mov.l   @r15+,r6\n"
    "    lds.l   @r15+,pr\n"
    "    rts\n"
    "    nop\n"
    "4:  mov.l   5f,r1\n"
    "    mov     r6,r4\n"
    "    jsr     @r1\n"
    "    mov.w   @(136,gbr),r0\n"
    "    add     #4,r0\n"
    "    mov.w   r0,@(136,gbr)\n"
    "    lds.l   @r15+,pr\n"
    "    rts\n"
    "    nop\n"
    "    .p2align 2\n"
    "3:  .long   _vx_emit\n"
    "5:  .long   0x06045E06\n"
    "6:  .long   0x0601B000\n"
    "7:  .long   _vx_fx_out\n"
    "10: .long   0x0603E438\n"
    "20: .long   " VX_STR(VX_MIN_CUT) "\n"
    "    .text\n");
