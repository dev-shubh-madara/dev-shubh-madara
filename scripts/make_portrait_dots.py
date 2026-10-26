#!/usr/bin/env python3
"""Turn a portrait photo into dot-matrix data for the HUD card.

One-off helper (needs opencv-python, numpy). The Action does NOT run this; it only reads the
resulting assets/portrait-dots.json. Only the dots are stored, never the original photo.

  python3 scripts/make_portrait_dots.py photo.jpg
  python3 scripts/make_portrait_dots.py photo.jpg --cx 0.48 --cy 0.42 --r 0.31   # re-centre / zoom

--cx/--cy/--r are the circle centre and radius as fractions of the image width/height.
"""
from __future__ import annotations

import argparse
import colorsys
import json
from pathlib import Path

import cv2
import numpy as np

N = 25  # dots from the centre to the rim (pitch = radius / N)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--cx", type=float, default=0.478)
    ap.add_argument("--cy", type=float, default=0.423)
    ap.add_argument("--r", type=float, default=0.307)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "assets" / "portrait-dots.json"))
    a = ap.parse_args()

    img = cv2.imread(a.photo)
    if img is None:
        raise SystemExit(f"cannot read {a.photo}")
    s = 700 / img.shape[1]
    sm = cv2.resize(img, (700, int(img.shape[0] * s)), interpolation=cv2.INTER_AREA)
    H, W = sm.shape[:2]

    # foreground cut-out (GrabCut from a loose rectangle)
    mask = np.zeros((H, W), np.uint8)
    rect = (5, int(H * 0.16), W - 10, H - int(H * 0.16) - 5)
    cv2.grabCut(sm, mask, rect, np.zeros((1, 65)), np.zeros((1, 65)), 8, cv2.GC_INIT_WITH_RECT)
    fg = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    fg = cv2.GaussianBlur(fg, (7, 7), 0)

    cx, cy, rad = a.cx * W, a.cy * H, a.r * W
    rgb = cv2.cvtColor(sm, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    pitch = rad / N

    fg_dots, bg_dots = [], []
    for j in range(-N, N + 1):
        for i in range(-N, N + 1):
            if i * i + j * j > N * N:
                continue
            x, y = cx + i * pitch, cy + j * pitch
            x0, y0 = int(max(0, min(W - 1, x))), int(max(0, min(H - 1, y)))
            if fg[y0, x0] < 128:
                bg_dots.append([i, j])
                continue
            # average colour over the dot's cell
            r = max(1, int(pitch / 2))
            patch = rgb[max(0, y0 - r): y0 + r + 1, max(0, x0 - r): x0 + r + 1].reshape(-1, 3).mean(0)
            h, l, sat = colorsys.rgb_to_hls(*patch)
            sat = min(1.0, sat * 1.15)
            l = 0.12 + 0.88 * (l ** 0.95)          # gentle lift so dark hair / shirt stay visible without washing out skin
            col = colorsys.hls_to_rgb(h, min(0.92, l), sat)
            size = int(round(100 * (0.28 + 0.72 * l)))
            fg_dots.append([i, j, size, "%02x%02x%02x" % tuple(int(c * 255) for c in col)])

    out = {"n": N, "fg": fg_dots, "bg": bg_dots}
    Path(a.out).write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{len(fg_dots)} portrait dots, {len(bg_dots)} background dots -> {a.out}")


if __name__ == "__main__":
    main()
