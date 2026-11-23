/*
 * 대시보드 실행기 — data/*.csv를 읽어 계산(dash.calc)을 돌리고, 화면 조각(dash.draw)을 그린다.
 * index.html의 페이지 코드는 이 파일이 만든 전역 `dash`만 사용한다.
 */
(function () {
  const files = {};        // 데이터셋 id -> CSV 경로 목록 (manifest.json에서 채움)
  const raw = {};          // 데이터셋 id -> {status, data, message}
  const calcs = {};        // 계산 id -> {inputs, fn, title, description}
  const calcVals = {};     // 계산 결과 캐시
  const draws = {};        // 그리기 이름 -> 함수
  const onDataFns = [];
  let params = {};
  let started = false;

  const colors = ['#2f6fdb', '#e8702a', '#1a9e77', '#e6a700', '#d04f8a', '#2a8a3a', '#8a5cd6', '#5f6b7a'];

  function status(id) {
    if (id in calcs) {
      for (const i of calcs[id].inputs) { const s = status(i); if (s !== 'ok') return s; }
      return 'ok';
    }
    return raw[id] ? raw[id].status : (started ? 'missing' : 'loading');
  }

  function value(id) {
    if (id in calcs) {
      if (!(id in calcVals)) {
        const c = calcs[id];
        try { calcVals[id] = c.fn(...c.inputs.map(value)); }
        catch (e) { console.error('계산 실패', id, e); calcVals[id] = []; }
      }
      return calcVals[id];
    }
    return raw[id] && raw[id].status === 'ok' ? raw[id].data : [];
  }

  function runDraw(name, el) {
    const fn = draws[name];
    if (!fn) return;
    try { fn(el); } catch (e) { console.error('그리기 실패', name, e); }
  }

  function redraw() {
    if (!started) return;
    for (const f of onDataFns) { try { f(); } catch (e) { console.error(e); } }
    for (const name of Object.keys(draws)) document.querySelectorAll(`[data-draw="${name}"]`).forEach((el) => runDraw(name, el));
  }

  let pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; redraw(); });
  }

  // 요소 폭이 바뀌면 그 요소만 다시 그린다
  const widths = new WeakMap();
  const ro = new ResizeObserver((entries) => {
    for (const en of entries) {
      const el = en.target, w = Math.round(en.contentRect.width);
      if (widths.get(el) === w) continue;
      widths.set(el, w);
      if (started) runDraw(el.dataset.draw, el);
    }
  });

  window.dash = {
    colors,
    calc(id, o) { calcs[id] = {inputs: o.inputs, fn: o.fn, title: o.title, description: o.description}; },
    data(id) {
      const s = status(id);
      return {status: s, data: s === 'ok' ? value(id) : [], message: raw[id] && raw[id].message, refreshing: false, meta: []};
    },
    draw(name, fn) {
      if (fn) {
        draws[name] = fn;
        document.querySelectorAll(`[data-draw="${name}"]`).forEach((el) => ro.observe(el));
        if (started) document.querySelectorAll(`[data-draw="${name}"]`).forEach((el) => runDraw(name, el));
      } else {
        document.querySelectorAll(`[data-draw="${name}"]`).forEach((el) => runDraw(name, el));
      }
    },
    onData(fn) { onDataFns.push(fn); if (started) fn(); },
    params() { return params; },
    setParams(o) {
      const next = {...params};
      for (const [k, v] of Object.entries(o)) { if (v == null) delete next[k]; else next[k] = v; }
      params = next;
      schedule();
    },
    resetParams() { params = {}; schedule(); },
    refresh() {},
    setLink() {},
  };

  async function loadCsv(paths) {
    const parts = await Promise.all(paths.map(async (p) => {
      const r = await fetch(p, {cache: 'no-cache'});
      if (!r.ok) throw new Error(`${p}: ${r.status}`);
      return d3.csvParse(await r.text());
    }));
    return [].concat(...parts);
  }

  async function start() {
    try {
      const m = await (await fetch('data/manifest.json', {cache: 'no-cache'})).json();
      Object.assign(files, m.datasets);
      document.querySelectorAll('[data-updated]').forEach((el) => { el.textContent = m.updated_kst || ''; });
    } catch (e) {
      console.error('manifest.json을 읽지 못함', e);
    }
    await Promise.all(Object.entries(files).map(async ([id, paths]) => {
      raw[id] = {status: 'loading', data: []};
      try { raw[id] = {status: 'ok', data: await loadCsv(paths)}; }
      catch (e) { console.error(e); raw[id] = {status: 'error', data: [], message: String(e)}; }
    }));
    started = true;
    redraw();
  }

  window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-draw]').forEach((el) => ro.observe(el));
    start();
  });
})();
