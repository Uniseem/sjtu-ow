// Real Go + production SSR + Caddy. All values belong to a temporary fixture.
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
const browser = spawn(chrome, ["--headless=new", "--no-sandbox", "--no-first-run", `--remote-debugging-port=${debugPort}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "ow-real-comments-browser-"))}`, "about:blank"], { stdio: "ignore" })
let ws
try {
  let targets
  for (let i=0;i<100;i++) { try { targets=await(await fetch(`http://127.0.0.1:${debugPort}/json`)).json(); if(targets.some((t)=>t.type==="page"))break } catch{} await pause(100) }
  ws = new WebSocket(targets.find((t)=>t.type==="page").webSocketDebuggerUrl)
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject})
  let counter=0;const pending=new Map()
  ws.onmessage=(message)=>{const value=JSON.parse(message.data);if(pending.has(value.id)){pending.get(value.id)(value);pending.delete(value.id)}else events.push(value)}
  const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++counter;const timer=setTimeout(()=>{pending.delete(id);reject(new Error(`CDP timeout ${method}`))},30000);pending.set(id,(value)=>{clearTimeout(timer);if(value.error)reject(new Error(JSON.stringify(value.error)));else resolve(value.result??{})});ws.send(JSON.stringify({id,method,params}))})
  const evaluate=async(expression)=>{const result=await send("Runtime.evaluate",{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));return result.result?.value}
  async function wait(expression) { for(let i=0;i<160;i++){if(await evaluate(`Boolean(${expression})`))return;await pause(75)}throw new Error(`wait failed ${expression}`) }
  await send("Runtime.enable");await send("Network.enable");await send("Log.enable");await send("Page.enable")
  await send("Page.addScriptToEvaluateOnNewDocument",{source:"window.confirm=()=>true;window.__violations=[];document.addEventListener('securitypolicyviolation',e=>window.__violations.push(e.violatedDirective))"})
  async function go(role, path="/news/real-comments/", hydrate=true) {
    await send("Network.clearBrowserCookies")
    if(role)await send("Network.setCookie",{name:"ow_session",value:config[role],url:config.base,path:"/",httpOnly:true,sameSite:"Lax"})
    await send("Page.navigate",{url:config.base+path})
    await wait("document.readyState === 'complete'")
    if(hydrate)await wait("document.querySelector('#slot-article-comments') && document.querySelector('#app')?.__vue_app__")
    await pause(150)
  }
  const api=async(path)=>evaluate(`fetch(${JSON.stringify(path)}).then(async r=>({status:r.status,body:await r.json()}))`)
  async function fill(form,text) { await evaluate(`(()=>{const f=document.querySelector(${JSON.stringify(form)});const t=f.querySelector('textarea');t.value=${JSON.stringify(text)};t.dispatchEvent(new Event('input',{bubbles:true}));f.querySelector('button[type=submit]').click()})()`);await pause(100) }
  async function action(id,label) { await evaluate(`(()=>{const root=document.querySelector('#comment-${id}');const b=[...root.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)});if(!b)throw new Error('missing action '+${JSON.stringify(label)});b.click()})()`);await pause(100) }
  async function openComposer(id,label) {await evaluate(`(()=>{const root=document.querySelector('#comment-${id}');const s=[...root.querySelectorAll('summary')].find(s=>s.textContent.trim()===${JSON.stringify(label)});s.parentElement.open=true})()`);return `#comment-${id} details[open] form.c-composer`}
  const rootForm="#slot-article-comments > form.c-composer"
  const row=(id)=>db("SELECT * FROM comments WHERE id=?",[id])[0]
  const newest=(text)=>db("SELECT * FROM comments WHERE content=? ORDER BY id DESC",[text])[0]
  await go(null)
  check("visitor read-only",await evaluate("document.querySelectorAll('#comment-list > li').length===20 && !document.querySelector('#slot-article-comments textarea')"))
  await go("member")
  await evaluate("document.querySelector('#comments-more a').click()")
  await wait("document.querySelectorAll('#comment-list > li').length===25")
  check("real pagination reaches final page",!(await evaluate("!!document.querySelector('#comments-more a')")))
  await fill(rootForm,"REAL top")
  await wait("[...document.querySelectorAll('.c-comment__body')].some(e=>e.textContent==='REAL top')")
  const top=newest("REAL top").id
  check("post saved by Go",row(top).user_id===1 && row(top).edited_at===null,{id:top,total:(await api(`/api/articles/${config.article}/comments`)).body.total})
  await evaluate(`document.querySelector('#comment-${top} button[aria-pressed]').click()`)
  await wait(`document.querySelector('#comment-${top} button[aria-pressed=true]')`)
  check("like persisted",row(top).like_count===1)
  await evaluate(`document.querySelector('.c-comments__sort a[href*="sort=top"]').click()`)
  await wait("document.querySelector('.c-comments__sort a[aria-current=true]')?.textContent==='最热'")
  check("real hottest ordering",(await api(`/api/articles/${config.article}/comments?sort=top`)).body.comments[0].id===top)
  await evaluate(`document.querySelector('#comment-${top} button[aria-pressed]').click()`)
  await wait(`document.querySelector('#comment-${top} button[aria-pressed=false]')`)
  check("unlike persisted",row(top).like_count===0)
  await go("other")
  await fill(await openComposer(top,"回复"),"REAL reply")
  await wait(`document.querySelector('#comment-${top} > details.c-comment__thread')`)
  const reply=newest("REAL reply").id
  check("reply persisted under root",row(reply).parent_id===top && row(reply).user_id===2,{id:reply})
  await evaluate(`document.querySelector('#comment-${top} > details.c-comment__thread').open=true`)
  await fill(await openComposer(reply,"编辑"),"REAL reply edited")
  await wait(`document.querySelector('#comment-${reply} .c-comment__body')?.textContent.includes('REAL reply edited')`)
  check("reply edited marker",!!row(reply).edited_at && await evaluate(`document.querySelector('#comment-${reply} .c-comment__meta').textContent.includes('已编辑')`))
  await evaluate(`document.querySelector('#comment-${top} > details.c-comment__thread').open=true`)
  await fill(await openComposer(reply,"回复"),"REAL flattened reply")
  await wait(`document.querySelector('#comment-${top} > details.c-comment__thread summary').textContent.includes('2 条回复')`)
  const flattened=newest("REAL flattened reply").id
  check("reply to reply flattened with attribution",row(flattened).parent_id===top && row(flattened).reply_to_user_id===2)
  await go("member")
  await fill(await openComposer(top,"编辑"),"REAL top edited")
  await wait(`document.querySelector('#comment-${top} .c-comment__body')?.textContent==='REAL top edited'`)
  const editedAt=row(top).edited_at
  check("root edit persisted and marked",!!editedAt && await evaluate(`document.querySelector('#comment-${top} .c-comment__meta').textContent.includes('已编辑')`))
  // The previous posts can straddle a UTC minute boundary. Exercise the
  // actual limiter with a short real UI burst instead of assuming its bucket.
  let acceptedBurst=0, deniedText, deniedResponse
  for(let attempt=0;attempt<8;attempt++) {
    const text=`REAL rate burst ${attempt}`
    const before=events.length
    await fill(rootForm,text)
    let response
    for(let poll=0;poll<100;poll++) {
      const request=events.slice(before).find(e=>e.method==='Network.requestWillBeSent' && e.params.request.method==='POST' && new URL(e.params.request.url).pathname===`/api/articles/${config.article}/comments`)
      response=request && events.slice(before).find(e=>e.method==='Network.responseReceived' && e.params.requestId===request.params.requestId)
      if(response)break
      await pause(50)
    }
    if(!response)throw new Error('missing rate burst POST response')
    await wait(`!document.querySelector(${JSON.stringify(rootForm)}+' button').disabled`)
    if(response.params.response.status===429) {deniedText=text;deniedResponse=response;break}
    if(response.params.response.status!==200)throw new Error('unexpected rate burst status '+response.params.response.status)
    await wait(`[...document.querySelectorAll('.c-comment__body')].some(e=>e.textContent===${JSON.stringify(text)})`)
    if(!newest(text))throw new Error('successful rate burst did not persist')
    acceptedBurst++
  }
  check("real 429 keeps draft",!!deniedResponse && !newest(deniedText) && await evaluate(`document.querySelector(${JSON.stringify(rootForm)}+' textarea').value===${JSON.stringify(deniedText)} && !!document.querySelector('.c-toast')`),{acceptedBurst})
  await go("moderator")
  await action(top,"置顶");await wait(`document.querySelector('#comment-${top} .c-tag')?.textContent==='置顶'`)
  check("pin persists without rewriting edited_at",row(top).is_pinned===1 && row(top).edited_at===editedAt)
  await action(top,"隐藏");await wait(`document.querySelector('#comment-${top} .c-status')?.textContent==='已隐藏'`)
  check("hide persists without editing",row(top).is_hidden===1 && row(top).is_pinned===0 && row(top).edited_at===editedAt)
  await go(null)
  check("visitor tombstone preserves visible reply",await evaluate(`document.querySelector('#comment-${top} > .c-comment__placeholder')?.textContent.includes('已隐藏') && !document.querySelector('#comment-${top} > div .c-comment__body') && !!document.querySelector('#comment-${reply}')`))
  await go("moderator")
  await action(top,"恢复");await wait(`document.querySelector('#comment-${top} .c-comment__body')?.textContent==='REAL top edited'`)
  await action(top,"置顶");await wait(`document.querySelector('#comment-${top} .c-tag')?.textContent==='置顶'`)
  await action(top,"取消置顶");await wait(`!document.querySelector('#comment-${top} .c-tag')`)
  check("restore/unpin preserved edit history",row(top).is_hidden===0 && row(top).is_pinned===0 && row(top).edited_at===editedAt)
  await go("member")
  await action(top,"删除");await wait(`document.querySelector('#comment-${top} > .c-comment__placeholder')?.textContent.includes('已删除')`)
  check("delete creates tombstone with reply",row(top).is_deleted===1 && row(top).content==="" && row(reply).is_deleted===0)
  await go("other")
  await evaluate(`document.querySelector('#comment-${top} > details.c-comment__thread').open=true`)
  await action(reply,"删除")
  await wait(`!document.querySelector('#comment-${reply}')`)
  check("one deleted reply keeps surviving thread",row(reply).is_deleted===1 && row(flattened).is_deleted===0)
  await evaluate(`document.querySelector('#comment-${top} > details.c-comment__thread').open=true`)
  await action(flattened,"删除")
  await wait(`!document.querySelector('#comment-${top}')`)
  check("deleted reply removes empty tombstone",row(reply).is_deleted===1 && (await api(`/api/articles/${config.article}/comments`)).body.total===25+acceptedBurst)
  await go("banned")
  check("real feature ban notice",await evaluate("document.querySelector('#slot-article-comments').textContent.includes('你暂时无法使用此功能') && !document.querySelector('#slot-article-comments > form')"))
  const bannedForm=await openComposer(25,"编辑")
  await fill(bannedForm,"BAN edit must remain draft")
  await wait(`!document.querySelector(${JSON.stringify(bannedForm)}+' button').disabled`)
  check("real ban edit refused and draft retained",row(25).content==="Seed comment 25" && await evaluate(`document.querySelector(${JSON.stringify(bannedForm)}+' textarea').value==='BAN edit must remain draft'`) && events.some((e)=>e.method==="Network.responseReceived" && e.params.response.status===403))
  await go("member","/news/closed-comments/")
  check("closed comments readable without composer",await evaluate("document.querySelector('#slot-article-comments').textContent.includes('这篇文章关闭了评论') && !document.querySelector('#slot-article-comments > form')"))
  const privateResponse=await fetch(config.base+"/news/private-comments/",{headers:{Cookie:`ow_session=${config.moderator}`}})
  check("real private page remains 404 for superuser",privateResponse.status===404)
  const violations=await evaluate("window.__violations")
  const runtime=events.filter((e)=>e.method==="Runtime.exceptionThrown")
  const errors500=events.filter((e)=>e.method==="Network.responseReceived" && e.params.response.status>=500)
  check("real runtime/CSP/server errors absent",!violations.length && !runtime.length && !errors500.length,{runtime:runtime.length,csp:violations,server500:errors500.length})
  console.log(`REAL-COMMENTS-JOURNEY-OK ${checks.length}`)
} finally {if(ws)ws.close();browser.kill("SIGTERM");await new Promise((r)=>browser.once("exit",r))}
