"""Background veins — faint rock texture recomposed for every page.

Two photographs of scholar's stones (tools/src/veins/rock-*.png) are turned
into a single "vein map": the crevices and surface striations of the stone,
with the white backdrop removed.  For each page a seeded random arrangement of
fragments of that map is laid out, feathered, and written as a transparent
WebP (black ink + alpha).  CSS shows it on a fixed layer at low opacity, so
every page carries the same stone, broken up and reassembled differently.

    python3 tools/make_veins.py            # (re)build all known pages
Called from build.py with the list of page keys; existing files are kept
unless the source photos or the recipe version change.
"""
import hashlib
import random
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'tools' / 'src' / 'veins'
OUT = ROOT / 'assets' / 'img' / 'veins'
W, H = 1280, 800           # landscape canvas, shown with background-size:cover
RECIPE = 'v3'
KEEP_ROWS = {'rock-2.png': 0.86}
# areas kept clear per page (cx, cy, rx, ry as fractions) — e.g. behind the home hero stone
QUIET = {'home': [(0.70, 0.52, 0.27, 0.50)]}

_maps = None


def _vein_map(path):
    g = np.asarray(Image.open(path).convert('L'), dtype=np.float32) / 255.0
    # stone vs. white backdrop: dark-ish pixels, closed and softened
    mask = g < 0.86
    mask = ndi.binary_opening(mask, iterations=2)
    mask = ndi.binary_closing(mask, iterations=6)
    mask = ndi.binary_fill_holes(mask)
    lab, n = ndi.label(mask)
    if n > 1:                                   # keep the stone, drop wall shadows
        sizes = ndi.sum(mask, lab, range(1, n + 1))
        mask = np.isin(lab, 1 + np.flatnonzero(sizes >= sizes.max() * 0.15))
    mask = ndi.binary_erosion(mask, iterations=3)
    m = ndi.gaussian_filter(mask.astype(np.float32), 10)
    # surface detail: local darkness relative to its neighbourhood
    fine = ndi.gaussian_filter(g, 1.0) - ndi.gaussian_filter(g, 9)
    mid = ndi.gaussian_filter(g, 3) - ndi.gaussian_filter(g, 28)
    dark = np.clip(-fine * 2.6, 0, 1) * 0.55 + np.clip(-mid * 1.3, 0, 1) * 0.45
    tone = np.clip(1.0 - g, 0, 1) * 0.30          # a whisper of the body itself
    v = np.clip(dark + tone, 0, 1) ** 1.15 * m
    return v


def maps():
    global _maps
    if _maps is None:
        _maps = []
        for p in sorted(SRC.glob('rock-*.png')):
            v = _vein_map(p)
            keep = KEEP_ROWS.get(p.name)
            if keep:                                 # e.g. cut the wooden stand off
                v = v[:int(v.shape[0] * keep)]
            _maps.append(v)
    return _maps


def _src_hash():
    h = hashlib.sha1(RECIPE.encode())
    for p in sorted(SRC.glob('rock-*.png')):
        h.update(p.read_bytes())
    return h.hexdigest()[:8]


def _feather(h, w, rng):
    """soft, slightly irregular oval falloff so fragments melt into paper"""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cy, cx = h / 2, w / 2
    r = np.sqrt(((yy - cy) / (h / 2)) ** 2 + ((xx - cx) / (w / 2)) ** 2)
    noise = ndi.gaussian_filter(rng.standard_normal((h, w)).astype(np.float32), min(h, w) / 9)
    noise /= (np.abs(noise).max() + 1e-6)
    r = r + noise * 0.22
    return np.clip((1.0 - r) / 0.55, 0, 1) ** 1.6


def compose(key):
    seed = int(hashlib.sha1(('veins:' + key).encode()).hexdigest()[:12], 16)
    rnd = random.Random(seed)
    rng = np.random.default_rng(seed)
    canvas = np.zeros((H, W), np.float32)
    srcs = maps()
    # anchors favour the edges and corners so reading columns stay quiet
    anchors = [(0.08, 0.15), (0.92, 0.12), (0.95, 0.85), (0.06, 0.88),
               (0.50, 0.04), (0.55, 0.97), (0.98, 0.48), (0.02, 0.5)]
    rnd.shuffle(anchors)
    n = rnd.randint(4, 6)
    for ax, ay in anchors[:n]:
        src = srcs[rnd.randrange(len(srcs))]
        sh, sw = src.shape
        # pick a fragment that actually contains stone
        for _ in range(30):
            ch = rnd.randint(int(sh * .22), int(sh * .5))
            cw = rnd.randint(int(sw * .25), int(sw * .6))
            y0 = rnd.randint(0, sh - ch)
            x0 = rnd.randint(0, sw - cw)
            frag = src[y0:y0 + ch, x0:x0 + cw]
            if frag.mean() > 0.10:
                break
        frag = frag * _feather(frag.shape[0], frag.shape[1], rng)
        img = Image.fromarray((frag * 255).astype(np.uint8))
        if rnd.random() < .5:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if rnd.random() < .35:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        img = img.rotate(rnd.choice([0, 90, 180, 270]) + rnd.uniform(-18, 18),
                         resample=Image.BICUBIC, expand=True)
        s = rnd.uniform(0.9, 1.7)
        img = img.resize((max(8, int(img.width * s)), max(8, int(img.height * s))), Image.BICUBIC)
        f = np.asarray(img, np.float32) / 255.0
        fh, fw = f.shape
        f = f * rnd.uniform(.6, 1.0)
        cx = int(ax * W + rnd.uniform(-.06, .06) * W)
        cy = int(ay * H + rnd.uniform(-.08, .08) * H)
        x0, y0 = cx - fw // 2, cy - fh // 2
        xa, ya = max(0, x0), max(0, y0)
        xb, yb = min(W, x0 + fw), min(H, y0 + fh)
        if xb <= xa or yb <= ya:
            continue
        region = f[ya - y0:yb - y0, xa - x0:xb - x0]
        canvas[ya:yb, xa:xb] = 1 - (1 - canvas[ya:yb, xa:xb]) * (1 - region)   # screen-style union
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    for qx, qy, rx, ry in QUIET.get(key, []):
        d = np.sqrt(((xx / W - qx) / rx) ** 2 + ((yy / H - qy) / ry) ** 2)
        canvas *= np.clip((d - 0.75) / 0.45, 0, 1)
    canvas = ndi.gaussian_filter(canvas, 0.6)
    a = (np.clip(canvas, 0, 1) * 255).astype(np.uint8)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 3] = a
    return Image.fromarray(rgba, 'RGBA')


def build(keys, force=False):
    """make assets/img/veins/<key>.webp for each key; returns {key: url-suffix}"""
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = _src_hash()
    stamp_file = OUT / '.stamp'
    fresh = force or not stamp_file.exists() or stamp_file.read_text().strip() != stamp
    made = 0
    for k in keys:
        p = OUT / ('%s.webp' % k)
        if fresh or not p.exists():
            compose(k).save(p, 'WEBP', quality=48, method=4)
            made += 1
    stamp_file.write_text(stamp)
    return made


def key_for(path):
    k = path.strip('/').replace('/', '-').replace('.html', '')
    return k or 'home'


if __name__ == '__main__':
    import sys
    keys = sys.argv[1:] or ['home', 'about', 'contact', '404']
    print('veins:', build(keys, force=True), 'made')
