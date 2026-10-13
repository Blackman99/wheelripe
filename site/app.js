(() => {
  'use strict';
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches || /[?&]still\b/.test(location.search);
  const $ = (s, r = document) => r.querySelector(s);
  const hero = $('#top'), svg = $('#cheese'), layer = $('#eyes'), slip = $('#slip');
  const NS = 'http://www.w3.org/2000/svg';
  const state = { py: '3.15', os: 'linux-x86_64' };
  const OSNAME = { 'linux-x86_64': 'Linux x86_64', 'macos-arm64': 'macOS arm64', 'windows-amd64': 'Windows amd64' };
  const WORD = { ready: 'READY — installs from a wheel', bump: 'BUMP', blocked: 'BLOCKED — no release has a wheel yet',
    excluded: 'EXCLUDED — requires-python', build: 'BUILD — sdist only', skip: 'SKIP — marker', missing: 'MISSING' };
  let data = null, eyes = [], geo = null, introDone = reduce;

  // deterministic RNG so the cheese looks the same on every visit
  const rng = (seed) => () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
  const el = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); return n; };

  function geometry() {
    const W = hero.clientWidth, H = hero.clientHeight, mobile = W < 760, e = 12;
    const a = mobile ? 0.21 : 0.07, c = mobile ? 0.34 : 0.66;
    const A = [W + e, a * H], C = [-e, c * H];
    const slopeY = (x) => C[1] + (A[1] - C[1]) * (x - C[0]) / (A[0] - C[0]);
    return { W, H, mobile, e, A, C, slopeY, rind: mobile ? 16 : Math.max(22, W * 0.025) };
  }

  function drawCheese(clipX) {
    const g = geo; svg.setAttribute('viewBox', `0 0 ${g.W} ${g.H}`);
    svg.textContent = '';
    const defs = el('defs', {});
    const cp = el('clipPath', { id: 'wire' });
    const cr = el('rect', { x: clipX == null ? -g.e : clipX, y: -g.e, width: g.W + 2 * g.e, height: g.H + 2 * g.e });
    cp.appendChild(cr); defs.appendChild(cp); svg.appendChild(defs);
    const face = el('g', { 'clip-path': 'url(#wire)' });
    const { W, H, e, A, C } = g;
    face.appendChild(el('path', { d: `M${A[0]} ${A[1]} L${W + e} ${H + e} L${-e} ${H + e} L${C[0]} ${C[1]} Z`, fill: '#ffd978' }));
    const rx = W - g.rind;
    face.appendChild(el('path', { d: `M${rx} ${g.slopeY(rx)} L${A[0]} ${A[1]} L${W + e} ${H + e} L${rx} ${H + e} Z`, fill: '#a8471a' }));
    // closed pores: the paste's texture
    const r = rng(7);
    for (let i = 0; i < (g.mobile ? 26 : 60); i++) {
      const x = r() * (rx - 20) + 10, y0 = g.slopeY(x) + 18, y = y0 + r() * (H - y0 - 10);
      if (y > H - 6) continue;
      const s = 2 + r() * 4.5;
      face.appendChild(el('ellipse', { cx: x.toFixed(1), cy: y.toFixed(1), rx: s.toFixed(1), ry: (s * 0.7).toFixed(1), fill: '#a8471a', opacity: '.38' }));
    }
    svg.appendChild(face);
    g.clipRect = cr;
    if (clipX != null) {
      g.wire = el('g', {});
      g.wire.appendChild(el('line', { x1: 0, y1: 0, x2: 0, y2: 0, stroke: '#2a160b', 'stroke-width': 2.5 }));
      g.wire.appendChild(el('rect', { width: 14, height: 34, rx: 7, fill: '#2a160b' }));
      svg.appendChild(g.wire);
    }
  }

  function moveWire(x) {
    const g = geo; g.clipRect.setAttribute('x', x);
    if (!g.wire) return;
    const y1 = g.slopeY(Math.min(g.W, x + 40)) - 30, x1 = x + 40, x2 = x - 40, y2 = g.H + 4;
    const line = g.wire.firstChild; line.setAttribute('x1', x1); line.setAttribute('y1', y1); line.setAttribute('x2', x2); line.setAttribute('y2', y2);
    const knob = g.wire.lastChild; knob.setAttribute('x', x1 - 7); knob.setAttribute('y', y1 - 34);
  }

  function rectOf(node, pad) {
    const h = hero.getBoundingClientRect(), b = node.getBoundingClientRect();
    return [b.left - h.left - pad, b.top - h.top - pad, b.right - h.left + pad, b.bottom - h.top + pad];
  }

  function placeEyes() {
    const g = geo, n = eyes.length;
    // reserve room for the longest headline / verdict any dial setting can produce
    $('#h1py').textContent = 'free-threaded\u00a03.15t';
    $('#verdict').innerHTML = '<b>NOT RIPE</b> 16 blocked · 16 need a bump · 16 ready (Windows amd64)';
    const avoid = [rectOf($('.face-copy'), 14), rectOf($('.dial'), 22), rectOf($('.topnav'), 8)];
    const right = g.W - g.rind - 6, bottom = g.H - g.W * 0.06 - (g.mobile ? 12 : 24);
    const hit = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
    const base = g.mobile ? 44 : Math.min(72, Math.max(54, g.W / 24));
    let best = null;
    for (const scale of [1, 0.86, 0.74, 0.64]) {
      const d = Math.round(base * scale);
      eyes.forEach((e) => {
        e.style.setProperty('--d', d + 'px');
        e.style.fontSize = scale < 0.8 ? '.68rem' : '';
        let longest = '';
        for (const t in data.v) for (const o in data.v[t]) { const f = data.v[t][o][e.dataset.pkg]; if (f && f[1] && f[1].length + 2 > longest.length) longest = '→ ' + f[1]; }
        e.querySelector('.fix').textContent = longest;
      });
      const size = eyes.map((e) => [e.offsetWidth, e.offsetHeight]);
      for (let pad = g.mobile ? 8 : 20; pad >= -4; pad -= 4) {
        const r = rng(42), boxes = [], pts = [];
        for (let i = 0; i < n; i++) {
          const [w, h] = size[i];
          let got = null;
          for (let t = 0; t < 2500 && !got; t++) {
            const x = w / 2 + 6 + r() * (right - w - 12), y = h / 2 + r() * (bottom - h);
            const box = [x - w / 2 - pad, y - h / 2 - pad, x + w / 2 + pad, y + h / 2 + pad];
            const inner = [x - w / 2, y - h / 2, x + w / 2, y + h / 2];
            if (inner[1] < g.slopeY(inner[0]) + 6 || inner[1] < g.slopeY(inner[2]) + 6) continue;
            if (avoid.some((a) => hit(inner, a)) || boxes.some((b) => hit(box, b))) continue;
            got = [x, y, box];
          }
          if (!got) break;
          boxes.push(got[2]); pts.push([got[0], got[1]]);
        }
        if (!best || pts.length > best.length) best = pts;
        if (pts.length === n) break;
      }
      if (best && best.length === n) break;
    }
    const order = best.map((p, i) => [p[0], i]).sort((p, q) => q[0] - p[0]);
    order.forEach(([, i], k) => { eyes[i].dataset.order = k; });
    eyes.forEach((eye, i) => {
      const p = best[i];
      eye.hidden = !p;  // only if the face is far too small for every eye
      if (p) { eye.style.left = p[0].toFixed(0) + 'px'; eye.style.top = p[1].toFixed(0) + 'px'; }
    });
    update();
  }

  function buildEyes() {
    layer.textContent = '';
    eyes = data.packages.map((name) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'eye' + (reduce ? '' : ' pending'); b.setAttribute('role', 'listitem');
      b.dataset.pkg = name;
      b.innerHTML = '<span class="hole"></span><span class="name"></span><span class="fix"></span>';
      b.querySelector('.name').textContent = name;
      b.addEventListener('mouseenter', () => showSlip(b)); b.addEventListener('focus', () => showSlip(b));
      b.addEventListener('mouseleave', hideSlip); b.addEventListener('blur', hideSlip);
      b.addEventListener('click', () => showSlip(b));
      layer.appendChild(b); return b;
    });
  }

  function verdictFor(name) { return data.v[state.py][state.os][name] || ['missing']; }

  function update() {
    if (!data) return;
    let blocked = 0, bump = 0, ready = 0;
    eyes.forEach((b) => {
      const [st, fix] = verdictFor(b.dataset.pkg);
      b.dataset.st = st;
      b.querySelector('.fix').textContent = fix ? '→ ' + fix : '';
      if (st === 'blocked' || st === 'excluded') blocked++; else if (st === 'bump') bump++; else if (st === 'ready') ready++;
      b.setAttribute('aria-label', `${b.dataset.pkg} ${data.pins[b.dataset.pkg]}: ${st}${fix ? ', fixed by ' + fix : ''}`);
    });
    const py = state.py.endsWith('t') ? `free-threaded\u00a0${state.py}` : `Python\u00a0${state.py}`;
    $('#h1py').textContent = py;
    const v = $('#verdict');
    if (!blocked && !bump) v.innerHTML = `<b>RIPE</b> all ${eyes.length} install from wheels on ${state.py} · ${OSNAME[state.os]}`;
    else v.innerHTML = `<b>NOT RIPE</b> ${blocked} blocked · ${bump} need a bump · ${ready} ready <span class="small">(${OSNAME[state.os]})</span>`;
    if (slip.dataset.pkg) { const b = eyes.find((x) => x.dataset.pkg === slip.dataset.pkg); if (b) showSlip(b); }
    slicerRender();
  }

  function showSlip(b) {
    const [st, fix] = verdictFor(b.dataset.pkg);
    slip.dataset.pkg = b.dataset.pkg;
    slip.innerHTML = '';
    const t = document.createElement('b'); t.textContent = `${b.dataset.pkg} ${data.pins[b.dataset.pkg]}`; slip.appendChild(t);
    const s = document.createElement('span'); s.className = 'st';
    s.textContent = st === 'bump' ? `BUMP → ${fix}: first release with a wheel` : WORD[st] || st; slip.appendChild(s);
    const p = document.createElement('div'); p.textContent = `CPython ${state.py} · ${OSNAME[state.os]}`; slip.appendChild(p);
    slip.hidden = false;
    const x = parseFloat(b.style.left), y = parseFloat(b.style.top), w = slip.offsetWidth;
    slip.style.left = Math.max(8, Math.min(geo.W - w - 8, x + 24)) + 'px';
    slip.style.top = Math.max(8, y - slip.offsetHeight - 30) + 'px';
  }
  function hideSlip() { slip.hidden = true; delete slip.dataset.pkg; }

  function reveal() {
    const order = [...eyes].sort((p, q) => p.dataset.order - q.dataset.order);
    order.forEach((b, i) => setTimeout(() => b.classList.remove('pending'), 60 * i));
  }

  function intro() {
    if (reduce) { drawCheese(null); return; }
    drawCheese(geo.W + geo.e);
    const t0 = performance.now(), dur = 1100;
    const step = (t) => {
      const k = Math.min(1, (t - t0) / dur), ease = 1 - Math.pow(1 - k, 3);
      moveWire(geo.W + geo.e - ease * (geo.W + 3 * geo.e + 60));
      if (k < 1) requestAnimationFrame(step);
      else { const w = geo.W; geo = geometry(); drawCheese(null); introDone = true; if (data && geo.W !== w) placeEyes(); reveal(); }
    };
    requestAnimationFrame(step);
  }

  // ---- wheel filename slicer: same tag rules as wheelripe/tags.py, trimmed ----
  const EXAMPLES = [
    'msgpack-1.2.3-cp315-cp315t-win_amd64.whl',
    'cryptography-46.0.3-cp311-abi3-manylinux_2_34_x86_64.whl',
    'orjson-3.13.0-cp315-cp315-manylinux_2_39_x86_64.whl',
    'example-1.0-cp315-abi3.abi3t-macosx_11_0_arm64.whl',
  ];
  let ex = 0;
  function judge(file) {
    const [py, abi, plat] = file.slice(0, -4).split('-').slice(-3);
    const ft = state.py.endsWith('t'), minor = parseInt(state.py.split('.')[1], 10);
    const pyMinor = parseInt(py.slice(3), 10);
    const abis = abi.split('.');
    const abiOk = abis.some((a) => (a === 'abi3' && !ft) || (a === 'abi3t' && ft && minor >= 14) ||
      (a === `cp${py.slice(2)}t` && ft) || (a === `cp${py.slice(2)}` && !ft));
    const stable = abis.some((a) => a === 'abi3' || a === 'abi3t');
    const pyOk = stable ? pyMinor <= minor : pyMinor === minor;
    let platOk = false, platWhy;
    const os = state.os;
    const m = plat.match(/^manylinux_(\d+)_(\d+)_(\w+)$/);
    if (m) { platOk = os === 'linux-x86_64' && m[3] === 'x86_64' && (+m[1] < 2 || (+m[1] === 2 && +m[2] <= 34));
      platWhy = os !== 'linux-x86_64' ? `a Linux wheel, you asked for ${OSNAME[os]}` : platOk ? `glibc ${m[1]}.${m[2]} ≤ your floor 2.34` : `needs glibc ${m[1]}.${m[2]}, floor is 2.34 (--glibc)`; }
    else if (plat.startsWith('macosx_')) { const mm = plat.match(/^macosx_(\d+)_(\d+)_(\w+)$/);
      platOk = os === 'macos-arm64' && ['arm64', 'universal2'].includes(mm[3]) && +mm[1] <= 14;
      platWhy = os !== 'macos-arm64' ? `a macOS wheel, you asked for ${OSNAME[os]}` : `macOS ${mm[1]} ≤ your floor 14`; }
    else if (plat.startsWith('win')) { platOk = os === 'windows-amd64' && plat === 'win_amd64';
      platWhy = os !== 'windows-amd64' ? `a Windows wheel, you asked for ${OSNAME[os]}` : 'win_amd64 matches'; }
    const abiWhy = abis.includes('abi3') && abis.includes('abi3t') ? 'abi3 + abi3t: GIL and free-threaded' :
      abis[0] === 'abi3' ? (ft ? 'abi3 never loads on free-threaded builds' : 'stable ABI: works on later GIL builds') :
      abis[0].endsWith('t') ? (ft ? 'free-threaded build: matches' : 'free-threaded only — you asked for a GIL build') :
      (ft ? 'GIL build only — you asked for 3.15t' : 'GIL build: matches');
    const pyWhy = stable ? `stable ABI from 3.${pyMinor}: ${pyOk ? 'covers' : 'too new for'} ${state.py}` : `exactly CPython 3.${pyMinor}`;
    return [[ 'python', py, pyOk, pyWhy ], [ 'abi', abi, abiOk, abiWhy ], [ 'platform', plat, platOk, platWhy ]];
  }
  function slicerRender() {
    const file = EXAMPLES[ex], parts = judge(file);
    $('#slicer-file').textContent = file;
    const box = $('#slices'); box.textContent = '';
    parts.forEach(([k, t, ok, why]) => {
      const c = document.createElement('div'); c.className = 'cut' + (ok ? '' : ' no');
      c.innerHTML = '<span class="pit" aria-hidden="true"></span><span class="k"></span><span class="t"></span><span class="why"></span>';
      c.querySelector('.k').textContent = k + (ok ? ' · fits' : ' · hole');
      c.querySelector('.t').textContent = t; c.querySelector('.why').textContent = why;
      box.appendChild(c);
    });
    const all = parts.every((p) => p[2]);
    $('#slicer-out').textContent = all ? `Installs on CPython ${state.py} · ${OSNAME[state.os]}.`
      : `No fit on CPython ${state.py} · ${OSNAME[state.os]} — if no other file fits, that's a hole.`;
  }
  document.querySelectorAll('.slicer-pick button').forEach((b) => b.addEventListener('click', () => {
    ex = +b.dataset.i;
    document.querySelectorAll('.slicer-pick button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    slicerRender();
  }));
  const slicer = $('#slicer');
  if (reduce || !('IntersectionObserver' in window)) slicer.classList.add('open');
  else new IntersectionObserver((ents, ob) => ents.forEach((en) => { if (en.isIntersecting) { slicer.classList.add('open'); ob.disconnect(); } }), { threshold: 0.4 }).observe(slicer);

  // ---- dial ----
  document.querySelectorAll('.seg').forEach((seg) => {
    const btns = [...seg.querySelectorAll('button')];
    btns.forEach((b, i) => {
      b.addEventListener('click', () => { pick(seg, b); });
      b.addEventListener('keydown', (ev) => {
        const d = ev.key === 'ArrowRight' || ev.key === 'ArrowDown' ? 1 : ev.key === 'ArrowLeft' || ev.key === 'ArrowUp' ? -1 : 0;
        if (d) { ev.preventDefault(); const nb = btns[(i + d + btns.length) % btns.length]; nb.focus(); pick(seg, nb); }
      });
      b.tabIndex = b.getAttribute('aria-checked') === 'true' ? 0 : -1;
    });
  });
  function pick(seg, b) {
    seg.querySelectorAll('button').forEach((x) => { const on = x === b; x.setAttribute('aria-checked', String(on)); x.tabIndex = on ? 0 : -1; });
    state[seg.dataset.key] = b.dataset.v; update();
  }

  let rt;
  addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (!introDone && !reduce) return; geo = geometry(); drawCheese(null); placeEyes(); }, 120); });

  slicerRender();
  geo = geometry();
  fetch('data.json').then((r) => r.json()).then((d) => {
    data = d; $('#gen').textContent = d.generated;
    buildEyes(); update(); placeEyes();
    if (introDone) reveal();
    if (document.fonts) document.fonts.ready.then(() => { if (introDone) { geo = geometry(); drawCheese(null); } placeEyes(); });
  }).catch(() => { $('#verdict').textContent = 'Demo data failed to load — run wheelripe yourself.'; });
  intro();
})();
