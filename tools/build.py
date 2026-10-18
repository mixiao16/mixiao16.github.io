#!/usr/bin/env python3
"""Static site generator for yinghanart.com

    python3 tools/build.py

Reads   data/works.json  (works, text, site settings)  and  data/images.json  (made by process_images.py)
Writes  index.html, about/, contact/, works/<slug>/, 404.html, sitemap.xml, robots.txt, CNAME, .nojekyll
        assets/css/site.css, assets/js/main.js   (from tools/src/)

All paths are relative to the page depth, so the site works from any folder or sub-path.
"""
import hashlib
import html
import json
import re
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = json.loads((ROOT / 'data/works.json').read_text(encoding='utf-8'))
IM = json.loads((ROOT / 'data/images.json').read_text(encoding='utf-8'))
SITE, WORKS, EX = D['site'], D['works'], D['extras']
DOMAIN = SITE['domain'].rstrip('/')
YEAR = date.today().year
TODAY = date.today().isoformat()
N = len(WORKS)
esc = html.escape

# --------------------------------------------------------------------------- text
BIO_EN = [
    "Yinghan Zhang is a printmaker whose work focuses on the cultural and philosophical meaning of scholars' stones—natural rocks shaped by time and admired for their unique forms. Drawing on traditional Chinese aesthetics and Daoist philosophy, Zhang explores the connection between nature, human perception, and art.",
    "A key part of Zhang's practice is the ancient technique of full-shape rubbing, which they studied under a master artisan in Shandong. This method allows for a deep interaction with the texture of stone, capturing its qualities in a way that reflects both time and the meditative nature of stone appreciation. By combining rubbing with printmaking, woodcut, drawing, and collage, Zhang transforms stones into meditative landscapes, revealing their hidden essence.",
    "Zhang’s work invites viewers to reflect on themes of time, spirituality, and interconnectedness. Inspired by the Daoist idea that “a stone is the smallest mountain,” their art encourages a deeper exploration of even the smallest details, blending ancient traditions with modern techniques. Through their prints and mixed-media works, Zhang offers new perspectives on the world and human experience.",
]
BIO_ZH = [
    "张樱瀚是一位版画家,作品关注文人石的文化意涵与哲学意味——这些由时间塑造、因形态独特而被历代赏玩的天然奇石。创作植根于中国传统美学与道家思想,探索自然、人的感知与艺术之间的联系。",
    "全形拓是这套创作实践的重要一环。这门古老的技艺,张樱瀚曾在山东师从一位传统匠人。它让人得以与石头的肌理深度对话,将石之质地如实留存——既映照时间,也呼应赏石时的静观之意。通过把拓印与版画、木刻、绘画和拼贴结合起来,张樱瀚把石头化作静观的山水,显露其隐藏的本质。",
    "张樱瀚的作品邀请观者思考时间、精神性与万物相连。受道家“石为最小之山”这一观念的启发,其艺术鼓励人们去深究最微小的细节,让古老的传统与当代的手法相互交融。通过版画与综合媒介作品,艺术家为我们打开看待世界与人类经验的新视角。",
]
DESC_EN = ("Portfolio of Yinghan Zhang, a Seattle-based stone artist and printmaker working with full-shape rubbing, "
           "printmaking, woodcut, drawing and collage.")

# Silent Veins process: frames on the home page teaser and the work-page board
TEASER_FRAMES = [2, 3, 5, 7, 9, 10, 12, 14]   # home teaser: chosen by MiMi, no red thread
BOARD_THREAD = '2,3,9,12,13,14,16,18'
NOTE_FRAME = 12


# --------------------------------------------------------------------------- seal
# 「張櫻瀚印」 in small-seal script, 朱文 (red characters, red frame). Glyphs from the CNS11643
# 全字庫說文解字 font (Taiwan, Open Government Data License); 櫻 = 木+嬰 and 瀚 = 水+翰 are composed
# the way seal carvers do, since neither character is in the Shuowen. Path: tools/src/seal-path.txt.
SEAL_PATH = (ROOT / 'tools' / 'src' / 'seal-path.txt').read_text().strip()
SEAL_V = hashlib.md5(SEAL_PATH.encode()).hexdigest()[:8]


def write_seal_svg():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><symbol id="seal" viewBox="0 0 512 512">'
           '<rect x="20" y="20" width="472" height="472" rx="24" fill="none" stroke="currentColor" style="stroke-width:var(--seal-frame,24px)"/>'
           '<path d="%s" fill="currentColor" stroke="currentColor" stroke-linejoin="round" style="stroke-width:var(--seal-stroke,8px)"/>'
           '</symbol><use href="#seal" style="color:#C8281C"/></svg>\n') % SEAL_PATH
    (ROOT / 'assets' / 'img' / 'ui' / 'seal.svg').write_text(svg)


def seal_svg(rel, cls):
    return ('<svg class="seal %s" viewBox="0 0 512 512" aria-hidden="true" focusable="false">'
            '<use href="%sassets/img/ui/seal.svg?v=%s#seal"/></svg>') % (cls, rel, SEAL_V)


# --------------------------------------------------------------------------- helpers
def bi(en, zh, raw=False):
    if not raw:
        en, zh = esc(en), esc(zh)
    return '<span class="en">%s</span><span class="zh" lang="zh-Hans">%s</span>' % (en, zh)


def a(s):
    return esc(s, quote=True)


def info(src):
    return IM[src]


def iurl(i, w, rel):
    return '%sassets/img/%s/%s-%d.webp' % (rel, i['slug'], i['id'], w)


def pick(i, target):
    ws = [w for w in i['widths'] if w >= target]
    return ws[0] if ws else i['widths'][-1]


def srcset(i, rel):
    return ', '.join('%s %dw' % (iurl(i, w, rel), w) for w in i['widths'])


def ratio(i):
    return round(i['w'] / i['h'], 4)


def ph(i, rel, alt_en, alt_zh, sizes, eager=False, extra=''):
    style = "--c:%s;background-image:url('%s')" % (i['color'], i['lqip'])
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return ('<span class="ph%s" style="%s"><img src="%s" srcset="%s" sizes="%s" width="%d" height="%d" alt="%s" '
            'data-alt-en="%s" data-alt-zh="%s" %s decoding="async"></span>') % (
        extra, a(style), iurl(i, pick(i, 1000), rel), srcset(i, rel), sizes, i['w'], i['h'],
        a(alt_en), a(alt_en), a(alt_zh), load)


def lb_attrs(i, rel, cap_en, cap_zh):
    return ('data-lb data-small="%s" data-big="%s" data-w="%d" data-h="%d" data-cap-en="%s" data-cap-zh="%s" data-lqip="%s"') % (
        iurl(i, pick(i, 1600), rel), iurl(i, i['widths'][-1], rel), i['w'], i['h'], a(cap_en), a(cap_zh), a(i['lqip']))


def num(n, width=2):
    return str(n).zfill(width)


def tag_html(tag, cls, inner):
    return '<%s class="%s">%s</%s>' % (tag, cls, inner, tag)


def work_href(rel, w):
    return '%sworks/%s/' % (rel, w['slug'])


def cover(w):
    return info(w['images'][w.get('cover', 0)]['src'])


def count_label(n):
    return bi('%d image%s' % (n, '' if n == 1 else 's'), '%d 幅' % n)


# --------------------------------------------------------------------------- page chrome
ARROW_L = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>'
ARROW_R = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>'


def prepaint(is_home):
    js = ("(function(){var d=document.documentElement,g=function(k){try{return localStorage.getItem(k)}catch(e){return null}},"
          "l=g('lang'),t=g('theme');l=(l==='zh')?'zh':'en';d.dataset.lang=l;d.lang=l==='zh'?'zh-Hans':'en';"
          "d.dataset.theme=t==='ink'?'ink':'paper';")
    if is_home:
        js += ("try{if(!sessionStorage.getItem('introSeen')&&!matchMedia('(prefers-reduced-motion: reduce)').matches)"
               "{d.classList.add('intro-on');setTimeout(function(){d.classList.remove('intro-on')},4500)}}catch(e){}")
    return js + '})();'


def head(rel, title_en, title_zh, desc, path, og, is_home=False, ld=None, asset_v=''):
    canon = DOMAIN + '/' + path
    t_en = title_en
    out = ['<!doctype html>',
           '<html lang="en" data-lang="en" data-theme="paper" data-title-en="%s" data-title-zh="%s">' % (a(t_en), a(title_zh)),
           '<head>', '<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
           '<title>%s</title>' % esc(t_en),
           '<meta name="description" content="%s">' % a(desc),
           '<meta name="theme-color" content="#F4F4F2">',
           '<meta name="color-scheme" content="light dark">',
           '<link rel="canonical" href="%s">' % a(canon),
           '<link rel="icon" href="%sassets/img/ui/favicon.svg" type="image/svg+xml">' % rel,
           '<meta property="og:type" content="website">',
           '<meta property="og:site_name" content="Yinghan Zhang">',
           '<meta property="og:title" content="%s">' % a(t_en),
           '<meta property="og:description" content="%s">' % a(desc),
           '<meta property="og:url" content="%s">' % a(canon),
           '<meta property="og:image" content="%s">' % a(DOMAIN + '/' + og),
           '<meta name="twitter:card" content="summary_large_image">',
           '<script>%s</script>' % prepaint(is_home)]
    for f in ('cormorant-garamond-latin-300-normal', 'cormorant-garamond-latin-300-italic'):
        out.append('<link rel="preload" href="%sassets/fonts/%s.woff2" as="font" type="font/woff2" crossorigin>' % (rel, f))
    out.append('<link rel="stylesheet" href="%sassets/css/site.css%s">' % (rel, asset_v))
    out.append('<noscript><style>.rv{opacity:1!important;transform:none!important}.ph>img{opacity:1!important}#rub,.intro{display:none!important}'
               '[hidden]{display:block!important}.zh{display:none!important}</style></noscript>')
    if ld:
        out.append('<script type="application/ld+json">%s</script>' % json.dumps(ld, ensure_ascii=False).replace('</', '<\\/'))
    out.append('</head>')
    return '\n'.join(out)


def chrome(rel, current):
    home = rel or './'
    items = [('work', home + '#works', 'Work', '作品'),
             ('about', rel + 'about/', 'About', '关于'),
             ('contact', rel + 'contact/', 'Contact', '联系')]
    links = ''.join('<a class="nl mono" href="%s"%s>%s</a>' % (h, ' aria-current="page"' if k == current else '', bi(en, zh))
                    for k, h, en, zh in items)
    return f'''<a class="skip" href="#main">{bi('Skip to content', '跳到正文')}</a>
<span class="reg reg-tl" aria-hidden="true"><i></i></span><span class="reg reg-tr" aria-hidden="true"><i></i></span><span class="reg reg-bl" aria-hidden="true"><i></i></span><span class="reg reg-br" aria-hidden="true"><i></i></span>
<header class="chrome mono">
  <a class="brand" href="{home}" aria-label="Yinghan Zhang, home">{seal_svg(rel, 'brand-seal')}{bi(SITE['name'], SITE['name_zh'])}</a>
  <span class="where">{bi('Seattle', '西雅图')} · <span data-clock>--:--</span></span>
  <nav class="nav" id="nav" aria-label="Main">
    {links}
    <span class="sep" aria-hidden="true"></span>
    <span class="tools">
      <button type="button" class="tg" data-toggle-lang aria-label="Switch language / 切换语言">{bi('中文', 'EN')}</button>
      <button type="button" class="tg" data-toggle-theme aria-pressed="false" aria-label="Toggle paper / ink theme"><span class="th-ink">{bi('Ink', '墨')}</span><span class="th-paper">{bi('Paper', '纸')}</span></button>
    </span>
  </nav>
  <button type="button" class="menu-btn mono" aria-expanded="false" aria-controls="nav"><span>{bi('Menu', '菜单')}</span><i></i></button>
</header>'''


def footer(rel):
    home = rel or './'
    ig = SITE['instagram']
    handle = '@' + ig.rstrip('/').split('/')[-1]
    mail = ''
    if SITE.get('email'):
        mail = '<a href="mailto:%s">%s</a>' % (a(SITE['email']), esc(SITE['email']))
    return f'''<footer class="foot">
  <div class="foot-mark" aria-hidden="true"><span class="en">Yinghan <em>Zhang</em></span><span class="zh" lang="zh-Hans">张<em>樱瀚</em></span></div>
  <div class="foot-col mono"><span class="dim">{bi('Based in', '工作地')}</span><span>{bi('Seattle, WA', '美国 · 西雅图')}</span><span class="dim" data-clock>--:--</span></div>
  <div class="foot-col c mono"><a href="{home}#works">{bi('Work', '作品')}</a><a href="{rel}about/">{bi('About', '关于')}</a><a href="{rel}contact/">{bi('Contact', '联系')}</a></div>
  <div class="foot-col r mono"><a href="{a(ig)}" target="_blank" rel="noopener">Instagram {esc(handle)} ↗</a>{mail}<span class="dim">© {YEAR} {bi(SITE['name'], SITE['name_zh'])}</span></div>
</footer>'''


def lang_script_tail(rel):
    return '<script src="%sassets/js/main.js%s" defer></script>' % (rel, ASSET_V)


def page(rel, *, title_en, title_zh, desc, path, og, body, current=None, is_home=False, ld=None, extra_body=''):
    return '\n'.join([
        head(rel, title_en, title_zh, desc, path, og, is_home, ld, ASSET_V),
        '<body>', chrome(rel, current), extra_body, '<main id="main">', body, '</main>', footer(rel),
        lang_script_tail(rel), '</body>', '</html>', ''])


def og_for(slug=None):
    p = 'assets/og/%s.jpg' % (slug or 'default')
    return p if (ROOT / p).exists() else 'assets/og/default.jpg'


# --------------------------------------------------------------------------- home
def home_page():
    rel = ''
    # --- hero
    hero = f'''<section class="hero" id="top" aria-label="Introduction">
  <p class="hero-kicker mono"><span>{bi(SITE['tagline'], SITE['tagline_zh'])}</span><span class="dim">{bi('Seattle, WA', '美国 · 西雅图')}</span></p>
  <h1 class="hero-name" aria-label="{a(SITE['name'])}"><span><span class="en">Yinghan</span><span class="zh" lang="zh-Hans">张</span></span><span><span class="en">Zhang</span><span class="zh" lang="zh-Hans">樱瀚</span></span></h1>
  <div class="hero-stage" id="stage">
    <img class="hero-stone" src="assets/img/ui/stone-1500.webp" srcset="assets/img/ui/stone-760.webp 760w, assets/img/ui/stone-1500.webp 1500w" sizes="(max-width:900px) 70vw, 36vw" width="1001" height="1500" alt="A full-shape rubbing of a scholar’s stone" data-alt-en="A full-shape rubbing of a scholar’s stone" data-alt-zh="一块文人石的全形拓" fetchpriority="high" draggable="false">
    <canvas id="rub" data-mask="assets/img/ui/stone-mask.png" aria-hidden="true"></canvas>
    <span class="hero-done mono">{bi('The stone, revealed.', '石形已现。')}</span>
  </div>
  {seal_svg('', 'hero-seal')}
  <div class="hero-foot">
    <div class="hero-hint mono">
      <span>{bi('Rub the paper to reveal the stone.', '轻拂纸面,拓出石形。')}</span>
      <span class="dim"><span class="hero-pct" data-pct>0</span>% {bi('revealed', '已显现')}</span>
      <button type="button" data-reveal-all>{bi('Reveal all', '全部显现')}</button>
    </div>
    <a class="scroll-cue mono" href="#works"><span>{bi('Scroll', '向下')}</span><i></i></a>
  </div>
</section>'''

    # --- plates
    plates = []
    for n, w in enumerate(WORKS, 1):
        c = cover(w)
        meta = w.get('year')
        sub = bi(w['title_zh'], w['title'])
        plates.append(f'''<article class="plate" style="--ar:{ratio(c)}">
  <a href="{work_href(rel, w)}" aria-label="{a(w['title'])}">
    <span class="plate-no mono"><b>{num(n)}</b><span>/ {num(N)}</span></span>
    <figure>{ph(c, rel, w['images'][w.get('cover', 0)]['alt'], w['images'][w.get('cover', 0)]['alt_zh'], '(max-width:900px) 72vw, 34vw', eager=n <= 3)}</figure>
    <span class="plate-cap"><span class="plate-title">{bi(w['title'], w['title_zh'])}</span><span class="plate-sub mono">{sub}{(' · ' + str(meta)) if meta else ''}</span></span>
  </a>
</article>''')
    index = []
    for n, w in enumerate(WORKS, 1):
        c = cover(w)
        index.append(f'''<li><a href="{work_href(rel, w)}" data-ar="{ratio(c)}" data-lqip="{a(c['lqip'])}" data-color="{c['color']}" data-peek="{iurl(c, c['widths'][0] if c['widths'][0] >= 480 else c['widths'][0], rel)}">
  <span class="n mono">{num(n)}</span>
  <span class="t">{bi(w['title'], w['title_zh'])}<em><span class="en">{esc(w['title_zh'])}</span><span class="zh" lang="zh-Hans">{esc(w['title'])}</span></em></span>
  <span class="m mono">{esc(str(w.get('year', '')))}</span>
  <span class="c mono">{count_label(len(w['images']) + len(w.get('process', [])))}</span>
</a></li>''')

    works = f'''<section class="works" id="works" aria-labelledby="works-h">
  <div class="works-head">
    <h2 class="sec-title rv" id="works-h"><small class="mono">{bi('Selected works', '精选作品')} — {num(N)}</small>{bi('The <em>Work</em>', '作品 <em>集</em>', raw=True)}</h2>
    <div class="view-toggle mono rv" role="group" aria-label="View">
      <button type="button" data-view="plates" aria-pressed="true">{bi('Plates', '图版')}</button>
      <button type="button" data-view="index" aria-pressed="false">{bi('Index', '目录')}</button>
    </div>
  </div>
  <div class="plates" id="plates">
    <div class="plates-arrows">
      <button type="button" class="arrow" data-plates-prev aria-label="Previous">{ARROW_L}</button>
      <button type="button" class="arrow" data-plates-next aria-label="Next">{ARROW_R}</button>
    </div>
    <div class="plates-track" tabindex="0" role="region" aria-label="Works — scroll sideways">
{chr(10).join(plates)}
    </div>
    <div class="ruler"><div class="ruler-scale"></div><div class="ruler-ticks"></div><div class="ruler-mark"></div></div>
  </div>
  <div class="index" id="index" hidden>
    <ol class="index-list">
{chr(10).join(index)}
    </ol>
  </div>
</section>
<div class="peek" aria-hidden="true"><span class="ph"><img alt="" src="data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=="></span></div>'''

    # --- quote
    quote = f'''<section class="quote" aria-label="Quote">
  <p class="quote-en rv"><span>A stone is</span> <span>the smallest</span> <span>mountain.</span></p>
  <p class="quote-zh rv" lang="zh-Hans" style="--d:.15s">石为最小之山</p>
  <p class="quote-cap mono rv"><span>{bi('A Daoist idea, and the thread through the work', '一个道家的观念,也是贯穿作品的线索')}</span></p>
</section>'''

    # --- process teaser
    sv = WORKS[0]
    proc = sv['process']
    frames = []
    for k, n in enumerate(TEASER_FRAMES, 1):
        p = proc[n - 1]
        i = info(p['src'])
        frames.append(f'''<figure class="frame">
  <span class="no mono">{num(k)}</span>
  <a href="{work_href(rel, sv)}#process" aria-label="{a(p['caption'])}">{ph(i, rel, p['alt'], p['alt_zh'], '(max-width:900px) 33vw, 14vw')}</a>
  <figcaption>{bi(p['caption'], p['caption_zh'])}</figcaption>
</figure>''')
    feature = f'''<section class="feature" id="process" aria-labelledby="process-h">
  <div class="feature-head">
    <h2 class="sec-title rv" id="process-h">{bi('From the studio — <em>Silent Veins</em>', '工作室手记 — <em>静观</em>', raw=True)}</h2>
    <div class="rv" style="--d:.12s">
      <p>{bi('Frames from the making of Silent Veins — from the cord and the table to the slow gathering of ink.', '《静观》创作过程中的片段——从绳与案,到墨一点点聚拢。')}</p>
      <a class="cta mono" href="{work_href(rel, sv)}#process">{bi('See the full process', '查看完整过程')} <span aria-hidden="true">→</span></a>
    </div>
  </div>
  <div class="frames" data-thread="">
{chr(10).join(frames)}
  </div>
</section>'''

    ld = {'@context': 'https://schema.org', '@type': 'Person', 'name': SITE['name'], 'alternateName': SITE['name_zh'],
          'url': DOMAIN + '/', 'jobTitle': 'Stone artist and printmaker', 'sameAs': [SITE['instagram']],
          'homeLocation': {'@type': 'Place', 'name': 'Seattle, WA'}}
    intro = f'<div class="intro" aria-hidden="true">{seal_svg('', 'intro-seal')}<div class="intro-name">{SITE["name"]}</div></div>'
    body = '\n'.join([hero, works, quote, feature])
    return page(rel, title_en='Yinghan Zhang — Stone Artist. Printmaker', title_zh='张樱瀚 — 石头艺术家 · 版画家', desc=DESC_EN,
                path='', og=og_for(), body=body, is_home=True, ld=ld, extra_body=intro)


# --------------------------------------------------------------------------- work pages
def essay_para(p):
    if p.get('poem'):
        cjk = lambda l: re.search('[\u4e00-\u9fff]', l)
        lines = lambda ls: '<br>'.join(('<span class="cjk" lang="zh-Hans">%s</span>' % esc(l)) if cjk(l) else esc(l) for l in ls)
        return '<p class="poem"><span class="en">%s</span><span class="zh" lang="zh-Hans">%s</span></p>' % (lines(p['en']), lines(p['zh']))
    return '<p>%s</p>' % bi(p['en'], p['zh'])


def essay_block(w):
    e = w.get('essay')
    credit = w.get('credit')
    if not e and not credit:
        return ''
    out = []
    if e:
        if e.get('title'):
            out.append('<h2 class="essay-title">%s</h2>' % bi(e['title'], e['title_zh']))
        paras = e['paras']
        k = e.get('fold_after')
        out.extend(essay_para(p) for p in (paras[:k] if k else paras))
        if k and len(paras) > k:
            out.append('<details class="essay-more"><summary class="mono">%s</summary>%s</details>' % (
                bi(e.get('more_en', 'Read more'), e.get('more_zh', '展开全文')), ''.join(essay_para(p) for p in paras[k:])))
    if credit:
        out.append('<p class="essay-credit mono">%s</p>' % bi(credit['en'], credit['zh']))
    return '<section class="essay rv" aria-label="%s">\n%s\n</section>' % (a(e.get('title', 'Text') if e else 'Credits'), '\n'.join(out))


def work_page(idx):
    w = WORKS[idx]
    rel = '../../'
    prev_w, next_w = WORKS[(idx - 1) % N], WORKS[(idx + 1) % N]
    long = len(w['title']) > 22
    meta = []
    if w.get('year'):
        meta.append(('Year', '年份', esc(str(w['year'])), esc(str(w['year']))))
    if w.get('medium'):
        meta.append(('Medium', '媒介', esc(w['medium']), esc(w.get('medium_zh', w['medium']))))
    if w.get('size'):
        meta.append(('Size', '尺寸', esc(w['size']), esc(w.get('size_zh', w['size']))))
    meta_html = ''
    if meta:
        meta_html = '<dl class="work-meta mono">%s</dl>' % ''.join('<dt>%s</dt><dd>%s</dd>' % (bi(e, z), bi(ev, zv, raw=True)) for e, z, ev, zv in meta)
    desc_html = ''
    if w.get('text'):
        desc_html = '<div class="work-desc">%s</div>' % ''.join('<p>%s</p>' % bi(p['en'], p['zh']) for p in w['text'])
    essay_html = essay_block(w)
    links = []
    if w.get('video', {}).get('youtube'):
        links.append('<a class="mono" href="https://youtu.be/%s" target="_blank" rel="noopener">%s</a>' % (w['video']['youtube'], bi('Watch the video ↗', '观看影像 ↗')))
    if w.get('process'):
        links.append('<a class="mono" href="#process">%s</a>' % bi('Process ↓', '创作过程 ↓'))
    info_html = f'''<aside class="work-info{' has-text' if w.get('text') else ''}">
    <p class="work-no mono"><b>{num(idx + 1)}</b><span>/ {num(N)}</span><span class="fig-count">{count_label(len(w['images']))}</span></p>
    <h1 class="work-title{' long' if long else ''}"><span class="en">{esc(w['title'])}<span class="work-alt zhs" lang="zh-Hans">{esc(w['title_zh'])}</span></span><span class="zh" lang="zh-Hans">{esc(w['title_zh'])}<span class="work-alt">{esc(w['title'])}</span></span></h1>
    {meta_html}
    {desc_html}
    {('<div class="work-links">' + ''.join(links) + '</div>') if links else ''}
  </aside>'''

    figs = []
    total = len(w['images'])
    for n, im in enumerate(w['images'], 1):
        i = info(im['src'])
        cap = im.get('caption'), im.get('caption_zh')
        lb_en, lb_zh = (cap[0] or w['title']), (cap[1] or w['title_zh'])
        figs.append(f'''<figure class="fig rv">
  <div class="fig-frame" style="--ar:{ratio(i)};--c:{i['color']}" role="button" tabindex="0" aria-label="{a(w['title'])} {n}/{total}: open image" {lb_attrs(i, rel, lb_en, lb_zh)}>
    {ph(i, rel, im['alt'], im['alt_zh'], '(max-width:900px) 94vw, 58vw', eager=n == 1)}
  </div>
  <figcaption class="mono"><b>{num(n)} / {num(total)}</b><span>{bi(cap[0], cap[1]) if cap[0] else ''}</span></figcaption>
</figure>''')
    figs_html = '<div class="work-figs">\n%s\n  </div>' % '\n'.join(figs)

    video_html = ''
    if w.get('video', {}).get('youtube'):
        v = w['video']
        vid = v['youtube']
        video_html = f'''<section class="video-block rv" aria-label="Video">
  <div class="video-frame" data-yt="{vid}" data-title="{a(v['title'])}">
    <img class="yt-poster" src="https://i.ytimg.com/vi/{vid}/maxresdefault.jpg" alt="" loading="lazy" decoding="async" onerror="this.style.visibility='hidden'">
    <button type="button" class="play" aria-label="Play video: {a(v['title'])}"><span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4l14 8-14 8z"/></svg></span></button>
  </div>
  <p class="video-cap mono"><span>{bi(v['title'], v['title_zh'])}</span><a href="https://youtu.be/{vid}" target="_blank" rel="noopener">{bi('Watch on YouTube ↗', '在 YouTube 观看 ↗')}</a></p>
</section>'''
    if w.get('local_video'):
        v = w['local_video']
        video_html = f'''<section class="video-block rv" aria-label="Video">
  <div class="video-frame" style="aspect-ratio:1280/854">
    <video data-loop muted loop playsinline preload="none" poster="{rel}assets/video/{v['poster']}" aria-label="{a(v['caption'])}"><source src="{rel}assets/video/{v['src']}" type="video/mp4"></video>
  </div>
  <p class="video-cap mono"><span>{bi(v['caption'], v['caption_zh'])}</span><span>{bi('Click to pause', '点击暂停')}</span></p>
</section>'''

    process_html = ''
    if w.get('process'):
        items, frames = [], []
        proc = w['process']
        for n, p in enumerate(proc, 1):
            i = info(p['src'])
            items.append('<li><button type="button"><b>%s</b><span>%s</span></button></li>' % (num(n), bi(p['caption'], p['caption_zh'])))
            frames.append(f'''<figure class="frame">
  <span class="no mono">{num(n)}</span>
  <button type="button" aria-label="{a(p['caption'])}" {lb_attrs(i, rel, p['caption'], p['caption_zh'])}>{ph(i, rel, p['alt'], p['alt_zh'], '(max-width:900px) 33vw, 15vw')}</button>
  <figcaption>{bi(p['caption'], p['caption_zh'])}</figcaption>
</figure>''')
        process_html = f'''<section class="process" id="process" aria-labelledby="process-h">
  <div class="process-head">
    <h2 class="sec-title rv" id="process-h"><small class="mono">{bi('Process', '创作过程')} — {len(proc)} {bi('frames', '帧')}</small>{bi('How the <em>ink</em> arrives', '墨,<em>如何到来</em>', raw=True)}</h2>
    <p class="rv" style="--d:.12s">{bi('Click a frame to look closer.', '点击任一画面可细看。')}</p>
  </div>
  <div class="board">
    <nav class="board-index" aria-label="Frames"><h3>{bi('Frames', '画面')}</h3><ol>{''.join(items)}</ol></nav>
    <div class="frames" data-thread="">
{chr(10).join(frames)}
    </div>
  </div>
</section>'''

    nav_html = f'''<nav class="work-nav" aria-label="More work">
  <a href="{work_href(rel, prev_w)}" rel="prev"><span class="mono">← {bi('Previous', '上一件')} · {num(((idx - 1) % N) + 1)}</span><span class="t">{bi(prev_w['title'], prev_w['title_zh'])}</span></a>
  <a href="{work_href(rel, next_w)}" rel="next"><span class="mono">{bi('Next', '下一件')} · {num(((idx + 1) % N) + 1)} →</span><span class="t">{bi(next_w['title'], next_w['title_zh'])}</span></a>
</nav>'''

    body = f'''<article class="work">
  <div class="work-main">
  {info_html}
  {figs_html}
  </div>
  {essay_html}
  {video_html}
  {process_html}
  {nav_html}
</article>'''
    c = cover(w)
    desc = '%s — a work by Yinghan Zhang, stone artist and printmaker in Seattle.' % w['title']
    if w.get('text'):
        first = w['text'][0]['en']
        desc = first if len(first) <= 158 else first[:155].rsplit(' ', 1)[0].rstrip(',;:—') + '…'
    elif w.get('medium'):
        desc = '%s (%s%s) — a work by Yinghan Zhang, stone artist and printmaker in Seattle.' % (
            w['title'], (str(w['year']) + ', ') if w.get('year') else '', w['medium'])
    ld = {'@context': 'https://schema.org', '@type': 'VisualArtwork', 'name': w['title'], 'alternateName': w['title_zh'],
          'creator': {'@type': 'Person', 'name': SITE['name']}, 'url': '%s/works/%s/' % (DOMAIN, w['slug']),
          'image': '%s/%s' % (DOMAIN, 'assets/img/%s/%s-%d.webp' % (c['slug'], c['id'], pick(c, 1000)))}
    if w.get('year'):
        ld['dateCreated'] = str(w['year'])
    if w.get('medium'):
        ld['artMedium'] = w['medium']
    return page(rel, title_en='%s — Yinghan Zhang' % w['title'], title_zh='%s — 张樱瀚' % w['title_zh'], desc=desc,
                path='works/%s/' % w['slug'], og=og_for(w['slug']), body=body, current='work', ld=ld)


# --------------------------------------------------------------------------- about
def about_page():
    rel = '../'
    ex = EX['about']
    i = info(ex['src'])
    stone_ar = round(1001 / 1500, 4)
    paras = []
    for n, (en, zh) in enumerate(zip(BIO_EN, BIO_ZH)):
        paras.append('<p%s>%s</p>' % (' class="lede"' if n == 0 else '', bi(en, zh)))
    stone = f'<div class="about-stone" style="--ar:{stone_ar}" aria-hidden="true"><img src="{rel}assets/img/ui/stone-760.webp" width="760" height="1138" alt="" loading="lazy" decoding="async"></div>'
    ig = SITE['instagram']
    handle = '@' + ig.rstrip('/').split('/')[-1]
    aside = [
        ('Based in', '工作地', 'Seattle, WA', '美国 · 西雅图'),
        ('Practice', '媒介', 'Full-shape rubbing, printmaking, woodcut, drawing, collage', '全形拓、版画、木刻、绘画、拼贴'),
        ('Studied', '师承', 'Full-shape rubbing, under a master artisan in Shandong', '山东,师从传统拓印匠人学习全形拓'),
    ]
    aside_html = ''.join('<dt>%s</dt><dd>%s</dd>' % (bi(e, z), bi(ev, zv)) for e, z, ev, zv in aside)
    aside_html += '<dt>%s</dt><dd><a href="%s" target="_blank" rel="noopener">%s ↗</a></dd>' % (bi('Instagram', 'Instagram'), a(ig), esc(handle))
    if SITE.get('email'):
        aside_html += '<dt>%s</dt><dd><a href="mailto:%s">%s</a></dd>' % (bi('Email', '邮箱'), a(SITE['email']), esc(SITE['email']))
    body = f'''<section class="about">
  <header class="about-head">
    <h1 class="sec-title rv"><small class="mono">{bi('Artist bio', '艺术家简介')}</small>{bi('About', '关于', raw=False)}</h1>
    <p class="mono dim rv">{bi(SITE['tagline'], SITE['tagline_zh'])}</p>
  </header>
  <figure class="about-photo rv">
    <span class="ph" style="--ar:{ratio(i)};--c:{i['color']};background-image:url('{i['lqip']}')"><img src="{iurl(i, 1000, rel)}" srcset="{srcset(i, rel)}" sizes="(max-width:900px) 80vw, 30vw" width="{i['w']}" height="{i['h']}" alt="{a(ex['alt'])}" data-alt-en="{a(ex['alt'])}" data-alt-zh="{a(ex['alt_zh'])}" fetchpriority="high" decoding="async"></span>
    <figcaption class="mono">{bi('In the studio, taking a rubbing', '工作室里,正在拓印')}</figcaption>
  </figure>
  <div class="about-body">
    {stone}
    {''.join(paras)}
    <dl class="about-aside mono">{aside_html}</dl>
  </div>
</section>'''
    ld = {'@context': 'https://schema.org', '@type': 'Person', 'name': SITE['name'], 'alternateName': SITE['name_zh'],
          'description': BIO_EN[0], 'url': DOMAIN + '/about/', 'sameAs': [SITE['instagram']]}
    return page(rel, title_en='About — Yinghan Zhang', title_zh='关于 — 张樱瀚', desc=BIO_EN[0][:155].rstrip() + '…',
                path='about/', og=og_for(), body=body, current='about', ld=ld)


# --------------------------------------------------------------------------- contact
def contact_page():
    rel = '../'
    ex = EX['contact']
    i = info(ex['src'])
    ig = SITE['instagram']
    handle = '@' + ig.rstrip('/').split('/')[-1]
    rows = []
    if SITE.get('email'):
        rows.append('<a href="mailto:%s"><span class="mono">%s</span><span class="v">%s</span><span class="arr mono">↗</span></a>' % (
            a(SITE['email']), bi('Email', '邮箱'), esc(SITE['email'])))
    rows.append('<a href="%s" target="_blank" rel="noopener"><span class="mono">Instagram</span><span class="v">%s</span><span class="arr mono">↗</span></a>' % (a(ig), esc(handle)))
    rows.append('<div><span class="mono">%s</span><span class="v">%s</span><span class="arr mono"></span></div>' % (bi('Based in', '工作地'), bi('Seattle, WA', '美国 · 西雅图')))
    rows.append('<div><span class="mono">%s</span><span class="v" data-clock>--:--</span><span class="arr mono"></span></div>' % bi('Local time', '当地时间'))
    note = ('For inquiries about works, exhibitions or collaborations, write by email or send a message on Instagram.'
            if SITE.get('email') else
            'For inquiries about works, exhibitions or collaborations, send a message on Instagram.')
    note_zh = ('作品咨询、展览或合作,欢迎来信,或在 Instagram 私信联系。'
               if SITE.get('email') else '作品咨询、展览或合作,欢迎在 Instagram 私信联系。')
    body = f'''<section class="contact">
  <div class="contact-main">
    <h1 class="rv">{bi('Get in<br><em>touch.</em>', '联系<em>我</em>', raw=True)}</h1>
    <div class="contact-list rv" style="--d:.1s">{''.join(rows)}</div>
    <p class="contact-note rv" style="--d:.18s">{bi(note, note_zh)}</p>
  </div>
  <figure class="contact-art rv" style="--d:.2s">
    <span class="ph" style="--ar:{ratio(i)};--c:{i['color']};background-image:url('{i['lqip']}')"><img src="{iurl(i, 480, rel)}" srcset="{srcset(i, rel)}" sizes="(max-width:900px) 70vw, 28vw" width="{i['w']}" height="{i['h']}" alt="{a(ex['alt'])}" data-alt-en="{a(ex['alt'])}" data-alt-zh="{a(ex['alt_zh'])}" loading="lazy" decoding="async"></span>
    <figcaption class="mono">{bi('Printed sheets, repeated', '版画纸张,重复排列')}</figcaption>
  </figure>
</section>'''
    return page(rel, title_en='Contact — Yinghan Zhang', title_zh='联系 — 张樱瀚',
                desc='Contact Yinghan Zhang, stone artist and printmaker in Seattle.', path='contact/', og=og_for(), body=body, current='contact')


# --------------------------------------------------------------------------- 404 + redirects
def not_found():
    rel = '/'
    body = f'''<section class="nf">
  <div>
    <p class="mono dim">404</p>
    <h1>{bi('Nothing <em>here.</em>', '此处<em>无石。</em>', raw=True)}</h1>
    <p>{bi('This page has wandered off. Try the work instead.', '这一页走丢了,去看看作品吧。')}</p>
    <a class="cta mono" href="/">{bi('Back to the work', '回到作品')} <span aria-hidden="true">→</span></a>
  </div>
</section>'''
    h = page(rel, title_en='Not found — Yinghan Zhang', title_zh='未找到 — 张樱瀚', desc='Page not found.', path='404.html', og=og_for(), body=body)
    return h.replace('<meta name="theme-color"', '<meta name="robots" content="noindex">\n<meta name="theme-color"', 1)


def redirect(to):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Redirecting…</title>'
            '<meta http-equiv="refresh" content="0; url=%s"><link rel="canonical" href="%s%s"><meta name="robots" content="noindex">'
            '</head><body><a href="%s">Continue</a></body></html>\n') % (to, DOMAIN, to, to)


# --------------------------------------------------------------------------- assets
def build_assets():
    css_dir = ROOT / 'tools/src/css'
    parts = [p.read_text(encoding='utf-8') for p in sorted(css_dir.glob('*.css'))]
    zh = []
    for wgt in (300, 400):
        f = ROOT / ('assets/fonts/noto-serif-sc-%d.woff2' % wgt)
        if f.exists():
            zh.append('@font-face{font-family:"Noto Serif SC";font-style:normal;font-weight:%d;font-display:swap;src:url(../fonts/%s) format("woff2")}' % (wgt, f.name))
    css = '\n'.join(parts + zh)
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    css = re.sub(r'\s*\n\s*', '', css)
    css = re.sub(r'\s*([{};,>])\s*', r'\1', css)
    css = re.sub(r';}', '}', css)
    (ROOT / 'assets/css').mkdir(parents=True, exist_ok=True)
    (ROOT / 'assets/js').mkdir(parents=True, exist_ok=True)
    (ROOT / 'assets/css/site.css').write_text(css, encoding='utf-8')
    shutil.copyfile(ROOT / 'tools/src/js/main.js', ROOT / 'assets/js/main.js')
    h = hashlib.sha1((css + (ROOT / 'assets/js/main.js').read_text(encoding='utf-8')).encode()).hexdigest()[:8]
    return '?v=' + h


def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


ASSET_V = ''


def main():
    global ASSET_V
    ASSET_V = build_assets()
    write_seal_svg()
    write('index.html', home_page())
    for n in range(N):
        write('works/%s/index.html' % WORKS[n]['slug'], work_page(n))
    write('about/index.html', about_page())
    write('contact/index.html', contact_page())
    write('contact-form/index.html', redirect('/contact/'))
    write('404.html', not_found())
    urls = ['', 'about/', 'contact/'] + ['works/%s/' % w['slug'] for w in WORKS]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append('<url><loc>%s/%s</loc><lastmod>%s</lastmod></url>' % (DOMAIN, u, TODAY))
    sm.append('</urlset>')
    write('sitemap.xml', '\n'.join(sm) + '\n')
    write('robots.txt', 'User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n' % DOMAIN)
    write('CNAME', DOMAIN.replace('https://', '').replace('http://', '') + '\n')
    write('.nojekyll', '')
    print('built %d pages, css/js %s' % (3 + N + 2, ASSET_V))


if __name__ == '__main__':
    main()
