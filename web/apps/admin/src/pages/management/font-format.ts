export function bytes(value:number){return value<1024?`${value} 字节`:value<1024*1024?`${(value/1024).toFixed(1)} KB`:`${(value/1024/1024).toFixed(1)} MB`}
export function source(value:string){const labels:Record<string,string>={google:'Google Fonts',package:'上传',upload:'上传',google_fonts:'Google Fonts',url:'网址下载'};return labels[value]||value}
export function status(value:string){const labels:Record<string,string>={ready:'可用',processing:'处理中',failed:'处理失败',unavailable:'尚未添加字重'};return labels[value]||value}
export function weight(value:number,style:string){return `${value}${style==='italic'?' 斜体':''}`}
export const weightChoices = [
  { value: 100, label: '100 Thin' }, { value: 200, label: '200 ExtraLight' },
  { value: 300, label: '300 Light' }, { value: 400, label: '400 Regular' },
  { value: 500, label: '500 Medium' }, { value: 600, label: '600 SemiBold' },
  { value: 700, label: '700 Bold' }, { value: 800, label: '800 ExtraBold' },
  { value: 900, label: '900 Black' },
]

export function license(value:string){const labels:Record<string,string>={open_source:"开源授权",web_license:"已购买网页嵌入授权",other:"其他"};return labels[value]||value}
