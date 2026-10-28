"""Deterministic browser UI smoke test (inline test assets; HTTP CSP tested separately)."""
import json
import os
import shutil
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

ROOT = Path(__file__).resolve().parents[1]
otp = app.local_assessment('Salam sir, main Easypaisa head office se bol raha hoon. Apka account block hone wala hai. Abhi jo OTP aaya hai wo mujhe bata dain.')
parcel = app.local_assessment('Pakistan Post Customs: your parcel is held. Pay Rs 4,200 immediately at https://bit.ly/pk-custom-pay to avoid FIR.')
html = (ROOT / 'index.html').read_text()
html = html.replace('<link rel="stylesheet" href="/styles.css">', '<style>' + (ROOT / 'styles.css').read_text() + '</style>')
html = html.replace('<script src="/app.js" defer></script>', '''<script>
window.__analyzeCalls = 0;
window.fetch = async (path, options) => {
 if (path === '/api/config') return new Response(JSON.stringify({ai_available:false}),{status:200});
 if (path === '/api/analyze') {
  window.__analyzeCalls++;
  const text = JSON.parse(options.body).message;
  await new Promise(resolve=>setTimeout(resolve,70));
  return new Response(JSON.stringify(text.toLowerCase().includes('parcel') ? PARCEL_RESULT : OTP_RESULT),{status:200});
 }
 throw new Error('Unexpected endpoint');
};
</script><script>''' .replace('PARCEL_RESULT',json.dumps(parcel,ensure_ascii=False)).replace('OTP_RESULT',json.dumps(otp,ensure_ascii=False)) + (ROOT / 'app.js').read_text() + '</script>')
# No real external resources are required for this test; original web font link is optional.
html = '\n'.join(line for line in html.splitlines() if 'fonts.googleapis.com' not in line and 'fonts.gstatic.com' not in line)

with sync_playwright() as p:
    executable = os.environ.get('CHROME_BIN') or shutil.which('chromium') or shutil.which('google-chrome')
    options = {'headless': True, 'args': ['--no-sandbox']}
    if executable:
        options['executable_path'] = executable
    browser = p.chromium.launch(**options)
    errors = []
    for width, height, name, sample in ((1440,1100,'desktop','otp'), (390,844,'mobile','parcel')):
        page = browser.new_page(viewport={'width':width, 'height':height}, device_scale_factor=1)
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.set_content(html, wait_until='domcontentloaded')
        page.locator(f'[data-sample="{sample}"]').click()
        # The second shortcut must not send another concurrent paid request.
        page.locator('#message').press('Control+Enter')
        page.locator('#message').press('Control+Enter')
        page.locator('#verdictTitle').wait_for(state='visible')
        assert page.evaluate('window.__analyzeCalls') == 1
        assert page.locator('#verdictTitle').inner_text() == 'High fraud risk'
        assert page.locator('#flags li').count() > 0
        page.locator('#langUr').click()
        assert 'urdu' in page.locator('#explanation').get_attribute('class')
        assert page.locator('#explanation').inner_text().startswith('اس')
        page.locator('#themeBtn').click()
        assert page.locator('html').get_attribute('data-theme') == 'dark'
        page.locator('#themeBtn').click()
        page.screenshot(path=str(ROOT / f'sach-pro-{name}.png'), full_page=True, timeout=20000)
        assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
        page.locator('#message').fill('New content not yet checked')
        assert page.locator('#assessment').is_hidden()
        assert page.locator('#resultEmpty').is_visible()
        page.locator('#clearHistory').click()
        assert page.locator('#historySection').is_hidden()
        page.close()
        print(f'{name}: assessment, Urdu, theme, stale results, history, repeated submission — PASS')
    assert not errors, errors
    print('Browser JavaScript errors: none')
    browser.close()
