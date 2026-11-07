// Stick Lab's Saturn start-up, screen and pad (see platform.h). The bitmap
// layer follows the Tomb Raider project's (dspbench/platform.cpp,
// saturn/screen.cpp), the pad its saturn/input.cpp; the Saturn has proven
// both.

#include "platform.h"
#include "hw.h"

#define BIOS_CHG_SYSCK      (*(void (**)(uint32_t))0x06000320)  // 0: 320-dot clock, 1: 352-dot

#define SMPC_INTBACK    0x10
#define SMPC_SR_NPE     0x20    // an INTBACK holds more peripheral data
#define SMPC_BREAK      0x40    // IREG0: end that INTBACK
#define SMPC_DOTSEL     0x40    // system status 1: the 352-dot clock
#define IREG1_PEN       0x08    // peripheral data, 15-byte mode for both ports
#define PORT_DIRECT     0xF1    // port status: one peripheral, no multitap

#define BACK_COLOR_ADDR 0x7FFFE // the last word of VDP2 VRAM
#define BLACK           RGB(0, 0, 0)

uint32_t ticks()
{
    uint32_t sr;
    asm volatile("stc sr, %0" : "=r"(sr));
    asm volatile("ldc %0, sr" : : "r"(sr | 0xF0));
    uint32_t hi = FRT_FRCH;     // latches FRCL
    uint32_t lo = FRT_FRCL;
    asm volatile("ldc %0, sr" : : "r"(sr));
    return (hi << 8) | lo;
}

void delayTicks(uint32_t n)
{
    uint32_t start = ticks();
    while (ticksSince(start) < n);
}

void waitVblankIn()
{
    while (VDP2_TVSTAT & TVSTAT_VBLANK);
    while (!(VDP2_TVSTAT & TVSTAT_VBLANK));
}

// --- the SMPC and the clock ---------------------------------------------

static void smpcIdle()
{
    while (SMPC_SF & 1);
    if (SMPC_SR & SMPC_SR_NPE)
    {
        SMPC_IREG(0) = SMPC_BREAK;
        while (SMPC_SF & 1);
    }
}

// INTBACK without peripheral data: system status 1 (SMPC_DOTSEL).
static uint32_t smpcStatus()
{
    smpcIdle();
    SMPC_SF = 1;
    SMPC_IREG(0) = 0x01;
    SMPC_IREG(1) = 0x00;
    SMPC_IREG(2) = 0xF0;
    SMPC_COMREG = SMPC_INTBACK;
    while (SMPC_SF & 1);
    return SMPC_OREG(10);
}

// --- the pad ------------------------------------------------------------

static bool gPadPending;

void padRead(Pad& pad)
{
    if (gPadPending)
    {
        if (SMPC_SF & 1)
            return;     // not finished yet: the last state stands

        if (SMPC_OREG(0) == PORT_DIRECT)
        {
            pad.id = SMPC_OREG(1);
            pad.buttons = ~((SMPC_OREG(2) << 8) | SMPC_OREG(3)) & 0xFFF8;
            // an analog device (type 1) with at least one axis byte after the buttons
            bool analog = (pad.id >> 4) == 1 && (pad.id & 0xF) >= 3;
            pad.x = analog ? SMPC_OREG(4) : -1;
        }
        else
        {
            pad.id = PAD_ID_NONE;
            pad.buttons = 0;
            pad.x = -1;
        }

        if (SMPC_SR & SMPC_SR_NPE) {
            SMPC_IREG(0) = SMPC_BREAK;
        }
        gPadPending = false;
    }

    SMPC_SF = 1;
    SMPC_IREG(0) = 0x00;
    SMPC_IREG(1) = IREG1_PEN;
    SMPC_IREG(2) = 0xF0;
    SMPC_COMREG = SMPC_INTBACK;
    gPadPending = true;
}

// --- the bitmap ---------------------------------------------------------

static uint32_t vdp2Line()
{
    (void)VDP2_EXTEN;   // latch the counter
    return VDP2_VCNT & 0x1FF;
}

// Until the line counter enters the vertical blank.
static void waitBlankLines()
{
    uint32_t polls = 0;
    while (vdp2Line() >= SCREEN_HEIGHT && ++polls < 200000);
    while (vdp2Line() < SCREEN_HEIGHT && ++polls < 200000);
}

void fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t colour)
{
    for (int32_t row = y; row < y + h; row++)
    {
        volatile uint16_t* p = pixelAt(x, row);
        for (int32_t i = 0; i < w; i++) {
            p[i] = colour;
        }
    }
}

// NBG0: a 512x256 15-bit bitmap in VRAM bank A, the Tomb Raider game's
// layout. Every other register is cleared first, whatever the BIOS or the
// Satiator's menu left there, inside a vertical blank. The display comes on
// inside a vertical blank too (TVMD's DISP may go from 0 to 1 only then).
static void vdp2Init()
{
    waitBlankLines();
    VDP2_BGON = 0;
    for (uint32_t a = 0x25F8000E; a < VDP2_REGS_END; a += 2) {
        REG16(a) = 0;
    }
    VDP2_SPCTL = SPCTL_SPCLMD;  // sprites at priority 0: VDP1 never shows
    REG16(VDP2_VRAM + BACK_COLOR_ADDR) = BLACK;
    VDP2_BKTAU = (BACK_COLOR_ADDR >> 17) & 7;
    VDP2_BKTAL = (BACK_COLOR_ADDR >> 1) & 0xFFFF;

    uint16_t bitmap = (CYCP_N0CG << 12) | (CYCP_N0CG << 8) | (CYCP_N0CG << 4) | CYCP_N0CG;
    uint16_t cpu = (CYCP_CPU << 12) | (CYCP_CPU << 8) | (CYCP_CPU << 4) | CYCP_CPU;
    VDP2_RAMCTL = RAMCTL_VRAMD | RAMCTL_VRBMD;
    VDP2_CYCA0L = VDP2_CYCA1L = bitmap;
    VDP2_CYCA0U = VDP2_CYCA1U = cpu;
    VDP2_CYCB0L = VDP2_CYCB0U = VDP2_CYCB1L = VDP2_CYCB1U = cpu;
    VDP2_CHCTLA = CHCTLA_N0_32K | CHCTLA_N0BMEN;
    VDP2_ZMXIN0 = VDP2_ZMYIN0 = 1;
    VDP2_PRINA = 7;

    volatile uint32_t* p = (volatile uint32_t*)VDP2_VRAM;
    for (uint32_t i = 0; i < PITCH * 256 / 2; i++) {
        p[i] = 0;
    }
    VDP2_BGON = BGON_N0ON;
    waitBlankLines();
    VDP2_TVMD = TVMD_DISP;
}

void platformInit()
{
    // The BIOS boots on the 320-dot clock; should something have left the
    // 352-dot one, back to 320, repeated until the SMPC reports it.
    for (int32_t tries = 0; tries < 4 && (smpcStatus() & SMPC_DOTSEL); tries++)
    {
        smpcIdle();
        BIOS_CHG_SYSCK(0);
    }
    FRT_TCR = 0;        // a tick every 8 cycles
    vdp2Init();
}
