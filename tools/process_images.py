#!/usr/bin/env python3
"""Turn the original artwork files into web-ready responsive WebP images.

Usage:  python3 tools/process_images.py --art /path/to/art --site /path/to/site
Reads   data/works.json
Writes  assets/img/<slug>/<id>-<width>.webp  and  data/images.json (sizes, colours, blur-up previews)
"""
import argparse, base64, io, json, os, re, sys
from concurrent.futures import ProcessPoolExecutor
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None
SIZES_PLATE = [480, 1000, 1800, 2600]
SIZES_PROCESS = [480, 1000, 1800]


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def widths_for(src_w, cands):
    ws = [w for w in cands if w <= src_w]
    if not ws:
        ws = [src_w]
    elif src_w > ws[-1] * 1.12 and src_w <= cands[-1]:
        ws.append(src_w)
    return ws


def resolve(art, src):
    """Find the file even if the extension case (.jpg / .JPG) differs."""
    p = os.path.join(art, src)
    if os.path.exists(p):
        return p
    d, f = os.path.split(p)
    for x in os.listdir(d):
        if x.lower() == f.lower():
            return os.path.join(d, x)
    raise FileNotFoundError(p)


def process(job):
    art, site, slug, iid, src, role, zoom = job
    path = resolve(art, src)
    out_dir = os.path.join(site, 'assets', 'img', slug)
    os.makedirs(out_dir, exist_ok=True)
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert('RGB')
    W, H = im.size
    cands = SIZES_PROCESS if role == 'process' else SIZES_PLATE
    ws = widths_for(W, cands)
    files = {}
    for w in ws:
        h = round(H * w / W)
        r = im if w == W else im.resize((w, h), Image.LANCZOS)
        q = 84 if (zoom and w >= 1800) else 80
        out = os.path.join(out_dir, f'{iid}-{w}.webp')
        r.save(out, 'WEBP', quality=q, method=6)
        files[w] = os.path.getsize(out)
    # blur-up preview + average colour
    tiny = im.resize((20, max(1, round(20 * H / W))), Image.LANCZOS)
    buf = io.BytesIO()
    tiny.save(buf, 'WEBP', quality=35, method=6)
    lqip = 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode()
    avg = im.resize((1, 1), Image.LANCZOS).getpixel((0, 0))
    return src, {'id': iid, 'slug': slug, 'w': W, 'h': H, 'widths': ws,
                 'color': '#%02x%02x%02x' % avg, 'lqip': lqip, 'bytes': sum(files.values())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--art', required=True)
    ap.add_argument('--site', default='.')
    ap.add_argument('--force', action='store_true', help='re-process everything')
    a = ap.parse_args()
    data = json.load(open(os.path.join(a.site, 'data', 'works.json')))
    jobs, seen = [], set()
    old = {}
    mp = os.path.join(a.site, 'data', 'images.json')
    if os.path.exists(mp) and not a.force:
        old = json.load(open(mp))
    for k, ex in data.get('extras', {}).items():
        if ex['src'] not in seen:
            seen.add(ex['src'])
            jobs.append((a.art, a.site, 'site', k, ex['src'], ex.get('role', 'plate'), True))
    for w in data['works']:
        for group in ('images', 'process'):
            for i, im in enumerate(w.get(group, [])):
                if im['src'] in seen:
                    continue
                seen.add(im['src'])
                if im['src'] in old:
                    continue
                iid = f"{'p' if group == 'process' else 'i'}{i + 1:02d}"
                # shared files keep the id of their first use
                jobs.append((a.art, a.site, w['slug'], iid, im['src'], im.get('role', 'plate'), im.get('zoom', False)))
    manifest = dict(old)
    jobs = [j for j in jobs if j[4] not in old]
    with ProcessPoolExecutor(2) as ex:
        for src, info in ex.map(process, jobs):
            manifest[src] = info
            print(f"{src}: {info['w']}x{info['h']} -> {info['widths']} {info['bytes']//1024}KB")
    json.dump(manifest, open(os.path.join(a.site, 'data', 'images.json'), 'w'), ensure_ascii=False)
    total = sum(m['bytes'] for m in manifest.values())
    print(f'TOTAL {total/1e6:.1f} MB for {len(manifest)} images')


if __name__ == '__main__':
    main()
