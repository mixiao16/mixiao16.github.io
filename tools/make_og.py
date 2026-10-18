#!/usr/bin/env python3
"""Make 1200x630 share images (Open Graph) for the home page and every work.

    python3 tools/make_og.py          (run before tools/build.py)

Writes assets/og/default.jpg and assets/og/<slug>.jpg
"""
import io
import json
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
PAPER, INK, MUTE, SEAL = (244, 244, 242), (20, 20, 20), (120, 120, 120), (200, 40, 28)
W, H = 1200, 630
CACHE = ROOT / 'tools/.fontcache'


def ttf(woff2):
    CACHE.mkdir(exist_ok=True)
    out = CACHE / (Path(woff2).stem + '.ttf')
    if not out.exists():
        f = TTFont(woff2)
        f.flavor = None
        f.save(out)
    return str(out)


F = ROOT / 'assets/fonts'
SERIF = ttf(F / 'cormorant-garamond-latin-300-normal.woff2')
ITAL = ttf(F / 'cormorant-garamond-latin-300-italic.woff2')
MONO = ttf(F / 'dm-mono-latin-400-normal.woff2')
ZH = ttf(F / 'noto-serif-sc-400.woff2')


def grain(img):
    import random
    random.seed(7)
    px = img.load()
    for _ in range(26000):
        x, y = random.randrange(W), random.randrange(H)
        r, g, b = px[x, y]
        d = random.randint(-9, 6)
        px[x, y] = (r + d, g + d, b + d)
    return img


def seal(base, x, y, s=64):
    """Paste the site seal 「張櫻瀚印」 (tools/src/seal-path.txt), rendered with cairosvg."""
    import cairosvg
    path = (ROOT / 'tools/src/seal-path.txt').read_text().strip()
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="%d" height="%d">'
           '<rect x="20" y="20" width="472" height="472" rx="24" fill="none" stroke="#C8281C" stroke-width="28"/>'
           '<path d="%s" fill="#C8281C" stroke="#C8281C" stroke-width="10" stroke-linejoin="round"/></svg>') % (s * 2, s * 2, path)
    im = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode()))).convert('RGBA').resize((s, s), Image.LANCZOS)
    base.paste(im, (x, y), im)


def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def shadowed(base, im, xy):
    sh = Image.new('RGBA', (im.width + 80, im.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([40, 52, 40 + im.width, 52 + im.height], fill=(0, 0, 0, 60))
    sh = sh.filter(ImageFilter.GaussianBlur(16))
    base.paste(sh, (xy[0] - 40, xy[1] - 40), sh)
    base.paste(im, xy)


def make(title, zh, img_path, out, home=False):
    base = Image.new('RGB', (W, H), PAPER)
    grain(base)
    d = ImageDraw.Draw(base)
    art = Image.open(img_path).convert('RGBA')
    if home:
        art.thumbnail((470, 560))
        x, y = 640 + (420 - art.width) // 2, (H - art.height) // 2
        base.paste(art, (x, y), art)
        art = None
    else:
        flat = Image.new('RGB', art.size, (255, 255, 255))
        flat.paste(art, mask=art.split()[3])
        art = flat
    if home:
        pass
    else:
        box_w, box_h = 560, 500
        art.thumbnail((box_w, box_h))
        x, y = 1200 - 70 - art.width, (H - art.height) // 2
        shadowed(base, art, (x, y))
    seal(base, 70, 64, 56)
    d = ImageDraw.Draw(base)
    d.text((140, 92), 'YINGHAN ZHANG', font=ImageFont.truetype(MONO, 20), fill=INK, anchor='lm')
    if home:
        f1 = ImageFont.truetype(SERIF, 150)
        f2 = ImageFont.truetype(ITAL, 150)
        d.text((70, 330), 'Yinghan', font=f1, fill=INK, anchor='ls')
        d.text((150, 470), 'Zhang', font=f2, fill=INK, anchor='ls')
        d.text((72, 560), 'STONE ARTIST. PRINTMAKER', font=ImageFont.truetype(MONO, 20), fill=MUTE, anchor='ls')
    else:
        size = 84
        font = ImageFont.truetype(ITAL, size)
        lines = wrap(d, title, font, 480)
        while len(lines) > 4 and size > 44:
            size -= 6
            font = ImageFont.truetype(ITAL, size)
            lines = wrap(d, title, font, 480)
        y0 = 250
        for ln in lines:
            d.text((70, y0), ln, font=font, fill=INK, anchor='ls')
            y0 += int(size * 1.02)
        d.text((72, y0 + 26), zh, font=ImageFont.truetype(ZH, 30), fill=MUTE, anchor='ls')
        d.text((72, 572), 'STONE ARTIST. PRINTMAKER', font=ImageFont.truetype(MONO, 17), fill=MUTE, anchor='ls')
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    base.save(out, 'JPEG', quality=86, optimize=True, progressive=True)


def main():
    data = json.loads((ROOT / 'data/works.json').read_text(encoding='utf-8'))
    im = json.loads((ROOT / 'data/images.json').read_text(encoding='utf-8'))
    make('', '', ROOT / 'assets/img/ui/stone-760.webp', ROOT / 'assets/og/default.jpg', home=True)
    for w in data['works']:
        c = im[w['images'][w.get('cover', 0)]['src']]
        ws = [x for x in c['widths'] if x >= 1000] or c['widths']
        p = ROOT / ('assets/img/%s/%s-%d.webp' % (c['slug'], c['id'], ws[0]))
        make(w['title'], w['title_zh'], p, ROOT / ('assets/og/%s.jpg' % w['slug']))
    print('og images done')


if __name__ == '__main__':
    main()
