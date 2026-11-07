"""Step through a video, or a folder of screenshots, one frame at a time in the browser.

usage: framestep.py video VIDEO --name NAME [--start M:SS] [--end M:SS]
       framestep.py frames DIR --name NAME [--fps N] [--first N]
Writes build/framestep/NAME/index.html with the frames beside it and opens it.

video: a capture-card recording (1920x1080, the Saturn's 4:3 picture in the middle) from
--start to --end; every frame the video holds, cropped to the picture, labelled with its
frame number from --start and its time in the video. frames: a folder of PNGs in name
order (screenshots of consecutive emulator frames, say), labelled from --first.

On the page: left / right one frame, shift for ten, home / end, space plays at the
chosen speed, M marks the frame (the marks list can be copied), Z toggles 2x zoom.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Frame step: __NAME__</title>
<style>
:root { --bg: #15171c; --fg: #e8eaf0; --dim: #9aa0ad; --accent: #ffcc33; }
body { background: var(--bg); color: var(--fg); font: 15px system-ui, sans-serif; margin: 0; }
header { padding: 10px 16px; display: flex; gap: 18px; align-items: baseline; flex-wrap: wrap; }
h1 { font-size: 17px; margin: 0; }
#label { font: 600 22px ui-monospace, monospace; color: var(--accent); }
#time { font: 15px ui-monospace, monospace; color: var(--dim); }
main { display: flex; gap: 16px; padding: 0 16px 16px; align-items: flex-start; }
#view { flex: 1; min-width: 0; overflow: auto; }
#img { width: 70%; image-rendering: pixelated; display: block; background: #000; }
#view.zoom #img { width: 140%; }
aside { width: 230px; flex: none; }
input[type=range] { width: 100%; }
button { background: #2a2e38; color: var(--fg); border: 1px solid #3a3f4c; border-radius: 4px; padding: 4px 9px; cursor: pointer; }
#marks { width: 100%; height: 240px; background: #0e1014; color: var(--fg); border: 1px solid #3a3f4c; font: 13px ui-monospace, monospace; }
.keys { color: var(--dim); font-size: 13px; line-height: 1.6; }
</style></head><body>
<header><h1>__NAME__</h1><span id="label"></span><span id="time"></span></header>
<main>
<div id="view"><img id="img" alt="frame"></div>
<aside>
<input id="slider" type="range" min="0" value="0">
<p><button id="prev10">&laquo;10</button> <button id="prev">&lsaquo;</button> <button id="play">play</button>
<button id="next">&rsaquo;</button> <button id="next10">10&raquo;</button></p>
<p>speed <select id="speed"><option value="1">1x</option><option value="0.25">1/4</option><option value="0.1">1/10</option></select>
<button id="zoom">zoom</button></p>
<p><button id="mark">mark (M)</button></p>
<textarea id="marks" placeholder="marked frames appear here: add a note after each"></textarea>
<p class="keys">&larr; &rarr; one frame, shift: ten<br>Home / End, space: play<br>M: mark, Z: zoom</p>
</aside></main>
<script>
const F = __FRAMES__;
let i = 0, timer = null;
const img = document.getElementById('img'), slider = document.getElementById('slider');
slider.max = F.length - 1;
const cache = new Map();
function preload(k) { if (k >= 0 && k < F.length && !cache.has(k)) { const p = new Image(); p.src = F[k].src; cache.set(k, p); } }
function show(k) {
  i = Math.max(0, Math.min(F.length - 1, k));
  img.src = F[i].src; slider.value = i;
  document.getElementById('label').textContent = 'frame ' + F[i].n;
  document.getElementById('time').textContent = F[i].t;
  for (let d = 1; d < 12; d++) { preload(i + d); preload(i - d); }
}
function step(d) { stop(); show(i + d); }
function stop() { if (timer) { clearInterval(timer); timer = null; document.getElementById('play').textContent = 'play'; } }
function play() {
  if (timer) return stop();
  const rate = __FPS__ * parseFloat(document.getElementById('speed').value);
  timer = setInterval(() => { if (i >= F.length - 1) return stop(); show(i + 1); }, 1000 / rate);
  document.getElementById('play').textContent = 'pause';
}
function mark() { const m = document.getElementById('marks'); m.value += 'frame ' + F[i].n + '  ' + F[i].t + '  \n'; }
document.getElementById('prev').onclick = () => step(-1);
document.getElementById('next').onclick = () => step(1);
document.getElementById('prev10').onclick = () => step(-10);
document.getElementById('next10').onclick = () => step(10);
document.getElementById('play').onclick = play;
document.getElementById('mark').onclick = mark;
document.getElementById('zoom').onclick = () => document.getElementById('view').classList.toggle('zoom');
slider.oninput = () => { stop(); show(parseInt(slider.value)); };
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'TEXTAREA') return;
  const n = e.shiftKey ? 10 : 1;
  if (e.key === 'ArrowRight') { step(n); e.preventDefault(); }
  else if (e.key === 'ArrowLeft') { step(-n); e.preventDefault(); }
  else if (e.key === 'Home') step(-F.length);
  else if (e.key === 'End') step(F.length);
  else if (e.key === ' ') { play(); e.preventDefault(); }
  else if (e.key === 'm' || e.key === 'M') mark();
  else if (e.key === 'z' || e.key === 'Z') document.getElementById('view').classList.toggle('zoom');
});
show(0);
</script></body></html>
"""


def seconds(text):
    parts = [float(p) for p in text.split(':')]
    return sum(p * 60 ** k for k, p in enumerate(reversed(parts)))


def clock(t):
    return f'{int(t // 60)}:{t % 60:06.3f}'


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def frame_rate(video):
    out = subprocess.run([ffmpeg(), '-hide_banner', '-i', video], capture_output=True, text=True).stderr
    for token in out.split(','):
        if token.strip().endswith(' fps'):
            return float(token.split()[0])
    sys.exit(f'no frame rate found in {video}')


def from_video(args, out):
    fps = frame_rate(args.source)
    start = seconds(args.start) if args.start else 0.0
    cmd = [ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-ss', f'{start:.3f}', '-i', args.source]
    if args.end:
        cmd += ['-t', f'{seconds(args.end) - start:.3f}']
    # the capture box puts the Saturn's 4:3 picture in the middle of a 16:9 frame
    cmd += ['-vf', 'crop=ih*4/3:ih', '-q:v', '3', os.path.join(out, 'f%05d.jpg')]
    subprocess.run(cmd, check=True)
    files = sorted(glob.glob(os.path.join(out, 'f*.jpg')))
    return fps, [{'src': os.path.basename(f), 'n': k, 't': f'video {clock(start + k / fps)}'}
                 for k, f in enumerate(files)]


def from_frames(args, out):
    frames = []
    for k, f in enumerate(sorted(glob.glob(os.path.join(args.source, '*.png')))):
        name = f'f{k:05d}.png'
        with Image.open(f) as im:
            im.save(os.path.join(out, name))
        frames.append({'src': name, 'n': args.first + k, 't': os.path.basename(f)})
    return args.fps, frames


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('kind', choices=['video', 'frames'])
    ap.add_argument('source')
    ap.add_argument('--name', required=True)
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--fps', type=float, default=60)
    ap.add_argument('--first', type=int, default=0)
    ap.add_argument('--no-open', action='store_true')
    args = ap.parse_args()
    out = os.path.join(ROOT, 'build', 'framestep', args.name)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    fps, frames = (from_video if args.kind == 'video' else from_frames)(args, out)
    page = PAGE.replace('__NAME__', args.name).replace('__FRAMES__', json.dumps(frames)).replace('__FPS__', str(fps))
    path = os.path.join(out, 'index.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(page)
    print(f'{path}: {len(frames)} frames')
    if not args.no_open:
        os.startfile(path)


main()
