/** Public typography is an external, immutable same-origin stylesheet. API
 * metadata cannot inject arbitrary links into a document head. */
export function fontCSSPath(value:unknown):string|null {
 return typeof value==='string'&&/^\/media\/fonts\/css\/fonts\.(?:[a-f0-9]{12}|[a-f0-9]{20})\.css$/.test(value)?value:null
}
export function syncFontCSS(value:unknown):void {
 const path=fontCSSPath(value)
 const current=document.querySelector<HTMLLinkElement>('link[data-site-font-css]')
 if(!path){current?.remove();return}
 if(current?.getAttribute('href')===path)return
 const link=document.createElement('link')
 link.rel='stylesheet';link.href=path;link.dataset.siteFontCss=''
 link.addEventListener('load',()=>current?.remove(),{once:true})
 link.addEventListener('error',()=>link.remove(),{once:true})
 document.head.append(link)
}
