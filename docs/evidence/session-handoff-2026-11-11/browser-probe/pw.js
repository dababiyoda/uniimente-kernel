const { chromium } = require('playwright');
(async () => { const t=Date.now(); const b = await chromium.launch(); const p = await b.newPage(); await p.goto(process.argv[2]); console.log('playwright got', await p.textContent('#x'), 'ms', Date.now()-t); await b.close(); })().catch(e => { console.log('playwright error', String(e).slice(0,300)); process.exit(1); });
