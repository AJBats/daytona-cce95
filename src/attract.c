/* DUSA's attract camera in CCE95's attract (docs/attract.md, "Camera work").
 * Built by tools/build_attract.py into LWRAM 0x002E2780 (DEMOTTL.BIN);
 * the race loop calls attract_entry for the attract's 30 Hz tick
 * (patches/attract.s points 060285AC at it).
 *
 * DUSA (060055BC): keyframes, each a camera position and a point it looks
 * at, either in the world or riding with a car (DUSA's car 0 is the player,
 * here CCE's player car; car n its n-th car, here CCE's n-th AI car). The
 * camera moves linearly between keyframes in 20 Hz ticks; a keyframe at
 * time 0 starts a shot, -1 jumps. Look-at (06005294): yaw = -atan2(dx, dz),
 * pitch = atan2(dy, d), d ~ 0.924 max + 0.383 min of |dx|, |dz|, roll 0.
 * A riding point is car + Ry(yaw) Rx(pitch) Rz(roll) point, with DUSA's
 * signs (fitted to DUSA's own camera to 0.01 units).
 *
 * CCE's attract camera (the struct at *06052094): pivot +0, angles +0xC
 * pitch, +0xE yaw, +0x10 roll; offset +0x14, set to 0 so the eye is the
 * pivot. Angles in both games: 0x10000 a turn, yaw 0 along +z.
 */
typedef struct {
    short time;
    signed char pcar, tcar;
    int jump;
    int pos[3], tgt[3];
} kf_t;

typedef struct {
    short first;    /* the scene's first keyframe */
    short end;      /* its length in DUSA ticks */
} scene_t;

#include "dusa_attract.h"

typedef struct {
    int x, y, z;
    short pitch, yaw, roll, pad;
    int ox, oy, oz;
} cam_t;

#define CAM (*(cam_t *volatile *)0x06052094)
#define ATTRACT (*(volatile unsigned char *)0x0601335C)
#define FADE_R (*(volatile short *)0x06051F58)     /* colour offset, < 0 while the screen is dark */
#define P1 ((unsigned char *)0x0605224C)
#define AI0 ((unsigned char *)0x060FD400)           /* the AI cars, 0x100 apart */
#define atan2_cce ((int (*)(int x, int y))0x06047E0C)
#define PRISA (*(volatile unsigned short *)0x25F800F0)   /* sprite priority: 0 hides VDP1 */
#define RACE_PRISA 0x0604
#define TILT_UP 0x2000                                  /* 45 degrees */

/* state lives in .data (the blob is reloaded with the attract) */
static int frames = -1;     /* frames since the scene began; -1 before the cut */
static int ticks = 0;       /* DUSA ticks run */
static int dtime = 0;       /* DUSA's camera time */
static int kf = 0;          /* current keyframe */
static int scene = 0;

static int mul16(int a, int b)
{
    return (int)(((long long)a * b) >> 16);
}

static int sin16(int a)     /* 16.16, a in 0x10000 a turn */
{
    static const int q[65] = {
        0, 1608, 3212, 4808, 6393, 7962, 9512, 11039, 12540, 14010, 15447, 16846,
        18205, 19520, 20788, 22006, 23170, 24279, 25330, 26320, 27246, 28106,
        28899, 29622, 30274, 30853, 31357, 31786, 32138, 32413, 32610, 32729,
        32768, 32729, 32610, 32413, 32138, 31786, 31357, 30853, 30274, 29622,
        28899, 28106, 27246, 26320, 25330, 24279, 23170, 22006, 20788, 19520,
        18205, 16846, 15447, 14010, 12540, 11039, 9512, 7962, 6393, 4808, 3212,
        1608, 0};
    int i, f, v;
    a &= 0xFFFF;
    i = (a & 0x7FFF) >> 9;          /* 64 steps over a half turn */
    f = a & 0x1FF;
    v = q[i] + (((q[i + 1] - q[i]) * f) >> 9);
    v <<= 1;                        /* the table is in 1.15 */
    return a & 0x8000 ? -v : v;
}

static int cos16(int a)
{
    return sin16(a + 0x4000);
}

static unsigned char *car_at(int n)
{
    return n == 0 ? P1 : AI0 + (n - 1) * 0x100;
}

static void place(const int *p, int car, int *out)
{
    unsigned char *c;
    int sp, cp, sy, cy, sr, cr, x, y, z, x1, y1, y2, z2;
    if (car < 0) {
        out[0] = p[0]; out[1] = p[1]; out[2] = p[2];
        return;
    }
    c = car_at(car);
    sp = sin16(*(short *)(c + 0xC)); cp = cos16(*(short *)(c + 0xC));
    sy = sin16(*(short *)(c + 0xE)); cy = cos16(*(short *)(c + 0xE));
    sr = sin16(*(short *)(c + 0x10)); cr = cos16(*(short *)(c + 0x10));
    x = p[0]; y = p[1]; z = p[2];
    x1 = mul16(x, cr) + mul16(y, sr);       /* roll */
    y1 = mul16(y, cr) - mul16(x, sr);
    y2 = mul16(y1, cp) + mul16(z, sp);      /* pitch */
    z2 = mul16(z, cp) - mul16(y1, sp);
    out[0] = ((int *)c)[0] + mul16(x1, cy) - mul16(z2, sy);   /* yaw */
    out[1] = ((int *)c)[1] + y2;
    out[2] = ((int *)c)[2] + mul16(x1, sy) + mul16(z2, cy);
}

static int lerp(int a, int b, int f)
{
    return a + mul16(b - a, f);
}

static int frac(int num, int den)   /* num / den in 16.16, 0 <= num <= den < 0x8000 */
{
    volatile int *div = (volatile int *)0xFFFFFF00;
    div[0] = den;                   /* DVSR */
    div[1] = num << 16;             /* DVDNT: starts the 32 / 32 divide */
    return div[1];
}

static void look(cam_t *c, const int *e, const int *t)
{
    int dx = t[0] - e[0], dy = t[1] - e[1], dz = t[2] - e[2];
    int ax = dx < 0 ? -dx : dx, az = dz < 0 ? -dz : dz, d;
    d = ax > az ? mul16(ax, 0xEC83) + mul16(az, 0x61F7) : mul16(az, 0xEC83) + mul16(ax, 0x61F7);
    c->x = e[0]; c->y = e[1]; c->z = e[2];
    c->yaw = atan2_cce(dz, -dx);
    c->pitch = atan2_cce(d, dy);
    c->roll = 0;
    c->ox = c->oy = c->oz = 0;
}

static const kf_t *next_kf(int k)
{
    const kf_t *n = &kfs[k + 1];
    return n->time == -1 ? &kfs[n->jump] : n;
}

/* One DUSA tick of 060055BC's keyframe logic: on to the next keyframe
 * once its time comes (at once for a shot's first, time 0, which restarts
 * the time); the time counts up after the tick's camera. */
static void dusa_tick(void)
{
    const kf_t *n;
    if (ticks > 0)
        dtime++;
    n = next_kf(kf);
    if (dtime >= n->time) {
        kf = n - kfs;
        if (n->time == 0)
            dtime = 0;
    }
    ticks++;
}

static void camera(void)
{
    const kf_t *k0, *k1;
    int f, span, p0[3], p1[3], e[3], g[3], i;
    cam_t *c = CAM;
    if (!ATTRACT || scene >= 1)
        return;
    if (frames < 0) {               /* hold the first keyframe until the cut */
        kf = scenes[scene].first;
        if (FADE_R < 0) {
            place(kfs[kf].pos, kfs[kf].pcar, e);
            place(kfs[kf].tgt, kfs[kf].tcar, g);
            look(c, e, g);
            c->pitch = TILT_UP;     /* the cut's first frame (below) */
            PRISA = 0;
            return;
        }
        frames = 0;
    }
    while (ticks <= frames / 3)     /* DUSA ticks begun by this frame */
        dusa_tick();
    k0 = &kfs[kf];
    k1 = next_kf(kf);
    span = 3 * (k1->time - k0->time);
    f = span > 0 ? frac(3 * (dtime - k0->time) + frames % 3, span) : 0;
    place(k0->pos, k0->pcar, p0);
    place(k1->pos, k1->pcar, p1);
    for (i = 0; i < 3; i++)
        e[i] = lerp(p0[i], p1[i], f);
    place(k0->tgt, k0->tcar, p0);
    place(k1->tgt, k1->tcar, p1);
    for (i = 0; i < 3; i++)
        g[i] = lerp(p0[i], p1[i], f);
    look(c, e, g);
    /* DUSA's opening: before its first 3D frame shows, its sky and ground
     * alone, three frames tilted up (the horizon low), then four level.
     * Here four and four: from the cut (the tick before frame 0), sprites
     * hidden and tilted up, frame 0 still up, 2 and 4 level, 3D from 6. */
    if (scene == 0 && frames < 6) {
        if (frames < 2)
            c->pitch = TILT_UP;
    } else if (scene == 0 && frames == 6) {
        PRISA = RACE_PRISA;
    }
    frames += 2;
    if (ticks > scenes[scene].end)
        scene++;
}

/* patches/reflection.s's window reflection for the demo car (player 1):
 * reflect takes r9 = player, r12 = car and keeps r0 */
static void reflect_p1(void)
{
    __asm__ volatile(
        "mov.l r9,@-r15\n\t"
        "mov.l r12,@-r15\n\t"
        "mov #0,r9\n\t"
        "mov.l 1f,r12\n\t"
        "mov.l 2f,r1\n\t"
        "jsr @r1\n\t"
        "nop\n\t"
        "mov.l @r15+,r12\n\t"
        "bra 3f\n\t"
        "mov.l @r15+,r9\n\t"
        ".align 2\n"
        "1:\t.long 0x0605224C\n"
        "2:\t.long 0x0603C4D8\n"
        "3:\n"
        ::: "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "pr", "t", "memory");
}

/* The attract's tick (called through 060285AC in place of 06031DFA): the
 * reflection, CCE's attract routine (its answer goes back to the race
 * loop), then DUSA's camera over CCE's. */
int attract_entry(void) __attribute__((section(".text.entry")));
int attract_entry(void)
{
    int answer;
    reflect_p1();
    answer = ((int (*)(void))0x06031DFA)();
    camera();
    return answer;
}
