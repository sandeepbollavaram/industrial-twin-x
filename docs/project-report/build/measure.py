import glob, sys
import fitz
# Text width 6.27 in, usable height about 8 in on A4 with 1 in margins; 15 px font at render scale 2.
for f in sorted(glob.glob(sys.argv[1] + "/*.png")):
    p = fitz.Pixmap(f)
    w, h = p.width / 2, p.height / 2
    scale = min(6.27 * 96 / w, 8.0 * 96 / h, 1.0)
    print(f"{f.split('/')[-1].split(chr(92))[-1]:32s} natural {w:5.0f}x{h:<5.0f} -> font {15 * scale * 0.75:4.1f} pt")
