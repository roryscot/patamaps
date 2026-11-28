const fs=require('node:fs');
const {test,expect}=require("/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/original-owner-five-project-browser-20261027/tools/packages/web/node_modules/@playwright/test");
const cfg=JSON.parse(fs.readFileSync(process.env.PATAMAPS_OWNED_AUTH_CONFIG,'utf8'));
const marker="PatamapsRetainedOwnerLabel20261026";

function attachDiagnostic(page,project){
 const destination=require('node:path').join(__dirname,'diagnostic-browser-'+project.replace(/[^A-Za-z0-9_-]/g,'_')+'.jsonl');
 fs.writeFileSync(destination,'',{flag:'wx',mode:0o600});let count=0;
 const endpoints=new Set(['/api/v1/auth/login','/api/v1/auth/me','/api/v1/rbac/permissions','/api/v1/rbac/check-permission','/login','/admin/users']);
 const emit=(kind,url,method,status,stage)=>{
  if(++count>4096)throw Error('OWNED_DIAGNOSTIC_EVENT_LIMIT');
  let u;try{u=new URL(url);}catch{}
  const origin=u?.origin==='http://127.0.0.1:18765'?'api':u?.origin==='http://127.0.0.1:13000'?'web':'other';
  const endpoint=endpoints.has(u?.pathname)?u.pathname:'other';
  const row={kind,origin,endpoint};
  if(['GET','POST','OPTIONS','HEAD','PUT','PATCH','DELETE'].includes(method))row.method=method;
  if(Number.isInteger(status)&&status>=100&&status<=599)row.status=status;
  if(['login-start','submit','login-response','current-user-response','permissions-navigation','permissions-response','page-error'].includes(stage))row.stage=stage;
  fs.appendFileSync(destination,JSON.stringify(row)+'\n');
 };
 page.on('request',r=>emit('request',r.url(),r.method()));
 page.on('response',r=>emit('response',r.url(),r.request().method(),r.status()));
 page.on('requestfailed',r=>emit('request-failed',r.url(),r.method()));
 page.on('pageerror',()=>emit('stage',undefined,undefined,undefined,'page-error'));
 page.__ownedDiagnostic=stage=>emit('stage',undefined,undefined,undefined,stage);
}

async function login(page,user){
 page.__ownedDiagnostic('login-start');
 await page.goto('/login');
 await page.locator('#email').fill(user.email);
 await page.locator('#password').fill(user.password);
 const response=page.waitForResponse(r=>r.url()==='http://127.0.0.1:18765/api/v1/auth/login'&&r.request().method()==='POST');
 const current=page.waitForResponse(r=>r.url()==='http://127.0.0.1:18765/api/v1/auth/me'&&r.status()===200);
 page.__ownedDiagnostic('submit');
 await page.locator('button[type="submit"]').click();
 expect((await response).status()).toBe(200);page.__ownedDiagnostic('login-response');
 const me=await(await current).json();page.__ownedDiagnostic('current-user-response');expect(me.id).toBe(user.id);expect(me.email).toBe(user.email);
}
test('real login, edited navigation and exact permission denial',async({browser},info)=>{
 test.setTimeout(20000);
 for(const which of['allowed','denied']){
  const options={};for(const key of['viewport','screen','deviceScaleFactor','isMobile','hasTouch','userAgent','locale','timezoneId','colorScheme','reducedMotion','forcedColors'])if(info.project.use[key]!==undefined)options[key]=info.project.use[key];
  const context=await browser.newContext({...options,baseURL:process.env.PLAYWRIGHT_TEST_BASE_URL,proxy:{server:process.env.PATAMAPS_TEST_PROXY}});
  try{
   const page=await context.newPage();attachDiagnostic(page,info.project.name);
   await login(page,cfg.users[which]);
   const permissions=page.waitForResponse(r=>r.url()==='http://127.0.0.1:18765/api/v1/rbac/permissions'&&r.status()===200);
   page.__ownedDiagnostic('permissions-navigation');
   await page.goto('/admin/users');
   const perms=await(await permissions).json();page.__ownedDiagnostic('permissions-response');
   expect(perms.permissions.includes('admin:users')).toBe(which==='allowed');
   if(info.project.name.startsWith('Mobile')){
    const trigger=page.locator('[data-sidebar="trigger"]').first();
    if(await trigger.isVisible())await trigger.click();
   }
   const link=page.getByRole('link',{name:marker,exact:true});
   if(which==='allowed'){
    await expect(link).toBeVisible();await expect(link).toHaveAttribute('href','/admin/users');
    await link.click();await expect(page).toHaveURL(/\/admin\/users/);
    await expect(page.getByRole('heading',{name:'Users',exact:true})).toBeVisible();
    await expect(page.getByText('Access Denied',{exact:true})).toHaveCount(0);
   }else{
    await expect(link).toHaveCount(0);
    await expect(page.getByText('Access Denied',{exact:true})).toBeVisible();
   }
  }finally{await context.close();}
 }
});
