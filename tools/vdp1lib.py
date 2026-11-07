"""The Tomb Raider project's Mednafen fork's VDP1 drawing code, as a library
(TombRaiderSaturn build/stepwise/vdp1lib.dll, built there by
tools/crunch/build_vdp1lib.sh; copied to tools/mednafen/vdp1lib.dll),
driven from Python. A copy of that project's tools/crunch/vdp1.py, with the
calibrated costs tools/vdp1_lap.py runs Mednafen with.

VRAM and the frame buffer are numpy views of the library's arrays: 16-bit
words in host order, as Mednafen keeps them. Saturn memory dumps are
big-endian bytes; load_vram / load_fb convert.
"""
import ctypes
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DLL = os.path.join(ROOT, 'tools', 'mednafen', 'vdp1lib.dll')
CALIBRATED = dict(texel=20, tex_pixel=0, gouraud=14, pixel=0, line=262)

FB_WIDTH = 512      # words a frame buffer line, 16bpp
FB_LINES = 256


class PlotTotals(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in ('commands', 'cycles', 'lines', 'pixels', 'texels', 'gouraud')]


class CommandCost(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in ('addr', 'cycles', 'lines', 'pixels', 'texels', 'gouraud')]


class Vdp1:
    def __init__(self, tvmr=0, fbcr=0x03, costs=None, dll=DLL):
        self.lib = ctypes.CDLL(dll)
        self.lib.vdp1_vram.restype = ctypes.POINTER(ctypes.c_uint16)
        self.lib.vdp1_fb.restype = ctypes.POINTER(ctypes.c_uint16)
        self.lib.vdp1_plot.restype = ctypes.c_int32
        self.lib.vdp1_plot.argtypes = [ctypes.POINTER(PlotTotals), ctypes.POINTER(CommandCost), ctypes.c_int32]
        self.vram = np.ctypeslib.as_array(self.lib.vdp1_vram(), shape=(0x40000,))
        self.fb = np.ctypeslib.as_array(self.lib.vdp1_fb(), shape=(FB_LINES, FB_WIDTH))
        self.costs = costs or CALIBRATED
        self.tvmr, self.fbcr = tvmr, fbcr

    def load_vram(self, data):
        """data: VDP1 VRAM as the Saturn sees it (big-endian bytes, up to 512 KB)."""
        words = np.frombuffer(data, dtype='>u2')
        self.vram[:len(words)] = words

    def load_fb(self, data):
        self.fb.reshape(-1)[:] = np.frombuffer(data, dtype='>u2')

    def plot(self, log_max=0):
        """Runs the command list from address 0. Returns the totals and, with
        log_max, a CommandCost a command (cycles are VDP1 cycles)."""
        c = self.costs
        self.lib.vdp1_reset(self.tvmr, self.fbcr, c['texel'], c['tex_pixel'], c['gouraud'], c['pixel'], c['line'])
        totals = PlotTotals()
        log = (CommandCost * max(log_max, 1))()
        n = self.lib.vdp1_plot(ctypes.byref(totals), log, log_max)
        return totals, [log[i] for i in range(min(n, log_max))]


    def reset(self):
        """Ready for step: the clip and local coordinates cleared, as a plot begins."""
        c = self.costs
        self.lib.vdp1_reset(self.tvmr, self.fbcr, c['texel'], c['tex_pixel'], c['gouraud'], c['pixel'], c['line'])

    def step(self, addr, ret_addr):
        """One command at addr (VRAM words): (the next's address or -1, its cost). ret_addr: a c_int32 the
        list's return address stays in, -1 for none."""
        cost = CommandCost()
        step = self.lib.vdp1_step
        step.restype = ctypes.c_int32
        return step(ctypes.c_int32(addr), ctypes.byref(ret_addr), ctypes.byref(cost)), cost


def rgb(fb, width=352, height=224):
    """A 16bpp frame buffer's RGB (MSB-on pixels, 15-bit BGR) as an 8-bit
    height x width x 3 array; palette-format pixels (MSB off) show black."""
    p = fb[:height, :width].astype(np.uint32)
    out = np.zeros((height, width, 3), np.uint8)
    on = (p & 0x8000) != 0
    for ch, shift in enumerate((0, 5, 10)):
        v = (p >> shift) & 31
        out[..., ch] = np.where(on, (v << 3) | (v >> 2), 0)
    return out
