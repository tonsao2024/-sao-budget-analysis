// ทดสอบ: ข้อมูลจากไฟล์ columnar ให้ผลตรงกับที่เซิร์ฟเวอร์ (FastAPI) ตอบไหม
const zlib=require('zlib'), fs=require('fs');
const api=require('./docs/static/api.js');
const read=(f)=>JSON.parse(zlib.gunzipSync(fs.readFileSync(f)).toString('utf8'));
const t0=Date.now();
const m=api.rowsFromColumns(read('docs/data/main.cols.json.gz'),'main');
const c=api.rowsFromColumns(read('docs/data/comm.cols.json.gz'),'commitments');
api.setData(m,c);
console.log(`  โหลด+ประกอบข้อมูล (จำลองเบราว์เซอร์): ${((Date.now()-t0)/1000).toFixed(2)} วิ`);
(async()=>{
  const get=(p)=>api.localApi(p);
  const ov=await get('/api/overview?year=2026');
  const mi=await get('/api/ministries?year=2026');
  const se=await get('/api/search?q=%E0%B8%99%E0%B9%89%E0%B8%B3&per_page=5');
  const meta=await get('/api/meta');
  console.log(`  overview 2026 total = ${ov.kpis.total.toLocaleString()}`);
  console.log('  ministries 2026 =', JSON.stringify(mi).slice(0,120));
  console.log('  search "น้ำ" =', JSON.stringify({total: se.total, rows: (se.rows||[]).length}));
  console.log(`  meta counts = main ${meta.counts.main_rows.toLocaleString()} + comm ${meta.counts.commitments_rows.toLocaleString()}`);
  console.log(`  RAM = ${(process.memoryUsage().heapUsed/1e6).toFixed(0)} MB`);
})();
