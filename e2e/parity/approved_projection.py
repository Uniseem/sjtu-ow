"""Narrow visual projections for already approved migration differences.

Inspect the real controls before replacing technical editor/engine regions.
Everything outside these exact regions remains in the original comparison.
"""
import json
import re

_preview_tokens = {}


def normalize_timed_links(tools, evaluate):
    """Validate real signed recipients before stabilizing preview timestamps."""
    from django.core import signing
    strings = evaluate(tools, """(() => {
      const main=document.querySelector('#main');if(!main)return [];
      return [main.textContent,...[...main.querySelectorAll('a[href]')].map(a=>a.getAttribute('href'))];
    })()""")
    mapping = {}
    recipients = []
    signer = signing.TimestampSigner(key='parity-signing-key-0123456789-abcdefghij',
                                    salt='core.announcements.unsubscribe', fallback_keys=[])
    for value in strings:
        for token in re.findall(r'/unsubscribe/([^/\s<"\']+)/', value):
            recipient = signer.unsign_object(token, max_age=600)
            if not isinstance(recipient, int) or recipient <= 0:
                raise RuntimeError('notice preview has an invalid unsubscribe recipient')
            canonical = _preview_tokens.setdefault(recipient, token)
            mapping[token] = canonical
            recipients.append(recipient)
    if mapping:
        evaluate(tools, """(() => {
          const replacements=MAPPING,main=document.querySelector('#main');
          const replace=value=>{for(const [old,fresh] of Object.entries(replacements))value=value.split('/unsubscribe/'+old+'/').join('/unsubscribe/'+fresh+'/');return value};
          const walker=document.createTreeWalker(main,NodeFilter.SHOW_TEXT);
          while(walker.nextNode())walker.currentNode.textContent=replace(walker.currentNode.textContent);
          for(const link of main.querySelectorAll('a[href]'))link.setAttribute('href',replace(link.getAttribute('href')));
        })()""".replace('MAPPING', json.dumps(mapping)))
    return sorted(set(recipients))


def project(tools, evaluate, name, is_new):
    return evaluate(tools, """(async () => {
      const name=NAME, fresh=FRESH, main=document.querySelector('#main');
      if(!main || Number(main.dataset.pageStatus||200)!==200)return {};
      const evidence={};
      const placeholder=(node,label)=>{
        const item=document.createElement('div');item.className='c-notice';
        item.textContent=label;node.replaceWith(item);
      };
      const editorPages=['admin-article-new','admin-article','admin-intro','admin-page',
        'admin-tournaments-new','admin-tournaments-edit','admin-tournaments-copy',
        'admin-scrims-new','admin-scrims-edit','admin-scrims-copy'];
      if(editorPages.includes(name)) {
        if(fresh && name==='admin-article'){
          const target=location.pathname+'revisions/';
          const links=[...main.querySelectorAll('a[href]')].filter(link=>new URL(link.href,location.href).pathname===target);
          if(links.length!==1 || links[0].textContent.trim()!=='修订')throw new Error('approved revision entry missing or ambiguous');
          evidence.revisions=target;links[0].remove();
        }
        if(!fresh && ['admin-article','admin-article-new'].includes(name)){
          const guide=main.querySelector('.c-notice--info .c-notice__body > ul');
          if(guide)for(const item of guide.children){
            item.textContent=item.textContent.replace('点最右边的「?」看写法','点「写法」看写法').replace('点眼睛图标看排出来的样子','点「预览」看排出来的样子').replace('发布后 AI 会定时检查，有问题管理员会联系你或者撤下。','');
          }
        }
        const roots=[...main.querySelectorAll(fresh?'.markdown-editor[data-markdown-editor]':'.md-field')];
        evidence.editors=roots.map(root=>{
          const source=root.querySelector(fresh?'textarea[data-markdown-source]':'textarea[data-markdown-editor]');
          if(!source)throw new Error('approved editor region has no source textarea');
          const result={name:source.name,value:source.value,disabled:source.matches(':disabled')};
          if(fresh){
            const host=root.querySelector('.markdown-editor__host');
            const content=host?.shadowRoot?.querySelector('.cm-content');
            if(!content)throw new Error('CodeMirror did not initialize');
            if(content.getAttribute('contenteditable')!==String(!result.disabled))throw new Error('CodeMirror editable state differs from source');
            const value=[...content.querySelectorAll('.cm-line')].map(line=>line.textContent).join('\\n');
            if(value!==source.value)throw new Error('CodeMirror/source Markdown differs');
            for(const command of ['bold','italic','strike','heading','heading3','quote','unordered','ordered','link','code','image-upload','video','table','rule','preview','side-by-side','fullscreen']){
              const control=root.querySelector('[data-markdown-command="'+command+'"]');
              if(!control)throw new Error('missing Markdown command '+command);
              if(!['preview','side-by-side','fullscreen'].includes(command) && control.matches(':disabled')!==result.disabled)throw new Error('Markdown command disabled state differs: '+command);
            }
            if(![...root.querySelectorAll('button')].some(button=>button.textContent==='写法'))throw new Error('missing Markdown help');
          } else if(!root.querySelector('.CodeMirror'))throw new Error('legacy Markdown editor did not initialize');
          const plain=document.createElement('textarea');plain.className='c-input';plain.rows=18;
          plain.name=source.name;plain.value=source.value;plain.disabled=result.disabled;
          const frame=document.createElement('div');frame.className='md-field';frame.append(plain);root.replaceWith(frame);
          return result;
        });
        if(!evidence.editors.length)throw new Error('expected approved Markdown editor missing');
      }
      if(name==='admin-moderation'){
        const note=main.querySelector(':scope > .c-notice--warn');
        if(!note)throw new Error('AI status explanation missing');
        evidence.aiStatus=note.textContent.trim();
        if(fresh ? evidence.aiStatus!=='AI 巡查引擎将在割接后移植，已有记录仍可查看、人工记录处理结果。' : !evidence.aiStatus.startsWith('AI 审核没有在运行：'))throw new Error('unexpected AI status explanation');
        placeholder(note,'AI 引擎按 D5 延期，历史记录继续验收');
        main.querySelector(':scope > .b-section > p.b-sub')?.remove();
        if(!fresh){
          const button=document.querySelector('.b-head button[title="发一句测试内容给 AI，看密钥和模型能不能用（算一次调用，不留记录）"]');
          const form=button?.closest('form');
          if(form){if(new URL(form.action,location.href).pathname!=='/admin/moderation/try/')throw new Error('unexpected AI test action');form.remove();}
        }
      }
      if(name==='admin-fonts'){
        evidence.disk=[...main.querySelectorAll('tbody tr')].map(row=>{
          const cell=row.children[5];if(!cell || !cell.textContent.trim())throw new Error('font disk metric missing');
          const actual=cell.textContent.trim();cell.textContent='D4 字体文件';return actual;
        });
      }
      if(name==='admin-font-detail'){
        const upload=main.querySelector('.b-split > .b-form > section.b-section');
        if(!upload)throw new Error('font weight upload missing');
        if(upload.querySelector(':scope > h2')?.textContent.trim()!=='添加字重' || upload.querySelectorAll('button[type=submit]').length!==1 || upload.querySelector('button[type=submit]')?.textContent.trim()!=='添加')throw new Error('common font-weight heading/submit changed');
        if(fresh){
          const file=upload.querySelector('input[type=file][accept=".zip"]'),license=upload.querySelector('input[type=checkbox]'),submit=upload.querySelector('button[type=submit]');
          if(!file || file.matches(':disabled') || !license || license.checked || license.matches(':disabled') || !submit || !submit.matches(':disabled'))throw new Error('offline weight package/licence/submit controls invalid');
        }
        placeholder(upload,'D4 离线字重成品包');
        const disk=[...main.querySelectorAll('.b-aside dt')].find(item=>item.textContent==='磁盘占用')?.nextElementSibling;
        if(!disk)throw new Error('font disk metric missing');evidence.disk=[disk.textContent.trim()];disk.textContent='D4 字体文件';
        if(!fresh)main.querySelector('.b-aside .b-actions form')?.remove();
      }
      if(name==='admin-font-add'){
        const sections=[...main.querySelectorAll(':scope > section.b-section')];
        const upload=sections[0];
        if(!upload)throw new Error('font upload section missing');
        if(fresh){
          if(!upload.querySelector('input[type=file][accept=".zip"]') || !upload.querySelector('input[type=checkbox]'))throw new Error('offline font package/licence controls missing');
          const google=sections.find(section=>section.querySelector('h2')?.textContent==='从 Google Fonts 下载');
          if(!google || !google.querySelector('input[name="google-family_name"]') || google.querySelectorAll('input[name="google-weights"]').length!==9)throw new Error('Google family/weight controls missing');
        }else{
          const url=sections.find(section=>section.querySelector('h2')?.textContent==='从网址下载');
          if(!url)throw new Error('legacy font URL section missing');url.remove();
        }
        placeholder(upload,'D4 离线字体成品包');evidence.fontPackage=true;
      }
      if(name==='admin-font-delete'){
        const description=main.querySelector('.b-section > p.b-section__text');
        if(description){
          evidence.deleteDescription=description.textContent.trim();
          const parts=evidence.deleteDescription.split('吗？');
          const expected=fresh?'字体库记录会被移除，未被其他字体或正在上传的文件引用的切片会安全回收；共享切片保留。此操作无法恢复。':'原始文件和全部分片都会一起删除，无法恢复。';
          if(parts.length!==2 || parts[1].trim()!==expected)throw new Error('unexpected font deletion safety explanation');
          description.textContent=parts[0]+'吗？D4 删除离线字体分片，保留共享文件。无法恢复。';
        }
      }
      if(name==='admin-typography'){
        for(const node of main.querySelectorAll('code,.b-mono')){
          if(/^\\/media\\/fonts\\/.*\\.css$/.test(node.textContent.trim())){
            evidence.cssPath=node.textContent.trim();node.textContent='/media/fonts/D4-generated.css';
          }
        }
      }
      if(name==='admin-image'){
        const label=[...main.querySelectorAll('.b-aside dt')].find(item=>item.textContent===(fresh?'预览':'原图'));
        const link=label?.nextElementSibling?.querySelector('a[href]');
        if(!label || !link || link.textContent!=='打开')throw new Error('image source/preview link missing');
        const target=new URL(link.href,location.href);
        if(target.origin!==location.origin || target.search || target.hash)throw new Error('image preview origin/query changed');
        if(fresh){
          const id=location.pathname.match(/^\/admin\/images\/(\d+)\/$/)?.[1];
          if(!id || target.pathname!=='/media/r/'+id+'/max-800x600.webp')throw new Error('unexpected private image preview rendition');
          const response=await fetch(link.href);const bytes=new Uint8Array(await response.arrayBuffer());
          const word=offset=>String.fromCharCode(...bytes.slice(offset,offset+4));
          if(response.status!==200 || response.headers.get('content-type')?.split(';')[0]!=='image/webp' || word(0)!=='RIFF' || word(8)!=='WEBP')throw new Error('image preview is not a real WebP resource');
          evidence.imagePreview={path:target.pathname,status:response.status,type:'image/webp'};
        }else if(!target.pathname.startsWith('/media/original_images/'))throw new Error('unexpected old original image link');
        label.textContent='预览';link.setAttribute('href','/media/D4-image-preview');
      }
      if(name==='admin-settings'){
        const aside=main.querySelector('.b-aside');if(!aside)throw new Error('settings checks missing');
        if(fresh){
          const notice=[...aside.querySelectorAll('p.b-sub')].find(item=>item.textContent==='AI 巡查引擎按已批准的迁移安排在割接后启用。');
          if(!notice)throw new Error('approved AI deferral notice missing');
          placeholder(notice,'D5 AI 巡查割接后启用');
          const field=main.querySelector('input[name="backup_retention_days"]');
          if(!field || field.type!=='number' || field.min!=='1' || field.max!=='365' || field.matches(':disabled'))throw new Error('approved retention-days control invalid');
          evidence.retentionDays=field.value;
          const wrapper=field.closest('.c-field');
          if(!wrapper || wrapper.querySelector('.c-field__label')?.textContent!=='备份保留天数' || wrapper.querySelector('.c-field__help')?.textContent!=='本地与对象存储备份均按此天数清理；关闭上传仍会清理本地备份。')throw new Error('retention-days field explanation invalid');
          wrapper.remove();
        }else{
          const ai=[...aside.querySelectorAll('form')].find(form=>new URL(form.action,location.href).pathname==='/admin/moderation/try/');
          if(!ai || ai.querySelector('button')?.textContent!=='试一下 AI' || ai.querySelector('p.b-sub')?.textContent.trim()!=='用已保存的 AI 审核设置发一句测试内容，看密钥、接口地址和模型能不能用（算一次调用，不留记录）。刚改的设置会先存好再试；「启用 AI 内容审核」没打开也能试。')throw new Error('legacy AI test control missing');
          placeholder(ai,'D5 AI 巡查割接后启用');
          const wagtail=[...aside.querySelectorAll('section')].find(section=>section.querySelector('h2')?.textContent==='Wagtail 底层后台（应急用）');
          if(!wagtail || wagtail.querySelector('a')?.getAttribute('href')!=='/wagtail/' || wagtail.querySelector('p')?.textContent.trim()!=='新后台不做的事：用户组的细粒度权限、页面的修订历史、重定向。平时用不到。')throw new Error('legacy emergency backend region invalid');
          wagtail.remove();
        }
        evidence.settingsEngine=true;
      }
      if(name==='admin-manual' && !fresh){
        const obsolete=[...main.querySelectorAll('li')].filter(node=>node.textContent.trim()==='新后台不做的事（改用户组的细粒度权限、看页面的修订历史、重定向）在Wagtail 底层后台里，入口在右上角账号菜单，只有超级管理员看得到。平时用不到，别在那里改文章和活动。');
        if(obsolete.length>1)throw new Error('ambiguous obsolete emergency-backend guide');
        for(const node of obsolete){evidence.emergencyBackend=true;node.remove();}
        const changes=[
          ['异地备份填完对象存储后先点全站设置里的「测试对象存储」。','本地备份按全站设置中的保留天数清理。'],
          ['AI 每 30 分钟巡查一次，有可疑的会发信给站长（或全站设置里填的邮箱）。','AI 巡查暂未启用，已有记录仍可查看。'],
          ['、重新生成静态页',''],['、静态页生成失败','']
        ];
        const walker=document.createTreeWalker(main,NodeFilter.SHOW_TEXT);
        while(walker.nextNode())for(const [old,replacement] of changes){
          if(walker.currentNode.textContent.includes(old)){
            evidence.manual=true;walker.currentNode.textContent=walker.currentNode.textContent.replace(old,replacement);
          }
        }
      }
      return evidence;
    })()""".replace('NAME', json.dumps(name)).replace('FRESH', json.dumps(is_new)))


def compare(old, new):
    problems = []
    if old.get('editors') != new.get('editors'):
        problems.append('已批准编辑器差异之外的正文名称、内容或禁用状态不同')
    return problems


def negative_probe():
    baseline = {'editors': [{'name': 'body', 'value': 'real body', 'disabled': False}]}
    for field, value in (('name', 'other'), ('value', 'wrong body'), ('disabled', True)):
        damaged = {'editors': [{**baseline['editors'][0], field: value}]}
        if not compare(baseline, damaged):
            raise RuntimeError('approved editor projection missed changed ' + field)
    if compare(baseline, baseline):
        raise RuntimeError('approved editor projection rejected identical controls')
