"""Generate the Photo Addendum app icons (navy tile, white house with a camera lens).
Usage: python3 make_icons.py <output_dir>"""
import sys, os
from PIL import Image, ImageDraw

NAVY = (29, 58, 95)
WHITE = (255, 255, 255)
AMBER = (232, 176, 75)


def draw_icon(size, pad_frac=0.0):
    S = 1024
    img = Image.new('RGB', (S, S), NAVY)
    d = ImageDraw.Draw(img)
    # inner area (maskable icons need a safe zone)
    p = int(S * pad_frac)
    box = (p, p, S - p, S - p)
    bw = box[2] - box[0]
    def X(f): return int(box[0] + f * bw)
    def Y(f): return int(box[1] + f * bw)
    lw = max(6, int(bw * 0.055))
    # house: roof + body
    roof = [(X(0.18), Y(0.47)), (X(0.50), Y(0.20)), (X(0.82), Y(0.47))]
    d.line(roof, fill=WHITE, width=lw, joint='curve')
    for (cx, cy) in (roof[0], roof[2], roof[1]):
        d.ellipse([cx - lw // 2, cy - lw // 2, cx + lw // 2, cy + lw // 2], fill=WHITE)
    d.rounded_rectangle([X(0.26), Y(0.44), X(0.74), Y(0.80)], radius=int(bw * 0.05), outline=WHITE, width=lw)
    # camera lens in the middle of the house
    cx, cy, r = X(0.50), Y(0.615), int(bw * 0.11)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=WHITE, width=lw)
    r2 = int(r * 0.42)
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=AMBER)
    return img.resize((size, size), Image.LANCZOS)


def main(out):
    os.makedirs(out, exist_ok=True)
    draw_icon(180).save(os.path.join(out, 'icon-180.png'), optimize=True)
    draw_icon(192).save(os.path.join(out, 'icon-192.png'), optimize=True)
    draw_icon(512).save(os.path.join(out, 'icon-512.png'), optimize=True)
    draw_icon(512, pad_frac=0.12).save(os.path.join(out, 'icon-maskable-512.png'), optimize=True)
    print('icons written to', out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
