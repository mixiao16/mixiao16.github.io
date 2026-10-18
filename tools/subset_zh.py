#!/usr/bin/env python3
"""Build a small Noto Serif SC web font that contains only the characters this site uses.

    python3 tools/subset_zh.py --src <path to @fontsource/noto-serif-sc>

Reads the built pages (*.html), CSS and JS, collects every character, then merges the needed
glyphs from the font's unicode-range slices into  assets/fonts/noto-serif-sc-{300,400}.woff2
Re-run it whenever new Chinese text is added (it is quick).
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.merge import Merger
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent


def needed_chars():
    chars = set()
    files = list(ROOT.glob('*.html')) + list(ROOT.glob('*/index.html')) + list(ROOT.glob('works/*/index.html'))
    files += [ROOT / 'tools/src/js/main.js'] + list((ROOT / 'tools/src/css').glob('*.css'))
    files += [ROOT / 'data/works.json']
    for f in files:
        if f.exists():
            chars |= set(f.read_text(encoding='utf-8'))
    # base: ASCII, CJK + full-width punctuation we may use
    chars |= {chr(c) for c in range(0x20, 0x7F)}
    chars |= set('，。、；：？！“”‘’（）《》〈〉「」『』—…·～→←↗↓×')
    keep = {c for c in chars if ord(c) >= 0x20 and not (0x2500 <= ord(c) <= 0x25FF)}
    return keep


def build(src, weight, chars, out):
    files = sorted((src / 'files').glob('noto-serif-sc-*-%d-normal.woff' % weight))
    parts = []
    covered = set()
    for f in files:
        font = TTFont(f)
        cmap = font.getBestCmap()
        want = {ord(c) for c in chars if ord(c) in cmap and ord(c) not in covered}
        if not want:
            continue
        opts = subset.Options()
        opts.layout_features = []
        opts.name_IDs = [1, 2]
        opts.notdef_outline = True
        opts.glyph_names = False
        opts.hinting = False
        opts.desubroutinize = True
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=sorted(want))
        sub.subset(font)
        buf = io.BytesIO()
        font.flavor = None
        font.save(buf)
        buf.seek(0)
        parts.append(buf)
        covered |= want
    missing = sorted(c for c in chars if ord(c) not in covered and ord(c) > 0x7F)
    merger = Merger()
    merged = merger.merge(parts) if len(parts) > 1 else TTFont(parts[0])
    merged.flavor = 'woff2'
    merged.save(out)
    return len(parts), len(covered), missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    a = ap.parse_args()
    chars = needed_chars()
    cjk = [c for c in chars if ord(c) > 0x2E80]
    print('characters:', len(chars), '(CJK-ish: %d)' % len(cjk))
    for wgt in (300, 400):
        out = ROOT / ('assets/fonts/noto-serif-sc-%d.woff2' % wgt)
        n, cov, missing = build(Path(a.src), wgt, chars, out)
        print(wgt, 'slices used', n, 'glyphs', cov, '->', out.name, round(out.stat().st_size / 1024), 'KB',
              'missing:', ''.join(missing)[:60])


if __name__ == '__main__':
    main()
