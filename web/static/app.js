/* ============================================================
   Thai Budget Analyzer 2566-2569 — frontend
   ============================================================ */
'use strict';

/* ---------------- helpers ---------------- */
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));
/* ปลอดภัยสำหรับส่งสตริงไทยผ่าน inline onclick */
const A = (s) => `decodeURIComponent("${encodeURIComponent(String(s ?? ''))}")`;

const fmtInt = (v) => Number(v ?? 0).toLocaleString('en-US');
const fmtBE = (y) => `พ.ศ. ${(Number(y) + 543).toLocaleString('en-US')}`;
const fmtYear = (y) => `${y} · ${fmtBE(y)}`;

/* ตัวย่อหน่วยเงินไทย */
function fmtTHB(v) {
  v = Number(v ?? 0);
  const neg = v < 0 ? '−' : '';
  const a = Math.abs(v);
  if (a >= 1e12) return `${neg}${(a / 1e12).toLocaleString('en-US', { maximumFractionDigits: 2 })} ล้านล้านบาท`;
  if (a >= 1e9) return `${neg}${(a / 1e9).toLocaleString('en-US', { maximumFractionDigits: 2 })} พันล้านบาท`;
  if (a >= 1e6) return `${neg}${(a / 1e6).toLocaleString('en-US', { maximumFractionDigits: 2 })} ล้านบาท`;
  if (a >= 1e3) return `${neg}${(a / 1e3).toLocaleString('en-US', { maximumFractionDigits: 1 })} พันบาท`;
  return `${neg}${a.toLocaleString('en-US')} บาท`;
}
const fmtTHBFull = (v) => `${Number(v ?? 0).toLocaleString('en-US')} บาท`;
function fmtAxis(v) {
  const a = Math.abs(v);
  if (a >= 1e12) return `${+(a / 1e12).toFixed(2)} ล้านล.`;
  if (a >= 1e9) return `${+(a / 1e9).toFixed(1)} พันล.`;
  if (a >= 1e6) return `${+(a / 1e6).toFixed(0)} ล้าน`;
  if (a >= 1e3) return `${+(a / 1e3).toFixed(0)} พัน`;
  return String(v);
}

const debounce = (fn, ms) => {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
};

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}

let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  requestAnimationFrame(() => t.classList.add('show'));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => t.classList.add('hidden'), 300);
  }, 2600);
}

/* ---------------- modal ---------------- */
function openModal(title, html) {
  $('#modal-title').textContent = title;
  $('#modal-body').innerHTML = html;
  $('#modal-backdrop').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}
function closeModal() {
  $('#modal-backdrop').classList.add('hidden');
  document.body.style.overflow = '';
}

/* ---------------- dq flag labels ---------------- */
const FLAG_LABELS = {
  commitment_year_outside_range: 'ปีนอกช่วง (ภาระผูกพัน)',
  commitment_year_suspect_past: 'ปี ≤2021 น่าสงสัย',
  commitment_year_impossible: 'ปี ≤2005 เป็นไปไม่ได้',
  amount_zero: 'ยอด 0 บาท',
  amount_negative: 'ยอดติดลบ',
  cross_func_filled: 'เติม CROSS_FUNC?',
  ministry_inferred: 'อนุมานกระทรวง',
  category_lv1_unresolved: 'หมวด LV1 ว่าง',
  budget_plan_missing: 'ไม่มีแผนงาน',
  item_description_missing: 'ไม่มีรายละเอียด',
  ref_page_no_invalid: 'เลขหน้าอ้างอิงผิด',
};
const FLAG_CLASS = {
  commitment_year_impossible: 'red',
  amount_negative: 'red',
  commitment_year_suspect_past: 'amber',
  category_lv1_unresolved: 'amber',
  budget_plan_missing: 'amber',
  item_description_missing: 'amber',
  ref_page_no_invalid: 'amber',
};
function flagBadges(flags, max = 3) {
  const list = String(flags || '').split(';').filter(Boolean);
  if (!list.length) return '<span class="muted">—</span>';
  const shown = list.slice(0, max).map(
    (f) => `<span class="badge ${FLAG_CLASS[f] || 'blue'}" title="${esc(f)}">${esc(FLAG_LABELS[f] || f)}</span>`
  ).join(' ');
  return shown + (list.length > max ? ` <span class="badge">+${list.length - max}</span>` : '');
}

/* ---------------- charts ---------------- */
let charts = [];
function killCharts() {
  charts.forEach((c) => { try { c.destroy(); } catch (e) { /* noop */ } });
  charts = [];
}
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const PALETTE = ['#C96442', '#D98A5B', '#E5B87E', '#7FA08E', '#6E93A8',
  '#9A8AB5', '#C9A45C', '#8E7B6B', '#5F8D7B', '#B4766A', '#7A9E9F', '#A8847C'];

function setupCharts() {
  const tick = cssVar('--chart-tick');
  Chart.defaults.font.family = "'Noto Sans Thai', sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = tick;
  Chart.defaults.borderColor = cssVar('--chart-grid');
}
function newChart(id, cfg) {
  const el = document.getElementById(id);
  if (!el) return null;
  const c = new Chart(el, cfg);
  charts.push(c);
  return c;
}
function baseTooltip(fmt = fmtTHBFull) {
  return {
    backgroundColor: 'rgba(35,33,27,.94)',
    titleFont: { family: "'Noto Sans Thai', sans-serif", size: 13, weight: '600' },
    bodyFont: { family: "'Noto Sans Thai', sans-serif", size: 13 },
    padding: 12, cornerRadius: 10, displayColors: false,
    callbacks: { label: (c) => ` ${fmt(c.parsed.y ?? c.parsed.x ?? c.parsed ?? 0)}` },
  };
}
const gridOpts = () => ({ color: cssVar('--chart-grid') });

/* treemap (progressive enhancement — ถ้าโหลดไม่ได้จะ fallback เป็นแท่ง) */
let TREEMAP_OK = false;
try {
  const tm = window['chartjs-chart-treemap'];
  if (tm && tm.TreemapController && tm.TreemapElement) {
    Chart.register(tm.TreemapController, tm.TreemapElement);
    TREEMAP_OK = true;
  }
} catch (e) { TREEMAP_OK = false; }

/* ---------------- state ---------------- */
const state = {
  route: 'overview',
  year: 2026,
  meta: null,
  search: {
    q: '', years: [], ministry: '', cat1: '', plan: '', amt_min: '', amt_max: '',
    obliged: false, cross: false, flagged: false, source: 'all',
    sort: 'AMOUNT', order: 'desc', page: 1, per_page: 50,
  },
  minDetail: null,
  compare: [],
  catPath: [],
  catRowsOpen: false,
  planDetail: null,
  planQ: '',
  comm: { q: '', year: '', ministry: '', page: 1, per_page: 50 },
  quality: { type: '', source: 'all', page: 1, per_page: 50 },
};
let ROWS = []; // แถวล่าสุดสำหรับเปิด modal

const ROUTES = {
  overview: 'ภาพรวม',
  search: 'ค้นหารายการ',
  ministries: 'กระทรวง / หน่วยงาน',
  categories: 'หมวดงบประมาณ',
  plans: 'แผนงาน / ยุทธศาสตร์',
  commitments: 'ภาระผูกพัน',
  quality: 'คุณภาพข้อมูล',
};

/* ---------------- shared builders ---------------- */
function kpiCard(label, value, extra = '', small = false) {
  return `<div class="card"><div class="kpi-label">${label}</div>
    <div class="kpi-value${small ? ' sm' : ''}">${value}</div>${extra}</div>`;
}
function deltaBadge(pct, suffix = 'จากปีก่อน') {
  if (pct === null || pct === undefined || Number.isNaN(pct))
    return `<div><span class="kpi-delta neutral">ไม่มีข้อมูลปีก่อน</span></div>`;
  const cls = pct > 0.005 ? 'up' : pct < -0.005 ? 'down' : 'neutral';
  const arrow = pct > 0.005 ? '▲' : pct < -0.005 ? '▼' : '●';
  const sign = pct > 0 ? '+' : '';
  return `<div><span class="kpi-delta ${cls}">${arrow} ${sign}${pct.toFixed(2)}% ${suffix}</span></div>`;
}

function rankList(items, max, onclick, valFmt = fmtTHB) {
  const top = items.slice(0, max);
  const m = Math.max(...top.map((d) => d.total), 1);
  return `<div class="rank-list">` + top.map((d, i) => `
    <div class="rank-row" onclick="${onclick}(${A(d.name)})" title="${esc(d.name)}&#10;${fmtTHBFull(d.total)}">
      <span class="rank-pos">${i + 1}</span>
      <span class="rank-name">${esc(d.name)}</span>
      <span class="rank-val">${valFmt(d.total)}</span>
      <div class="rank-bar-wrap"><div class="rank-bar" style="width:${(d.total / m * 100).toFixed(1)}%"></div></div>
    </div>`).join('') + `</div>`;
}

function sparkBars(byYear, years) {
  const vals = years.map((y) => byYear[y] || 0);
  const m = Math.max(...vals, 1);
  return `<div class="mini-bars">` + vals.map((v) => {
    const h = Math.max(6, Math.round((v / m) * 100));
    return `<div class="mini-bar${v === m && v > 0 ? ' max' : ''}" style="height:${h}%"></div>`;
  }).join('') + `</div>`;
}

function pagHTML(total, page, perPage, fn) {
  const pages = Math.max(1, Math.ceil(total / perPage));
  const from = total ? (page - 1) * perPage + 1 : 0;
  const to = Math.min(total, page * perPage);
  let nums = [];
  const cand = [1, pages, page - 1, page, page + 1];
  cand.forEach((p) => { if (p >= 1 && p <= pages && !nums.includes(p)) nums.push(p); });
  nums.sort((a, b) => a - b);
  let btns = '';
  let prev = 0;
  nums.forEach((p) => {
    if (p - prev > 1) btns += `<span style="color:var(--text-3)">…</span>`;
    btns += `<button class="page-btn${p === page ? ' active' : ''}" onclick="${fn}(${p})">${p}</button>`;
    prev = p;
  });
  return `<div class="pagination">
    <div class="pagination-info">แสดง ${fmtInt(from)}–${fmtInt(to)} จาก ${fmtInt(total)} รายการ · หน้า ${page}/${pages}</div>
    <div class="pagination-btns">
      <button class="page-btn" ${page <= 1 ? 'disabled' : ''} onclick="${fn}(${page - 1})" aria-label="ก่อนหน้า">
        <svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg></button>
      ${btns}
      <button class="page-btn" ${page >= pages ? 'disabled' : ''} onclick="${fn}(${page + 1})" aria-label="ถัดไป">
        <svg viewBox="0 0 24 24"><path d="M9 6l6-6-6 6"/></svg></button>
    </div></div>`;
}

function emptyHTML(title, sub) {
  return `<div class="empty">
    <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
    <div class="empty-title">${title}</div><div>${sub}</div></div>`;
}

function rowDetailHTML(r) {
  const yrs = Number(r['FISCAL_YEAR']);
  const flagList = String(r.dq_flag || '').split(';').filter(Boolean);
  const flagHTML = flagList.length
    ? flagList.map((f) => `<div style="margin:3px 0"><span class="badge ${FLAG_CLASS[f] || 'blue'}">${esc(FLAG_LABELS[f] || f)}</span>
        <span class="cell-sub" style="margin-left:6px">${esc(f)}</span></div>`).join('')
    : '<span class="muted">ไม่มี</span>';
  const boolBadge = (v) => v === true || v === 'True' || v === '1' || v === 1
    ? '<span class="badge green">ใช่</span>' : '<span class="badge">ไม่ใช่</span>';
  const row = (k, v, num = false) =>
    `<dt>${k}</dt><dd class="${num ? 'num' : ''}">${v}</dd>`;
  return `<dl class="detail-grid">
    ${row('ปีงบประมาณ', `${esc(r['FISCAL_YEAR'])} (${fmtBE(yrs)})`)}
    ${row('แหล่งข้อมูล', r.source === 'commitments'
      ? '<span class="badge amber">ภาระผูกพัน (ปีนอกช่วง)</span>' : '<span class="badge green">ไฟล์หลัก</span>')}
    ${row('กระทรวง', esc(r.MINISTRY))}
    ${row('หน่วยงาน', esc(r.BUDGETARY_UNIT))}
    ${row('รายการ', esc(r.ITEM_DESCRIPTION) || '<span class="muted">—</span>')}
    ${row('แผนงาน', esc(r.BUDGET_PLAN) || '<span class="muted">—</span>')}
    ${row('หมวดงบ LV1', esc(r.CATEGORY_LV1) || '<span class="muted">—</span>')}
    ${row('หมวดงบ LV2', esc(r.CATEGORY_LV2) || '<span class="muted">—</span>')}
    ${row('หมวดงบ LV3', esc(r.CATEGORY_LV3) || '<span class="muted">—</span>')}
    ${row('จำนวนเงิน', fmtTHBFull(r.AMOUNT), true)}
    ${row('ผูกพัน?', boolBadge(r['OBLIGED?']))}
    ${row('ข้ามฟังก์ชัน?', boolBadge(r['CROSS_FUNC?']))}
    ${row('เอกสารอ้างอิง', esc(r.REF_DOC) || '<span class="muted">—</span>')}
    ${row('เลขหน้า', esc(r.REF_PAGE_NO) || '<span class="muted">—</span>')}
    ${row('DQ Flags', flagHTML)}
  </dl>`;
}

function rowsTableHTML(rows, opts = {}) {
  ROWS = rows;
  const showSource = opts.source !== false;
  const head = `<tr><th>ปี</th><th>กระทรวง / หน่วยงาน</th><th>รายการ</th><th>หมวดงบ</th>
    <th class="num">จำนวนเงิน</th>${showSource ? '<th>แหล่ง</th>' : ''}<th>Flags</th></tr>`;
  const body = rows.map((r, i) => {
    const y = Number(r['FISCAL_YEAR']);
    const cls = y <= 2005 && r.source === 'commitments' ? 'row-suspicious'
      : String(r.dq_flag || '') ? 'row-flagged' : '';
    const item = r.ITEM_DESCRIPTION || r.BUDGETARY_UNIT || '(ไม่มีรายละเอียด)';
    return `<tr class="${cls}" onclick="S.showRow(${i})">
      <td style="white-space:nowrap">${esc(r['FISCAL_YEAR'])}<div class="cell-sub">${fmtBE(y)}</div></td>
      <td><div class="cell-main">${esc(r.MINISTRY)}</div><div class="cell-sub">${esc(r.BUDGETARY_UNIT)}</div></td>
      <td style="max-width:340px"><div style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden" title="${esc(item)}">${esc(item)}</div>
        ${r.BUDGET_PLAN ? `<div class="cell-sub">${esc(r.BUDGET_PLAN)}</div>` : ''}</td>
      <td><div class="cell-main" style="font-weight:500">${esc(r.CATEGORY_LV1) || '<span class="muted">—</span>'}</div>
        ${r.CATEGORY_LV2 ? `<div class="cell-sub">${esc(r.CATEGORY_LV2)}</div>` : ''}</td>
      <td class="num"><b>${fmtTHB(r.AMOUNT)}</b><div class="cell-sub">${fmtInt(r.AMOUNT)}</div></td>
      ${showSource ? `<td>${r.source === 'commitments' ? '<span class="badge amber">ผูกพัน</span>' : '<span class="badge green">หลัก</span>'}</td>` : ''}
      <td>${flagBadges(r.dq_flag)}</td>
    </tr>`;
  }).join('');
  return `<div class="table-wrap"><table class="data"><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
}

/* ============================================================
   VIEW: ภาพรวม
   ============================================================ */
async function vOverview() {
  const app = $('#app');
  app.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const d = await api(`/api/overview?year=${state.year}`);
  const k = d.kpis;
  const years = state.meta.years;

  app.innerHTML = `
  <div class="page-head">
    <div class="page-title">ภาพรวมงบประมาณ ${fmtBE(state.year)}</div>
    <div class="page-desc">ข้อมูลงบประมาณรายจ่ายประจำปี ${years.map(fmtBE).join(' · ')} จากเอกสารร่าง พ.ร.บ. งบประมาณ ผ่านการทำความสะอาดข้อมูลแล้ว ${fmtInt(state.meta.counts.main_rows + state.meta.counts.commitments_rows)} รายการ</div>
  </div>

  <div class="grid grid-kpi">
    ${kpiCard(`งบประมาณปี ${state.year + 543}`, fmtTHB(k.total), deltaBadge(k.yoy_pct))}
    ${kpiCard('กระทรวง / หน่วยงานหลัก', fmtInt(k.n_ministries), `<div class="kpi-foot">${fmtInt(k.n_units)} หน่วยงานเบิกจ่าย · ${fmtInt(k.n_plans)} แผนงาน</div>`)}
    ${kpiCard('จำนวนรายการ', fmtInt(k.n_rows), `<div class="kpi-foot">ไฟล์หลักปีนี้ · รวมทุกปี ${fmtTHB(k.total_all_years)}</div>`)}
    ${kpiCard('ภาระผูกพัน (ทุกปี)', fmtTHB(k.comm_total), `<div class="kpi-foot">${fmtInt(k.comm_rows)} รายการ · <a class="link-btn" onclick="S.go('commitments')" style="cursor:pointer">ดูรายละเอียด</a></div>`, true)}
  </div>

  <div class="grid grid-2 section-gap">
    <div class="card card-chart">
      <div class="card-head"><div><div class="card-title">งบประมาณรายปี</div>
        <div class="card-sub">เปรียบเทียบ ${years.map(String).join(' – ')} (หน่วย: บาท)</div></div></div>
      <div class="chart-box chart-med"><canvas id="ch-yearly"></canvas></div>
      <div class="card-sub" style="margin-top:8px">* ปี 2022 มูลค่าน้อยเพราะข้อมูลปีนั้นมีไม่ครบทุกกระทรวง (ดูรายงานคุณภาพข้อมูล)</div>
    </div>
    <div class="card card-chart">
      <div class="card-head"><div><div class="card-title">สัดส่วนหมวดงบประมาณ</div>
        <div class="card-sub">Top 10 หมวดระดับ 1 · ปี ${fmtBE(state.year)}</div></div></div>
      <div class="chart-box chart-med"><canvas id="ch-catpie"></canvas></div>
    </div>
  </div>

  <div class="grid grid-2 section-gap">
    <div class="card">
      <div class="card-head"><div><div class="card-title">กระทรวงงบสูงสุด</div>
        <div class="card-sub">Top 10 · คลิกเพื่อดูรายละเอียดกระทรวง</div></div>
        <button class="btn" onclick="S.go('ministries')">ทั้งหมด</button></div>
      ${rankList(d.top_ministries, 10, 'S.openMinistry')}
    </div>
    <div class="card">
      <div class="card-head"><div><div class="card-title">หน่วยงานงบสูงสุด</div>
        <div class="card-sub">Top 10 · คลิกเพื่อค้นหารายการของหน่วยงาน</div></div></div>
      ${rankList(d.top_units, 10, 'S.searchUnit')}
    </div>
  </div>

  <div class="grid grid-2 section-gap">
    <div class="card">
      <div class="card-head"><div><div class="card-title">แผนงานงบสูงสุด</div>
        <div class="card-sub">Top 10 · คลิกเพื่อดูรายละเอียดแผนงาน</div></div>
        <button class="btn" onclick="S.go('plans')">ทั้งหมด</button></div>
      ${rankList(d.top_plans, 10, 'S.openPlan')}
    </div>
    <div class="card card-chart">
      <div class="card-head"><div><div class="card-title">การกระจายของวงเงินรายการ</div>
        <div class="card-sub">จำนวนรายการตามช่วงวงเงิน · ปี ${fmtBE(state.year)}</div></div></div>
      <div class="chart-box chart-med"><canvas id="ch-dist"></canvas></div>
    </div>
  </div>

  <div class="card section-gap">
    <div class="card-head"><div><div class="card-title">ภาระผูกพันรายปี (Top 10 ปีที่มียอดสูงสุด)</div>
      <div class="card-sub">ข้อมูลปีนอกช่วง 2022–2026 ถูกแยกไว้ต่างหาก · <a class="link-btn" onclick="S.go('commitments')" style="cursor:pointer">ดูทั้งหมด</a></div></div></div>
    <div class="chart-box chart-short"><canvas id="ch-comm"></canvas></div>
  </div>

  <div class="footer-note">ข้อมูล: output/budget_2566-2569_clean.csv.gz + commitments · clean เมื่อ 2026-10-09 · ไฟล์ต้นฉบับไม่ถูกแก้ไข</div>`;

  setupCharts();
  /* yearly */
  newChart('ch-yearly', {
    type: 'bar',
    data: {
      labels: d.yearly.map((r) => `${r.year}\n(${r.year + 543})`),
      datasets: [{
        data: d.yearly.map((r) => r.total),
        backgroundColor: d.yearly.map((r) => r.year === state.year ? '#C96442' : '#E4CDBB'),
        hoverBackgroundColor: '#C96442',
        borderRadius: 8, borderSkipped: false, maxBarThickness: 90,
      }],
    },
    options: {
      plugins: { legend: { display: false }, tooltip: baseTooltip() },
      scales: {
        y: { grid: gridOpts(), ticks: { callback: fmtAxis } },
        x: { grid: { display: false } },
      },
      onClick: (_, els) => {
        if (els.length) S.setYear(d.yearly[els[0].index].year);
      },
    },
  });
  /* category pie */
  const cats = d.categories_lv1.slice(0, 10);
  newChart('ch-catpie', {
    type: 'doughnut',
    data: {
      labels: cats.map((c) => c.name || '(ไม่ระบุ)'),
      datasets: [{ data: cats.map((c) => c.total), backgroundColor: cats.map((_, i) => PALETTE[i % PALETTE.length]), borderWidth: 2, borderColor: cssVar('--card') }],
    },
    options: {
      cutout: '58%',
      plugins: {
        legend: { position: 'right', labels: { boxWidth: 12, boxHeight: 12, borderRadius: 3, useBorderRadius: true, padding: 10, font: { size: 11 } } },
        tooltip: { ...baseTooltip(), callbacks: { label: (c) => ` ${fmtTHBFull(c.parsed)} (${cats[c.dataIndex].share}%)` } },
      },
    },
  });
  /* distribution */
  newChart('ch-dist', {
    type: 'bar',
    data: {
      labels: d.distribution.labels,
      datasets: [{ data: d.distribution.counts, backgroundColor: '#7FA08E', borderRadius: 4, borderSkipped: false }],
    },
    options: {
      plugins: { legend: { display: false }, tooltip: { ...baseTooltip(), callbacks: { label: (c) => ` ${fmtInt(c.parsed.y)} รายการ` } } },
      scales: { y: { grid: gridOpts(), ticks: { callback: (v) => fmtInt(v) } }, x: { grid: { display: false }, ticks: { maxRotation: 60, minRotation: 45, font: { size: 10 } } } },
    },
  });
  /* commitments */
  const cy = d.comm_yearly.slice(0, 10);
  newChart('ch-comm', {
    type: 'bar',
    data: {
      labels: cy.map((r) => String(r.year)),
      datasets: [{ data: cy.map((r) => r.total), backgroundColor: '#9A8AB5', borderRadius: 6, borderSkipped: false, maxBarThickness: 60 }],
    },
    options: {
      plugins: { legend: { display: false }, tooltip: baseTooltip() },
      scales: { y: { grid: gridOpts(), ticks: { callback: fmtAxis } }, x: { grid: { display: false } } },
      onClick: () => S.go('commitments'),
    },
  });
}

/* ============================================================
   VIEW: ค้นหา
   ============================================================ */
function vSearchShell() {
  const s = state.search;
  const m = state.meta;
  const yearChips = m.years.map((y) =>
    `<button class="chip${s.years.includes(y) ? ' active' : ''}" onclick="S.toggleYear(${y})">${y + 543}</button>`).join('');
  const minOpts = `<option value="">ทุกกระทรวง</option>` +
    m.ministries.map((x) => `<option value="${esc(x)}"${s.ministry === x ? ' selected' : ''}>${esc(x)}</option>`).join('');
  const catOpts = `<option value="">ทุกหมวด</option>` +
    m.cat_lv1.map((x) => `<option value="${esc(x)}"${s.cat1 === x ? ' selected' : ''}>${esc(x)}</option>`).join('');
  const planList = m.plans.map((x) => `<option value="${esc(x)}">`).join('');

  $('#app').innerHTML = `
  <div class="page-head">
    <div class="page-title">ค้นหารายการงบประมาณ</div>
    <div class="page-desc">ค้นหาทุกข้อความใน ${fmtInt(m.counts.main_rows + m.counts.commitments_rows)} รายการ (ไฟล์หลัก + ภาระผูกพัน) — กระทรวง หน่วยงาน รายการ แผนงาน ยุทธศาสตร์ หมวดงบ</div>
  </div>
  <div class="searchbar">
    <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
    <input class="input input-lg" id="f-q" placeholder="พิมพ์คำค้น เช่น ถนนคอนกรีต, กองทุนหมู่บ้าน, ไซเบอร์…" value="${esc(s.q)}">
  </div>
  <div class="filter-panel">
    <div class="field"><span class="field-label">ปีงบประมาณ (พ.ศ. — ไม่เลือก = ทุกปี)</span>
      <div class="chip-row">${yearChips}</div></div>
    <div class="field"><span class="field-label">กระทรวง</span>
      <select class="select" id="f-ministry">${minOpts}</select></div>
    <div class="field"><span class="field-label">หมวดงบ LV1</span>
      <select class="select" id="f-cat1">${catOpts}</select></div>
    <div class="field"><span class="field-label">แผนงาน (พิมพ์เพื่อเลือก)</span>
      <input class="input" id="f-plan" list="plan-list" placeholder="ทุกแผนงาน" value="${esc(s.plan)}">
      <datalist id="plan-list">${planList}</datalist></div>
    <div class="field"><span class="field-label">วงเงินขั้นต่ำ (บาท)</span>
      <input class="input" id="f-min" inputmode="numeric" placeholder="เช่น 1000000" value="${esc(s.amt_min)}"></div>
    <div class="field"><span class="field-label">วงเงินสูงสุด (บาท)</span>
      <input class="input" id="f-max" inputmode="numeric" placeholder="เช่น 50000000" value="${esc(s.amt_max)}"></div>
    <div class="field"><span class="field-label">แหล่งข้อมูล</span>
      <div class="chip-row">
        <button class="chip${s.source === 'all' ? ' active' : ''}" onclick="S.setSource('all')">ทั้งหมด</button>
        <button class="chip${s.source === 'main' ? ' active' : ''}" onclick="S.setSource('main')">ไฟล์หลัก</button>
        <button class="chip${s.source === 'commitments' ? ' active' : ''}" onclick="S.setSource('commitments')">ภาระผูกพัน</button>
      </div></div>
    <div class="field"><span class="field-label">ตัวเลือก</span>
      <div style="display:flex;gap:14px;flex-wrap:wrap;padding-top:6px">
        <label class="check"><input type="checkbox" id="f-obliged"${s.obliged ? ' checked' : ''}> ผูกพันเท่านั้น</label>
        <label class="check"><input type="checkbox" id="f-cross"${s.cross ? ' checked' : ''}> ข้ามฟังก์ชัน</label>
        <label class="check"><input type="checkbox" id="f-flagged"${s.flagged ? ' checked' : ''}> มี DQ flag</label>
      </div></div>
  </div>
  <div class="filter-row">
    <div class="field" style="min-width:170px"><span class="field-label">เรียงตาม</span>
      <select class="select" id="f-sort">
        ${[['AMOUNT', 'จำนวนเงิน'], ['FISCAL_YEAR', 'ปีงบประมาณ'], ['MINISTRY', 'กระทรวง'], ['BUDGETARY_UNIT', 'หน่วยงาน'], ['ITEM_DESCRIPTION', 'รายการ']]
          .map(([v, l]) => `<option value="${v}"${s.sort === v ? ' selected' : ''}>${l}</option>`).join('')}
      </select></div>
    <div class="field" style="min-width:130px"><span class="field-label">ลำดับ</span>
      <select class="select" id="f-order">
        <option value="desc"${s.order === 'desc' ? ' selected' : ''}>มาก → น้อย</option>
        <option value="asc"${s.order === 'asc' ? ' selected' : ''}>น้อย → มาก</option>
      </select></div>
    <div class="field" style="min-width:120px"><span class="field-label">ต่อหน้า</span>
      <select class="select" id="f-perpage">
        ${[25, 50, 100, 200].map((v) => `<option${s.per_page === v ? ' selected' : ''}>${v}</option>`).join('')}
      </select></div>
    <div style="flex:1"></div>
    <button class="btn" onclick="S.resetSearch()">ล้างตัวกรอง</button>
    <button class="btn btn-primary" onclick="S.doSearch()">
      <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>ค้นหา</button>
  </div>
  <div id="search-results" style="margin-top:18px"><div class="loading"><div class="spinner"></div></div></div>`;

  $('#f-q').addEventListener('input', debounce(() => { state.search.q = $('#f-q').value; state.search.page = 1; runSearch(); }, 450));
  $('#f-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') S.doSearch(); });
  $('#f-ministry').addEventListener('change', (e) => { state.search.ministry = e.target.value; state.search.page = 1; runSearch(); });
  $('#f-cat1').addEventListener('change', (e) => { state.search.cat1 = e.target.value; state.search.page = 1; runSearch(); });
  $('#f-plan').addEventListener('change', (e) => { state.search.plan = e.target.value; state.search.page = 1; runSearch(); });
  $('#f-min').addEventListener('change', (e) => { state.search.amt_min = e.target.value.replace(/,/g, ''); state.search.page = 1; runSearch(); });
  $('#f-max').addEventListener('change', (e) => { state.search.amt_max = e.target.value.replace(/,/g, ''); state.search.page = 1; runSearch(); });
  $('#f-obliged').addEventListener('change', (e) => { state.search.obliged = e.target.checked; state.search.page = 1; runSearch(); });
  $('#f-cross').addEventListener('change', (e) => { state.search.cross = e.target.checked; state.search.page = 1; runSearch(); });
  $('#f-flagged').addEventListener('change', (e) => { state.search.flagged = e.target.checked; state.search.page = 1; runSearch(); });
  $('#f-sort').addEventListener('change', (e) => { state.search.sort = e.target.value; runSearch(); });
  $('#f-order').addEventListener('change', (e) => { state.search.order = e.target.value; runSearch(); });
  $('#f-perpage').addEventListener('change', (e) => { state.search.per_page = Number(e.target.value); state.search.page = 1; runSearch(); });
}

function searchQuery(page) {
  const s = state.search;
  const p = new URLSearchParams();
  if (s.q) p.set('q', s.q);
  if (s.years.length) p.set('years', s.years.join(','));
  if (s.ministry) p.set('ministry', s.ministry);
  if (s.cat1) p.set('cat1', s.cat1);
  if (s.plan) p.set('plan', s.plan);
  if (s.amt_min !== '') p.set('amt_min', s.amt_min);
  if (s.amt_max !== '') p.set('amt_max', s.amt_max);
  if (s.obliged) p.set('obliged', 'true');
  if (s.cross) p.set('cross', 'true');
  if (s.flagged) p.set('flagged', 'true');
  p.set('source', s.source);
  p.set('sort', s.sort);
  p.set('order', s.order);
  p.set('page', page || s.page);
  p.set('per_page', s.per_page);
  return p.toString();
}

async function runSearch() {
  const box = $('#search-results');
  if (!box) return;
  box.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  try {
    const d = await api(`/api/search?${searchQuery()}`);
    state.search.page = d.page;
    if (!d.total) {
      box.innerHTML = emptyHTML('ไม่พบรายการ', 'ลองเปลี่ยนคำค้นหรือล้างตัวกรอง');
      return;
    }
    box.innerHTML = `
      <div class="card" style="margin-bottom:14px"><div class="stat-inline">
        <div class="si"><b>${fmtInt(d.total)}</b><span>รายการที่พบ</span></div>
        <div class="si"><b>${fmtTHB(d.sum)}</b><span>รวมวงเงิน (${fmtTHBFull(d.sum)})</span></div>
        <div style="flex:1"></div>
        <div style="align-self:center"><button class="btn btn-primary" onclick="S.exportCSV()">
          <svg viewBox="0 0 24 24"><path d="M12 3v12M7 10l5 5 5-5M4 21h16"/></svg>ส่งออก CSV</button></div>
      </div></div>
      ${rowsTableHTML(d.rows)}
      ${pagHTML(d.total, d.page, d.per_page, 'S.searchPage')}`;
  } catch (e) {
    box.innerHTML = emptyHTML('เกิดข้อผิดพลาด', 'โหลดข้อมูลไม่สำเร็จ กรุณาลองใหม่');
  }
}

async function vSearch() {
  killCharts();
  vSearchShell();
  await runSearch();
}

/* ============================================================
   VIEW: กระทรวง
   ============================================================ */
async function vMinistries() {
  killCharts();
  if (state.minDetail) return vMinistryDetail();
  const app = $('#app');
  app.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const d = await api(`/api/ministries?year=${state.year}`);
  const years = state.meta.years;
  const cmp = state.compare;

  app.innerHTML = `
  <div class="page-head">
    <div class="page-title">กระทรวง / หน่วยงานหลัก</div>
    <div class="page-desc">${d.ministries.length} กระทรวง · ปี ${fmtBE(state.year)} · คลิกแถวเพื่อดูรายละเอียด หรือติ๊กถูกเพื่อเปรียบเทียบ (สูงสุด 4)</div>
  </div>
  <div id="compare-box">${cmp.length ? '' : `<div class="callout info">💡 <b>เปรียบเทียบ:</b> ติ๊กถูกหน้าชื่อกระทรวงที่ต้องการ (สูงสุด 4 กระทรวง) ระบบจะวาดกราฟแนวโน้ม 5 ปีย้อนหลังให้อัตโนมัติ</div>`}</div>
  <div class="grid grid-kpi section-gap" style="margin-top:16px">
    ${kpiCard('งบรวมทุกกระทรวง', fmtTHB(d.grand_total), `<div class="kpi-foot">ปี ${fmtBE(state.year)}</div>`)}
    ${kpiCard('อันดับ 1', esc(d.ministries[0]?.name || '—'), `<div class="kpi-foot">${fmtTHB(d.ministries[0]?.total)} · ${d.ministries[0]?.share}% ของงบทั้งหมด</div>`, true)}
    ${kpiCard('ค่าเฉลี่ยต่อกระทรวง', fmtTHB(d.grand_total / Math.max(d.ministries.length, 1)), `<div class="kpi-foot">มัธยฐาน ${fmtTHB(median(d.ministries.map((x) => x.total)))}</div>`, true)}
  </div>
  <div class="table-wrap section-gap"><table class="data"><thead><tr>
    <th style="width:40px"></th><th style="width:44px">#</th><th>กระทรวง</th>
    <th class="num">งบปี ${state.year + 543}</th><th class="num">สัดส่วน</th>
    <th>แนวโน้ม ${years[0] + 543}–${years[years.length - 1] + 543}</th>
    <th class="num">หน่วยงาน</th><th class="num">รายการ</th>
  </tr></thead><tbody>
    ${d.ministries.map((m, i) => `
    <tr onclick="S.openMinistry(${A(m.name)})">
      <td onclick="event.stopPropagation()"><input type="checkbox" style="width:16px;height:16px;accent-color:var(--accent);cursor:pointer"
        ${cmp.includes(m.name) ? 'checked' : ''} onchange="S.toggleCompare(${A(m.name)})"></td>
      <td style="color:var(--text-3);font-weight:700">${i + 1}</td>
      <td><div class="cell-main">${esc(m.name)}</div></td>
      <td class="num"><b>${fmtTHB(m.total)}</b></td>
      <td class="num">${m.share}%</td>
      <td style="min-width:120px">${sparkBars(m.by_year, years)}</td>
      <td class="num">${fmtInt(m.n_units)}</td>
      <td class="num">${fmtInt(m.n_rows)}</td>
    </tr>`).join('')}
  </tbody></table></div>
  <div class="footer-note">เปลี่ยนปีที่แถบบนเพื่อดูอันดับของปีอื่น · แนวโน้มแสดงสัดส่วน 5 ปีย้อนหลังของแต่ละกระทรวง</div>`;

  if (cmp.length) await renderCompare();
}

function median(arr) {
  if (!arr.length) return 0;
  const s = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

async function renderCompare() {
  const box = $('#compare-box');
  if (!box || !state.compare.length) return;
  const d = await api(`/api/compare?names=${encodeURIComponent(state.compare.join(','))}&year=${state.year}`);
  box.innerHTML = `
  <div class="card card-chart">
    <div class="card-head"><div><div class="card-title">เปรียบเทียบ ${d.series.length} กระทรวง</div>
      <div class="card-sub">แนวโน้มงบประมาณ 5 ปีย้อนหลัง</div></div>
      <button class="btn" onclick="S.clearCompare()">ล้างการเลือก</button></div>
    <div class="chart-box chart-med"><canvas id="ch-compare"></canvas></div>
    <div class="table-wrap" style="margin-top:14px;box-shadow:none"><table class="data"><thead><tr>
      <th>กระทรวง</th>${state.meta.years.map((y) => `<th class="num">${y + 543}</th>`).join('')}<th class="num">รวม 5 ปี</th>
    </tr></thead><tbody>
      ${d.series.map((s, i) => `<tr style="cursor:default">
        <td><span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${PALETTE[i % PALETTE.length]};margin-right:8px"></span>${esc(s.name)}</td>
        ${state.meta.years.map((y) => `<td class="num">${fmtTHB(s.by_year[y] || 0)}</td>`).join('')}
        <td class="num"><b>${fmtTHB(s.total)}</b></td></tr>`).join('')}
    </tbody></table></div>
  </div>`;
  setupCharts();
  newChart('ch-compare', {
    type: 'line',
    data: {
      labels: state.meta.years.map((y) => `${y + 543}`),
      datasets: d.series.map((s, i) => ({
        label: s.name.length > 32 ? s.name.slice(0, 32) + '…' : s.name,
        data: state.meta.years.map((y) => s.by_year[y] || 0),
        borderColor: PALETTE[i % PALETTE.length],
        backgroundColor: PALETTE[i % PALETTE.length] + '22',
        fill: true, tension: 0.35, borderWidth: 2.5, pointRadius: 4,
      })),
    },
    options: {
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 14, font: { size: 11 } } }, tooltip: baseTooltip() },
      scales: { y: { grid: gridOpts(), ticks: { callback: fmtAxis } }, x: { grid: { display: false } } },
    },
  });
}

async function vMinistryDetail() {
  const name = state.minDetail;
  const app = $('#app');
  app.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const d = await api(`/api/ministry?name=${encodeURIComponent(name)}&year=${state.year}`);
  const years = state.meta.years;

  app.innerHTML = `
  <div class="page-head">
    <button class="btn" onclick="S.backMinistries()" style="margin-bottom:12px">
      <svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg>กลับรายชื่อกระทรวง</button>
    <div class="page-title">${esc(d.name)}</div>
    <div class="page-desc">อันดับ ${d.rank} จาก ${d.n_ranked} กระทรวง · ปี ${fmtBE(state.year)}</div>
  </div>
  <div class="grid grid-kpi">
    ${kpiCard(`งบปี ${state.year + 543}`, fmtTHB(d.total), `<div class="kpi-foot">${fmtTHBFull(d.total)}</div>`)}
    ${kpiCard('สัดส่วนของงบทั้งหมด', `${d.share}%`, `<div class="kpi-foot">อันดับ ${d.rank}/${d.n_ranked}</div>`)}
    ${kpiCard('หน่วยงานเบิกจ่าย', fmtInt(d.n_units), `<div class="kpi-foot">${fmtInt(d.n_rows)} รายการในปีนี้</div>`)}
  </div>
  <div class="grid grid-2 section-gap">
    <div class="card card-chart">
      <div class="card-head"><div class="card-title">แนวโน้ม 5 ปี</div></div>
      <div class="chart-box chart-med"><canvas id="ch-mtrend"></canvas></div>
    </div>
    <div class="card card-chart">
      <div class="card-head"><div class="card-title">สัดส่วนตามหมวดงบ (LV1)</div></div>
      <div class="chart-box chart-med"><canvas id="ch-mcat"></canvas></div>
    </div>
  </div>
  <div class="grid grid-2 section-gap">
    <div class="card">
      <div class="card-head"><div><div class="card-title">หน่วยงานงบสูงสุด</div>
        <div class="card-sub">Top 15 · คลิกเพื่อค้นหารายการ</div></div></div>
      ${rankList(d.top_units, 15, 'S.searchUnit')}
    </div>
    <div class="card">
      <div class="card-head"><div><div class="card-title">รายการงบสูงสุด</div>
        <div class="card-sub">Top 20 ของกระทรวงนี้ · คลิกเพื่อดูรายละเอียด</div></div>
        <button class="btn" onclick="S.gotoSearchMinistry(${A(d.name)})">ดูทั้งหมด</button></div>
      ${rankList(d.top_items.map((r) => ({ name: r.ITEM_DESCRIPTION || r.BUDGETARY_UNIT, total: r.AMOUNT })), 20, 'S.searchItem')}
    </div>
  </div>
  <div class="footer-note">${esc(d.name)} · ${fmtInt(d.n_rows)} รายการในปี ${fmtBE(state.year)}</div>`;

  setupCharts();
  newChart('ch-mtrend', {
    type: 'bar',
    data: {
      labels: years.map((y) => `${y + 543}`),
      datasets: [{
        data: years.map((y) => d.by_year[y] || 0),
        backgroundColor: years.map((y) => y === state.year ? '#C96442' : '#E4CDBB'),
        hoverBackgroundColor: '#C96442', borderRadius: 8, borderSkipped: false, maxBarThickness: 80,
      }],
    },
    options: {
      plugins: { legend: { display: false }, tooltip: baseTooltip() },
      scales: { y: { grid: gridOpts(), ticks: { callback: fmtAxis } }, x: { grid: { display: false } } },
      onClick: (_, els) => { if (els.length) S.setYear(years[els[0].index]); },
    },
  });
  const bc = d.by_category.slice(0, 8);
  newChart('ch-mcat', {
    type: 'doughnut',
    data: {
      labels: bc.map((c) => c.name),
      datasets: [{ data: bc.map((c) => c.total), backgroundColor: bc.map((_, i) => PALETTE[i % PALETTE.length]), borderWidth: 2, borderColor: cssVar('--card') }],
    },
    options: {
      cutout: '58%',
      plugins: { legend: { position: 'right', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } }, tooltip: baseTooltip() },
    },
  });
}

/* ============================================================
   VIEW: หมวดงบ
   ============================================================ */
const CAT_LEVEL_NAMES = { 1: 'หมวดงบประมาณ', 2: 'ประเภท', 3: 'ระดับ 3', 4: 'ระดับ 4', 5: 'ระดับ 5', 6: 'ระดับ 6' };

async function vCategories() {
  killCharts();
  const app = $('#app');
  const path = state.catPath;
  const qs = path.map(encodeURIComponent).join('/');
  app.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const d = await api(`/api/categories?year=${state.year}&path=${qs}`);
  const pct = d.grand_total ? (d.total / d.grand_total * 100) : 0;

  const crumbs = [`<a onclick="S.catRoot()" style="cursor:pointer">หมวดทั้งหมด</a>`];
  path.forEach((p, i) => {
    crumbs.push(`<span class="sep">›</span>`);
    crumbs.push(i === path.length - 1
      ? `<span class="current">${esc(p)}</span>`
      : `<a onclick="S.catGo(${i})" style="cursor:pointer">${esc(p)}</a>`);
  });

  app.innerHTML = `
  <div class="page-head">
    <div class="page-title">หมวดงบประมาณ</div>
    <div class="page-desc">โครงสร้างหมวดงบ 6 ระดับ · ปี ${fmtBE(state.year)} · คลิกเพื่อเจาะลึก (drill-down)</div>
  </div>
  <div class="card" style="margin-bottom:16px"><div class="breadcrumb">${crumbs.join('')}</div>
    <div class="stat-inline" style="margin-top:12px">
      <div class="si"><b>${fmtTHB(d.total)}</b><span>ยอดรวมระดับนี้ (${pct.toFixed(2)}% ของงบทั้งหมด)</span></div>
      <div class="si"><b>${fmtInt(d.rows)}</b><span>รายการ</span></div>
      <div class="si"><b>${d.level}/6</b><span>ระดับ (${CAT_LEVEL_NAMES[d.level]})</span></div>
      <div style="flex:1"></div>
      <div style="align-self:center"><button class="btn btn-primary" onclick="S.catToggleRows()">
        ${state.catRowsOpen ? 'ซ่อนรายการ' : `ดูรายการในระดับนี้ (Top 100)`}</button></div>
    </div></div>
  ${!d.nodes.length ? emptyHTML('ไม่มีหมวดย่อย', 'ระดับนี้เป็นระดับล่างสุด — กด "ดูรายการ" เพื่อดูรายละเอียด') : `
  <div class="card card-chart">
    <div class="card-head"><div><div class="card-title">สัดส่วนหมวดย่อย</div>
      <div class="card-sub">${d.nodes.length} หมวด · คลิกแท่งเพื่อเจาะลึก</div></div></div>
    <div class="chart-box" style="height:${Math.max(220, Math.min(560, d.nodes.length * 34))}px"><canvas id="ch-cat"></canvas></div>
  </div>
  <div class="table-wrap section-gap"><table class="data"><thead><tr>
    <th style="width:44px">#</th><th>ชื่อหมวด</th><th class="num">ยอดรวม</th><th class="num">สัดส่วน</th>
    <th class="num">รายการ</th><th></th>
  </tr></thead><tbody>
    ${d.nodes.map((n, i) => `
    <tr onclick="S.catOpen(${A(n.name)})">
      <td style="color:var(--text-3);font-weight:700">${i + 1}</td>
      <td><div class="cell-main">${esc(n.name)}</div>
        <div class="rank-bar-wrap" style="grid-column:auto;margin-top:6px;max-width:280px"><div class="rank-bar" style="width:${(n.total / Math.max(d.nodes[0].total, 1) * 100).toFixed(1)}%"></div></div></td>
      <td class="num"><b>${fmtTHB(n.total)}</b></td>
      <td class="num">${(n.total / Math.max(d.total, 1) * 100).toFixed(2)}%</td>
      <td class="num">${fmtInt(n.rows)}</td>
      <td style="white-space:nowrap">${n.has_children ? '<span class="badge accent">มีหมวดย่อย ›</span>' : '<span class="badge">ปลายทาง</span>'}</td>
    </tr>`).join('')}
  </tbody></table></div>`}
  <div id="cat-rows" class="section-gap"></div>
  <div class="footer-note">โครงสร้างหมวดงบมาจากเอกสารงบประมาณโดยตรง · บางรายการอาจไม่มีหมวดระดับลึก (ดูคุณภาพข้อมูล)</div>`;

  if (d.nodes.length) {
    setupCharts();
    const top = d.nodes.slice(0, 40);
    newChart('ch-cat', {
      type: 'bar',
      data: {
        labels: top.map((n) => n.name.length > 42 ? n.name.slice(0, 42) + '…' : n.name),
        datasets: [{ data: top.map((n) => n.total), backgroundColor: '#C96442', hoverBackgroundColor: '#B04E2E', borderRadius: 5, borderSkipped: false }],
      },
      options: {
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: { ...baseTooltip(), callbacks: { title: (items) => top[items[0].dataIndex].name, label: (c) => ` ${fmtTHBFull(c.parsed.x)}` } },
        },
        scales: { x: { grid: gridOpts(), ticks: { callback: fmtAxis } }, y: { grid: { display: false }, ticks: { font: { size: 11 } } } },
        onClick: (_, els) => { if (els.length) S.catOpen(top[els[0].index].name); },
      },
    });
  }
  if (state.catRowsOpen) await catLoadRows();
}

async function catLoadRows() {
  const box = $('#cat-rows');
  if (!box) return;
  box.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const qs = state.catPath.map(encodeURIComponent).join('/');
  const d = await api(`/api/category_rows?year=${state.year}&path=${qs}&n=100`);
  box.innerHTML = `
  <div class="card" style="margin-bottom:14px"><div class="stat-inline">
    <div class="si"><b>${fmtInt(d.count)}</b><span>รายการ (Top 100 ตามวงเงิน)</span></div>
    <div class="si"><b>${fmtTHB(d.total)}</b><span>รวม Top 100</span></div>
  </div></div>
  ${rowsTableHTML(d.rows, { source: false })}`;
}

/* ============================================================
   VIEW: แผนงาน
   ============================================================ */
async function vPlans() {
  killCharts();
  if (state.planDetail) return vPlanDetail();
  const app = $('#app');
  app.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const d = await api(`/api/plans?year=${state.year}&q=${encodeURIComponent(state.planQ)}`);
  const years = state.meta.years;

  app.innerHTML = `
  <div class="page-head">
    <div class="page-title">แผนงาน / ยุทธศาสตร์</div>
    <div class="page-desc">${fmtInt(d.plans.length)} แผนงาน · ปี ${fmtBE(state.year)} · คลิกเพื่อดูรายละเอียด (กระทรวง หน่วยงาน ยุทธศาสตร์ ที่เกี่ยวข้อง)</div>
  </div>
  <div class="searchbar">
    <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
    <input class="input input-lg" id="plan-q" placeholder="กรองชื่อแผนงาน เช่น บูรณาการ, พื้นฐาน, ยุทธศาสตร์…" value="${esc(state.planQ)}">
  </div>
  <div class="grid grid-kpi section-gap">
    ${kpiCard('งบรวมทุกแผนงาน', fmtTHB(d.grand_total), `<div class="kpi-foot">ปี ${fmtBE(state.year)}</div>`)}
    ${kpiCard('แผนงานงบสูงสุด', esc((d.plans[0]?.name || '—').slice(0, 40)), `<div class="kpi-foot">${fmtTHB(d.plans[0]?.total)} · ${d.plans[0]?.share}%</div>`, true)}
    ${kpiCard('จำนวนแผนงาน', fmtInt(d.plans.length), `<div class="kpi-foot">ที่มีงบในปีนี้</div>`)}
  </div>
  ${!d.plans.length ? emptyHTML('ไม่พบแผนงาน', 'ลองเปลี่ยนคำค้น') : `
  <div class="table-wrap section-gap"><table class="data"><thead><tr>
    <th style="width:44px">#</th><th>แผนงาน</th><th class="num">งบปี ${state.year + 543}</th>
    <th class="num">สัดส่วน</th><th>แนวโน้ม 5 ปี</th><th class="num">รายการ</th>
  </tr></thead><tbody>
    ${d.plans.map((p, i) => `
    <tr onclick="S.openPlan(${A(p.name)})">
      <td style="color:var(--text-3);font-weight:700">${i + 1}</td>
      <td><div class="cell-main">${esc(p.name)}</div></td>
      <td class="num"><b>${fmtTHB(p.total)}</b></td>
      <td class="num">${p.share}%</td>
      <td style="min-width:120px">${sparkBars(p.by_year, years)}</td>
      <td class="num">${fmtInt(p.rows)}</td>
    </tr>`).join('')}
  </tbody></table></div>`}`;

  $('#plan-q').addEventListener('input', debounce(async () => {
    state.planQ = $('#plan-q').value;
    await vPlans();
    const el = $('#plan-q');
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }, 500));
}

async function vPlanDetail() {
  const name = state.planDetail;
  const app = $('#app');
  app.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const d = await api(`/api/plan?name=${encodeURIComponent(name)}&year=${state.year}`);
  const years = state.meta.years;

  const lists = [
    ['กระทรวงที่เกี่ยวข้อง', d.by_ministry, 'S.openMinistry'],
    ['หน่วยงานที่เกี่ยวข้อง', d.by_unit, 'S.searchUnit'],
    ['ยุทธศาสตร์', d.by_strategy, 'S.searchItem'],
    ['แผนแม่บท', d.by_mother_plan, 'S.searchItem'],
  ];

  app.innerHTML = `
  <div class="page-head">
    <button class="btn" onclick="S.backPlans()" style="margin-bottom:12px">
      <svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg>กลับรายชื่อแผนงาน</button>
    <div class="page-title" style="font-size:23px">${esc(d.name)}</div>
    <div class="page-desc">${fmtInt(d.n_ministries)} กระทรวง · ${fmtInt(d.n_rows)} รายการ · ปี ${fmtBE(state.year)}</div>
  </div>
  <div class="grid grid-kpi">
    ${kpiCard(`งบปี ${state.year + 543}`, fmtTHB(d.total), `<div class="kpi-foot">${fmtTHBFull(d.total)}</div>`)}
    ${kpiCard('สัดส่วนของงบทั้งหมด', `${d.share}%`, `<div class="kpi-foot">ปี ${fmtBE(state.year)}</div>`)}
    ${kpiCard('รายการ Panel', fmtInt(d.n_rows), `<div class="kpi-foot">
      <a class="link-btn" onclick="S.gotoSearchPlan(${A(d.name)})" style="cursor:pointer">ดูรายการทั้งหมดในหน้าค้นหา</a></div>`)}
  </div>
  <div class="card card-chart section-gap">
    <div class="card-head"><div class="card-title">แนวโน้มงบ 5 ปี</div></div>
    <div class="chart-box chart-short"><canvas id="ch-ptrend"></canvas></div>
  </div>
  <div class="grid grid-2 section-gap">
    ${lists.map(([title, items, fn]) => `
    <div class="card"><div class="card-head"><div class="card-title">${title}</div>
      <div class="card-sub">Top 10 · คลิกเพื่อเจาะลึก</div></div>
      ${items.length ? rankList(items, 10, fn) : '<div class="card-sub">ไม่มีข้อมูล</div>'}</div>`).join('')}
  </div>
  <div class="card section-gap">
    <div class="card-head"><div><div class="card-title">รายการงบสูงสุดในแผนงานนี้</div>
      <div class="card-sub">Top 15 · คลิกเพื่อดูรายละเอียด</div></div></div>
    ${rowsTableHTML(d.top_items, { source: false })}
  </div>`;

  setupCharts();
  newChart('ch-ptrend', {
    type: 'line',
    data: {
      labels: years.map((y) => `${y + 543}`),
      datasets: [{
        label: 'งบประมาณ',
        data: years.map((y) => d.by_year[y] || 0),
        borderColor: '#C96442', backgroundColor: '#C9644222', fill: true,
        tension: 0.35, borderWidth: 2.5, pointRadius: 5, pointBackgroundColor: '#C96442',
      }],
    },
    options: {
      plugins: { legend: { display: false }, tooltip: baseTooltip() },
      scales: { y: { grid: gridOpts(), ticks: { callback: fmtAxis } }, x: { grid: { display: false } } },
    },
  });
}

/* ============================================================
   VIEW: ภาระผูกพัน
   ============================================================ */
async function vCommitments() {
  killCharts();
  const app = $('#app');
  app.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const d = await api('/api/commitments');
  const c = state.comm;

  const barColors = d.by_year.map((r) =>
    r.year <= 2005 ? '#B3402F' : r.year <= 2021 ? '#C9A45C' : r.year <= 2026 ? '#C96442' : '#6E93A8');

  app.innerHTML = `
  <div class="page-head">
    <div class="page-title">ภาระผูกพันข้ามปีงบประมาณ</div>
    <div class="page-desc">รายการที่ระบุปีนอกช่วง 2022–2026 ถูกแยกไว้ในไฟล์ commitments ต่างหาก เพื่อไม่ให้ปนกับงบรายปี</div>
  </div>
  <div class="callout warn">⚠️ <b>ข้อควรระวัง:</b> มี ${fmtInt(d.suspicious.rows)} รายการระบุปี ≤ 2021 (${fmtTHB(d.suspicious.total)})
    และ ${fmtInt(d.impossible.rows)} รายการระบุปี 1967–2005 (${fmtTHB(d.impossible.total)})
    ซึ่ง<b>เป็นไปไม่ได้</b>ในเอกสารงบ 2566–2569 — น่าจะเป็น artifact จากการแปลงไฟล์ PDF/Excel
    (<a class="link-btn" onclick="S.gotoQuality('commitment_year_impossible')" style="cursor:pointer">ดูในหน้าคุณภาพข้อมูล</a>)</div>
  <div class="grid grid-kpi section-gap">
    ${kpiCard('ยอดภาระผูกพันรวม', fmtTHB(d.total), `<div class="kpi-foot">${fmtTHBFull(d.total)}</div>`)}
    ${kpiCard('จำนวนรายการ', fmtInt(d.rows), `<div class="kpi-foot">${fmtInt(d.n_ministries)} กระทรวง · ช่วงปี ${d.year_min}–${d.year_max}</div>`)}
    ${kpiCard('ปีที่น่าสงสัย', fmtInt(d.impossible.rows), `<div class="kpi-foot" style="color:var(--red);font-weight:600">ปี 1967–2005 เป็นไปไม่ได้</div>`)}
  </div>
  <div class="grid grid-2 section-gap">
    <div class="card card-chart">
      <div class="card-head"><div><div class="card-title">ภาระผูกพันรายปี</div>
        <div class="card-sub"><span class="badge red">แดง ≤2005</span> <span class="badge amber">เหลือง 2006–21</span> <span class="badge accent">ส้ม 2022–26</span> <span class="badge blue">น้ำเงิน ≥2027</span></div></div></div>
      <div class="chart-box chart-med"><canvas id="ch-cyear"></canvas></div>
    </div>
    <div class="card card-chart">
      <div class="card-head"><div><div class="card-title">ภาระผูกพันรายกระทรวง (Top 15)</div></div></div>
      <div class="chart-box chart-med"><canvas id="ch-cmin"></canvas></div>
    </div>
  </div>
  <div class="page-head section-gap" style="margin-bottom:12px">
    <div class="page-title" style="font-size:20px">สำรวจรายการภาระผูกพัน</div>
  </div>
  <div class="searchbar">
    <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
    <input class="input input-lg" id="c-q" placeholder="ค้นหาในภาระผูกพัน…" value="${esc(c.q)}">
  </div>
  <div class="filter-row">
    <div class="field" style="min-width:140px"><span class="field-label">ปี (ค.ศ.)</span>
      <input class="input" id="c-year" inputmode="numeric" placeholder="เช่น 2030" value="${esc(c.year)}"></div>
    <div class="field" style="min-width:260px;flex:1"><span class="field-label">กระทรวง</span>
      <select class="select" id="c-ministry"><option value="">ทุกกระทรวง</option>
        ${d.by_ministry.map((x) => `<option value="${esc(x.name)}"${c.ministry === x.name ? ' selected' : ''}>${esc(x.name)}</option>`).join('')}
      </select></div>
    <button class="btn" onclick="S.commReset()">ล้าง</button>
  </div>
  <div id="comm-results" style="margin-top:16px"><div class="loading"><div class="spinner"></div></div></div>
  <div class="footer-note">แถวสีแดง = ปีเป็นไปไม่ได้ (≤2005) · แถวสีเหลือง = มี DQ flag — คลิกแถวเพื่อดูรายละเอียด</div>`;

  $('#c-q').addEventListener('input', debounce(() => { state.comm.q = $('#c-q').value; state.comm.page = 1; runCommRows(); }, 450));
  $('#c-year').addEventListener('change', (e) => { state.comm.year = e.target.value.trim(); state.comm.page = 1; runCommRows(); });
  $('#c-ministry').addEventListener('change', (e) => { state.comm.ministry = e.target.value; state.comm.page = 1; runCommRows(); });

  setupCharts();
  const byYearAsc = [...d.by_year].sort((a, b) => a.year - b.year);
  const colAsc = byYearAsc.map((r) =>
    r.year <= 2005 ? '#B3402F' : r.year <= 2021 ? '#C9A45C' : r.year <= 2026 ? '#C96442' : '#6E93A8');
  newChart('ch-cyear', {
    type: 'bar',
    data: {
      labels: byYearAsc.map((r) => String(r.year)),
      datasets: [{ data: byYearAsc.map((r) => r.total), backgroundColor: colAsc, borderRadius: 3, borderSkipped: false }],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: { ...baseTooltip(), callbacks: {
          title: (items) => `ปี ${byYearAsc[items[0].dataIndex].year} (${fmtInt(byYearAsc[items[0].dataIndex].rows)} รายการ)`,
          label: (cc) => ` ${fmtTHBFull(cc.parsed.y)}` } },
      },
      scales: { y: { grid: gridOpts(), ticks: { callback: fmtAxis } }, x: { grid: { display: false }, ticks: { maxRotation: 70, minRotation: 60, font: { size: 9 } } } },
      onClick: (_, els) => {
        if (els.length) {
          state.comm.year = String(byYearAsc[els[0].index].year);
          state.comm.page = 1;
          $('#c-year').value = state.comm.year;
          runCommRows();
          $('#comm-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      },
    },
  });
  const cm = d.by_ministry.slice(0, 15);
  newChart('ch-cmin', {
    type: 'bar',
    data: {
      labels: cm.map((x) => x.name.length > 30 ? x.name.slice(0, 30) + '…' : x.name),
      datasets: [{ data: cm.map((x) => x.total), backgroundColor: '#9A8AB5', borderRadius: 5, borderSkipped: false }],
    },
    options: {
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { ...baseTooltip(), callbacks: { title: (items) => cm[items[0].dataIndex].name, label: (cc) => ` ${fmtTHBFull(cc.parsed.x)}` } },
      },
      scales: { x: { grid: gridOpts(), ticks: { callback: fmtAxis } }, y: { grid: { display: false }, ticks: { font: { size: 11 } } } },
    },
  });
  await runCommRows();
}

async function runCommRows() {
  const box = $('#comm-results');
  if (!box) return;
  box.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const c = state.comm;
  const p = new URLSearchParams();
  if (c.q) p.set('q', c.q);
  if (c.year) p.set('year', c.year);
  if (c.ministry) p.set('ministry', c.ministry);
  p.set('page', c.page);
  p.set('per_page', c.per_page);
  const d = await api(`/api/commitments_rows?${p.toString()}`);
  state.comm.page = d.page;
  if (!d.total) { box.innerHTML = emptyHTML('ไม่พบรายการ', 'ลองเปลี่ยนคำค้นหรือล้างตัวกรอง'); return; }
  box.innerHTML = `
    <div class="card" style="margin-bottom:14px"><div class="stat-inline">
      <div class="si"><b>${fmtInt(d.total)}</b><span>รายการที่พบ</span></div>
      <div class="si"><b>${fmtTHB(d.sum)}</b><span>รวมวงเงิน</span></div>
    </div></div>
    ${rowsTableHTML(d.rows)}
    ${pagHTML(d.total, d.page, d.per_page, 'S.commPage')}`;
}

/* ============================================================
   VIEW: คุณภาพข้อมูล
   ============================================================ */
async function vQuality() {
  killCharts();
  const app = $('#app');
  app.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const q = state.quality;
  const p = new URLSearchParams();
  p.set('page', 1); p.set('per_page', 1);
  if (q.type) p.set('type', q.type);
  p.set('source', q.source);
  const first = await api(`/api/flags?${p.toString()}`);
  const counts = first.counts;
  const types = Object.keys(counts);
  const total = state.meta.counts.main_rows + state.meta.counts.commitments_rows;

  app.innerHTML = `
  <div class="page-head">
    <div class="page-title">คุณภาพข้อมูล</div>
    <div class="page-desc">คอลัมน์ <b>dq_flag</b> ติดป้ายกำกับทุกรายการที่มีประเด็นคุณภาพ — คลิกประเภทเพื่อกรองดูรายการ</div>
  </div>
  <div class="callout info">ℹ️ ข้อมูลผ่านการ clean แล้ว: แก้คำผิด/OCR ~9,300 เซลล์ · ลบแถวซ้ำ 113 แถว · รวมชื่อกระทรวง 39→35 · แยกภาระผูกพัน ${fmtInt(state.meta.counts.commitments_rows)} แถว · ดูรายละเอียดใน <b>DATA_QUALITY_REPORT.md</b></div>
  <div class="grid grid-kpi section-gap">
    ${kpiCard('รายการที่มี flag', fmtInt(first.total), `<div class="kpi-foot">${(first.total / total * 100).toFixed(2)}% ของทั้งหมด</div>`)}
    ${kpiCard('ประเภท flag', fmtInt(types.length), `<div class="kpi-foot">แยกตามประเด็น</div>`)}
    ${kpiCard('แถวซ้ำที่ลบออก', '113', `<div class="kpi-foot">398.9 ล้านบาทที่เคยซ้ำซ้อน</div>`)}
  </div>
  <div class="card card-chart section-gap">
    <div class="card-head"><div><div class="card-title">จำนวนรายการตามประเภท flag</div>
      <div class="card-sub">คลิกแท่งเพื่อกรอง · 1 รายการอาจมีหลาย flag</div></div></div>
    <div class="chart-box" style="height:${Math.max(200, types.length * 36)}px"><canvas id="ch-flags"></canvas></div>
  </div>
  <div class="filter-row">
    <div class="field"><span class="field-label">ประเภท flag</span>
      <div class="chip-row">
        <button class="chip${!q.type ? ' active' : ''}" onclick="S.flagType('')">ทั้งหมด</button>
        ${types.map((t) => `<button class="chip${q.type === t ? ' active' : ''}" onclick="S.flagType(${A(t)})" title="${esc(t)}">${esc(FLAG_LABELS[t] || t)} (${fmtInt(counts[t])})</button>`).join('')}
      </div></div>
  </div>
  <div class="filter-row">
    <div class="field"><span class="field-label">แหล่งข้อมูล</span>
      <div class="chip-row">
        <button class="chip${q.source === 'all' ? ' active' : ''}" onclick="S.flagSource('all')">ทั้งหมด</button>
        <button class="chip${q.source === 'main' ? ' active' : ''}" onclick="S.flagSource('main')">ไฟล์หลัก</button>
        <button class="chip${q.source === 'commitments' ? ' active' : ''}" onclick="S.flagSource('commitments')">ภาระผูกพัน</button>
      </div></div>
  </div>
  <div id="flag-results" style="margin-top:16px"><div class="loading"><div class="spinner"></div></div></div>`;

  setupCharts();
  newChart('ch-flags', {
    type: 'bar',
    data: {
      labels: types.map((t) => FLAG_LABELS[t] || t),
      datasets: [{ data: types.map((t) => counts[t]), backgroundColor: types.map((t) => FLAG_CLASS[t] === 'red' ? '#B3402F' : FLAG_CLASS[t] === 'amber' ? '#C9A45C' : '#6E93A8'), borderRadius: 5, borderSkipped: false }],
    },
    options: {
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { ...baseTooltip(), callbacks: { title: (items) => `${FLAG_LABELS[types[items[0].dataIndex]] || types[items[0].dataIndex]}\n${types[items[0].dataIndex]}`, label: (cc) => ` ${fmtInt(cc.parsed.x)} รายการ` } },
      },
      scales: { x: { grid: gridOpts(), ticks: { callback: (v) => fmtInt(v) } }, y: { grid: { display: false }, ticks: { font: { size: 11 } } } },
      onClick: (_, els) => { if (els.length) S.flagType(types[els[0].index]); },
    },
  });
  await runFlagRows();
}

async function runFlagRows() {
  const box = $('#flag-results');
  if (!box) return;
  box.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  const q = state.quality;
  const p = new URLSearchParams();
  p.set('page', q.page);
  p.set('per_page', q.per_page);
  if (q.type) p.set('type', q.type);
  p.set('source', q.source);
  const d = await api(`/api/flags?${p.toString()}`);
  state.quality.page = d.page;
  if (!d.total) { box.innerHTML = emptyHTML('ไม่พบรายการ', 'ลองเปลี่ยนตัวกรอง'); return; }
  box.innerHTML = `
    <div class="card" style="margin-bottom:14px"><div class="stat-inline">
      <div class="si"><b>${fmtInt(d.total)}</b><span>รายการที่พบ</span></div>
      ${q.type ? `<div class="si"><b style="font-size:15px;font-family:var(--sans)">${esc(FLAG_LABELS[q.type] || q.type)}</b><span>${esc(q.type)}</span></div>` : ''}
    </div></div>
    ${rowsTableHTML(d.rows)}
    ${pagHTML(d.total, d.page, d.per_page, 'S.flagPage')}`;
}

/* ============================================================
   Router + actions
   ============================================================ */
const VIEWS = {
  overview: vOverview,
  search: vSearch,
  ministries: vMinistries,
  categories: vCategories,
  plans: vPlans,
  commitments: vCommitments,
  quality: vQuality,
};

async function render() {
  killCharts();
  closeModal();
  $$('.nav-item').forEach((b) =>
    b.classList.toggle('active', b.dataset.route === state.route));
  $('#crumb').textContent = ROUTES[state.route] || '';
  $('#sidebar').classList.remove('open');
  window.scrollTo({ top: 0 });
  try {
    await VIEWS[state.route]();
  } catch (e) {
    console.error(e);
    $('#app').innerHTML = emptyHTML('โหลดข้อมูลไม่สำเร็จ', 'กรุณารีเฟรชหน้าเว็บแล้วลองใหม่');
  }
}

function buildYearChips() {
  $('#year-chips').innerHTML = state.meta.years.map((y) =>
    `<button class="year-chip${y === state.year ? ' active' : ''}" onclick="S.setYear(${y})">${y + 543}</button>`).join('');
}

/* global actions (เรียกจาก inline onclick) */
window.S = {
  go(route) {
    if (state.route === route) { render(); return; }
    state.route = route;
    location.hash = `#/${route}`;
  },
  setYear(y) {
    if (state.year === y) return;
    state.year = y;
    buildYearChips();
    render();
    toast(`เปลี่ยนเป็นปีงบประมาณ ${fmtBE(y)}`);
  },
  toggleTheme() {
    const cur = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = cur;
    try { localStorage.setItem('tb-theme', cur); } catch (e) { /* noop */ }
    render();
  },
  showRow(i) {
    const r = ROWS[i];
    if (!r) return;
    openModal('รายละเอียดรายการ', rowDetailHTML(r));
  },
  closeModal,

  /* search */
  doSearch() { state.search.q = $('#f-q') ? $('#f-q').value : state.search.q; state.search.page = 1; runSearch(); },
  searchPage(p) { state.search.page = p; runSearch(); window.scrollTo({ top: 0, behavior: 'smooth' }); },
  toggleYear(y) {
    const ys = state.search.years;
    const i = ys.indexOf(y);
    if (i >= 0) ys.splice(i, 1); else ys.push(y);
    state.search.page = 1;
    vSearchShell(); runSearch();
  },
  setSource(s) { state.search.source = s; state.search.page = 1; vSearchShell(); runSearch(); },
  resetSearch() {
    state.search = {
      q: '', years: [], ministry: '', cat1: '', plan: '', amt_min: '', amt_max: '',
      obliged: false, cross: false, flagged: false, source: 'all',
      sort: 'AMOUNT', order: 'desc', page: 1, per_page: 50,
    };
    vSearchShell(); runSearch();
  },
  exportCSV() {
    toast('กำลังส่งออก CSV…');
    window.location = `/api/export?${searchQuery()}`;
  },
  searchUnit(name) {
    state.search = {
      q: name, years: [], ministry: '', cat1: '', plan: '', amt_min: '', amt_max: '',
      obliged: false, cross: false, flagged: false, source: 'all',
      sort: 'AMOUNT', order: 'desc', page: 1, per_page: 50,
    };
    state.route = 'search';
    location.hash = '#/search';
    render();
  },
  searchItem(name) {
    S.searchUnit(name);
  },
  gotoSearchMinistry(name) {
    state.search.ministry = name; state.search.q = '';
    state.search.page = 1; state.search.source = 'all';
    state.route = 'search';
    location.hash = '#/search';
    render();
  },
  gotoSearchPlan(name) {
    state.search.plan = name; state.search.q = '';
    state.search.page = 1; state.search.source = 'all';
    state.route = 'search';
    location.hash = '#/search';
    render();
  },

  /* ministries */
  openMinistry(name) { state.minDetail = name; render(); window.scrollTo({ top: 0 }); },
  backMinistries() { state.minDetail = null; render(); },
  toggleCompare(name) {
    const c = state.compare;
    const i = c.indexOf(name);
    if (i >= 0) c.splice(i, 1);
    else {
      if (c.length >= 4) { toast('เปรียบเทียบได้สูงสุด 4 กระทรวง'); render(); return; }
      c.push(name);
    }
    render();
  },
  clearCompare() { state.compare = []; render(); },

  /* categories */
  catOpen(name) {
    state.catPath.push(name);
    state.catRowsOpen = false;
    render(); window.scrollTo({ top: 0 });
  },
  catGo(i) { state.catPath = state.catPath.slice(0, i + 1); state.catRowsOpen = false; render(); },
  catRoot() { state.catPath = []; state.catRowsOpen = false; render(); },
  async catToggleRows() {
    state.catRowsOpen = !state.catRowsOpen;
    render();
    if (state.catRowsOpen) setTimeout(() => $('#cat-rows')?.scrollIntoView({ behavior: 'smooth' }), 400);
  },

  /* plans */
  openPlan(name) { state.planDetail = name; render(); window.scrollTo({ top: 0 }); },
  backPlans() { state.planDetail = null; render(); },

  /* commitments */
  commPage(p) { state.comm.page = p; runCommRows(); window.scrollTo({ top: 0, behavior: 'smooth' }); },
  commReset() {
    state.comm = { q: '', year: '', ministry: '', page: 1, per_page: 50 };
    render();
  },
  gotoQuality(type) {
    state.quality = { type, source: 'all', page: 1, per_page: 50 };
    state.route = 'quality';
    location.hash = '#/quality';
    render();
  },

  /* quality */
  flagType(t) { state.quality.type = t; state.quality.page = 1; render(); },
  flagSource(s) { state.quality.source = s; state.quality.page = 1; render(); },
  flagPage(p) { state.quality.page = p; runFlagRows(); window.scrollTo({ top: 0, behavior: 'smooth' }); },
};

/* ---------------- boot ---------------- */
async function boot() {
  /* theme */
  let theme = 'light';
  try { theme = localStorage.getItem('tb-theme') || 'light'; } catch (e) { /* noop */ }
  document.documentElement.dataset.theme = theme;

  /* nav */
  $$('.nav-item').forEach((b) =>
    b.addEventListener('click', () => S.go(b.dataset.route)));
  $('#hamburger').addEventListener('click', () =>
    $('#sidebar').classList.toggle('open'));
  $('#theme-toggle').addEventListener('click', () => S.toggleTheme());
  $('#modal-close').addEventListener('click', closeModal);
  $('#modal-backdrop').addEventListener('click', (e) => {
    if (e.target.id === 'modal-backdrop') closeModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  /* hash route */
  const applyHash = () => {
    const h = (location.hash || '').replace('#/', '');
    if (VIEWS[h] && h !== state.route) {
      state.route = h;
      state.minDetail = null;
      state.planDetail = null;
      render();
    }
  };
  window.addEventListener('hashchange', applyHash);
  const h0 = (location.hash || '').replace('#/', '');
  if (VIEWS[h0]) state.route = h0;

  /* meta + first render */
  try {
    state.meta = await api('/api/meta');
    buildYearChips();
    if (!location.hash) location.hash = '#/overview';
    await render();
  } catch (e) {
    console.error(e);
    $('#app').innerHTML = emptyHTML('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้', 'กรุณาตรวจสอบว่า backend กำลังทำงานแล้วรีเฟรช');
  }
}

document.addEventListener('DOMContentLoaded', boot);
