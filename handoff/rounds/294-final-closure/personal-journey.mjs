// Real Go + worker SMTP + production SSR + Caddy. All values belong to a temporary fixture.
import { readFileSync, mkdtempSync } from "node:fs"
import { spawn, spawnSync } from "node:child_process"
import { createServer } from "node:net"
import { tmpdir } from "node:os"
import { join } from "node:path"
const config = JSON.parse(readFileSync(process.argv[2], "utf8"))
const chrome = process.argv[3] ?? "/usr/bin/chromium"
const events = [], checks = []
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
async function port() { const server = createServer(); await new Promise((r) => server.listen(0, "127.0.0.1", r)); const value = server.address().port; await new Promise((r) => server.close(r)); return value }
function db(sql, params = []) {
  const code = "import sqlite3,json,sys; c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True); c.row_factory=sqlite3.Row; print(json.dumps([dict(r) for r in c.execute(sys.argv[2],json.loads(sys.argv[3]))])); c.close()"
  const result = spawnSync("python3", ["-c", code, config.database, sql, JSON.stringify(params)], { encoding: "utf8" })
  if (result.status !== 0) throw new Error(result.stderr)
  return JSON.parse(result.stdout)
}
function check(name, ok, detail = {}) { if (!ok) throw new Error(`${name}: ${JSON.stringify(detail)}`); checks.push(name); console.log(`PASS REAL ${name} ${JSON.stringify(detail)}`) }
const debugPort = await port()
const browser = spawn(chrome, ["--headless=new", "--no-sandbox", "--no-first-run", `--remote-debugging-port=${debugPort}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "ow-real-personal-290-browser-"))}`, "about:blank"], { stdio: "ignore" })
let ws, inspectFailure
try {
  let targets
  for (let i=0;i<100;i++) { try { targets=await(await fetch(`http://127.0.0.1:${debugPort}/json`)).json(); if(targets.some((t)=>t.type==="page"))break } catch{} await pause(100) }
  ws = new WebSocket(targets.find((t)=>t.type==="page").webSocketDebuggerUrl)
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject})
  let counter=0;const pending=new Map()
  ws.onmessage=(message)=>{const value=JSON.parse(message.data);if(pending.has(value.id)){pending.get(value.id)(value);pending.delete(value.id)}else events.push(value)}
  const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++counter;const timer=setTimeout(()=>{pending.delete(id);reject(new Error(`CDP timeout ${method}`))},30000);pending.set(id,(value)=>{clearTimeout(timer);if(value.error)reject(new Error(JSON.stringify(value.error)));else resolve(value.result??{})});ws.send(JSON.stringify({id,method,params}))})
  const evaluate=async(expression)=>{const result=await send("Runtime.evaluate",{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));return result.result?.value}
  inspectFailure=async()=>{
    console.error('JOURNEY-STATE',JSON.stringify(await evaluate("({path:location.pathname,title:document.title,errors:[...document.querySelectorAll('.c-field__error')].map(e=>e.textContent),forms:[...document.querySelectorAll('#main form')].map(f=>({action:f.action,valid:f.checkValidity()}))})")))
    console.error('JOURNEY-HTTP',JSON.stringify(events.filter(e=>e.method==='Network.responseReceived' && new URL(e.params.response.url).pathname.startsWith('/api/')).map(e=>({path:new URL(e.params.response.url).pathname,status:e.params.response.status}))))
  }
  async function wait(expression) { for(let i=0;i<160;i++){if(await evaluate(`Boolean(${expression})`))return;await pause(75)}throw new Error(`wait failed ${expression}`) }
  await send("Runtime.enable");await send("Network.enable");await send("Log.enable");await send("Page.enable")
  await send("Page.addScriptToEvaluateOnNewDocument",{source:"window.confirm=()=>true;window.__violations=[];document.addEventListener('securitypolicyviolation',e=>console.error('JOURNEY-CSP',e.violatedDirective))"})
  async function go(path) {
    await send("Page.navigate",{url:config.base+path})
    await wait(`location.href===${JSON.stringify(config.base+path)}`)
    await wait("document.readyState==='complete' && document.querySelector('#app')?.__vue_app__")
    await pause(120)
  }
  async function pathIs(path) { await wait(`location.pathname===${JSON.stringify(path)} && document.readyState==='complete' && document.querySelector('#app')?.__vue_app__`);await pause(120) }
  async function input(selector,value) { await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw new Error('missing input');e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('input',{bubbles:true}))})()`) }
  async function click(selector) { await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);await pause(100) }
  async function submit(selector="#main form") { await click(selector+" button[type=submit]") }
  async function error() { await wait("document.querySelector('.c-field__error,.c-notice--error') && !document.querySelector('#main form button[type=submit]').disabled") }
  async function persisted(name, predicate) {
    for (let i = 0; i < 160; i++) {
      if (predicate()) return
      await pause(75)
    }
    throw new Error(`persistence wait failed: ${name}`)
  }
  async function choice(selector, value) {
    await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e || e.disabled)throw new Error('missing or disabled choice');e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}))})()`)
  }
  const mutateAPI = async (path, body) => evaluate(`fetch(${JSON.stringify(path)},{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},body:${JSON.stringify(JSON.stringify(body))}}).then(async r=>({status:r.status,body:await r.json()}))`)
  const api=async(path)=>evaluate(`fetch(${JSON.stringify(path)}).then(async r=>({status:r.status,body:await r.json()}))`)
  async function mail(to,after=0,subject="") {
    for(let i=0;i<200;i++) {
      const lines=readFileSync(config.mailbox,{encoding:'utf8',flag:'a+'}).trim().split("\n").filter(Boolean).map(JSON.parse)
      const found=lines.slice(after).filter(m=>m.to===to && m.subject.includes(subject)).at(-1)
      if(found?.valid_mime && found?.code)return found.code
      await pause(75)
    }
    throw new Error('SMTP code not delivered')
  }
  const mailCount=()=>readFileSync(config.mailbox,{encoding:'utf8',flag:'a+'}).trim().split("\n").filter(Boolean).length
  const email="journey@example.test", changed="changed@example.test", canceled="cancel@example.test"
  const first="Maple!Orbit829",second="Birch!Comet736",third="Cedar!Meteor645"
  const user=()=>db("SELECT * FROM users WHERE nickname=?",["Journey member"])[0]
  const sessions=()=>db("SELECT count(*) AS n FROM sessions WHERE user_id=?",[user().id])[0].n
  async function login(address,password,next="/accounts/email/") {
    await go('/accounts/login/?next='+encodeURIComponent(next));await input('#id_login',address);await input('#id_password',password);await submit()
  }
  async function secondSession(address,password) {
    const response=await fetch(config.base+'/api/auth/login',{method:'POST',headers:{'content-type':'application/json',Origin:config.base},body:JSON.stringify({email:address,password})})
    if(response.status!==200)throw new Error('second session login failed '+response.status)
    return response.headers.getSetCookie().find(c=>c.startsWith('ow_session=')).split(';')[0]
  }
  const sessionWith=async(cookie)=>(await(await fetch(config.base+'/api/session',{headers:{Cookie:cookie}})).json()).user
  await send("Page.navigate",{url:config.base+'/accounts/password/reset/complete/'})
  await pathIs('/accounts/password/reset/')
  check("unproved reset cannot open new password form",!await evaluate("!!document.querySelector('#id_password1')"))
  await go('/accounts/signup/?next='+encodeURIComponent('/accounts/email/'))
  await input('#id_email',email);await input('#id_nickname','Journey member');await input('#id_password1',first);await input('#id_password2','Mismatch!825')
  await click('#id_is_sjtu_0');await click('#id_agreed_terms');await click('#id_agreed_cross_border');await submit();await error()
  check("real validation retains signup inputs",!user() && await evaluate(`document.querySelector('#id_email').value===${JSON.stringify(email)} && document.querySelector('#id_password1').value===${JSON.stringify(first)}`))
  await input('#id_password2',first);await submit();await pathIs('/accounts/confirm-email/')
  let signupCode=await mail(email,0,"邮箱验证码")
  check("registration persists unverified without session",user().email_verified_at===null && sessions()===0 && (await api('/api/session')).body.user===null)
  const loginMailStart=mailCount();await login(email,first);await pathIs('/accounts/confirm-email/')
  signupCode=await mail(email,loginMailStart,"邮箱验证码")
  check("unverified password login issues new SMTP code without session",sessions()===0 && (await api('/api/session')).body.user===null)
  await input('#id_code',signupCode==='000000'?'111111':'000000');await submit();await error()
  check("wrong signup code commits attempt",db("SELECT attempts FROM email_codes WHERE purpose='signup' AND email_norm=?",[email])[0].attempts===1 && sessions()===0)
  await submit();await error()
  await submit();await pathIs('/accounts/login/')
  check("third wrong signup code is discarded",!db("SELECT id FROM email_codes WHERE purpose='signup' AND email_norm=?",[email]).length && sessions()===0)
  const restartAfter=mailCount();await login(email,first);await pathIs('/accounts/confirm-email/')
  signupCode=await mail(email,restartAfter,"邮箱验证码")
  check("closed flow restarts only through real password login",(await api('/api/auth/verify-email/state')).body.active===true)
  let resentAfter=mailCount();await submit('#main form:nth-of-type(2)')
  signupCode=await mail(email,resentAfter,"邮箱验证码")
  await wait("document.querySelector('#main form:nth-of-type(2) button').disabled")
  check("real resend restarts code and browser cooldown",db("SELECT attempts FROM email_codes WHERE purpose='signup' AND email_norm=?",[email])[0].attempts===0 && await evaluate("document.querySelector('#main form:nth-of-type(2) button').textContent.includes('秒后')"))
  await input('#id_code',signupCode);await submit();await pathIs('/accounts/email/')
  check("SMTP signup code verifies and logs in",!!user().email_verified_at && sessions()===1 && (await api('/api/session')).body.user.id===user().id)
  check("welcome notice survives SSR then is consumed",await evaluate("document.querySelector('.c-toast')?.textContent.includes('欢迎加入社区')") && db("SELECT flash_message FROM sessions WHERE user_id=?",[user().id])[0].flash_message==='')
  await go('/accounts/logout/')
  check("GET logout only confirms",!!(await api('/api/session')).body.user && sessions()===1)
  await submit();await pathIs('/')
  check("POST logout revokes session",sessions()===0 && (await api('/api/session')).body.user===null)
  await login(email,'Wrong!Planet527');await error()
  check("wrong login stays with field/message error",await evaluate(`location.pathname==='/accounts/login/' && document.querySelector('#id_login').value===${JSON.stringify(email)}`) && sessions()===0)
  await input('#id_password',first);await submit();await pathIs('/accounts/email/')
  check("real login returns safe next",(await api('/api/session')).body.user.id===user().id)
  const other=await secondSession(email,first)
  check("second real password login creates separate session",sessions()===2)
  await go('/accounts/password/change/');await input('#id_oldpassword',first);await input('#id_password1',second);await input('#id_password2',second);await submit();await pathIs('/accounts/password/change/')
  await wait("document.querySelector('#id_oldpassword')?.value===''")
  check("password change retains current and revokes others",sessions()===1 && (await api('/api/session')).body.user.id===user().id && await sessionWith(other)===null)
  await go('/accounts/email/');await input('#id_email',changed);await submit();await pathIs('/accounts/reauthenticate/')
  check("email change requires reauthentication",!db('SELECT * FROM email_changes').length && await evaluate("new URLSearchParams(location.search).get('next').includes('changed%40example.test')"))
  await input('#id_password','Wrong!Comet527');await submit();await error()
  check("wrong reauthentication leaves state unchanged",!(await api('/api/auth/email/state')).body.reauthenticated)
  await input('#id_password',second);await submit();await pathIs('/accounts/email/')
  check("reauthentication restores email draft",await evaluate(`document.querySelector('#id_email').value===${JSON.stringify(changed)}`) && (await api('/api/auth/email/state')).body.reauthenticated)
  let before=mailCount();await submit();await pathIs('/accounts/confirm-email/')
  const emailCode=await mail(changed,before,"验证你的新邮箱")
  check("new address is pending until verified",user().email===email && (await api('/api/auth/email/state')).body.pending_email===changed)
  await input('#id_code',emailCode==='000000'?'111111':'000000');await submit();await error()
  check("wrong new-email code persists attempt",db('SELECT attempts FROM email_changes')[0].attempts===1 && user().email===email)
  await input('#id_code',emailCode);await submit();await pathIs('/accounts/email/')
  check("new-email SMTP code replaces login address",user().email===changed && !db('SELECT * FROM email_changes').length && (await api('/api/session')).body.user.id===user().id)
  before=mailCount();await input('#id_email',canceled);await submit();await pathIs('/accounts/confirm-email/');await mail(canceled,before)
  await go('/accounts/email/');await click('button[name=action_remove]');await wait("!document.querySelector('#pending-email')")
  check("cancel pending email keeps current address",user().email===changed && !db('SELECT * FROM email_changes').length)
  const resetOther=await secondSession(changed,second)
  before=mailCount();await go('/accounts/password/reset/');await input('#id_email',changed);await submit();await pathIs('/accounts/password/reset/confirm/')
  const resetCode=await mail(changed,before,"找回密码验证码")
  await input('#id_code',resetCode==='000000'?'111111':'000000');await submit();await error()
  check("wrong reset code commits attempt",db("SELECT attempts FROM email_codes WHERE purpose='password_reset'")[0].attempts===1 && (await api('/api/auth/reset-password/state')).body.verified===false)
  await input('#id_code',resetCode);await submit();await pathIs('/accounts/password/reset/complete/')
  const cookies=(await send('Network.getCookies',{urls:[config.base]})).cookies
  const grant=cookies.find(c=>c.name==='ow_password_reset')
  check("reset proof is private cookie without URL or JS access",grant?.httpOnly && grant.sameSite==='Lax' && await evaluate("!location.search && !document.cookie.includes('ow_password_reset') && localStorage.length===0 && sessionStorage.length===0") && (await api('/api/auth/reset-password/state')).body.verified)
  await input('#id_password1',third);await input('#id_password2',third);await submit();await pathIs('/accounts/password/reset/done/')
  check("password reset logs out all sessions without auto-login",sessions()===0 && (await api('/api/session')).body.user===null && await sessionWith(resetOther)===null && !(await send('Network.getCookies',{urls:[config.base]})).cookies.some(c=>c.name==='ow_password_reset'))
  await login(changed,second);await error()
  check("previous password fails after reset",sessions()===0)
  await input('#id_password',third);await submit();await pathIs('/accounts/email/')
  check("reset password signs in with changed email",(await api('/api/session')).body.user.id===user().id)
  await go('/accounts/logout/');await submit();await pathIs('/')
  await login(changed,third,'https://external.example.test/');await pathIs('/')
  check("external login next falls back inside site",await evaluate(`location.origin===${JSON.stringify(config.base)}`))
  await go('/accounts/logout/');await submit();await pathIs('/')
  await go('/accounts/signup/?next='+encodeURIComponent('/accounts/email/'))
  await input('#id_email',changed);await input('#id_nickname','Alternate name');await input('#id_password1',first);await input('#id_password2',first)
  await click('#id_is_sjtu_1');await click('#id_agreed_terms');await click('#id_agreed_cross_border');await submit();await pathIs('/accounts/confirm-email/')
  check("existing-email signup shows same confirmation without login",user().nickname==='Journey member' && sessions()===0 && (await api('/api/session')).body.user===null && await evaluate(`new URLSearchParams(location.search).get('email')===${JSON.stringify(changed)}`))
  await go('/accounts/password/reset/');await input('#id_email','unknown@example.test');await submit();await pathIs('/accounts/password/reset/confirm/')
  check("unknown-email reset shows same confirmation",await evaluate("new URLSearchParams(location.search).get('email')==='unknown@example.test' && !!document.querySelector('#id_code')") && !db("SELECT id FROM users WHERE email='unknown@example.test'").length)
  await go('/accounts/inactive/')
  check("inactive explanation renders in real SSR",await evaluate("document.querySelector('#main').textContent.includes('停用') && !document.querySelector('#main input[type=password]')"))
  for(const [path,status,target] of [['/accounts/login/code/confirm/',302,'/accounts/login/'],['/accounts/password/change/',302,'/accounts/login/?next=%2Faccounts%2Fpassword%2Fchange%2F']]) {
    const response=await fetch(config.base+path,{redirect:'manual'})
    check('real redirect '+path,response.status===status && response.headers.get('location')===target)
  }
  await login(changed,third);await pathIs('/accounts/email/')
  const setResponse=await fetch(config.base+'/accounts/password/set/',{redirect:'manual',headers:{Cookie:(await send('Network.getCookies',{urls:[config.base]})).cookies.filter(c=>c.name==='ow_session').map(c=>c.name+'='+c.value).join(';')}})
  check("password-set is actual authenticated permanent redirect",setResponse.status===301 && setResponse.headers.get('location')==='/me/security/')
  const profileBefore = user()
  const beforePrivacy = profileBefore.show_rank
  const unchangedProfile = () => ['is_sjtu', 'nickname', 'motto', 'main_role', 'flex_roles'].every(key => user()[key] === profileBefore[key])
  await go('/me/');
  check('versioned profile editor offers real privacy control',!await evaluate("document.querySelector('#id_show_rank').disabled"))
  await click('#id_show_rank')
  await persisted('profile privacy toggle', () => user().show_rank === (beforePrivacy ? 0 : 1))
  check('profile saves explicit privacy choice without clearing omitted fields',unchangedProfile())
  const profileProjection = await api('/api/me/profile')
  check('saved privacy is in real owner API projection',profileProjection.status === 200 && profileProjection.body.show_rank === !Boolean(beforePrivacy))
  await click('#id_show_rank')
  await persisted('profile privacy restoration', () => user().show_rank === beforePrivacy)
  check('profile privacy restores original choice and keeps SJTU/role values',unchangedProfile())
  await go('/me/game-accounts/?new=1');
  await input('#id_battletag','Personal#12345');
  await evaluate("document.querySelector('#id_rank_tank').value='0';document.querySelector('#id_rank_tank').dispatchEvent(new Event('change',{bubbles:true}))")
  await submit('#create-game-account form');await pathIs('/me/game-accounts/');
  const game=db("SELECT * FROM game_accounts WHERE user_id=? AND battletag=?",[user().id,'Personal#12345'])[0]
  check('real game creation preserves bronze zero and other unranked nulls',game && game.rank_tank===0 && game.rank_damage===null && game.rank_support===null)
  await go('/me/game-accounts/'+game.id+'/');
  check('versioned game editor allows real rank changes',!await evaluate("document.querySelector('[name=rank_tank]').disabled"))
  const gameRow = () => db("SELECT * FROM game_accounts WHERE id=?", [game.id])[0]
  await choice('[name=rank_tank]', '7')
  await persisted('rank modification', () => gameRow().rank_tank === 7)
  check('rank edit preserves BattleTag and omitted damage/support ranks',gameRow().battletag === game.battletag && gameRow().rank_damage === null && gameRow().rank_support === null && gameRow().version > game.version)
  await choice('[name=rank_tank]', '')
  await persisted('rank explicit null', () => gameRow().rank_tank === null)
  check('rank null clears only chosen position and preserves BattleTag',gameRow().battletag === game.battletag && gameRow().rank_damage === null && gameRow().rank_support === null)
  await choice('[name=rank_tank]', '0')
  await persisted('rank original restoration', () => gameRow().rank_tank === game.rank_tank)
  await submit('#game-account-' + game.id + ' form');await pathIs('/me/game-accounts/')
  check('rank editing completion returns persisted card',await evaluate("document.querySelector('#game-account-" + game.id + "').textContent.includes('Personal#12345')"))
  await go('/me/contacts/?new=1');await input('#id_value','12345678');
  await submit('#create-contact form');await pathIs('/me/contacts/');
  const contact=db("SELECT * FROM contacts WHERE user_id=?",[user().id])[0]
  check('real contact creation persists and refreshes list',contact && contact.value==='12345678' && await evaluate("document.querySelector('#contact-list').textContent.includes('12345678')"))
  await go('/me/contacts/' + contact.id + '/')
  const contactRow = () => db("SELECT * FROM contacts WHERE id=?", [contact.id])[0]
  await input('#edit_' + contact.id + '_value', '87654321')
  await submit('#contact-' + contact.id + ' form');await pathIs('/me/contacts/')
  await persisted('contact edit', () => contactRow().value === '87654321')
  check('existing contact edit persists same ID/type with advanced version',contactRow().id === contact.id && contactRow().type === contact.type && contactRow().version > contact.version && await evaluate("document.querySelector('#contact-" + contact.id + "').textContent.includes('87654321')"))
  await go('/me/contacts/' + contact.id + '/')
  await input('#edit_' + contact.id + '_value', contact.value)
  await submit('#contact-' + contact.id + ' form');await pathIs('/me/contacts/')
  await persisted('contact original restoration', () => contactRow().value === contact.value)
  check('contact editor restores original value without changing type',contactRow().type === contact.type)
  await go('/me/security/');
  await click('form[action="/me/notifications/"] button');
  await wait("document.querySelector('#main').textContent.includes('活动通知：关着')")
  check('notification toggle is real persisted state',db("SELECT accepts_announcements FROM users WHERE id=?",[user().id])[0].accepts_announcements===0)
  await click('form[action="/me/notifications/"] button');
  await wait("document.querySelector('#main').textContent.includes('活动通知：开着')")
  check('notification toggle can be reenabled',db("SELECT accepts_announcements FROM users WHERE id=?",[user().id])[0].accepts_announcements===1)
  await go('/me/delete/');
  const deletionProjection = await api('/api/me/profile')
  check('real deletion preflight opens confirmation for eligible account',Array.isArray(deletionProjection.body.deletion_blockers) && deletionProjection.body.deletion_blockers.length === 0 && await evaluate("Boolean(document.querySelector('#id_password'))") && user().is_active === 1)
  await input('#id_password', 'Incorrect!DeletePassword927');await submit();await wait("document.querySelector('.c-field__error')?.textContent.includes('当前密码不正确') && !document.querySelector('#main form button[type=submit]').disabled")
  check('wrong deletion password keeps account and real session intact',user().is_active === 1 && sessions() > 0 && (await api('/api/session')).body.user.id === user().id)
  const captainTeam = await mutateAPI('/api/teams', {name:'Journey captain',description:'Temporary deletion preflight fixture',is_recruiting:true,recruiting_roles:[]})
  check('real team creation supplies captain deletion blocker',captainTeam.status === 200 && Number.isInteger(captainTeam.body.team?.id))
  const captainID = captainTeam.body.team.id
  await go('/me/delete/')
  check('captain preflight hides destructive form with real blocker',await evaluate("Boolean(document.querySelector('[data-deletion-blocked]')) && !document.querySelector('#id_password')") && (await api('/api/me/profile')).body.deletion_blockers.length > 0)
  const rejectedDeletion = await mutateAPI('/api/auth/delete-account', {password:third})
  check('server also rejects captain deletion despite correct password',rejectedDeletion.status === 400 && rejectedDeletion.body.error?.message?.includes('队长') && user().is_active === 1 && sessions() > 0)
  const disbanded = await mutateAPI('/api/teams/' + captainID + '/disband', {})
  check('real disband removes captain blocker',disbanded.status === 200 && db('SELECT disbanded_at FROM teams WHERE id=?', [captainID])[0].disbanded_at !== null)
  await go('/me/delete/')
  check('preflight reopens confirmation after disband',await evaluate("Boolean(document.querySelector('#id_password')) && !document.querySelector('[data-deletion-blocked]')") && (await api('/api/me/profile')).body.deletion_blockers.length === 0)
  await go('/me/contacts/');await click('#contact-'+contact.id+' button[type=submit]');
  await wait(`!document.querySelector('#contact-${contact.id}')`)
  check('real contact deletion removes persisted row',!db("SELECT id FROM contacts WHERE id=?",[contact.id]).length)
  await go('/me/game-accounts/');await click('#game-account-'+game.id+' button[type=submit]');
  await wait(`!document.querySelector('#game-account-${game.id}')`)
  check('real game deletion removes persisted row',!db("SELECT id FROM game_accounts WHERE id=?",[game.id]).length)
  const deletedUserID = user().id
  await go('/me/delete/');await input('#id_password', third);await submit();await pathIs('/')
  const erased = db('SELECT is_active,email,nickname FROM users WHERE id=?', [deletedUserID])[0]
  check('eligible account deletion anonymizes and revokes every session',erased.is_active === 0 && erased.nickname === '已注销用户' && erased.email !== changed && db('SELECT 1 FROM sessions WHERE user_id=?', [deletedUserID]).length === 0 && (await api('/api/session')).body.user === null)
  check('deleted account retains no game/contact records',db('SELECT 1 FROM game_accounts WHERE user_id=?', [deletedUserID]).length === 0 && db('SELECT 1 FROM contacts WHERE user_id=?', [deletedUserID]).length === 0)
  const runtime=events.filter(e=>e.method==='Runtime.exceptionThrown')
  const errors500=events.filter(e=>e.method==='Network.responseReceived' && e.params.response.status>=500)
  const violations=events.filter(e=>e.method==='Runtime.consoleAPICalled' && e.params.args.some(a=>a.value==='JOURNEY-CSP'))
  check("real account runtime/CSP/server errors absent",!runtime.length && !errors500.length && !violations.length,{runtime:runtime.length,csp:violations.length,server500:errors500.length})
  console.log(`REAL-PERSONAL-JOURNEY-OK ${checks.length}`)
} catch(error) {if(inspectFailure)await inspectFailure();throw error} finally {if(ws)ws.close();browser.kill('SIGTERM');await new Promise(r=>browser.once('exit',r))}
