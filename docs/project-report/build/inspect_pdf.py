"""Render PDF contact sheets and report structure for visual QA.

Usage: python inspect_pdf.py <pdf> <outdir>
"""

import re
import sys
from pathlib import Path

import fitz

pdf = fitz.open(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
print("pages:", pdf.page_count)

starts = {}
for i, page in enumerate(pdf):
    text = page.get_text()
    for line in text.splitlines()[:6]:
        m = re.match(r"^(Chapter \d+: .*|References|Appendix [A-I]: .*|Abstract|Table of Contents|List of (Figures|Tables|Abbreviations))$", line.strip())
        if m and m.group(1) not in starts:
            starts[m.group(1)] = i + 1
    if len(text.strip()) < 40:
        print("nearly empty page:", i + 1, repr(text.strip()[:40]))
for name, page_no in starts.items():
    print(f"{page_no:4d}  {name}")

cols, rows = 4, 3
per = cols * rows
for sheet in range((pdf.page_count + per - 1) // per):
    w, h = 595 * 0.32, 842 * 0.32
    doc = fitz.open()
    canvas = doc.new_page(width=w * cols + 10 * (cols + 1), height=h * rows + 10 * (rows + 1))
    for k in range(per):
        idx = sheet * per + k
        if idx >= pdf.page_count:
            break
        r, c = divmod(k, cols)
        rect = fitz.Rect(10 + c * (w + 10), 10 + r * (h + 10), 10 + c * (w + 10) + w, 10 + r * (h + 10) + h)
        canvas.show_pdf_page(rect, pdf, idx)
        canvas.draw_rect(rect, color=(0.6, 0.6, 0.6), width=0.5)
        canvas.insert_text((rect.x0 + 2, rect.y1 - 2), str(idx + 1), fontsize=7, color=(1, 0, 0))
    canvas.get_pixmap(dpi=110).save(str(out / f"sheet-{sheet + 1:02d}.png"))
print("sheets written to", out)
