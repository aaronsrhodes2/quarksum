#!/usr/bin/env node
/**
 * Visual test for improved NeoPixel LED rendering.
 * Tests: glow, hotspot, label hiding, Button Lights example.
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function main() {
  const browser = await chromium.launch({
    headless: true,
    channel: 'chrome',
  });
  const page = await browser.newPage();

  const consoleLogs = [];
  page.on('console', (msg) => {
    consoleLogs.push({ type: msg.type(), text: msg.text() });
  });

  const pageErrors = [];
  page.on('pageerror', (err) => {
    pageErrors.push(err.message);
  });

  const baseDir = path.join(__dirname, 'screenshots');
  if (!fs.existsSync(baseDir)) fs.mkdirSync(baseDir, { recursive: true });

  console.log('1. Navigating to http://localhost:8000...');
  await page.goto('http://localhost:8000', { waitUntil: 'domcontentloaded', timeout: 10000 });

  console.log('2. Waiting 20 seconds for Pyodide...');
  await page.waitForTimeout(20000);

  const loaded = await page.evaluate(() => {
    const overlay = document.getElementById('loading-overlay');
    return overlay ? overlay.classList.contains('hidden') : false;
  });
  if (!loaded) console.log('   WARNING: Overlay still visible');

  // Screenshot 1: LEDs OFF (initial state)
  await page.screenshot({ path: path.join(baseDir, 'neo-01-leds-off.png'), fullPage: true });
  console.log('   Screenshot: neo-01-leds-off.png');

  // Screenshot 2: NeoPixel Rainbow running
  console.log('3. Clicking Run (NeoPixel Rainbow)...');
  await page.click('#btn-run');
  console.log('4. Waiting 4 seconds...');
  await page.waitForTimeout(4000);

  await page.screenshot({ path: path.join(baseDir, 'neo-02-rainbow-lit.png'), fullPage: true });
  console.log('   Screenshot: neo-02-rainbow-lit.png');

  // Stop, then test Button Lights
  console.log('5. Stopping, then loading Button Lights...');
  await page.click('#btn-stop');
  await page.waitForTimeout(300);

  await page.selectOption('#examples-select', 'button_lights');
  await page.waitForTimeout(200);

  console.log('6. Running Button Lights, pressing Button A...');
  await page.click('#btn-run');
  await page.waitForTimeout(500);

  // Button A is the first .board-button (left side of board)
  const btnA = page.locator('#board-container .board-button').first();
  const btnABox = await btnA.boundingBox();
  if (btnABox) {
    await page.mouse.move(btnABox.x + btnABox.width / 2, btnABox.y + btnABox.height / 2);
    await page.mouse.down();
    await page.waitForTimeout(800);
  }

  await page.screenshot({ path: path.join(baseDir, 'neo-03-button-a-red.png'), fullPage: true });
  console.log('   Screenshot: neo-03-button-a-red.png');

  await page.mouse.up();

  await browser.close();

  // Report
  console.log('\n========== NEO PIXEL VISUAL TEST REPORT ==========\n');
  console.log('Screenshots saved to cpx-emulator/screenshots/neo-*.png');
  console.log('  neo-01-leds-off.png     - Initial state, LEDs off');
  console.log('  neo-02-rainbow-lit.png - NeoPixel Rainbow running');
  console.log('  neo-03-button-a-red.png - Button Lights, Button A pressed\n');

  if (pageErrors.length > 0) {
    console.log('--- Browser DevTools / Page Errors ---');
    pageErrors.forEach((e) => console.log(e));
    console.log('--- End ---\n');
  }

  const errorLogs = consoleLogs.filter((l) => l.type === 'error');
  if (errorLogs.length > 0) {
    console.log('--- Browser Console Errors ---');
    errorLogs.forEach((l) => console.log(l.text));
    console.log('--- End ---\n');
  }

  console.log('--- All Console Messages ---');
  consoleLogs.forEach((l) => console.log(`[${l.type}] ${l.text}`));
  console.log('--- End ---');
}

main().catch((err) => {
  console.error('Test failed:', err);
  process.exit(1);
});
