// Offline rendering of local original HTML; no remote browser or network service.
const {chromium} = require('C:/Users/14156/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
(async()=>{
 const root=__dirname;
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try {
  const context=await browser.newContext({javaScriptEnabled:false,viewport:{width:1250,height:1000}});
  const blocked=[];
  await context.route('**/*',async route=>{
   if(route.request().url().startsWith('file:')) await route.continue();
   else {blocked.push(route.request().url());await route.abort();}
  });
  const page=await context.newPage();
  await page.goto(pathToFileURL(path.join(root,'html/config/ini-homing.html')).href);
  const table=page.locator('table.tableblock');
  await table.screenshot({path:path.join(root,'render/linux-table.png')});
  const sections=[['_home_search_vel','linux-search'],['_home_latch_vel','linux-latch'],['_home_final_vel','linux-final'],['_home_absolute_encoder','linux-absolute'],['sec:homing-section','linux-sequence'],['_immediate_homing','linux-immediate']];
  const dom={title:await page.title(),table:await table.locator('tr').evaluateAll(rows=>rows.map(r=>Array.from(r.cells,c=>c.innerText.trim()))),sections:{}};
  for (const [id,name] of sections){
   const section=page.locator(`[id="${id}"]`).locator('..');
   await section.screenshot({path:path.join(root,`render/${name}.png`)});
   dom.sections[id]={text:await section.innerText(),pre:await section.locator('pre').allTextContents()};
  }
  fs.writeFileSync(path.join(root,'browser-dom.json'),JSON.stringify({browser:await browser.version(),javaScriptEnabled:false,network:'file only, all remote requests blocked',blocked,dom},null,2)+'\n');
  console.log(JSON.stringify({status:'RENDERED_NOT_YET_VISUALLY_REVIEWED',table:dom.table,sections:sections.length,browser:await browser.version()}));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
