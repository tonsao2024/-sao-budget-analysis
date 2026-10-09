/* ============================================================
   Thai Budget Analyzer — local data engine (static / GitHub Pages)
   - โหลด .csv.gz (ไฟล์เดียวกับ output/) แล้วแกะ + parse ในเบราว์เซอร์
   - logic ตรงกับ web/server.py ทุก endpoint (offline 100%)
   - export CSV / Excel (SheetJS) ทั้งแบบกรองและทั้งฐาน
   ไฟล์นี้ถูกออกแบบให้รันได้ทั้งในเบราว์เซอร์และใน node (สำหรับเทสต์)
   ============================================================ */
(function (global) {
  'use strict';

  const isBrowser = typeof window !== 'undefined' && typeof document !== 'undefined';
  const PAPA = () => global.Papa;

  /* ---------------- constants (parity กับ server.py) ---------------- */
  const YEARS = [2022, 2023, 2024, 2025, 2026];
  const CATS = ['CATEGORY_LV1', 'CATEGORY_LV2', 'CATEGORY_LV3',
    'CATEGORY_LV4', 'CATEGORY_LV5', 'CATEGORY_LV6'];
  const SEARCHABLE = ['MINISTRY', 'BUDGETARY_UNIT', 'ITEM_DESCRIPTION', 'BUDGET_PLAN',
    'OUTPUT', 'PROJECT', 'STRATEGY', 'MOTHER_PLAN'].concat(CATS);
  const SEARCH_COLS = ['FISCAL_YEAR', 'MINISTRY', 'BUDGETARY_UNIT', 'ITEM_DESCRIPTION',
    'CATEGORY_LV1', 'CATEGORY_LV2', 'CATEGORY_LV3', 'AMOUNT',
    'OBLIGED?', 'CROSS_FUNC?', 'BUDGET_PLAN', 'dq_flag', 'source',
    'REF_DOC', 'REF_PAGE_NO'];
  const SORTABLE = ['AMOUNT', 'FISCAL_YEAR', 'MINISTRY', 'BUDGETARY_UNIT', 'ITEM_DESCRIPTION'];

  /* ลำดับคอลัมน์ + หัวตารางภาษาไทยสำหรับ Excel */
  const EXPORT_ORDER = ['FISCAL_YEAR', 'MINISTRY', 'BUDGETARY_UNIT', 'ITEM_DESCRIPTION',
    'BUDGET_PLAN', 'OUTPUT', 'PROJECT', 'STRATEGY', 'MOTHER_PLAN',
    'CATEGORY_LV1', 'CATEGORY_LV2', 'CATEGORY_LV3', 'CATEGORY_LV4', 'CATEGORY_LV5', 'CATEGORY_LV6',
    'AMOUNT', 'OBLIGED?', 'CROSS_FUNC?', 'REF_DOC', 'REF_PAGE_NO', 'Source_Sheet', 'dq_flag', 'source'];
  const HEADER_TH = {
    FISCAL_YEAR: 'ปีงบประมาณ (ค.ศ.)', MINISTRY: 'กระทรวง', BUDGETARY_UNIT: 'หน่วยงาน',
    ITEM_DESCRIPTION: 'รายการ', BUDGET_PLAN: 'แผนงาน', OUTPUT: 'ผลผลิต (OUTPUT)',
    PROJECT: 'โครงการ (PROJECT)', STRATEGY: 'ยุทธศาสตร์', MOTHER_PLAN: 'แผนแม่บท',
    CATEGORY_LV1: 'หมวดงบ LV1', CATEGORY_LV2: 'หมวดงบ LV2', CATEGORY_LV3: 'หมวดงบ LV3',
    CATEGORY_LV4: 'หมวดงบ LV4', CATEGORY_LV5: 'หมวดงบ LV5', CATEGORY_LV6: 'หมวดงบ LV6',
    AMOUNT: 'จำนวนเงิน (บาท)', 'OBLIGED?': 'ผูกพันข้ามปี', 'CROSS_FUNC?': 'ข้ามฟังก์ชัน',
    REF_DOC: 'เอกสารอ้างอิง', REF_PAGE_NO: 'เลขหน้า', Source_Sheet: 'ชีตต้นฉบับ',
    dq_flag: 'DQ Flag', source: 'แหล่งข้อมูล',
  };
  const EXCEL_WIDTHS = {
    FISCAL_YEAR: 13, MINISTRY: 32, BUDGETARY_UNIT: 42, ITEM_DESCRIPTION: 55,
    BUDGET_PLAN: 42, OUTPUT: 32, PROJECT: 32, STRATEGY: 32, MOTHER_PLAN: 32,
    CATEGORY_LV1: 26, CATEGORY_LV2: 26, CATEGORY_LV3: 26,
    CATEGORY_LV4: 26, CATEGORY_LV5: 26, CATEGORY_LV6: 26,
    AMOUNT: 20, 'OBLIGED?': 12, 'CROSS_FUNC?': 12, REF_DOC: 34, REF_PAGE_NO: 10,
    Source_Sheet: 16, dq_flag: 34, source: 12,
  };

  /* ---------------- state ---------------- */
  let MAIN = [], COMM = [], ALL = [];
  let CSV_COLS = [];   // ลำดับคอลัมน์ตามไฟล์ CSV (สำหรับ CSV export ให้ตรง backend)
  let META = null;
  const cache = new Map();
  function cached(key, fn) {
    if (!cache.has(key)) cache.set(key, fn());
    return cache.get(key);
  }

  /* ---------------- utils ---------------- */
  const sumAmt = (rows) => rows.reduce((s, r) => s + r.AMOUNT, 0);

  function groupSum(rows, col) {
    const m = new Map();
    for (const r of rows) {
      const k = (r[col] === null || r[col] === undefined) ? '' : String(r[col]);
      m.set(k, (m.get(k) || 0) + r.AMOUNT);
    }
    return [...m.entries()]
      .map(([name, total]) => ({ name, total }))
      .sort((a, b) => (b.total - a.total) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  }

  function groupSumCount(rows, col) {
    const m = new Map();
    for (const r of rows) {
      const k = (r[col] === null || r[col] === undefined) ? '' : String(r[col]);
      const e = m.get(k) || { name: k, total: 0, rows: 0 };
      e.total += r.AMOUNT; e.rows += 1;
      m.set(k, e);
    }
    return [...m.values()]
      .sort((a, b) => (b.total - a.total) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  }

  function byYear(rows) {
    const o = {};
    for (const r of rows) o[r.FISCAL_YEAR] = (o[r.FISCAL_YEAR] || 0) + r.AMOUNT;
    return o;
  }

  function pick(r, cols) {
    const o = {};
    for (const c of cols) o[c] = (r[c] === undefined ? '' : r[c]);
    return o;
  }

  function sortRows(rows, col, asc) {
    const m = asc ? 1 : -1;
    return rows.slice().sort((a, b) => {
      const x = a[col], y = b[col];
      if (x === y) return 0;
      const ex = (x === null || x === undefined || x === '');
      const ey = (y === null || y === undefined || y === '');
      if (ex && ey) return 0;
      if (ex) return 1;   // ค่าว่างไว้ท้ายเสมอ (na_position='last')
      if (ey) return -1;
      return (x < y ? -1 : 1) * m;
    });
  }

  const clampYear = (y) => (YEARS.includes(y) ? y : 2026);

  /* ---------------- parsing ---------------- */
  function parseCSV(text, source) {
    const res = PAPA().parse(text, { header: true, skipEmptyLines: true });
    if (!CSV_COLS.length && res.meta && res.meta.fields) CSV_COLS = res.meta.fields.slice();
    const out = new Array(res.data.length);
    for (let i = 0; i < res.data.length; i++) {
      const d = res.data[i];
      const r = {};
      for (const k in d) r[k] = (d[k] === null || d[k] === undefined) ? '' : String(d[k]);
      r.AMOUNT = Number(r.AMOUNT) || 0;
      r.FISCAL_YEAR = Number(r.FISCAL_YEAR) || 0;
      r['OBLIGED?'] = (r['OBLIGED?'] === 'True' || r['OBLIGED?'] === '1');
      r['CROSS_FUNC?'] = (r['CROSS_FUNC?'] === 'True' || r['CROSS_FUNC?'] === '1');
      r.source = source;
      let s = '';
      for (const c of SEARCHABLE) s += (r[c] || '') + ' ';
      r._search = s.toLowerCase();
      out[i] = r;
    }
    return out;
  }

  function setData(mainRows, commRows) {
    MAIN = mainRows; COMM = commRows; ALL = mainRows.concat(commRows);
    cache.clear();
    META = buildMeta();
  }

  /* ---------------- meta ---------------- */
  function uniqSorted(rows, col) {
    const s = new Set();
    for (const r of rows) if (r[col]) s.add(r[col]);
    return [...s].sort();
  }

  function buildMeta() {
    const flagSet = new Set();
    for (const r of ALL) {
      if (!r.dq_flag) continue;
      for (const f of String(r.dq_flag).split(';')) if (f) flagSet.add(f);
    }
    return {
      years: YEARS.slice(),
      ministries: uniqSorted(MAIN, 'MINISTRY'),
      cat_lv1: uniqSorted(MAIN, 'CATEGORY_LV1'),
      plans: uniqSorted(MAIN, 'BUDGET_PLAN'),
      strategies: uniqSorted(MAIN, 'STRATEGY'),
      mother_plans: uniqSorted(MAIN, 'MOTHER_PLAN'),
      flag_types: [...flagSet].sort(),
      counts: {
        main_rows: MAIN.length,
        commitments_rows: COMM.length,
        ministries: new Set(MAIN.map((r) => r.MINISTRY)).size,
        units: new Set(MAIN.map((r) => r.BUDGETARY_UNIT)).size,
        plans: new Set(MAIN.map((r) => r.BUDGET_PLAN)).size,
      },
      generated: '2026-10-09',
      source_files: ['output/budget_2566-2569_clean.csv.gz',
        'output/budget_2566-2569_commitments.csv.gz'],
    };
  }

  /* ---------------- filters ---------------- */
  function applyFilters(p) {
    let d = ALL;
    if (p.source === 'main') d = MAIN;
    else if (p.source === 'commitments') d = COMM;
    if (p.q) {
      const q = String(p.q).toLowerCase();
      d = d.filter((r) => r._search.indexOf(q) !== -1);
    }
    if (p.years && p.years.length) {
      const ys = new Set(p.years);
      d = d.filter((r) => ys.has(r.FISCAL_YEAR));
    }
    if (p.ministry) d = d.filter((r) => r.MINISTRY === p.ministry);
    if (p.cat1) d = d.filter((r) => r.CATEGORY_LV1 === p.cat1);
    if (p.plan) d = d.filter((r) => r.BUDGET_PLAN === p.plan);
    if (p.amt_min !== null && p.amt_min !== undefined && p.amt_min !== '')
      d = d.filter((r) => r.AMOUNT >= Number(p.amt_min));
    if (p.amt_max !== null && p.amt_max !== undefined && p.amt_max !== '')
      d = d.filter((r) => r.AMOUNT <= Number(p.amt_max));
    if (p.obliged === true) d = d.filter((r) => r['OBLIGED?'] === true);
    if (p.cross === true) d = d.filter((r) => r['CROSS_FUNC?'] === true);
    if (p.flagged === true) d = d.filter((r) => !!r.dq_flag);
    return d;
  }

  function paginate(d, page, perPage) {
    page = Math.max(1, page || 1);
    perPage = Math.min(Math.max(perPage || 50, 10), 200);
    const start = (page - 1) * perPage;
    return { page, per_page: perPage, rows: d.slice(start, start + perPage) };
  }

  /* ---------------- endpoints ---------------- */
  function epOverview(year) {
    return cached('ov:' + year, () => {
      const my = MAIN.filter((r) => r.FISCAL_YEAR === year);
      const prev = MAIN.filter((r) => r.FISCAL_YEAR === year - 1);
      const total = sumAmt(my);
      const prevTotal = prev.length ? sumAmt(prev) : null;
      const yoy = prevTotal ? Math.round((total - prevTotal) / prevTotal * 10000) / 100 : null;

      const yg = groupSumCount(MAIN, 'FISCAL_YEAR')
        .map((g) => ({ year: Number(g.name), total: g.total, rows: g.rows }))
        .sort((a, b) => a.year - b.year);
      const commYearly = groupSum(COMM, 'FISCAL_YEAR')
        .map((g) => ({ year: Number(g.name), total: g.total }));

      const topGroup = (col, n) => groupSum(my, col).slice(0, n).map((g) => ({
        name: g.name || '(ไม่ระบุ)', total: g.total,
        share: total ? Math.round(g.total / total * 10000) / 100 : 0,
      }));

      const minRank = groupSum(my, 'MINISTRY');
      const topMinistry = minRank.length ? {
        name: minRank[0].name, total: minRank[0].total,
        share: total ? Math.round(minRank[0].total / total * 10000) / 100 : 0,
      } : null;
      const catRank = groupSum(my.filter((r) => r.CATEGORY_LV1), 'CATEGORY_LV1');
      const topCat = catRank.length ? {
        name: catRank[0].name, total: catRank[0].total,
        share: total ? Math.round(catRank[0].total / total * 10000) / 100 : 0,
      } : null;

      const labels = ['0 บาท', 'ติดลบ'];
      const counts = [
        my.filter((r) => r.AMOUNT === 0).length,
        my.filter((r) => r.AMOUNT < 0).length,
      ];
      const pos = my.filter((r) => r.AMOUNT > 0).map((r) => r.AMOUNT);
      const edges = [];
      for (let i = 0; i <= 12; i++) edges.push(Math.pow(10, i));
      for (let i = 0; i < edges.length - 1; i++) {
        const lo = edges[i], hi = edges[i + 1];
        let n = 0;
        for (const v of pos) if (v >= lo && v < hi) n++;
        labels.push(lo.toLocaleString('en-US') + '–' + hi.toLocaleString('en-US'));
        counts.push(n);
      }
      let nLast = 0;
      for (const v of pos) if (v >= edges[edges.length - 1]) nLast++;
      labels.push('≥ ' + edges[edges.length - 1].toLocaleString('en-US'));
      counts.push(nLast);

      let flaggedRows = 0;
      for (const r of ALL) if (r.dq_flag) flaggedRows++;

      return {
        year,
        kpis: {
          total, prev_total: prevTotal, yoy_pct: yoy,
          n_ministries: new Set(my.map((r) => r.MINISTRY)).size,
          n_units: new Set(my.map((r) => r.BUDGETARY_UNIT)).size,
          n_rows: my.length,
          n_plans: new Set(my.map((r) => r.BUDGET_PLAN)).size,
          total_all_years: sumAmt(MAIN),
          comm_total: sumAmt(COMM),
          comm_rows: COMM.length,
          flagged_rows: flaggedRows,
          top_ministry: topMinistry,
          top_category: topCat,
        },
        yearly: yg,
        comm_yearly: commYearly,
        top_ministries: topGroup('MINISTRY', 12),
        categories_lv1: topGroup('CATEGORY_LV1', 10),
        top_plans: topGroup('BUDGET_PLAN', 12),
        top_units: topGroup('BUDGETARY_UNIT', 15),
        distribution: { labels, counts },
      };
    });
  }

  function epSearch(p) {
    const d = applyFilters(p);
    const sortCol = SORTABLE.includes(p.sort) ? p.sort : 'AMOUNT';
    const sorted = sortRows(d, sortCol, p.order === 'asc');
    const pg = paginate(sorted, p.page, p.per_page);
    return {
      total: d.length, page: pg.page, per_page: pg.per_page,
      pages: pg.per_page ? Math.ceil(d.length / pg.per_page) : 1,
      sum: sumAmt(d),
      rows: pg.rows.map((r) => pick(r, SEARCH_COLS)),
    };
  }

  function epMinistries(year) {
    return cached('mins:' + year, () => {
      const my = MAIN.filter((r) => r.FISCAL_YEAR === year);
      const pivot = {};
      for (const r of MAIN) {
        if (!pivot[r.MINISTRY]) pivot[r.MINISTRY] = {};
        const o = pivot[r.MINISTRY];
        o[r.FISCAL_YEAR] = (o[r.FISCAL_YEAR] || 0) + r.AMOUNT;
      }
      const totals = groupSum(my, 'MINISTRY');
      const grand = totals.reduce((s, g) => s + g.total, 0);
      const out = totals.map((g) => {
        const sub = my.filter((r) => r.MINISTRY === g.name);
        const byYear = {};
        for (const y of YEARS) byYear[y] = (pivot[g.name] && pivot[g.name][y]) || 0;
        return {
          name: g.name, total: g.total,
          share: grand ? Math.round(g.total / grand * 10000) / 100 : 0,
          by_year: byYear,
          n_units: new Set(sub.map((r) => r.BUDGETARY_UNIT)).size,
          n_rows: sub.length,
        };
      });
      return { year, grand_total: grand, ministries: out };
    });
  }

  function epMinistry(name, year) {
    return cached('min:' + year + ':' + name, () => {
      const m = MAIN.filter((r) => r.MINISTRY === name);
      const my = m.filter((r) => r.FISCAL_YEAR === year);
      const total = sumAmt(my);
      const grandYear = sumAmt(MAIN.filter((r) => r.FISCAL_YEAR === year));
      const topUnits = groupSum(my, 'BUDGETARY_UNIT').slice(0, 15)
        .map((g) => ({ name: g.name, total: g.total }));
      const byCat = groupSum(my.filter((r) => r.CATEGORY_LV1), 'CATEGORY_LV1')
        .map((g) => ({ name: g.name, total: g.total }));
      const topItems = sortRows(my, 'AMOUNT', false).slice(0, 20)
        .map((r) => pick(r, ['FISCAL_YEAR', 'BUDGETARY_UNIT', 'ITEM_DESCRIPTION',
          'CATEGORY_LV1', 'AMOUNT', 'OBLIGED?', 'dq_flag']));
      const rank = groupSum(MAIN.filter((r) => r.FISCAL_YEAR === year), 'MINISTRY');
      const idx = rank.findIndex((g) => g.name === name);
      return {
        name, year, total,
        share: grandYear ? Math.round(total / grandYear * 10000) / 100 : 0,
        rank: idx >= 0 ? idx + 1 : null, n_ranked: rank.length,
        by_year: byYear(m),
        n_rows: my.length,
        n_units: new Set(my.map((r) => r.BUDGETARY_UNIT)).size,
        top_units: topUnits,
        by_category: byCat,
        top_items: topItems,
      };
    });
  }

  function epCompare(names) {
    const out = names.slice(0, 4).map((name) => {
      const m = MAIN.filter((r) => r.MINISTRY === name);
      const by = byYear(m);
      return { name, by_year: by, total: Object.values(by).reduce((s, v) => s + v, 0) };
    });
    return { series: out, years: YEARS.slice() };
  }

  function epCategories(year, pathStr) {
    return cached('cat:' + year + ':' + pathStr, () => {
      const path = pathStr ? pathStr.split('/').filter(Boolean) : [];
      let level = path.length + 1;
      if (level > 6) level = 6;
      let d = MAIN.filter((r) => r.FISCAL_YEAR === year);
      for (let i = 0; i < path.length; i++) d = d.filter((r) => r[CATS[i]] === path[i]);
      const col = CATS[level - 1];
      const g = groupSumCount(d.filter((r) => r[col]), col);
      const nodes = g.map((x) => {
        const sub = d.filter((r) => r[col] === x.name);
        let hasChildren = false;
        for (let j = level; j < 6; j++) {
          for (const r of sub) {
            if (r[CATS[j]]) { hasChildren = true; break; }
          }
          if (hasChildren) break;
        }
        return { name: x.name, total: x.total, rows: x.rows, has_children: hasChildren };
      });
      return {
        year, level, path,
        nodes, total: sumAmt(d), rows: d.length,
        grand_total: sumAmt(MAIN.filter((r) => r.FISCAL_YEAR === year)),
      };
    });
  }

  function epCategoryRows(year, pathStr, n) {
    const path = pathStr ? pathStr.split('/').filter(Boolean) : [];
    let d = MAIN.filter((r) => r.FISCAL_YEAR === year);
    for (let i = 0; i < path.length; i++) d = d.filter((r) => r[CATS[i]] === path[i]);
    d = sortRows(d, 'AMOUNT', false).slice(0, Math.min(n || 100, 500));
    return {
      rows: d.map((r) => pick(r, ['FISCAL_YEAR', 'MINISTRY', 'BUDGETARY_UNIT',
        'ITEM_DESCRIPTION', 'AMOUNT', 'OBLIGED?', 'dq_flag'])),
      total: sumAmt(d), count: d.length,
    };
  }

  function epPlans(year, q) {
    return cached('plans:' + year + ':' + (q || ''), () => {
      const my = MAIN.filter((r) => r.FISCAL_YEAR === year);
      const g = groupSumCount(my.filter((r) => r.BUDGET_PLAN), 'BUDGET_PLAN');
      const grand = sumAmt(my);
      const ql = (q || '').toLowerCase();
      const out = [];
      for (const x of g) {
        if (ql && x.name.toLowerCase().indexOf(ql) === -1) continue;
        out.push({
          name: x.name, total: x.total, rows: x.rows,
          share: grand ? Math.round(x.total / grand * 10000) / 100 : 0,
          by_year: byYear(MAIN.filter((r) => r.BUDGET_PLAN === x.name)),
        });
      }
      return { year, grand_total: grand, plans: out };
    });
  }

  function epPlan(name, year) {
    return cached('plan:' + year + ':' + name, () => {
      const m = MAIN.filter((r) => r.BUDGET_PLAN === name);
      const my = m.filter((r) => r.FISCAL_YEAR === year);
      const total = sumAmt(my);
      const grandYear = sumAmt(MAIN.filter((r) => r.FISCAL_YEAR === year));
      const topn = (col, n) => groupSum(my.filter((r) => r[col]), col)
        .slice(0, n).map((g) => ({ name: g.name, total: g.total }));
      const topItems = sortRows(my, 'AMOUNT', false).slice(0, 15)
        .map((r) => pick(r, ['FISCAL_YEAR', 'MINISTRY', 'BUDGETARY_UNIT',
          'ITEM_DESCRIPTION', 'AMOUNT', 'dq_flag']));
      return {
        name, year, total,
        share: grandYear ? Math.round(total / grandYear * 10000) / 100 : 0,
        by_year: byYear(m), n_rows: my.length,
        n_ministries: new Set(my.map((r) => r.MINISTRY)).size,
        by_ministry: topn('MINISTRY', 10),
        by_unit: topn('BUDGETARY_UNIT', 10),
        by_strategy: topn('STRATEGY', 10),
        by_mother_plan: topn('MOTHER_PLAN', 10),
        top_items: topItems,
      };
    });
  }

  function epCommitments() {
    return cached('comm', () => {
      const byYearList = groupSumCount(COMM, 'FISCAL_YEAR')
        .map((g) => ({ year: Number(g.name), total: g.total, rows: g.rows }));
      const byMin = groupSum(COMM, 'MINISTRY').slice(0, 15)
        .map((g) => ({ name: g.name, total: g.total }));
      const susp = COMM.filter((r) => r.FISCAL_YEAR <= 2021);
      const imposs = COMM.filter((r) => r.FISCAL_YEAR <= 2005);
      const yrs = COMM.map((r) => r.FISCAL_YEAR);
      return {
        total: sumAmt(COMM), rows: COMM.length,
        n_ministries: new Set(COMM.map((r) => r.MINISTRY)).size,
        year_min: Math.min.apply(null, yrs), year_max: Math.max.apply(null, yrs),
        by_year: byYearList,
        by_ministry: byMin,
        suspicious: {
          rows: susp.length, total: sumAmt(susp),
          note: 'ปี ≤ 2021 — น่าจะเป็น artifact จากการแปลงไฟล์ (ดู quarantine_review.csv.gz)',
        },
        impossible: {
          rows: imposs.length, total: sumAmt(imposs),
          note: 'ปี 1967–2005 — เป็นไปไม่ได้ในเอกสารงบประมาณปี 2566–2569',
        },
      };
    });
  }

  function epCommitmentsRows(p) {
    let d = COMM;
    if (p.q) {
      const q = String(p.q).toLowerCase();
      d = d.filter((r) => r._search.indexOf(q) !== -1);
    }
    if (p.year !== null && p.year !== undefined && p.year !== '')
      d = d.filter((r) => r.FISCAL_YEAR === Number(p.year));
    if (p.ministry) d = d.filter((r) => r.MINISTRY === p.ministry);
    d = sortRows(d, 'AMOUNT', false);
    const pg = paginate(d, p.page, p.per_page);
    return {
      total: d.length, page: pg.page, per_page: pg.per_page,
      pages: pg.per_page ? Math.ceil(d.length / pg.per_page) : 1,
      sum: sumAmt(d),
      rows: pg.rows.map((r) => pick(r, SEARCH_COLS)),
    };
  }

  function epFlags(p) {
    let d = ALL.filter((r) => !!r.dq_flag);
    if (p.type) d = d.filter((r) => String(r.dq_flag).indexOf(p.type) !== -1);
    if (p.source === 'main') d = d.filter((r) => r.source === 'main');
    else if (p.source === 'commitments') d = d.filter((r) => r.source === 'commitments');
    const counts = {};
    for (const r of ALL) {
      if (!r.dq_flag) continue;
      for (const f of String(r.dq_flag).split(';')) {
        if (f) counts[f] = (counts[f] || 0) + 1;
      }
    }
    const sortedCounts = {};
    Object.keys(counts).sort((a, b) => counts[b] - counts[a])
      .forEach((k) => { sortedCounts[k] = counts[k]; });
    d = sortRows(d, 'AMOUNT', false);
    const pg = paginate(d, p.page, p.per_page);
    return {
      counts: sortedCounts,
      total: d.length, page: pg.page, per_page: pg.per_page,
      pages: pg.per_page ? Math.ceil(d.length / pg.per_page) : 1,
      rows: pg.rows.map((r) => pick(r, SEARCH_COLS)),
    };
  }

  /* ---------------- router (รับ path แบบเดียวกับ backend) ---------------- */
  async function localApi(path) {
    const u = new URL(path, 'http://local');
    const q = u.searchParams;
    const g = (k, dflt) => {
      const v = q.get(k);
      return (v === null || v === '') ? dflt : v;
    };
    const numOr = (v, dflt) => {
      if (v === null || v === undefined || v === '') return dflt;
      const n = Number(v);
      return Number.isNaN(n) ? dflt : n;
    };
    switch (u.pathname) {
      case '/api/health':
        return { ok: true, rows: ALL.length };
      case '/api/meta':
        return META;
      case '/api/overview':
        return epOverview(clampYear(numOr(g('year', null), 2026)));
      case '/api/search': {
        const yrs = (g('years', '') || '').split(',')
          .map((s) => s.trim()).filter((s) => s !== '')
          .map((s) => Number(s)).filter((n) => !Number.isNaN(n));
        return epSearch({
          q: g('q', ''), years: yrs,
          ministry: g('ministry', ''), cat1: g('cat1', ''), plan: g('plan', ''),
          amt_min: g('amt_min', ''), amt_max: g('amt_max', ''),
          obliged: q.get('obliged') === 'true' ? true : null,
          cross: q.get('cross') === 'true' ? true : null,
          flagged: q.get('flagged') === 'true',
          source: g('source', 'all'),
          sort: g('sort', 'AMOUNT'), order: g('order', 'desc'),
          page: numOr(g('page', null), 1), per_page: numOr(g('per_page', null), 50),
        });
      }
      case '/api/ministries':
        return epMinistries(clampYear(numOr(g('year', null), 2026)));
      case '/api/ministry':
        return epMinistry(g('name', ''), clampYear(numOr(g('year', null), 2026)));
      case '/api/compare': {
        const names = (g('names', '') || '').split(',').map((s) => s.trim()).filter(Boolean);
        return epCompare(names);
      }
      case '/api/categories':
        return epCategories(clampYear(numOr(g('year', null), 2026)), g('path', ''));
      case '/api/category_rows':
        return epCategoryRows(clampYear(numOr(g('year', null), 2026)),
          g('path', ''), numOr(g('n', null), 100));
      case '/api/plans':
        return epPlans(clampYear(numOr(g('year', null), 2026)), g('q', ''));
      case '/api/plan':
        return epPlan(g('name', ''), clampYear(numOr(g('year', null), 2026)));
      case '/api/commitments':
        return epCommitments();
      case '/api/commitments_rows':
        return epCommitmentsRows({
          q: g('q', ''),
          year: g('year', ''),
          ministry: g('ministry', ''),
          page: numOr(g('page', null), 1), per_page: numOr(g('per_page', null), 50),
        });
      case '/api/flags':
        return epFlags({
          page: numOr(g('page', null), 1), per_page: numOr(g('per_page', null), 50),
          type: g('type', ''), source: g('source', 'all'),
        });
      default:
        throw new Error('unknown api: ' + u.pathname);
    }
  }

  /* ---------------- export: CSV / Excel ---------------- */
  function parseSearchQS(qs) {
    const q = new URLSearchParams(qs || '');
    const g = (k, dflt) => {
      const v = q.get(k);
      return (v === null || v === '') ? dflt : v;
    };
    const yrs = (g('years', '') || '').split(',')
      .map((s) => s.trim()).filter((s) => s !== '')
      .map((s) => Number(s)).filter((n) => !Number.isNaN(n));
    return {
      q: g('q', ''), years: yrs,
      ministry: g('ministry', ''), cat1: g('cat1', ''), plan: g('plan', ''),
      amt_min: g('amt_min', ''), amt_max: g('amt_max', ''),
      obliged: q.get('obliged') === 'true' ? true : null,
      cross: q.get('cross') === 'true' ? true : null,
      flagged: q.get('flagged') === 'true',
      source: g('source', 'all'),
      sort: (['AMOUNT', 'FISCAL_YEAR'].includes(g('sort', 'AMOUNT'))) ? g('sort', 'AMOUNT') : 'AMOUNT',
      order: g('order', 'desc'),
    };
  }

  function filteredSorted(p) {
    const d = applyFilters(p);
    return sortRows(d, p.sort || 'AMOUNT', p.order === 'asc');
  }

  const csvCell = (v) => {
    let s;
    if (v === true) s = 'True';
    else if (v === false) s = 'False';
    else s = String((v === null || v === undefined) ? '' : v);
    return (/[",\n\r]/.test(s)) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };

  function buildCSV(rows, cols) {
    const lines = [cols.map(csvCell).join(',')];
    for (const r of rows) lines.push(cols.map((c) => csvCell(r[c])).join(','));
    return '﻿' + lines.join('\r\n');
  }

  function stampName(prefix, ext) {
    const d = new Date();
    const p2 = (n) => String(n).padStart(2, '0');
    return prefix + '_' + d.getFullYear() + p2(d.getMonth() + 1) + p2(d.getDate()) +
      '_' + p2(d.getHours()) + p2(d.getMinutes()) + p2(d.getSeconds()) + '.' + ext;
  }

  function describeFilter(p) {
    if (!p) return 'ทั้งฐานข้อมูล (ไฟล์หลัก + ภาระผูกพัน)';
    const parts = [];
    if (p.q) parts.push('คำค้น: ' + p.q);
    if (p.years && p.years.length) parts.push('ปี: ' + p.years.join(', '));
    if (p.ministry) parts.push('กระทรวง: ' + p.ministry);
    if (p.cat1) parts.push('หมวด LV1: ' + p.cat1);
    if (p.plan) parts.push('แผนงาน: ' + p.plan);
    if (p.amt_min !== '') parts.push('วงเงิน ≥ ' + p.amt_min);
    if (p.amt_max !== '') parts.push('วงเงิน ≤ ' + p.amt_max);
    if (p.obliged) parts.push('เฉพาะผูกพัน');
    if (p.cross) parts.push('เฉพาะข้ามฟังก์ชัน');
    if (p.flagged) parts.push('เฉพาะมี DQ flag');
    const src = { all: 'ทุกแหล่ง', main: 'ไฟล์หลัก', commitments: 'ภาระผูกพัน' };
    parts.push('แหล่ง: ' + (src[p.source] || p.source));
    return parts.join(' · ') || 'ทั้งฐานข้อมูล';
  }

  function excelCell(v, col) {
    if (v === true) return 'ใช่';
    if (v === false) return 'ไม่ใช่';
    if (v === null || v === undefined) return '';
    if (col === 'source') return v === 'commitments' ? 'ภาระผูกพัน' : 'ไฟล์หลัก';
    if (typeof v === 'number') return v;
    const s = String(v);
    if (col === 'REF_PAGE_NO' && s !== '') {
      const n = Number(s);
      if (!Number.isNaN(n)) return n;
    }
    return s;
  }

  function buildWorkbook(rows, filterDesc, cols) {
    const XLSX = global.XLSX;
    const headers = cols.map((c) => HEADER_TH[c] || c);
    const aoa = [headers];
    for (const r of rows) {
      const line = new Array(cols.length);
      for (let i = 0; i < cols.length; i++) line[i] = excelCell(r[cols[i]], cols[i]);
      aoa.push(line);
    }
    const ws = XLSX.utils.aoa_to_sheet(aoa);
    ws['!cols'] = cols.map((c) => ({ wch: EXCEL_WIDTHS[c] || 22 }));
    /* รูปแบบตัวเลขคอลัมน์ AMOUNT */
    try {
      const ai = cols.indexOf('AMOUNT');
      if (ai >= 0) {
        for (let R = 1; R <= rows.length; R++) {
          const addr = XLSX.utils.encode_cell({ r: R, c: ai });
          if (ws[addr] && typeof ws[addr].v === 'number') ws[addr].z = '#,##0';
        }
      }
      ws['!freeze'] = 'A2';
      ws['!autofilter'] = { ref: ws['!ref'] };
    } catch (e) { /* cosmetic only */ }
    const total = rows.reduce((s, r) => s + (Number(r.AMOUNT) || 0), 0);
    const now = new Date();
    const summary = [
      ['งบประมาณไทย 2566–2569 — ข้อมูลส่งออก'],
      ['วันที่ส่งออก', now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') +
        '-' + String(now.getDate()).padStart(2, '0') + ' ' +
        String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0')],
      ['เงื่อนไข', filterDesc],
      ['จำนวนแถว', rows.length],
      ['ยอดรวม (บาท)', total],
      ['แหล่งข้อมูล', 'budget_2566-2569_clean.csv.gz + commitments (clean 2026-10-09)'],
    ];
    const ws2 = XLSX.utils.aoa_to_sheet(summary);
    ws2['!cols'] = [{ wch: 18 }, { wch: 90 }];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'ข้อมูลงบประมาณ');
    XLSX.utils.book_append_sheet(wb, ws2, 'สรุป');
    return wb;
  }

  function downloadBlob(blob, filename) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
  }

  /* overlay สำหรับงานหนัก (export) */
  function showWork(title, sub) {
    if (!isBrowser) return;
    hideWork();
    const ov = document.createElement('div');
    ov.id = 'work-overlay';
    ov.setAttribute('style', 'position:fixed;inset:0;z-index:300;display:flex;align-items:center;' +
      'justify-content:center;background:rgba(30,27,20,.5);backdrop-filter:blur(4px);padding:24px;');
    ov.innerHTML = '<div style="background:var(--card,#fff);border-radius:18px;padding:28px 32px;' +
      'max-width:440px;width:100%;text-align:center;box-shadow:0 24px 60px -20px rgba(0,0,0,.35);">' +
      '<div class="spinner" style="width:34px;height:34px;border-radius:50%;margin:0 auto 14px;' +
      'border:3px solid var(--border,#e3dfd3);border-top-color:var(--accent,#c96442);' +
      'animation:spin .8s linear infinite;"></div>' +
      '<div style="font-family:var(--serif,serif);font-weight:700;font-size:17px;">' + title + '</div>' +
      '<div style="font-size:13px;color:var(--text-2,#625d4f);margin-top:6px;">' + sub + '</div></div>' +
      '<style>@keyframes spin{to{transform:rotate(360deg)}}</style>';
    document.body.appendChild(ov);
  }
  function hideWork() {
    if (!isBrowser) return;
    const ov = document.getElementById('work-overlay');
    if (ov) ov.remove();
  }
  const tick = () => new Promise((r) => setTimeout(r, 30));

  const DSX = {
    buildCSV, buildWorkbook, filteredSorted, parseSearchQS, describeFilter,
    csvCols: () => CSV_COLS.concat(['source']),
    excelCols: () => EXPORT_ORDER.slice(),

    async csv(queryString) {
      const p = parseSearchQS(queryString);
      const rows = filteredSorted(p).slice(0, 100000);
      const cols = CSV_COLS.concat(['source']);
      showWork('กำลังสร้างไฟล์ CSV…', rows.length.toLocaleString('en-US') + ' แถว');
      await tick();
      try {
        const text = buildCSV(rows, cols);
        downloadBlob(new Blob([text], { type: 'text/csv;charset=utf-8' }),
          stampName('budget_export', 'csv'));
      } finally { hideWork(); }
    },

    async excel(queryString, full) {
      const p = full ? null : parseSearchQS(queryString);
      const rows = full ? ALL.slice() : filteredSorted(p);
      const desc = describeFilter(p);
      const big = rows.length > 50000;
      showWork('กำลังสร้างไฟล์ Excel…',
        rows.length.toLocaleString('en-US') + ' แถว' +
        (big ? '<br>ไฟล์ใหญ่ อาจใช้เวลา 1–2 นาที กรุณารอ…' : ''));
      await tick();
      try {
        const wb = buildWorkbook(rows, desc, EXPORT_ORDER);
        global.XLSX.writeFile(wb, stampName(full ? 'budget_2566-2569_full' : 'budget_export', 'xlsx'));
      } finally { hideWork(); }
    },
  };

  /* ---------------- browser boot: โหลด .gz 2 ไฟล์ ---------------- */
  function showBoot(pct, status) {
    let ov = document.getElementById('boot-overlay');
    if (!ov) {
      ov = document.createElement('div');
      ov.id = 'boot-overlay';
      ov.setAttribute('style', 'position:fixed;inset:0;z-index:400;display:flex;align-items:center;' +
        'justify-content:center;background:#f6f4ee;padding:24px;');
      ov.innerHTML = '<div style="max-width:420px;width:100%;text-align:center;">' +
        '<div style="width:56px;height:56px;border-radius:16px;margin:0 auto 16px;' +
        'background:linear-gradient(135deg,#d97757,#b04e2e);color:#fff;' +
        'font-family:Georgia,serif;font-weight:700;font-size:30px;line-height:56px;">฿</div>' +
        '<div style="font-family:Georgia,serif;font-weight:700;font-size:22px;color:#23211b;">งบประมาณไทย 2566–2569</div>' +
        '<div id="boot-status" style="font-size:13.5px;color:#625d4f;margin:10px 0 12px;">กำลังโหลดฐานข้อมูล…</div>' +
        '<div style="height:10px;background:#e9e5d8;border-radius:999px;overflow:hidden;">' +
        '<div id="boot-bar" style="height:100%;width:0%;border-radius:999px;' +
        'background:linear-gradient(90deg,#d97757,#c96442);transition:width .2s;"></div></div>' +
        '<div id="boot-pct" style="font-size:12px;color:#918b7a;margin-top:8px;">0%</div></div>';
      document.body.appendChild(ov);
    }
    const bar = document.getElementById('boot-bar');
    const pc = document.getElementById('boot-pct');
    const st = document.getElementById('boot-status');
    if (bar) bar.style.width = Math.min(100, Math.max(0, pct)) + '%';
    if (pc) pc.textContent = Math.round(pct) + '%';
    if (st && status) st.textContent = status;
  }
  function hideBoot() {
    const ov = document.getElementById('boot-overlay');
    if (ov) {
      ov.style.transition = 'opacity .3s';
      ov.style.opacity = '0';
      setTimeout(() => ov.remove(), 320);
    }
  }
  function bootError(msg) {
    showBoot(0, 'เกิดข้อผิดพลาด: ' + msg + ' — กรุณารีเฟรชแล้วลองใหม่');
  }

  async function fetchGzText(url, onProgress) {
    const res = await fetch(url);
    if (!res.ok) throw new Error('โหลด ' + url + ' ไม่สำเร็จ (HTTP ' + res.status + ')');
    const total = Number(res.headers.get('content-length')) || 0;
    const reader = res.body.getReader();
    const chunks = [];
    let loaded = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      loaded += value.length;
      if (onProgress) onProgress(loaded, total);
    }
    const blob = new Blob(chunks);
    if (typeof DecompressionStream === 'undefined')
      throw new Error('เบราว์เซอร์ไม่รองรับ DecompressionStream กรุณาใช้ Chrome/Edge/Firefox/Safari รุ่นใหม่');
    const ds = new DecompressionStream('gzip');
    const stream = blob.stream().pipeThrough(ds);
    return await new Response(stream).text();
  }

  if (isBrowser) {
    global.__dataReady = (async () => {
      try {
        showBoot(2, 'กำลังโหลดฐานข้อมูล (ไฟล์หลัก ~12.5 MB)…');
        const TOTAL_GZ = 13673819; // ขนาด .gz รวม 2 ไฟล์ (ประมาณ)
        let done0 = 0;
        const prog = (base) => (loaded) => {
          showBoot((base + loaded) / TOTAL_GZ * 88,
            'กำลังโหลดฐานข้อมูล… ' + ((base + loaded) / 1048576).toFixed(1) + ' / 13.0 MB');
        };
        const t1 = await fetchGzText('data/budget_2566-2569_clean.csv.gz', prog(0));
        done0 = 12486226;
        showBoot(80, 'กำลังโหลดภาระผูกพัน (~1.2 MB)…');
        const t2 = await fetchGzText('data/budget_2566-2569_commitments.csv.gz', prog(done0));
        showBoot(92, 'กำลังประมวลผล 231,221 แถว…');
        await tick();
        const m = parseCSV(t1, 'main');
        const c = parseCSV(t2, 'commitments');
        setData(m, c);
        showBoot(100, 'พร้อมใช้งาน');
        await tick();
        hideBoot();
      } catch (e) {
        console.error(e);
        bootError(e.message || String(e));
        throw e;
      }
    })();
  }

  /* ---------------- exports ---------------- */
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      parseCSV, setData, buildMeta, localApi, DSX,
      _get: () => ({ MAIN, COMM, ALL, META, CSV_COLS }),
    };
  } else {
    global.__localApi = localApi;
    global.__DSX = DSX;
    global.DSX = DSX;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
