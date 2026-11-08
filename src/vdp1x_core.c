/* The course quads' VDP1 work, decided from their corners: whether a quad
 * draws faster turned a quarter, and a dear quad cut into pieces from its
 * texture's column strips, the pieces wholly off the screen left out.
 * src/vdp1x.c (the Saturn code) includes this; tools/vdp1x_eval.py builds
 * it alone for the PC, to run the same decisions over lap logs.
 *
 * A quad is its corners A, B, C, D as VDP1 has them (x, y from the local
 * origin). VDP1 draws a textured quad as lines from edge A-D to edge B-C,
 * one a texture row, as many as the longer of A-D and B-C is long; each
 * line costs a fixed time (about 26 cycles, tools/vdp1_lap.py's calibrated
 * Mednafen) and a time for each pixel it steps through, on the screen or
 * off it (VDP1 skips cheaply only a line wholly outside the clip window). */

#ifndef VX_API
#define VX_API
#endif

#ifdef _MSC_VER
#define VX_INLINE static __forceinline
#else
#define VX_INLINE static inline __attribute__((always_inline))   /* GCC may call them otherwise */
#endif

#define VX_LINE 26                  /* cycles a line, besides its pixels */
#define VX_BIAS 2048                /* added to coordinates (-1024 to 1023) to keep sums positive */
#define VX_MAX_U 16                 /* a cut quad's strips, at most */
#define VX_MAX_V 16                 /* and its bands of rows */

typedef struct {
    short c[8];                     /* the piece's corners: xa, ya, xb, yb, xc, yc, xd, yd */
    unsigned short strip;           /* its texture's strip */
    unsigned short row;             /* its first row in that strip */
    unsigned short rows;
    unsigned short pad;
} vx_piece;

VX_INLINE int vx_abs(int v)
{
    return v < 0 ? -v : v;
}

/* the longer of the two axes between corners i and j: the pixels a VDP1 edge steps */
VX_INLINE int vx_edge(const short *c, int i, int j)
{
    int dx = vx_abs(c[2 * i] - c[2 * j]), dy = vx_abs(c[2 * i + 1] - c[2 * j + 1]);
    return dx > dy ? dx : dy;
}

/* VDP1's time for a quad with these edges, estimated: a line a pixel of the longer of A-D and B-C,
   each as long as A-B and D-C on average */
static int vx_cost(int ad, int bc, int ab, int dc)
{
    int lines = (ad > bc ? ad : bc) + 1;
    return VX_LINE * lines + ((lines * (ab + dc + 2)) >> 1);
}

VX_API inline int vx_estimate(const short *c)
{
    return vx_cost(vx_edge(c, 0, 3), vx_edge(c, 1, 2), vx_edge(c, 0, 1), vx_edge(c, 3, 2));
}

/* Drawn turned (from B, its texture turned a quarter), estimated at least 5% cheaper? Over the lap
   logs this gets about 70% of what turning each quad the cheaper way would. A quad whose diagonal
   A-C spans under 16 pixels (x and y together) isn't tried: two thirds of the quads, a fifth of what
   turning saves. */
VX_API int vx_turn(const short *c)
{
    int ad, bc, ab, dc;
    if (vx_abs(c[0] - c[4]) + vx_abs(c[1] - c[5]) < 16) return 0;
    ad = vx_edge(c, 0, 3), bc = vx_edge(c, 1, 2), ab = vx_edge(c, 0, 1), dc = vx_edge(c, 3, 2);
    return vx_cost(ab, dc, ad, bc) * 20 < vx_cost(ad, bc, ab, dc) * 19;
}

/* corners all past one side of the screen (xmin, ymin, xmax, ymax)? */
static int vx_off(const short *c, const short *s)
{
    if (c[0] < s[0] && c[2] < s[0] && c[4] < s[0] && c[6] < s[0]) return 1;
    if (c[0] > s[2] && c[2] > s[2] && c[4] > s[2] && c[6] > s[2]) return 1;
    if (c[1] < s[1] && c[3] < s[1] && c[5] < s[1] && c[7] < s[1]) return 1;
    return c[1] > s[3] && c[3] > s[3] && c[5] > s[3] && c[7] > s[3];
}

static int vx_inside(const short *c, const short *s)
{
    int i;
    for (i = 0; i < 4; i++)
        if (c[2 * i] < s[0] || c[2 * i] > s[2] || c[2 * i + 1] < s[1] || c[2 * i + 1] > s[3]) return 0;
    return 1;
}

static short vx_lat[2 * (VX_MAX_U + 1) * (VX_MAX_V + 1)];

/* A texture's cut: nu strips sw wide, nv bands of band rows (the last what's left of h), and where
   their edges fall across the texture, in 4096ths: u[i] = i / nu, v[j] = (j band) / h */
typedef struct {
    short nu, nv, band, h;
    short u[VX_MAX_U + 1], v[VX_MAX_V + 1];
} vx_cutting;

/* The quad (flips: bit 0 horizontal, bit 1 vertical, as the command has them) cut into pieces from its
   texture's strips, in bands of rows: the pieces not wholly off the screen s, in out (max at most).
   The pieces' corners lie where the quad's mapping puts their texels' edges, bilinear across it,
   shared between neighbours so no gap opens; a mirrored quad's pieces keep its flips (its edges fall
   at 4096 - u, 4096 - v). Unsigned sums of biased coordinates: the SH-2 shifts a signed value right by
   more than one bit only through a library call. The count, or -1 when the quad isn't worth cutting:
   wholly on the screen, or estimated under min cycles. */
VX_API int vx_grid(const short *c, const vx_cutting *t, int flips, const short *s, int min, vx_piece *out, int max)
{
    int nu = t->nu, nv = t->nv, i, j, k, b, n = 0;
    unsigned int u[VX_MAX_U + 1];
    unsigned int ax = c[0] + VX_BIAS, ay = c[1] + VX_BIAS, bx = c[2] + VX_BIAS, by = c[3] + VX_BIAS;
    unsigned int cx = c[4] + VX_BIAS, cy = c[5] + VX_BIAS, dx = c[6] + VX_BIAS, dy = c[7] + VX_BIAS;
    if (vx_inside(c, s) || vx_estimate(c) < min) return -1;
    for (i = 0; i <= nu; i++) u[i] = (flips & 1) ? 4096 - t->u[i] : t->u[i];
    for (j = 0; j <= nv; j++) {
        unsigned int v = (flips & 2) ? 4096 - t->v[j] : t->v[j], iv = 4096 - v;
        /* A (1 - v) + D v and B (1 - v) + C v, in 16ths of a pixel */
        unsigned int lx = (ax * iv + dx * v) >> 8, ly = (ay * iv + dy * v) >> 8;
        unsigned int rx = (bx * iv + cx * v) >> 8, ry = (by * iv + cy * v) >> 8;
        short *p = vx_lat + 2 * j * (nu + 1);
        for (i = 0; i <= nu; i++) {
            unsigned int iu = 4096 - u[i];
            p[2 * i] = (short)(((((lx * iu + rx * u[i]) >> 12) + 8) >> 4) - VX_BIAS);
            p[2 * i + 1] = (short)(((((ly * iu + ry * u[i]) >> 12) + 8) >> 4) - VX_BIAS);
        }
    }
    for (k = 0; k < nu; k++) {
        int i0 = (flips & 1) ? k + 1 : k, i1 = (flips & 1) ? k : k + 1;
        for (b = 0; b < nv; b++) {
            int j0 = (flips & 2) ? b + 1 : b, j1 = (flips & 2) ? b : b + 1;
            const short *a = vx_lat + 2 * (j0 * (nu + 1) + i0), *bb = vx_lat + 2 * (j0 * (nu + 1) + i1);
            const short *cc = vx_lat + 2 * (j1 * (nu + 1) + i1), *d = vx_lat + 2 * (j1 * (nu + 1) + i0);
            vx_piece *q = out + n;
            q->c[0] = a[0], q->c[1] = a[1], q->c[2] = bb[0], q->c[3] = bb[1];
            q->c[4] = cc[0], q->c[5] = cc[1], q->c[6] = d[0], q->c[7] = d[1];
            if (vx_off(q->c, s)) continue;
            if (n == max) return -1;
            q->strip = (unsigned short)k;
            q->row = (unsigned short)(b * t->band);
            q->rows = (unsigned short)((b + 1) * t->band > t->h ? t->h - b * t->band : t->band);
            n++;
        }
    }
    return n;
}

/* A w x h texture's cut into strips sw wide (nu at most VX_MAX_U) and bands of rows; 0 if it can't be. */
VX_API int vx_cutting_of(vx_cutting *t, int w, int h, int sw, int band)
{
    int i, j;
    t->nu = (short)(w / sw), t->nv = (short)((h + band - 1) / band), t->band = (short)band, t->h = (short)h;
    if (t->nu < 1 || t->nu > VX_MAX_U || t->nv > VX_MAX_V) return 0;
    for (i = 0; i <= t->nu; i++) t->u[i] = (short)(i * 4096 / t->nu);
    for (j = 0; j <= t->nv; j++) t->v[j] = (short)((j * band > h ? h : j * band) * 4096 / h);
    return 1;
}
