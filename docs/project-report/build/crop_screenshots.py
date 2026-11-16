"""Crop dashboard screenshots to their content and save them as report figures.

Usage: python crop_screenshots.py <screenshot-dir>  (needs PyMuPDF)
Screenshots were captured from the running application (light theme) on 2026-11-16.
"""

import sys
from pathlib import Path

import fitz

OUT = Path(__file__).resolve().parents[1] / "figures"
SHOTS = {
    "screenshot-1794838741510-3.jpg": "screen-overview.png",
    "screenshot-1794838780796-6.jpg": "screen-factory3d.png",
    "screenshot-1794838780797-7.jpg": "screen-telemetry.png",
    "screenshot-1794838780798-8.jpg": "screen-ai.png",
    "screenshot-1794838780798-9.jpg": "screen-maintenance.png",
    "screenshot-1794838780798-10.jpg": "screen-network.png",
    "screenshot-1794838741512-5.jpg": "screen-security.png",
    "screenshot-1794838741511-4.jpg": "screen-recovery.png",
}
BACKGROUND = (244, 244, 242)


def content_box(pix: fitz.Pixmap) -> fitz.IRect:
    w, h, n = pix.width, pix.height, pix.n
    data = pix.samples

    def differs(x: int, y: int) -> bool:
        i = (y * w + x) * n
        return any(abs(data[i + c] - BACKGROUND[c]) > 14 for c in range(3))

    xs, ys = [], []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if differs(x, y):
                xs.append(x)
                ys.append(y)
    pad = 6
    return fitz.IRect(max(min(xs) - pad, 0), max(min(ys) - pad, 0), min(max(xs) + pad, w), min(max(ys) + pad, h))


def main() -> None:
    src = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, target in SHOTS.items():
        pix = fitz.Pixmap(str(src / name))
        if pix.alpha:
            pix = fitz.Pixmap(pix, 0)
        box = content_box(pix)
        doc = fitz.open()
        page = doc.new_page(width=pix.width, height=pix.height)
        page.insert_image(page.rect, pixmap=pix)
        page.get_pixmap(clip=fitz.Rect(box), dpi=144).save(str(OUT / target))
        print(target, box.width, "x", box.height)


if __name__ == "__main__":
    main()
