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
 *
 * DUSA's demos run on its three courses (CCE's 0-2); on CCE's own two
 * (3 and 4) CCE's demo plays, ending by the same clock.
 */
typedef struct {
    short time;
    signed char pcar, tcar;
    int jump;
    int pos[3], tgt[3];
} kf_t;

typedef struct {
    short first;    /* the scene's first keyframe (its length is its cars' track's) */
} scene_t;

typedef struct {
    short scene0, nscenes;          /* its scenes in scenes[] */
    const unsigned char *cars;      /* its cars (tools/build_attract.py) */
} course_t;

#include "dusa_attract.h"

typedef struct {
    int x, y, z;
    short pitch, yaw, roll, pad;
    int ox, oy, oz;
} cam_t;

#define CAM (*(cam_t *volatile *)0x06052094)
#define ATTRACT (*(volatile unsigned char *)0x0601335C)
#define COURSE (*(volatile unsigned char *)0x06054920)    /* 0 Three Seven, 1 Dinosaur Canyon, 2 Seaside Galaxy */
#define FADE_R (*(volatile short *)0x06051F58)     /* colour offset, < 0 while the screen is dark */
#define P1 ((unsigned char *)0x0605224C)
#define AI0 ((unsigned char *)0x060FD400)           /* the AI cars, 0x100 apart */
#define atan2_cce ((int (*)(int x, int y))0x06047E0C)
#define PRISA (*(volatile unsigned short *)0x25F800F0)   /* sprite priority: 0 hides VDP1 */
#define RACE_PRISA 0x0604
#define TILT_UP 0x2000                                  /* 45 degrees */
#define AI_COUNT (*(volatile unsigned char *)0x060529AC)    /* CCE's AI cars, listed through +0x84 */
#define VBL_VECTOR (*(void *volatile *)0x06000100)          /* VBlank-IN */
#define DEMO_VBL ((void *)0x0603C970)   /* patches/attract.s: counts frames, then the handler before */
#define VBL_COUNT (*(volatile int *)0x0603C984)
#define VBL_SAVED (*(void *volatile *)0x0603C988)
#define CCE_TICK (*(volatile unsigned short *)0x060520D6)   /* CCE's attract tick: the title at 1407 */
#define AI_HOLD (*(volatile int *)0x2603CD34)   /* patches/attract.s: CCE's AI update keeps the placed cars */
#define COURSE_LIST (*(short *volatile *)0x26043C20)    /* patches/course_list.s: the course blocks to draw */
#define PAD_PRESSED (*(volatile unsigned short *)0x060072C6)  /* player 1's buttons pressed this frame */
#define START 0x0800
#define DEMO_END 2762           /* frames from the cut to the tick that starts the title at 30 Hz */
#define SEASIDE_SHORT 180       /* DUSA's demo is 920 ticks, 60 fewer on Seaside Galaxy (06008984) */
#define JUMP (12 << 16)         /* a car's move in one tick past any driving (4 units at 300 km/h) */

/* One of DUSA's cars, played back from its recorded track: the tick shown
 * now and the next, between which CCE's 30 Hz frames fall. */
typedef struct {
    int prev[6];            /* this tick: position (16.16), pitch, yaw, roll (unwrapped) */
    int q[6];               /* the next tick */
    int d1[6];              /* the step to it */
    const unsigned char *p; /* the track */
    short run;              /* ticks left with no change */
    unsigned char vis, prev_vis;    /* DUSA draws it */
} track_t;

/* state lives in .data (the blob is reloaded with the attract) */
static const course_t *dusa;    /* DUSA's demo on this course, or 0: CCE's own */
static int frames = -1;     /* frames since the cut, by VBlank; -1 before it */
static int vb_last = 0;     /* the frame count at the last tick */
static int opened = 0;      /* the opening's 3D is on */
static int ticks = 0;       /* DUSA ticks run */
static int dtime = 0;       /* DUSA's camera time */
static int kf = 0;          /* current keyframe */
static int scene = 0;
static int scene_end = 0;   /* the tick the next scene starts */
static int ncars = 0;       /* DUSA's cars in this scene; 0 before it starts */
static int start_pending = 0;   /* Start pressed in the demo: the title at the next tick past the cut */
static track_t tracks[MAX_CARS];
static const unsigned char *blk_p;  /* the next change to the course blocks on screen, or 0 */
static unsigned char blk_on[64];    /* the blocks on screen, a bit each (tools/build_attract.py's MAX_BLOCKS) */
static short blk_list[513];         /* the same as patches/course_list.s takes them: a count, the blocks */

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

static int rd(const unsigned char *p, int n)    /* big-endian, signed, n = 2 or 4 bytes */
{
    int v = 0, i;
    for (i = 0; i < n; i++)
        v = v << 8 | p[i];
    return n == 2 ? (short)v : v;
}

static int varint(track_t *t)
{
    unsigned z = 0, b;
    int s = 0;
    do {
        b = *t->p++;
        z |= (b & 0x7F) << s;
        s += 7;
    } while (b & 0x80);
    return (int)(z >> 1) ^ -(int)(z & 1);
}

static void step(track_t *t)        /* on to the next tick */
{
    int i, m = 0;
    for (i = 0; i < 6; i++)
        t->prev[i] = t->q[i];
    t->prev_vis = t->vis;
    if (t->run > 0) {
        t->run--;
    } else {
        m = *t->p++;
        if (m & 0x80) {
            t->run = (m & 0x7F) - 1;
            m = 0;
        }
    }
    for (i = 0; i < 6; i++) {
        if (m & 1 << i)
            t->d1[i] += varint(t);
        t->q[i] += t->d1[i];
    }
    if (m & 0x40)
        t->vis ^= 1;
}

/* Scene s's cars at their first two ticks, from this tick on. CCE's AI
 * cars past DUSA's come off CCE's list (count 060529AC, next +0x84), so
 * nothing moves, draws or meets them; the list is CCE's cars in order.
 * The slave CPU walks the list (0603E60C) while this runs, so every car
 * links on to the next and only the count changes: a walk that read the
 * count before or after the change stays on cars (a 0 link would end the
 * list under a walk that took the larger count). */
static void cars_start(int s)
{
    const unsigned char *sc = dusa->cars + rd(dusa->cars + 4 + 4 * s, 4), *h;
    track_t *t;
    int c, i;
    ncars = sc[0];
    scene_end = ticks + rd(sc + 2, 2);
    for (c = 0; c < ncars; c++) {
        h = sc + 4 + 24 * c;
        t = &tracks[c];
        for (i = 0; i < 3; i++) {
            t->q[i] = rd(h + 4 * i, 4);
            t->q[3 + i] = rd(h + 12 + 2 * i, 2);
            t->d1[i] = t->d1[3 + i] = 0;
        }
        t->vis = h[19];
        t->p = dusa->cars + rd(h + 20, 4);
        t->run = 0;
        step(t);
    }
    for (c = 1; c < ncars; c++)
        *(unsigned char **)(car_at(c) + 0x84) = car_at(c + 1);
    AI_COUNT = ncars - 1;
}

/* Each car u (16.16) of the way from this tick to the next, as DUSA's
 * frames would show it at this moment; a car that jumps (DUSA moves a drone
 * coming back from its cheap mode on to where it should be, up to 100
 * units in one tick) stays put until the tick, as DUSA shows it. */
static void cars_place(int u)
{
    track_t *t;
    unsigned char *car;
    int n, i, v[6], f;
    for (n = 0; n < ncars; n++) {
        t = &tracks[n];
        car = car_at(n);
        f = u;
        for (i = 0; i < 3; i++)
            if (t->q[i] - t->prev[i] > JUMP || t->prev[i] - t->q[i] > JUMP)
                f = 0;
        for (i = 0; i < 6; i++)
            v[i] = t->prev[i] + mul16(t->q[i] - t->prev[i], f);
        ((int *)car)[0] = v[0];
        ((int *)car)[1] = v[1];
        ((int *)car)[2] = v[2];
        *(short *)(car + 0xC) = v[3];
        *(short *)(car + 0xE) = v[4];
        *(short *)(car + 0x10) = v[5];
    }
}

/* CCE's detail level for its AI cars (+0x98: the draw picks the model by
 * it, or skips the car) from the distance to this tick's camera, as
 * 0603FABE does, or 0, unseen, where DUSA doesn't draw the car. After the
 * camera is set: CCE's attract routine, which runs first in the tick, leaves
 * its own camera in the struct, and levels from there switched a car
 * between models from tick to tick. CCE's AI update sets its own level
 * after the cars are drawn, for its own use. */
static void cars_lod(void)
{
    cam_t *c = CAM;
    unsigned char *car;
    int n, dx, dz, d;
    for (n = 1; n < ncars; n++) {
        car = car_at(n);
        dx = (((int *)car)[0] - c->x) >> 16;
        dz = (((int *)car)[2] - c->z) >> 16;
        d = dx * dx + dz * dz;
        car[0x98] = !tracks[n].prev_vis ? 0 : d < 10 * 10 ? 4 : d < 52 * 52 ? 3 : 2;
    }
}

/* The course blocks for this frame count, for patches/course_list.s to draw
 * in place of CCE's choice by the camera's sector, which drops blocks still
 * on screen as a crane's sector changes: CCE's choice at each camera of
 * DUSA's demo and the blocks on screen it draws elsewhere in the shot
 * (tools/attract_vis.py, tools/build_attract.py, which keeps when each comes
 * and goes). */
static void course_blocks(void)
{
    int n, b, changed = 0;
    while (blk_p && (blk_p[0] << 8 | blk_p[1]) <= frames) {
        for (n = blk_p[2], blk_p += 3; n > 0; n--, blk_p += 2) {
            b = blk_p[0] << 8 | blk_p[1];
            blk_on[b >> 3] ^= 1 << (b & 7);
        }
        changed = 1;
    }
    if (!changed)
        return;
    for (b = n = 0; b < 512; b++)
        if (blk_on[b >> 3] & 1 << (b & 7))
            blk_list[++n] = b;
    blk_list[0] = n;
    COURSE_LIST = blk_list;
}

static const kf_t *next_kf(int k)
{
    const kf_t *n = &kfs[k + 1];
    return n->time == -1 ? &kfs[n->jump] : n;
}

/* One DUSA tick of 060055BC's keyframe logic: on to the next keyframe
 * once its time comes (at once for a shot's first, time 0, which restarts
 * the time); the time counts up after the tick's camera. DUSA's scenes
 * follow one another tick after tick: at the next one's first tick its
 * camera starts from its first keyframe and every car is placed afresh;
 * past the last recorded tick the cars hold. */
static void dusa_tick(void)
{
    const kf_t *n;
    int c;
    if (ticks == scene_end && scene + 1 < dusa->nscenes) {
        scene++;
        kf = scenes[dusa->scene0 + scene].first;
        dtime = 0;
        cars_start(scene);
    } else if (ticks > 0) {
        dtime++;
        if (ticks < scene_end)
            for (c = 0; c < ncars; c++)
                step(&tracks[c]);
    }
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
    if (!ATTRACT)
        return;
    if (frames < 0) {               /* hold the first keyframe until the cut */
        dusa = COURSE < N_DUSA_COURSES ? &courses[COURSE] : 0;
        AI_HOLD = dusa != 0;        /* the cars are placed here, not driven by CCE's AI */
        if (dusa && !ncars) {
            kf = scenes[dusa->scene0].first;
            cars_start(0);
            i = dusa->cars[1] << 16 | dusa->cars[2] << 8 | dusa->cars[3];
            blk_p = i ? dusa->cars + i : 0;
        }
        if (FADE_R < 0) {
            if (dusa) {
                cars_place(0);
                place(kfs[kf].pos, kfs[kf].pcar, e);
                place(kfs[kf].tgt, kfs[kf].tcar, g);
                look(c, e, g);
                cars_lod();
                c->pitch = TILT_UP;     /* the cut's first frame (below) */
                PRISA = 0;
            }
            return;
        }
        /* the cut: from here the clock is the VBlank count (wall time), so a
         * tick that takes three frames on a Saturn moves the scene on three */
        VBL_COUNT = 0;
        VBL_SAVED = VBL_VECTOR;
        VBL_VECTOR = DEMO_VBL;
        frames = vb_last = 0;
    } else {
        i = VBL_COUNT;
        frames = i != vb_last ? i : frames + 2;     /* 30 Hz if something took the vector */
        vb_last = i;
    }
    if (!dusa)                      /* CCE's own demo, on the clock all the same */
        return;
    course_blocks();
    while (ticks <= frames / 3)     /* DUSA ticks begun by this frame */
        dusa_tick();
    cars_place(frac(frames % 3, 3));
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
    cars_lod();
    /* DUSA's opening: before its first 3D frame shows, its sky and ground
     * alone, three frames tilted up (the horizon low), then four level.
     * Here four and four: from the cut (the tick before frame 0), sprites
     * hidden and tilted up, frame 0 still up, 2 and 4 level, 3D from 6. */
    if (scene == 0 && frames < 6) {
        if (frames < 2)
            c->pitch = TILT_UP;
    } else if (!opened) {
        PRISA = RACE_PRISA;
        opened = 1;
    }
}

/* The attract's tick (called through 060285AC in place of 06031DFA): CCE's
 * attract routine (its answer goes back to the race loop), then DUSA's
 * camera over CCE's. CCE starts the title by its own tick count, which
 * falls behind when ticks take longer than two frames: once the frame
 * count says the demo is over (DUSA's length, on every course), its count
 * is brought up to the title. Start in the demo, which CCE answers with its
 * own title page, brings it up to the title too, as DUSA's Start goes to
 * its title: taken from the pad (so CCE's routine doesn't see it, and the
 * title doesn't take it as its own Start), and held until the cut when it
 * comes in the dark before it. */
int attract_entry(void) __attribute__((section(".text.entry")));
int attract_entry(void)
{
    int answer;
    if (ATTRACT && CCE_TICK < 1406 && (PAD_PRESSED & START)) {
        PAD_PRESSED &= ~START;
        start_pending = 1;
    }
    if (ATTRACT && frames >= 0 && CCE_TICK < 1406
        && (start_pending || VBL_COUNT >= DEMO_END - (COURSE == 2 ? SEASIDE_SHORT : 0)))
        CCE_TICK = 1406;
    answer = ((int (*)(void))0x06031DFA)();
    camera();
    return answer;
}
