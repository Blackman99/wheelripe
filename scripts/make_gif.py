#!/usr/bin/env python3
"""Render site/demo.gif from REAL wheelripe output (captured files), in the site palette."""
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
for cand in ["/usr/share/fonts/truetype/sand-box/google/Reddit Mono/RedditMono-VariableFont_wght.ttf"]:
    try:
        ImageFont.truetype(cand, 10)
        MONO = cand
    except OSError:
        pass

INK, PASTE, ORANGE, VEIN, MUTED, RIND = "#2a160b", "#ffd978", "#e8742a", "#8cc2d4", "#b9906d", "#a8471a"
W, PAD, FS, LH = 1180, 34, 17, 26
font = ImageFont.truetype(MONO, FS)
bold = ImageFont.truetype(MONO, FS)
try:
    bold.set_variation_by_axes([700])
except Exception:
    pass


def run(cmd):
    env = {"NO_COLOR": "1", "PATH": "/usr/bin:/bin"}
    p = subprocess.run([sys.executable, "-m", "wheelripe", *cmd], capture_output=True, text=True,
                       env={**__import__("os").environ, **env})
    return p.stdout.rstrip("\n").split("\n")


def color_for(line):
    if line.startswith("BLOCKED") or line.startswith("NOT RIPE"):
        return ORANGE
    if line.startswith("BUMP"):
        return VEIN
    if line.startswith("READY") or line.startswith("RIPE"):
        return PASTE
    if line.startswith("wheelripe"):
        return PASTE
    return MUTED


SESSIONS = [
    (["examples/requirements-blocked.txt"], "wheelripe examples/requirements-blocked.txt"),
    (["examples/requirements-ripe.txt"], "wheelripe examples/requirements-ripe.txt"),
]
H = PAD * 2 + LH * 13


def frame(lines, cursor=False):
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 6], fill=RIND)
    y = PAD
    for text, col in lines:
        if text.startswith("$ "):
            d.text((PAD, y), "$", font=font, fill=ORANGE)
            d.text((PAD + 20, y), text[2:], font=font, fill=PASTE)
        else:
            head = text[:9]
            if head.strip() in ("BLOCKED", "BUMP", "READY"):
                d.text((PAD, y), head, font=bold, fill=col)
                d.text((PAD + font.getlength(head), y), text[9:], font=font,
                       fill=PASTE if not text.strip().startswith("upstream") else MUTED)
            elif text.lstrip().startswith("tracking: "):
                lead = text[:len(text) - len(text.lstrip())] + "tracking: "
                d.text((PAD, y), lead, font=font, fill=VEIN)
                d.text((PAD + font.getlength(lead), y), text[len(lead):], font=font, fill=PASTE)
            else:
                d.text((PAD, y), text, font=font, fill=col)
        y += LH
    if cursor:
        last = lines[-1][0] if lines else "$ "
        x = PAD + 20 + font.getlength(last[2:]) + 2
        d.rectangle([x, y - LH + 4, x + 10, y - 4], fill=ORANGE)
    return im


frames, durations = [], []
for args, cmd in SESSIONS:
    out = run(args)
    shown = []
    for i in range(0, len(cmd) + 1, 3):
        frames.append(frame(shown + [("$ " + cmd[:i], PASTE)], cursor=True))
        durations.append(45)
    shown.append(("$ " + cmd, PASTE))
    frames.append(frame(shown))
    durations.append(500)
    for line in out:
        line = line if len(line) <= 104 else line[:101] + "…"
        shown.append((line, color_for(line)))
        frames.append(frame(shown))
        durations.append(160 if line.strip() else 60)
    durations[-1] = 2600
frames = [f.convert("P", palette=Image.ADAPTIVE, colors=32) for f in frames]
frames[0].save(sys.argv[1] if len(sys.argv) > 1 else "site/demo.gif", save_all=True, append_images=frames[1:],
               duration=durations, loop=0, optimize=True, disposal=1)
print(len(frames), "frames")
