// Independent reviewer probe: production SSR and real Chromium; Go-shaped
// temporary API, never production data. This records observations, not fixes.
import { createServer, request } from 'node:http'
import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const site = process.cwd() + '/web/apps/site'
const children = [], servers = [], events = [], writes = [], findings = []
const pause = ms => new Promise(r => setTimeout(r, ms))
const user = { id:7,nickname:'Review member',email:'review@example.test',admin:true,superuser:false,caps:['comments.moderate'],email_verified:true,is_sjtu:true,can_comment:true }
function comment(id, articleId, content) { return {id,article_id:articleId,user_id:7,author_name:'Review member',content,is_pinned:false,is_hidden:false,is_deleted:false,like_count:0,liked_by_me:false,version:1,created_at:'2026-10-10T12:00:00Z',updated_at:'2026-10-10T12:00:00Z',replies:[]} }
const comments = {1:Array.from({length:21},(_,i)=>comment(100+i,1,`A comment ${i+1}`)),2:[comment(200,2,'B comment only')]}
function article(slug) {return {id:slug==='a'?1:2,slug,title:`Article ${slug.toUpperCase()}`,category_name:'Review',summary:'Review body',body_html:'<p>Public body</p>',char_count:10,reading_time:1,author_name:'Review member',comments_enabled:true,first_published_at:'2026-10-10T12:00:00Z',headings:[]}}
async function serve(handler) {const s=createServer(handler);servers.push(s);await new Promise(r=>s.listen(0,'127.0.0.1',r));return s.address().port}
let evaluate,send
try {
  const apiPort=await serve(async(req,res)=>{
    const url=new URL(req.url,'http://review');let raw='';for await(const c of req)raw+=c
    const body=raw?JSON.parse(raw):{}
    const json=(data,status=200)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(data))}
    if(req.method!=='GET') {
      writes.push({method:req.method,path:url.pathname,body,key:req.headers['idempotency-key']})
      const created=/^\/api\/articles\/(\d+)\/comments$/.exec(url.pathname)
      if(created) {const id=Number(created[1]);comments[id].unshift(comment(300+writes.length,id,body.content));await pause(150);json({comment:comments[id][0]});return}
      json({result:'ok'});return
    }
    if(url.pathname==='/api/session'){json({user});return}
    if(url.pathname==='/api/page/home'){json({stats:{member_count:1,team_count:0,scrims_held:0},scrims:[],news:[],notices:[],teams:[]});return}
    if(url.pathname==='/api/me/agenda'){json({items:[]});return}
    const art=/^\/api\/page\/news\/(a|b)$/.exec(url.pathname)
    if(art){json(article(art[1]));return}
    const list=/^\/api\/articles\/(\d+)\/comments$/.exec(url.pathname)
    if(list){const id=Number(list[1]),p=Number(url.searchParams.get('page')??1);json({total:comments[id].length,page:p,page_size:20,comments:comments[id].slice((p-1)*20,p*20)});return}
    json({error:{code:'not_found',message:'Missing review fixture'}},404)
  })
  const ssrPort=await serve((req,res)=>{res.end('reservation')})
  await new Promise(r=>servers.pop().close(r))
  const ssr=spawn(process.execPath,['dist/server/server.js'],{cwd:site,env:{...process.env,NODE_ENV:'production',STRICT_CSP:'1',PORT:String(ssrPort),API_BASE:`http://127.0.0.1:${apiPort}`},stdio:['ignore','ignore','inherit']});children.push(ssr)
  const proxyPort=await serve((req,res)=>{const up=request({hostname:'127.0.0.1',port:req.url.startsWith('/api/')?apiPort:ssrPort,path:req.url,method:req.method,headers:req.headers},reply=>{res.writeHead(reply.statusCode,reply.headers);reply.pipe(res)});up.on('error',()=>{res.writeHead(502);res.end()});req.pipe(up)})
  const base=`http://127.0.0.1:${proxyPort}`
  for(let i=0;i<50;i++){try{const r=await fetch(base+'/news/a/');if(r.status===200)break}catch{};await pause(100)}
  const debugPort=await serve((q,r)=>r.end('reservation'));await new Promise(r=>servers.pop().close(r))
  const browser=spawn('/usr/bin/chromium',['--headless=new','--no-sandbox','--no-first-run',`--remote-debugging-port=${debugPort}`,`--user-data-dir=${mkdtempSync(join(tmpdir(),'ow-review-276-'))}`,'about:blank'],{stdio:'ignore'});children.push(browser)
  let targets
  for(let i=0;i<50;i++){try{targets=await(await fetch(`http://127.0.0.1:${debugPort}/json`)).json();if(targets.some(t=>t.type==='page'))break}catch{};await pause(100)}
  const ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl)
  await new Promise(r=>ws.onopen=r)
  let id=0;const pending=new Map()
  ws.onmessage=m=>{const x=JSON.parse(m.data);if(x.id&&pending.has(x.id)){pending.get(x.id)(x);pending.delete(x.id)}else events.push(x)}
  send=(method,params={})=>new Promise(r=>{const i=++id;pending.set(i,r);ws.send(JSON.stringify({id:i,method,params}))})
  evaluate=async expression=>{const x=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(x.result?.exceptionDetails)return {evaluationError:x.result.exceptionDetails};return x.result?.result?.value}
  await send('Runtime.enable');await send('Page.enable')
  await send('Page.addScriptToEvaluateOnNewDocument',{source:'window.__confirmCalls=0; window.confirm=()=>{window.__confirmCalls++;return true;};'})
  async function open(path){await send('Page.navigate',{url:base+path});for(let i=0;i<50;i++){if(await evaluate("document.documentElement.classList.contains('js-ready') && !!document.querySelector('.c-comments')"))break;await pause(100)}await pause(200)}
  const errors=()=>events.filter(x=>x.method==='Runtime.exceptionThrown'||x.method==='Runtime.consoleAPICalled').map(x=>x.params.exceptionDetails?.exception?.description??x.params.args?.map(a=>a.value??a.description).join(' ')).filter(Boolean)
  const capture=(name,observed,passed)=>{const record={name,passed,observed};findings.push(record);console.log(JSON.stringify(record))}
  await open('/news/a/')
  const pagination=await evaluate("({visibleComments:document.querySelectorAll('#comment-list > li.c-comment').length,total:document.querySelector('.c-comments__head h2').textContent,more:!!document.querySelector('#comments-more a')})")
  capture('pagination uses Go page_size',pagination,pagination.more===true)
  const beforeLike=writes.length
  await evaluate("document.querySelector('#comment-100 button[aria-pressed]').click()")
  await pause(250)
  capture('like reaches API',{newWrites:writes.slice(beforeLike),errors:errors()},writes.length>beforeLike)
  const beforeDelete=writes.length
  await evaluate("[...document.querySelectorAll('#comment-100 button')].find(b=>b.textContent.trim()==='删除').click()")
  await pause(200)
  capture('delete confirmation reaches API',{newWrites:writes.slice(beforeDelete),confirmCalls:await evaluate('window.__confirmCalls'),errors:errors()},writes.some(w=>w.method==='DELETE'))
  const beforeHide=writes.length
  await evaluate("[...document.querySelectorAll('#comment-100 button')].find(b=>b.textContent.trim()==='隐藏').click()")
  await pause(200)
  capture('hide confirmation reaches API',{newWrites:writes.slice(beforeHide),confirmCalls:await evaluate('window.__confirmCalls'),errors:errors()},writes.some(w=>w.path.endsWith('/hide')))
  await evaluate("(()=>{const f=document.querySelector('#slot-article-comments > .c-composer');const t=f.querySelector('textarea');t.value='Independent review new comment';t.dispatchEvent(new Event('input',{bubbles:true}));f.querySelector('button[type=submit]').click()})()")
  await pause(700)
  const afterPost=await evaluate("({section:document.querySelector('.c-comments__head h2').textContent,header:document.querySelector('.c-cover__facts a[href=\"#comments\"]').textContent,draft:document.querySelector('#slot-article-comments > .c-composer textarea').value})")
  capture('create refreshes header count and clears draft',afterPost,afterPost.header.includes('22')&&afterPost.draft==='')
  const beforeDouble=writes.length
  await evaluate("(()=>{const b=document.querySelector('#slot-article-comments > .c-composer button[type=submit]');b.click();b.click()})()")
  await pause(700)
  capture('pending comment blocks duplicate submission',{newWrites:writes.slice(beforeDouble)},writes.length-beforeDouble<=1)
  await evaluate("document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/news/b/')")
  await pause(500)
  const reused=await evaluate("({title:document.querySelector('.c-cover__title').textContent,comments:[...document.querySelectorAll('.c-comment__body')].map(e=>e.textContent)})")
  capture('same route component switches thread',reused,reused.title==='Article B'&&reused.comments.join('|')==='B comment only')
  const navErrorStart=events.length
  await evaluate("document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/')")
  await pause(500)
  const navigation={title:await evaluate('document.title'),errors:events.slice(navErrorStart).filter(x=>x.method==='Runtime.exceptionThrown'||x.method==='Runtime.consoleAPICalled').map(x=>x.params.exceptionDetails?.exception?.description??x.params.args?.map(a=>a.value??a.description).join(' ')).filter(Boolean)}
  capture('leaving article does not throw',navigation,navigation.errors.length===0)
  writeFileSync('/tmp/sjtu-ow-review-276-browser.json',JSON.stringify(findings,null,2))
  ws.close()
  console.log(`REVIEW-PROBE ${findings.filter(x=>x.passed).length}/${findings.length} expected behaviors passed`)
  process.exitCode=findings.some(x=>!x.passed)?1:0
} finally {for(const p of children)p.kill('SIGTERM');for(const s of servers)s.close()}
