// Рендер постера: векторный PDF (A3 в обрез и с вылетами 3 мм) и PNG 300 dpi.
//   python3 build.py && node render.js
// Нужен Playwright с Chromium (в Node: npm i playwright).
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require('/opt/node-tools/node_modules/playwright')); }

const OUT = path.resolve(__dirname, '..');
const A3 = { w: 1122.52, h: 1587.4 };  // 297 x 420 мм в CSS-пикселях

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: Math.ceil(A3.w), height: Math.ceil(A3.h) }, deviceScaleFactor: 300 / 96 });

  await page.goto('file://' + path.join(__dirname, 'poster.html'));
  await page.pdf({ path: path.join(OUT, 'Постер_олимпиада_по_хирургии_A3.pdf'), width: '297mm', height: '420mm', printBackground: true });
  await page.screenshot({ path: path.join(OUT, 'Постер_олимпиада_по_хирургии_A3.png'), clip: { x: 0, y: 0, width: A3.w, height: A3.h } });

  await page.goto('file://' + path.join(__dirname, 'poster_bleed.html'));
  await page.pdf({ path: path.join(__dirname, 'Постер_A3_вылеты_3мм.pdf'), width: '303mm', height: '426mm', printBackground: true });

  await browser.close();
})();
