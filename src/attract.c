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
#define COURSE (*(volatile unsigned char *)0x06054920)    /* 0 Three Seven, 1 Dinosaur Canyon */
#define FADE_R (*(volatile short *)0x06051F58)     /* colour offset, < 0 while the screen is dark */
#define P1 ((unsigned char *)0x0605224C)
#define AI0 ((unsigned char *)0x060FD400)           /* the AI cars, 0x100 apart */
#define atan2_cce ((int (*)(int x, int y))0x06047E0C)
#define PRISA (*(volatile unsigned short *)0x25F800F0)   /* sprite priority: 0 hides VDP1 */
#define RACE_PRISA 0x0604
#define TILT_UP 0x2000                                  /* 45 degrees */
#define AI_COUNT (*(volatile unsigned char *)0x060529AC)    /* CCE's AI cars, listed through +0x84 */
#define CARS ((const unsigned char *)CARS_AT)    /* DUSA's demo cars (tools/build_attract.py) */

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
static int frames = -1;     /* frames since the scene began; -1 before the cut */
static int ticks = 0;       /* DUSA ticks run */
static int dtime = 0;       /* DUSA's camera time */
static int kf = 0;          /* current keyframe */
static int scene = 0;
static int ncars = 0;       /* DUSA's cars in this scene; 0 before it starts */
static track_t tracks[MAX_CARS];

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

/* The scene's cars at their first two ticks. CCE's AI cars past DUSA's
 * come off CCE's list (count 060529AC, next +0x84), so nothing moves,
 * draws or meets them for the rest of the demo. */
static void cars_start(int s)
{
    const unsigned char *sc = CARS + rd(CARS + 4 + 4 * s, 4), *h;
    track_t *t;
    int c, i;
    ncars = sc[0];
    for (c = 0; c < ncars; c++) {
        h = sc + 4 + 24 * c;
        t = &tracks[c];
        for (i = 0; i < 3; i++) {
            t->q[i] = rd(h + 4 * i, 4);
            t->q[3 + i] = rd(h + 12 + 2 * i, 2);
            t->d1[i] = t->d1[3 + i] = 0;
        }
        t->vis = h[19];
        t->p = CARS + rd(h + 20, 4);
        t->run = 0;
        step(t);
    }
    AI_COUNT = ncars - 1;
    *(int *)(car_at(ncars - 1) + 0x84) = 0;
}

/* Each car u (16.16) of the way from this tick to the next, as DUSA's
 * frames would show it at this moment. CCE's detail level for its AI cars
 * (+0x98, which CCE sets from the car's distance, 0603FABE, before this
 * and draws by after) from the distance to the camera, or 0, unseen, where
 * DUSA doesn't draw the car. */
static void cars_place(int u)
{
    track_t *t;
    unsigned char *car;
    cam_t *c = CAM;
    int n, i, v[6], dx, dz, d;
    for (n = 0; n < ncars; n++) {
        t = &tracks[n];
        car = car_at(n);
        for (i = 0; i < 6; i++)
            v[i] = t->prev[i] + mul16(t->q[i] - t->prev[i], u);
        ((int *)car)[0] = v[0];
        ((int *)car)[1] = v[1];
        ((int *)car)[2] = v[2];
        *(short *)(car + 0xC) = v[3];
        *(short *)(car + 0xE) = v[4];
        *(short *)(car + 0x10) = v[5];
        if (n > 0) {
            dx = (v[0] - c->x) >> 16;
            dz = (v[2] - c->z) >> 16;
            d = dx * dx + dz * dz;
            car[0x98] = !t->prev_vis ? 0 : d < 10 * 10 ? 4 : d < 52 * 52 ? 3 : 2;
        }
    }
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
    int c;
    if (ticks > 0) {
        dtime++;
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
    if (!ATTRACT || COURSE != 0 || scene >= 1)  /* DUSA's scenes for Three Seven */
        return;
    if (frames < 0) {               /* hold the first keyframe until the cut */
        kf = scenes[scene].first;
        if (!ncars && scene < N_CAR_SCENES)
            cars_start(scene);
        if (FADE_R < 0) {
            cars_place(0);
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

/* The attract's tick (called through 060285AC in place of 06031DFA): CCE's
 * attract routine (its answer goes back to the race loop), then DUSA's
 * camera over CCE's. */
int attract_entry(void) __attribute__((section(".text.entry")));
int attract_entry(void)
{
    int answer;
    answer = ((int (*)(void))0x06031DFA)();
    camera();
    return answer;
}
