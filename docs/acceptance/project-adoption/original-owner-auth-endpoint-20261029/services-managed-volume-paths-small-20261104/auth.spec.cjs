const fs=require('node:fs');
const {test,expect}=require("/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/original-owner-five-project-browser-20261027/tools/packages/web/node_modules/@playwright/test");
const cfg=JSON.parse(fs.readFileSync(process.env.PATAMAPS_OWNED_AUTH_CONFIG,'utf8'));
const marker="PatamapsRetainedOwnerLabel20261026";
async function login(page,user){
 await page.goto('/login');
 await page.locator('#email').fill(user.email);
 await page.locator('#password').fill(user.password);
 const response=page.waitForResponse(r=>r.url()==='http://127.0.0.1:18765/api/v1/auth/login'&&r.request().method()==='POST');
 const current=page.waitForResponse(r=>r.url()==='http://127.0.0.1:18765/api/v1/auth/me'&&r.status()===200);
 await page.locator('button[type="submit"]').click();
 expect((await response).status()).toBe(200);
 const me=await(await current).json();expect(me.id).toBe(user.id);expect(me.email).toBe(user.email);
}
test('real login, edited navigation and exact permission denial',async({browser},info)=>{
 test.setTimeout(20000);
 for(const which of['allowed','denied']){
  const options={};for(const key of['viewport','screen','deviceScaleFactor','isMobile','hasTouch','userAgent','locale','timezoneId','colorScheme','reducedMotion','forcedColors'])if(info.project.use[key]!==undefined)options[key]=info.project.use[key];
  const context=await browser.newContext({...options,baseURL:process.env.PLAYWRIGHT_TEST_BASE_URL,proxy:{server:process.env.PATAMAPS_TEST_PROXY}});
  try{
   const page=await context.newPage();
   await login(page,cfg.users[which]);
   const permissions=page.waitForResponse(r=>r.url()==='http://127.0.0.1:18765/api/v1/rbac/permissions'&&r.status()===200);
   await page.goto('/admin/users');
   const perms=await(await permissions).json();
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
