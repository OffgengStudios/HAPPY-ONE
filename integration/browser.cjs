const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require(require.resolve('@playwright/test', { paths: [path.join(__dirname,'../HAPPY_PLATFORM_CODEX/apps/web')] }));
const origin = process.env.HAPPY_INTAKE_TEST_ORIGIN || 'http://127.0.0.1:8765';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHANNEL ? {channel:process.env.PLAYWRIGHT_CHANNEL} : {}) });
  try {
    for (const [name, viewport] of [['desktop',{width:1440,height:900}],['mobile',{width:390,height:844}]]) {
      const context = await browser.newContext({viewport});
      const page = await context.newPage();
      const errors=[];page.on('pageerror', error=>errors.push(error.message));
      // Make the test independent of third-party font/CDN availability.
      await page.route(/^https:\/\/(?:fonts\.|cdn\.tailwindcss)/,route=>route.abort());
      await page.goto(origin + '/frontend/');
      await page.locator('#consent-submit').waitFor({state:'visible'});
      await page.locator('#consent-accepted').check();
      await page.locator('#consent-submit').click();
      await page.locator('#pi-firstName').fill('Synthetic');
      await page.locator('#pi-surname').fill('Browser '+name);
      await page.locator('#pi-telephone').fill(name==='desktop'?'0243334401':'0243334402');
      await page.locator('#pi-community').fill('Synthetic Browser Community');
      await page.reload();
      assert.equal(await page.locator('#pi-firstName').inputValue(),'Synthetic');
      await page.locator('#consent-accepted').check();await page.locator('#consent-submit').click();
      await page.locator('#pi-submit').click();
      await page.locator('#cb-submit').click();
      if (name === 'desktop') {
        await page.locator('#cv-file-input').setInputFiles(process.env.HAPPY_BROWSER_CV);
        await page.locator('#cv-review-btn').click();
      } else {
        await page.locator('#cv-skip-btn').click();
      }
      await page.locator('#intake-submit').click();
      await page.locator('#screen-complete').waitFor({state:'visible'});
      assert.match(await page.locator('#complete-participant-id').textContent(),/^[0-9a-f-]{36}$/);
      assert.equal(await page.evaluate(()=>sessionStorage.getItem('happy_hamis_local_draft_v1')),null);
      assert.equal(await page.locator('input[type=password]').count(),0);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.screenshot({path:path.join(__dirname,'../HAPPY_PLATFORM_CODEX/.local/hamis-'+name+'.png'),fullPage:true});
      await page.goto(origin + '/portal/');
      await page.getByLabel('Company name',{exact:true}).fill('Synthetic Browser Employer '+name);
      await page.getByLabel('Contact name',{exact:true}).fill('Synthetic Contact');
      await page.getByLabel('Contact phone',{exact:true}).fill(name==='desktop'?'0243335501':'0243335502');
      await page.getByLabel('Contact email',{exact:true}).fill('synthetic-'+name+'@example.org');
      await page.locator('[name=consent_agreement]').check();await page.locator('[name=consent_contact]').check();
      await page.getByLabel('Job title',{exact:true}).fill('Synthetic Warehouse Assistant');
      await page.getByLabel('Job location',{exact:true}).fill('Tema');
      await page.getByLabel('Required skills, one per line').fill('Excel');
      await page.getByRole('button',{name:'Review application',exact:true}).click();
      await page.getByRole('button',{name:'Submit application',exact:true}).click();
      await page.locator('#success').waitFor({state:'visible'});
      assert.match(await page.locator('#receipt').textContent(),/^[0-9a-f-]{36}$/);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.screenshot({path:path.join(__dirname,'../HAPPY_PLATFORM_CODEX/.local/employer-'+name+'.png'),fullPage:true});
      assert.deepEqual(errors,[]);
      await context.close();
      console.log(name+': participant and employer live API journeys passed.');
    }
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
