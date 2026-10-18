/* Yinghan Zhang — portfolio. Vanilla JS, no dependencies. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const root = document.documentElement;
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const fine = matchMedia('(hover: hover) and (pointer: fine)').matches;
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const lang = () => root.dataset.lang || 'en';

/* ------------------------------------------------------------------ */
/* Language + theme                                                    */
/* ------------------------------------------------------------------ */
function applyLang(l) {
  root.dataset.lang = l;
  root.lang = l === 'zh' ? 'zh-Hans' : 'en';
  store.set('lang', l);
  $$('img[data-alt-en]').forEach((im) => { im.alt = l === 'zh' ? im.dataset.altZh : im.dataset.altEn; });
  const t = l === 'zh' ? root.dataset.titleZh : root.dataset.titleEn;
  if (t) document.title = t;
  $$('[data-set-lang]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.setLang === l)));
  document.dispatchEvent(new CustomEvent('langchange', { detail: l }));
}
function applyTheme(t) {
  root.dataset.theme = t;
  store.set('theme', t);
  const m = $('meta[name="theme-color"]');
  if (m) m.content = t === 'ink' ? '#1C1B17' : '#EFEAE0';
  $$('[data-toggle-theme]').forEach((b) => b.setAttribute('aria-pressed', String(t === 'ink')));
  document.dispatchEvent(new CustomEvent('themechange', { detail: t }));
}
$$('[data-toggle-lang]').forEach((b) => b.addEventListener('click', () => applyLang(lang() === 'en' ? 'zh' : 'en')));
$$('[data-toggle-theme]').forEach((b) => b.addEventListener('click', () => applyTheme(root.dataset.theme === 'ink' ? 'paper' : 'ink')));
applyLang(lang());
applyTheme(root.dataset.theme || 'paper');

/* ------------------------------------------------------------------ */
/* Chrome: header, mobile menu, clock                                  */
/* ------------------------------------------------------------------ */
(function chrome() {
  const head = $('.chrome');
  if (!head) return;
  let lastY = scrollY, ticking = false;
  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      const y = scrollY;
      head.classList.toggle('is-scrolled', y > 24);
      head.classList.toggle('is-hidden', y > 520 && y > lastY + 4 && !document.body.classList.contains('menu-open'));
      if (y < lastY - 4) head.classList.remove('is-hidden');
      lastY = y;
      ticking = false;
    });
  };
  addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  const btn = $('.menu-btn');
  if (btn) {
    const set = (open) => {
      document.body.classList.toggle('menu-open', open);
      btn.setAttribute('aria-expanded', String(open));
      root.style.overflow = open ? 'hidden' : '';
    };
    btn.addEventListener('click', () => set(!document.body.classList.contains('menu-open')));
    $$('.nav a').forEach((a) => a.addEventListener('click', () => set(false)));
    addEventListener('keydown', (e) => { if (e.key === 'Escape') set(false); });
  }

  const clocks = $$('[data-clock]');
  if (clocks.length) {
    const fmt = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: '2-digit', minute: '2-digit', hour12: false, timeZoneName: 'short' });
    const tick = () => { const s = fmt.format(new Date()); clocks.forEach((c) => { c.textContent = s; }); };
    tick();
    setInterval(tick, 20000);
  }
})();

/* ------------------------------------------------------------------ */
/* Reveal on scroll + image fade-in                                    */
/* ------------------------------------------------------------------ */
(function reveal() {
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  $$('.rv, .frames').forEach((el) => io.observe(el));

  const ready = (im) => im.classList.add('ld');
  $$('.ph > img').forEach((im) => {
    if (im.complete && im.naturalWidth) ready(im);
    else { im.addEventListener('load', () => ready(im), { once: true }); im.addEventListener('error', () => ready(im), { once: true }); }
  });
})();

/* ------------------------------------------------------------------ */
/* Intro seal (first visit per session, home only)                     */
/* ------------------------------------------------------------------ */
(function intro() {
  const el = $('.intro');
  if (!el) return;
  if (!root.classList.contains('intro-on')) { el.remove(); return; }
  let done = false;
  const end = () => {
    if (done) return; done = true;
    el.classList.add('is-done');
    root.classList.remove('intro-on');
    try { sessionStorage.setItem('introSeen', '1'); } catch { /* ignore */ }
    setTimeout(() => el.remove(), 1600);
    document.dispatchEvent(new Event('introdone'));
  };
  setTimeout(end, reduce ? 200 : 1700);
  el.addEventListener('click', end);
})();

/* ------------------------------------------------------------------ */
/* Hero: rub the paper to reveal the stone                             */
/* ------------------------------------------------------------------ */
(function rub() {
  const stage = $('#stage'), cv = $('#rub');
  if (!stage || !cv) return;
  const pctEl = $('[data-pct]'), allBtn = $('[data-reveal-all]');
  const setPct = (p) => { if (pctEl) pctEl.textContent = String(Math.round(p * 100)); };
  if (reduce) { stage.classList.add('is-done'); cv.remove(); setPct(1); if (allBtn) allBtn.hidden = true; return; }

  const ctx = cv.getContext('2d', { willReadFrequently: true });
  const mask = new Image();
  mask.decoding = 'async';
  mask.src = cv.dataset.mask;
  let W = 0, H = 0, dpr = 1, geo = null, sil = null, finished = false, userTouched = false, demoRaf = 0, lastW = 0;
  const LO = 44; // sampling resolution for % measure
  let lo = null, loCtx = null, loMask = null, loMaskSum = 1;

  const paperColor = () => getComputedStyle(root).getPropertyValue('--paper').trim() || '#EFEAE0';

  // a grainy brush: soft core + speckle, so repeated passes read like graphite frottage
  function makeBrush(size) {
    const c = document.createElement('canvas'); c.width = c.height = size;
    const g = c.getContext('2d');
    const rg = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    rg.addColorStop(0, 'rgba(0,0,0,.42)'); rg.addColorStop(.6, 'rgba(0,0,0,.2)'); rg.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = rg; g.fillRect(0, 0, size, size);
    for (let i = 0; i < size * 7; i++) {
      const a = Math.random() * Math.PI * 2, r = Math.sqrt(Math.random()) * size / 2;
      g.fillStyle = `rgba(0,0,0,${(Math.random() * .55).toFixed(2)})`;
      const s = Math.random() * 2.2 + .6;
      g.fillRect(size / 2 + Math.cos(a) * r, size / 2 + Math.sin(a) * r, s, s);
    }
    return c;
  }
  let brush = null;

  function layout() {
    const r = cv.getBoundingClientRect();
    dpr = Math.min(devicePixelRatio || 1, 2);
    W = Math.max(2, Math.round(r.width * dpr)); H = Math.max(2, Math.round(r.height * dpr));
    cv.width = W; cv.height = H; lastW = r.width;
    // stage box inside the (larger) canvas: canvas is 124% x 110% of the stage, offset -12% / -5%
    const sw = W / 1.24, sh = H / 1.10;
    geo = { x: sw * 0.12, y: sh * 0.05, w: sw, h: sh };
    brush = makeBrush(Math.round(110 * dpr));
    drawPaper();
    // low-res stone mask for the % measure
    lo = document.createElement('canvas'); lo.width = LO; lo.height = Math.round(LO * H / W);
    loCtx = lo.getContext('2d', { willReadFrequently: true });
    if (mask.complete && mask.naturalWidth) buildMask();
  }
  function buildMask() {
    loCtx.clearRect(0, 0, lo.width, lo.height);
    const k = lo.width / W;
    loCtx.drawImage(mask, geo.x * k, geo.y * k, geo.w * k, geo.h * k);
    const d = loCtx.getImageData(0, 0, lo.width, lo.height).data;
    loMask = new Uint8Array(lo.width * lo.height); loMaskSum = 0;
    for (let i = 0; i < loMask.length; i++) { loMask[i] = d[i * 4 + 3] > 90 ? 1 : 0; loMaskSum += loMask[i]; }
    loMaskSum = Math.max(1, loMaskSum);
  }
  function drawPaper() {
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    ctx.fillStyle = paperColor(); ctx.fillRect(0, 0, W, H);
    // faint relief of the hidden stone, as if felt through the sheet
    if (mask.complete && mask.naturalWidth && geo) {
      const OFF = 20000, dark = root.dataset.theme === 'ink';
      ctx.save();
      ctx.shadowBlur = 7 * dpr;
      ctx.shadowColor = dark ? 'rgba(0,0,0,.55)' : 'rgba(66,46,28,.22)';
      ctx.shadowOffsetX = OFF + 3.5 * dpr; ctx.shadowOffsetY = 3.5 * dpr;
      ctx.drawImage(mask, geo.x - OFF, geo.y, geo.w, geo.h);
      ctx.shadowColor = dark ? 'rgba(255,255,255,.07)' : 'rgba(255,255,255,.75)';
      ctx.shadowOffsetX = OFF - 3.5 * dpr; ctx.shadowOffsetY = -3.5 * dpr;
      ctx.drawImage(mask, geo.x - OFF, geo.y, geo.w, geo.h);
      ctx.restore();
    }
  }
  function stamp(x, y, r) {
    ctx.globalCompositeOperation = 'destination-out';
    ctx.globalAlpha = 1;
    const s = r * 2;
    ctx.save(); ctx.translate(x, y); ctx.rotate(Math.random() * 6.28);
    ctx.drawImage(brush, -r, -r, s, s); ctx.restore();
  }
  function stroke(x0, y0, x1, y1, r) {
    const d = Math.hypot(x1 - x0, y1 - y0), n = Math.max(1, Math.ceil(d / (r * 0.3)));
    for (let i = 1; i <= n; i++) stamp(lerp(x0, x1, i / n), lerp(y0, y1, i / n), r);
  }
  function measure() {
    if (!loMask) return 0;
    loCtx.globalCompositeOperation = 'copy';
    loCtx.drawImage(cv, 0, 0, lo.width, lo.height);
    const d = loCtx.getImageData(0, 0, lo.width, lo.height).data;
    let rev = 0;
    for (let i = 0; i < loMask.length; i++) if (loMask[i]) rev += 1 - d[i * 4 + 3] / 255;
    return rev / loMaskSum;
  }
  let lastMeasure = 0;
  function maybeMeasure(force) {
    const now = performance.now();
    if (!force && now - lastMeasure < 350) return;
    lastMeasure = now;
    const p = measure();
    setPct(finished ? 1 : p);
    if (!finished && p > 0.8) finish();
  }
  function finish() {
    if (finished) return; finished = true;
    cancelAnimationFrame(demoRaf);
    cv.style.transition = 'opacity 1.4s cubic-bezier(.2,.7,.2,1)';
    cv.style.opacity = '0'; cv.style.pointerEvents = 'none';
    stage.classList.add('is-done'); setPct(1);
    if (allBtn) allBtn.hidden = true;
    setTimeout(() => cv.remove(), 1600);
  }
  allBtn?.addEventListener('click', finish);

  // pointer
  let down = false, px = 0, py = 0, has = false;
  const pos = (e) => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * dpr, (e.clientY - r.top) * dpr]; };
  const radius = () => 46 * dpr;
  cv.addEventListener('pointerdown', (e) => {
    userTouched = true; cancelAnimationFrame(demoRaf);
    down = true; has = false; cv.setPointerCapture?.(e.pointerId);
    const [x, y] = pos(e); px = x; py = y; has = true; stamp(x, y, radius()); maybeMeasure();
  });
  cv.addEventListener('pointermove', (e) => {
    if (finished) return;
    const mouse = e.pointerType === 'mouse';
    if (!mouse && !down) return;
    userTouched = true; cancelAnimationFrame(demoRaf);
    const [x, y] = pos(e);
    if (has) stroke(px, py, x, y, radius()); else stamp(x, y, radius());
    px = x; py = y; has = true; maybeMeasure();
  });
  const up = () => { down = false; has = false; maybeMeasure(true); };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  cv.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') has = false; });

  // a first, invisible hand shows how it works
  function demo() {
    if (userTouched || finished) return;
    const t0 = performance.now(), dur = 3200;
    let lx = null, ly = null;
    const step = (now) => {
      if (userTouched || finished) return;
      const t = clamp((now - t0) / dur, 0, 1), e = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      const x = geo.x + geo.w * (0.5 + 0.3 * Math.sin(e * Math.PI * 5.2) * (1 - 0.25 * e));
      const y = geo.y + geo.h * (0.08 + 0.84 * e);
      if (lx !== null) stroke(lx, ly, x, y, radius() * 1.05);
      lx = x; ly = y;
      if (t < 1) demoRaf = requestAnimationFrame(step); else maybeMeasure(true);
    };
    demoRaf = requestAnimationFrame(step);
  }

  mask.addEventListener('load', () => { if (geo) { drawPaper(); buildMask(); } });
  layout();
  const ro = new ResizeObserver(() => { if (!finished && Math.abs(cv.getBoundingClientRect().width - lastW) > 3) layout(); });
  ro.observe(cv);
  document.addEventListener('themechange', () => { if (!finished) layout(); });
  const startDemo = () => setTimeout(demo, 600);
  if (root.classList.contains('intro-on')) document.addEventListener('introdone', startDemo, { once: true });
  else startDemo();
})();

/* ------------------------------------------------------------------ */
/* Cursor label (shared)                                               */
/* ------------------------------------------------------------------ */
const cursorLabel = (() => {
  if (!fine) return null;
  const el = $('.cursor-label');
  if (!el) return null;
  let x = 0, y = 0, tx = 0, ty = 0, on = false, raf = 0;
  const loop = () => {
    x = lerp(x, tx, .22); y = lerp(y, ty, .22);
    el.style.transform = `translate3d(${x}px,${y}px,0) scale(${on ? 1 : .4})`;
    raf = (Math.abs(tx - x) > .1 || Math.abs(ty - y) > .1 || on) ? requestAnimationFrame(loop) : 0;
  };
  return {
    show(kind) {
      el.dataset.kind = kind; on = true; el.classList.add('is-on');
      if (!raf) raf = requestAnimationFrame(loop);
    },
    hide() { on = false; el.classList.remove('is-on'); },
    move(e) { tx = e.clientX; ty = e.clientY; if (!on && !raf) { x = tx; y = ty; } if (!raf) raf = requestAnimationFrame(loop); },
  };
})();

/* ------------------------------------------------------------------ */
/* Home: plates strip, ruler, index list                               */
/* ------------------------------------------------------------------ */
(function plates() {
  const wrap = $('#plates'), track = $('.plates-track');
  if (!wrap || !track) return;
  const items = $$('.plate', track);
  const ruler = $('.ruler'), ticks = $('.ruler-ticks');
  const prev = $('[data-plates-prev]'), next = $('[data-plates-next]');
  let centers = [], cur = 0;

  const measure = () => {
    centers = items.map((p) => p.offsetLeft + p.offsetWidth / 2);
    if (ruler) ruler.style.setProperty('--w', (ruler.clientWidth - 1.5) + 'px');
  };
  const idxAt = () => {
    const c = track.scrollLeft + track.clientWidth / 2;
    let best = 0, bd = 1e9;
    centers.forEach((x, i) => { const d = Math.abs(x - c); if (d < bd) { bd = d; best = i; } });
    return best;
  };
  const goTo = (i) => {
    i = clamp(i, 0, items.length - 1);
    track.scrollTo({ left: centers[i] - track.clientWidth / 2, behavior: reduce ? 'auto' : 'smooth' });
  };

  // ruler ticks
  if (ticks) {
    ticks.innerHTML = items.map((_, i) => `<button type="button" data-i="${i}" aria-label="${i + 1}">${String(i + 1).padStart(2, '0')}</button>`).join('');
    ticks.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) goTo(+b.dataset.i); });
  }

  let raf = 0;
  const update = () => {
    raf = 0;
    const c = track.scrollLeft + track.clientWidth / 2, span = track.clientWidth * 0.62;
    items.forEach((p, i) => {
      const f = clamp(1 - Math.abs(centers[i] - c) / span, 0, 1), e = f * f * (3 - 2 * f);
      p.style.setProperty('--s', (0.86 + 0.14 * e).toFixed(3));
      p.style.setProperty('--o', (0.5 + 0.5 * e).toFixed(3));
    });
    const i = idxAt();
    if (i !== cur || !track.dataset.init) {
      cur = i; track.dataset.init = '1';
      items.forEach((p, k) => p.classList.toggle('is-focus', k === i));
      if (ticks) $$('button', ticks).forEach((b, k) => { if (k === i) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current'); });
      if (prev) prev.disabled = i === 0;
      if (next) next.disabled = i === items.length - 1;
    }
    const max = track.scrollWidth - track.clientWidth;
    ruler?.style.setProperty('--p', max > 0 ? (track.scrollLeft / max).toFixed(4) : 0);
  };
  const sched = () => { if (!raf) raf = requestAnimationFrame(update); };
  track.addEventListener('scroll', sched, { passive: true });
  new ResizeObserver(() => { measure(); sched(); }).observe(track);
  addEventListener('load', () => { measure(); sched(); });
  measure(); update();
  // start centred on the first plate
  track.scrollLeft = 0;

  prev?.addEventListener('click', () => goTo(idxAt() - 1));
  next?.addEventListener('click', () => goTo(idxAt() + 1));
  track.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight') { e.preventDefault(); goTo(idxAt() + 1); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); goTo(idxAt() - 1); }
  });

  // mouse drag with a little inertia
  let drag = false, moved = 0, sx = 0, sl = 0, vx = 0, lx = 0, lt = 0, inertia = 0;
  track.addEventListener('pointerdown', (e) => {
    if (e.pointerType !== 'mouse' || e.button !== 0) return;
    cancelAnimationFrame(inertia);
    drag = true; moved = 0; sx = lx = e.clientX; sl = track.scrollLeft; vx = 0; lt = performance.now();
  });
  addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dx = e.clientX - sx; moved = Math.max(moved, Math.abs(dx));
    if (moved > 5 && !track.classList.contains('is-drag')) { track.classList.add('is-drag'); cursorLabel?.show('drag'); }
    track.scrollLeft = sl - dx;
    const now = performance.now(); vx = (lx - e.clientX) / Math.max(1, now - lt); lx = e.clientX; lt = now;
  });
  const endDrag = () => {
    if (!drag) return; drag = false;
    track.classList.remove('is-drag');
    if (moved > 5) {
      let v = vx * 16;
      const glide = () => { track.scrollLeft += v; v *= 0.93; if (Math.abs(v) > .4) inertia = requestAnimationFrame(glide); };
      glide();
    }
  };
  addEventListener('pointerup', endDrag); addEventListener('pointercancel', endDrag);
  track.addEventListener('click', (e) => { if (moved > 5) { e.preventDefault(); e.stopPropagation(); moved = 0; } }, true);

  // cursor label
  if (cursorLabel) {
    track.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse') return;
      cursorLabel.move(e);
      if (!drag) cursorLabel.show(e.target.closest('.plate figure') ? 'view' : 'drag');
    });
    track.addEventListener('pointerleave', () => { if (!drag) cursorLabel.hide(); });
  }

  // view toggle: plates / index
  const idx = $('#index');
  const setView = (v) => {
    wrap.hidden = v !== 'plates'; if (idx) idx.hidden = v !== 'index';
    $$('[data-view]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.view === v)));
    store.set('view', v);
    if (v === 'plates') requestAnimationFrame(() => { measure(); update(); });
  };
  $$('[data-view]').forEach((b) => b.addEventListener('click', () => setView(b.dataset.view)));
  setView(store.get('view') === 'index' ? 'index' : 'plates');

  // index: floating preview
  const peek = $('.peek');
  if (idx && peek && fine) {
    const ph = $('.ph', peek), im = $('img', ph);
    let x = 0, y = 0, tx = 0, ty = 0, rf = 0;
    const loop = () => {
      x = lerp(x, tx, .16); y = lerp(y, ty, .16);
      const w = peek.offsetWidth, h = peek.offsetHeight;
      const px = clamp(x + 28, 8, innerWidth - w - 8), py = clamp(y - h / 2, 8, innerHeight - h - 8);
      peek.style.transform = `translate3d(${px}px,${py}px,0) rotate(${clamp((tx - x) * .04, -4, 4)}deg)`;
      rf = peek.classList.contains('is-on') ? requestAnimationFrame(loop) : 0;
    };
    $$('.index-list a', idx).forEach((a) => {
      a.addEventListener('pointerenter', (e) => {
        ph.style.setProperty('--ar', a.dataset.ar); ph.style.aspectRatio = a.dataset.ar;
        ph.style.backgroundImage = `url(${a.dataset.lqip})`; ph.style.setProperty('--c', a.dataset.color);
        im.classList.remove('ld'); im.src = a.dataset.peek; im.onload = () => im.classList.add('ld');
        tx = x = e.clientX; ty = y = e.clientY;
        peek.classList.add('is-on'); if (!rf) rf = requestAnimationFrame(loop);
      });
      a.addEventListener('pointermove', (e) => { tx = e.clientX; ty = e.clientY; });
      a.addEventListener('pointerleave', () => peek.classList.remove('is-on'));
    });
  }
})();

/* ------------------------------------------------------------------ */
/* Lightbox (zoom + pan + swipe)                                       */
/* ------------------------------------------------------------------ */
(function lightbox() {
  const triggers = $$('[data-lb]');
  if (!triggers.length) return;
  const t = (en, zh) => `<span class="en">${en}</span><span class="zh" lang="zh-Hans">${zh}</span>`;
  const lb = document.createElement('div');
  lb.className = 'lb'; lb.setAttribute('role', 'dialog'); lb.setAttribute('aria-modal', 'true'); lb.setAttribute('aria-label', 'Image viewer');
  lb.innerHTML = `
    <div class="lb-top mono"><button type="button" class="lb-close" data-lb-close><i></i><span>${t('Close', '关闭')}</span></button><span class="lb-title dim"></span></div>
    <div class="lb-stage"><img class="lb-img" alt="" draggable="false"></div>
    <div class="lb-bar mono">
      <div class="lb-cap"></div>
      <div class="lb-nav"><button type="button" class="arrow" data-lb-prev aria-label="Previous"><svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg></button><span class="lb-count"></span><button type="button" class="arrow" data-lb-next aria-label="Next"><svg viewBox="0 0 24 24"><path d="M9 5l7 7-7 7"/></svg></button></div>
      <div class="lb-zoom"><button type="button" data-lb-zoom="-">−</button><span class="lb-pct">100%</span><button type="button" data-lb-zoom="+">+</button><button type="button" data-lb-zoom="0">${t('Fit', '适应')}</button></div>
    </div>`;
  document.body.appendChild(lb);
  const stage = $('.lb-stage', lb), img = $('.lb-img', lb), cap = $('.lb-cap', lb), count = $('.lb-count', lb), pct = $('.lb-pct', lb);
  const list = triggers.map((el) => ({
    el, small: el.dataset.small, big: el.dataset.big, w: +el.dataset.w, h: +el.dataset.h,
    en: el.dataset.capEn || '', zh: el.dataset.capZh || '',
  }));
  let i = 0, s = 1, x = 0, y = 0, open = false, lastFocus = null, upgraded = false;
  const pointers = new Map();
  let pinch0 = 0, pinchS = 1, panStart = null, swipe = null;

  const apply = () => {
    img.style.transform = `translate3d(${x}px,${y}px,0) scale(${s})`;
    pct.textContent = Math.round(s * 100) + '%';
  };
  const bound = () => {
    const r = img.getBoundingClientRect(), base = { w: r.width / s, h: r.height / s };
    const sr = stage.getBoundingClientRect();
    const mx = Math.max(0, (base.w * s - sr.width) / 2 + 80), my = Math.max(0, (base.h * s - sr.height) / 2 + 80);
    x = clamp(x, -mx, mx); y = clamp(y, -my, my);
    if (s <= 1.001) { x = 0; y = 0; }
  };
  const zoomAt = (ns, cx, cy) => {
    ns = clamp(ns, 1, 6);
    const sr = stage.getBoundingClientRect(), ox = cx - (sr.left + sr.width / 2), oy = cy - (sr.top + sr.height / 2);
    x = ox - (ox - x) * (ns / s); y = oy - (oy - y) * (ns / s); s = ns;
    if (s > 1.25 && !upgraded) { upgraded = true; const b = list[i].big; if (b && img.src !== b) { const pre = new Image(); pre.onload = () => { if (open) img.src = b; }; pre.src = b; } }
    bound(); apply();
  };
  const show = (n, dir = 0) => {
    i = (n + list.length) % list.length; s = 1; x = 0; y = 0; upgraded = false;
    const it = list[i];
    img.style.opacity = '0';
    const src = it.small || it.big;
    const done = () => { img.style.opacity = '1'; };
    img.onload = done; img.src = src; img.alt = lang() === 'zh' ? it.zh : it.en;
    if (img.complete) done();
    cap.innerHTML = `<span class="en">${it.en}</span><span class="zh" lang="zh-Hans">${it.zh}</span>`;
    count.textContent = `${String(i + 1).padStart(2, '0')} / ${String(list.length).padStart(2, '0')}`;
    apply();
    [i + 1, i - 1].forEach((k) => { const o = list[(k + list.length) % list.length]; if (o) { const p = new Image(); p.src = o.small || o.big; } });
  };
  const openAt = (n, from) => {
    if (open) return; open = true; lastFocus = from || document.activeElement;
    lb.classList.add('is-open'); root.style.overflow = 'hidden';
    requestAnimationFrame(() => lb.classList.add('is-vis'));
    show(n); $('[data-lb-close]', lb).focus({ preventScroll: true });
  };
  const close = () => {
    if (!open) return; open = false; lb.classList.remove('is-vis'); root.style.overflow = '';
    setTimeout(() => { if (!open) lb.classList.remove('is-open'); }, 350);
    lastFocus?.focus?.({ preventScroll: true });
  };
  triggers.forEach((el, n) => {
    el.addEventListener('click', (e) => { e.preventDefault(); openAt(n, el); });
    el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openAt(n, el); } });
  });
  lb.addEventListener('click', (e) => {
    if (e.target.closest('[data-lb-close]')) return close();
    if (e.target.closest('[data-lb-prev]')) return show(i - 1);
    if (e.target.closest('[data-lb-next]')) return show(i + 1);
    const z = e.target.closest('[data-lb-zoom]');
    if (z) { const r = stage.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2; if (z.dataset.lbZoom === '0') { s = 1; x = y = 0; apply(); } else zoomAt(s * (z.dataset.lbZoom === '+' ? 1.4 : 1 / 1.4), cx, cy); }
    if (e.target === stage && s <= 1.01) close();
  });
  stage.addEventListener('wheel', (e) => { e.preventDefault(); zoomAt(s * Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0018)), e.clientX, e.clientY); }, { passive: false });
  stage.addEventListener('dblclick', (e) => { if (s > 1.05) { s = 1; x = y = 0; apply(); } else zoomAt(2.6, e.clientX, e.clientY); });
  stage.addEventListener('pointerdown', (e) => {
    stage.setPointerCapture?.(e.pointerId); pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 2) { const [a, b] = [...pointers.values()]; pinch0 = Math.hypot(a.x - b.x, a.y - b.y); pinchS = s; panStart = null; swipe = null; }
    else if (s > 1.01) { panStart = { x: e.clientX - x, y: e.clientY - y }; stage.classList.add('is-pan'); }
    else if (e.pointerType !== 'mouse') swipe = { x: e.clientX, y: e.clientY };
  });
  stage.addEventListener('pointermove', (e) => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 2) { const [a, b] = [...pointers.values()]; zoomAt(pinchS * Math.hypot(a.x - b.x, a.y - b.y) / pinch0, (a.x + b.x) / 2, (a.y + b.y) / 2); }
    else if (panStart) { x = e.clientX - panStart.x; y = e.clientY - panStart.y; bound(); apply(); }
  });
  const end = (e) => {
    if (swipe && pointers.size === 1) { const dx = e.clientX - swipe.x, dy = e.clientY - swipe.y; if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.4) show(i + (dx < 0 ? 1 : -1)); else if (dy > 120 && Math.abs(dy) > Math.abs(dx) * 1.5) close(); }
    pointers.delete(e.pointerId); panStart = null; swipe = null; stage.classList.remove('is-pan');
  };
  stage.addEventListener('pointerup', end); stage.addEventListener('pointercancel', end);
  addEventListener('keydown', (e) => {
    if (!open) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowRight') show(i + 1);
    else if (e.key === 'ArrowLeft') show(i - 1);
    else if (e.key === '+' || e.key === '=') { const r = stage.getBoundingClientRect(); zoomAt(s * 1.3, r.left + r.width / 2, r.top + r.height / 2); }
    else if (e.key === '-') { const r = stage.getBoundingClientRect(); zoomAt(s / 1.3, r.left + r.width / 2, r.top + r.height / 2); }
    else if (e.key === '0') { s = 1; x = y = 0; apply(); }
    else if (e.key === 'Tab') { const f = $$('button', lb).filter((b) => b.offsetParent); const a = f[0], z = f[f.length - 1]; if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); } else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); } }
  });
  document.addEventListener('langchange', () => { if (open) { const it = list[i]; img.alt = lang() === 'zh' ? it.zh : it.en; } });
})();

/* ------------------------------------------------------------------ */
/* Loupe: inspect the ink, like a printmaker's linen tester            */
/* ------------------------------------------------------------------ */
(function loupe() {
  if (!fine) return;
  const frames = $$('.fig-frame[data-big]');
  if (!frames.length) return;
  const lp = document.createElement('div');
  lp.className = 'loupe'; lp.innerHTML = '<span class="mono"></span>';
  document.body.appendChild(lp);
  const label = $('span', lp);
  let cur = null, nat = 0, z = 2.4, ready = false;
  const cache = new Map();
  const prep = (f) => {
    const url = f.dataset.big; ready = false;
    lp.style.backgroundImage = `url(${f.dataset.lqip || ''})`;
    if (!cache.has(url)) { const im = new Image(); im.onload = () => { cache.set(url, im.naturalWidth); if (cur === f) { nat = im.naturalWidth; lp.style.backgroundImage = `url(${url})`; ready = true; } }; im.src = url; }
    else { nat = cache.get(url); lp.style.backgroundImage = `url(${url})`; ready = true; }
  };
  frames.forEach((f) => {
    f.addEventListener('pointerenter', (e) => { if (e.pointerType !== 'mouse') return; cur = f; prep(f); });
    f.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse' || cur !== f) return;
      const r = f.getBoundingClientRect();
      z = clamp(nat / r.width || 2, 1.5, 2.8);
      label.textContent = '×' + z.toFixed(1);
      const px = e.clientX - r.left, py = e.clientY - r.top;
      lp.style.backgroundSize = `${r.width * z}px ${r.height * z}px`;
      lp.style.backgroundPosition = `${95 - px * z}px ${95 - py * z}px`;
      lp.style.transform = `translate3d(${e.clientX}px,${e.clientY}px,0) scale(1)`;
      lp.classList.toggle('is-on', ready);
    });
    f.addEventListener('pointerleave', () => { cur = null; lp.classList.remove('is-on'); lp.style.transform = lp.style.transform.replace(/scale\([^)]*\)/, 'scale(.6)'); });
  });
  addEventListener('scroll', () => lp.classList.remove('is-on'), { passive: true });
})();

/* ------------------------------------------------------------------ */
/* Process board: hover linking + hand-drawn red thread                */
/* ------------------------------------------------------------------ */
(function board() {
  const grid = $('.board .frames, .frames[data-thread]');
  if (!grid) return;
  const frames = $$('.frame', grid), items = $$('.board-index li');
  const light = (n, on) => { frames[n]?.classList.toggle('is-lit', on); items[n]?.classList.toggle('is-lit', on); };
  frames.forEach((f, n) => {
    f.addEventListener('pointerenter', () => light(n, true));
    f.addEventListener('pointerleave', () => { if (!f.hasAttribute('data-note')) light(n, false); });
    f.addEventListener('focusin', () => light(n, true));
    f.addEventListener('focusout', () => { if (!f.hasAttribute('data-note')) light(n, false); });
  });
  items.forEach((li, n) => {
    li.addEventListener('pointerenter', () => light(n, true));
    li.addEventListener('pointerleave', () => { if (!frames[n].hasAttribute('data-note')) light(n, false); });
    $('button', li)?.addEventListener('click', () => { frames[n].scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' }); $('a,button', frames[n])?.focus({ preventScroll: true }); });
  });
  frames.forEach((f, n) => { if (f.hasAttribute('data-note')) light(n, true); });

  const route = (grid.dataset.thread || '').split(',').map((v) => parseInt(v, 10) - 1).filter((v) => v >= 0);
  if (route.length < 2) return;
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('class', 'thread'); svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(NS, 'path'), head = document.createElementNS(NS, 'path'); head.setAttribute('class', 'head');
  svg.append(path, head); grid.appendChild(svg);
  const draw = () => {
    const g = grid.getBoundingClientRect();
    const pts = route.map((n) => { const r = $('.ph', frames[n]).getBoundingClientRect(); return [r.left - g.left + r.width * (0.5), r.top - g.top + r.height * 0.5]; });
    let d = `M${pts[0][0]} ${pts[0][1]}`;
    for (let k = 1; k < pts.length; k++) {
      const [x0, y0] = pts[k - 1], [x1, y1] = pts[k], mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
      const nx = -(y1 - y0), ny = x1 - x0, l = Math.hypot(nx, ny) || 1, bend = Math.min(60, l * .22) * (k % 2 ? 1 : -1);
      d += ` Q${mx + nx / l * bend} ${my + ny / l * bend} ${x1} ${y1}`;
    }
    path.setAttribute('d', d);
    path.style.setProperty('--len', Math.ceil(path.getTotalLength()) + 2);
    const L = path.getTotalLength(), a = path.getPointAtLength(L - 1), b = path.getPointAtLength(Math.max(0, L - 18));
    const ang = Math.atan2(a.y - b.y, a.x - b.x), s = 11;
    head.setAttribute('d', `M${a.x - Math.cos(ang - .45) * s} ${a.y - Math.sin(ang - .45) * s} L${a.x} ${a.y} L${a.x - Math.cos(ang + .45) * s} ${a.y - Math.sin(ang + .45) * s}`);
  };
  draw();
  let t; new ResizeObserver(() => { clearTimeout(t); t = setTimeout(draw, 120); }).observe(grid);
  addEventListener('load', draw);
})();

/* ------------------------------------------------------------------ */
/* Video: lazy YouTube + looping local video                           */
/* ------------------------------------------------------------------ */
(function video() {
  $$('[data-yt]').forEach((box) => {
    const id = box.dataset.yt, poster = $('.yt-poster', box), btn = $('.play', box);
    if (poster) poster.addEventListener('load', () => { if (poster.naturalWidth && poster.naturalWidth < 400 && !poster.dataset.fb) { poster.dataset.fb = '1'; poster.src = `https://i.ytimg.com/vi/${id}/hqdefault.jpg`; } });
    btn?.addEventListener('click', () => {
      const f = document.createElement('iframe');
      f.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0&modestbranding=1&playsinline=1`;
      f.title = box.dataset.title || 'Video';
      f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen'; f.allowFullscreen = true; f.referrerPolicy = 'strict-origin-when-cross-origin';
      box.append(f); poster?.remove(); btn.remove();
    });
  });
  $$('video[data-loop]').forEach((v) => {
    if (reduce) { v.controls = true; return; }
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) v.play().catch(() => {}); else v.pause(); }), { threshold: .4 });
    io.observe(v);
    v.addEventListener('click', () => (v.paused ? v.play() : v.pause()));
  });
})();

/* ------------------------------------------------------------------ */
/* Shared-element page transitions (Chromium): cover <-> work         */
/* ------------------------------------------------------------------ */
(function transitions() {
  if (!('PageSwapEvent' in window) && !('onpageswap' in window)) return;
  const slugOf = (u) => { const m = new URL(u, location.href).pathname.match(/\/works\/([^/]+)/); return m ? m[1] : null; };
  const plateFor = (slug) => $$('.plate a').find((a) => slugOf(a.href) === slug)?.querySelector('.ph') || null;
  const heroHere = () => $('.fig-frame') || null;
  addEventListener('pageswap', (e) => {
    if (!e.viewTransition || !e.activation?.entry) return;
    const to = e.activation.entry.url, s = slugOf(to);
    const target = location.pathname.includes('/works/') ? heroHere() : (s ? plateFor(s) : null);
    if (target) target.style.viewTransitionName = 'hero-img';
  });
  addEventListener('pagereveal', (e) => {
    if (!e.viewTransition) return;
    const from = navigation.activation?.from?.url;
    let target = null;
    if (location.pathname.includes('/works/')) target = heroHere();
    else if (from) { const s = slugOf(from); if (s) target = plateFor(s); }
    if (target) { target.style.viewTransitionName = 'hero-img'; e.viewTransition.finished.finally(() => { target.style.viewTransitionName = ''; }); }
  });
})();


/* ---------------------------------------------------------------------------
   work text: on small screens, fold long descriptions so the images stay close
   --------------------------------------------------------------------------- */
(function descFold() {
  const d = document.querySelector('.work-desc');
  if (!d) return;
  const mq = matchMedia('(max-width: 900px)');
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'desc-more mono';
  const label = (open) => {
    btn.innerHTML = open
      ? '<span class="en">Show less ↑</span><span class="zh" lang="zh-Hans">收起 ↑</span>'
      : '<span class="en">Read more ↓</span><span class="zh" lang="zh-Hans">展开全文 ↓</span>';
    btn.setAttribute('aria-expanded', String(open));
  };
  const apply = () => {
    d.classList.remove('is-clamped');
    btn.remove();
    if (!mq.matches || d.scrollHeight < 300) return;
    d.classList.add('is-clamped');
    d.after(btn);
    label(false);
  };
  btn.addEventListener('click', () => label(!d.classList.toggle('is-clamped')));
  apply();
  mq.addEventListener('change', apply);
})();
