/* Saturn hardware registers (cache-through addresses): the ones Stick Lab
   uses, from the Tomb Raider project's saturn/hw.h. */
#ifndef HW_H
#define HW_H

#include <stdint.h>

#define REG16(a) (*(volatile uint16_t *)(a))

/* VDP2 */
#define VDP2_VRAM   0x25E00000
#define VDP2_REGS   0x25F80000
#define VDP2_REGS_END 0x25F80120
#define VDP2_TVMD   REG16(0x25F80000)
#define VDP2_EXTEN  REG16(0x25F80002)   /* reading it latches HCNT/VCNT */
#define VDP2_TVSTAT REG16(0x25F80004)
#define VDP2_VCNT   REG16(0x25F8000A)
#define VDP2_RAMCTL REG16(0x25F8000E)
#define VDP2_CYCA0L REG16(0x25F80010)
#define VDP2_CYCA0U REG16(0x25F80012)
#define VDP2_CYCA1L REG16(0x25F80014)
#define VDP2_CYCA1U REG16(0x25F80016)
#define VDP2_CYCB0L REG16(0x25F80018)
#define VDP2_CYCB0U REG16(0x25F8001A)
#define VDP2_CYCB1L REG16(0x25F8001C)
#define VDP2_CYCB1U REG16(0x25F8001E)
#define VDP2_BGON   REG16(0x25F80020)
#define VDP2_CHCTLA REG16(0x25F80028)
#define VDP2_ZMXIN0 REG16(0x25F80078)
#define VDP2_ZMYIN0 REG16(0x25F8007C)
#define VDP2_BKTAU  REG16(0x25F800AC)
#define VDP2_BKTAL  REG16(0x25F800AE)
#define VDP2_SPCTL  REG16(0x25F800E0)
#define VDP2_PRINA  REG16(0x25F800F8)

#define TVMD_DISP       0x8000  /* 320 dots, 224 lines, non-interlaced with the other bits 0 */
#define TVSTAT_VBLANK   0x0008
#define RAMCTL_VRAMD    0x0100  /* VRAM A as banks A0 and A1 */
#define RAMCTL_VRBMD    0x0200  /* VRAM B as banks B0 and B1 */
#define CYCP_N0CG       0x4     /* cycle pattern slots: NBG0 character/bitmap read */
#define CYCP_CPU        0xE     /* CPU access */
#define BGON_N0ON       0x0001
#define CHCTLA_N0BMEN   0x0002  /* NBG0 is a bitmap (512x256 with size bits 0) */
#define CHCTLA_N0_32K   0x0030  /* NBG0 in 15-bit RGB */
#define SPCTL_SPCLMD    0x0020

/* SMPC (odd bytes only) */
#define SMPC_REG(x)     (*(volatile uint8_t*)(0x20100000 + (x)))
#define SMPC_IREG(n)    SMPC_REG(0x01 + (n) * 2)
#define SMPC_COMREG     SMPC_REG(0x1F)
#define SMPC_OREG(n)    SMPC_REG(0x21 + (n) * 2)
#define SMPC_SR         SMPC_REG(0x61)
#define SMPC_SF         SMPC_REG(0x63)

/* the CPU's free-running timer */
#define FRT_TCR         (*(volatile uint8_t*)0xFFFFFE16)
#define FRT_FRCH        (*(volatile uint8_t*)0xFFFFFE12)
#define FRT_FRCL        (*(volatile uint8_t*)0xFFFFFE13)

/* 15-bit colour; bit 15 marks an RGB pixel (0 is transparent: the back colour) */
#define RGB(r, g, b) (0x8000 | ((b) << 10) | ((g) << 5) | (r))

#endif
