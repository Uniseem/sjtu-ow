import { globSync,readFileSync } from "node:fs"
import { resolve } from "node:path"
import { expect,test } from "vitest"
const root=resolve(import.meta.dirname,"../../../..")
const files=globSync("**/*.vue",{cwd:import.meta.dirname})
const sourceFiles=globSync("**/*.ts",{cwd:import.meta.dirname}).filter(file=>!file.endsWith(".test.ts"))
const known=new Set<string>()
const component=/\b[cbl]-[a-z0-9]+(?:-[a-z0-9]+)*(?:__[a-z0-9]+(?:-[a-z0-9]+)*)?(?:--[a-z0-9]+(?:-[a-z0-9]+)*)?/g
for(const file of ["web/packages/styles/input.css",...globSync("{templates,*/templates}/**/*.html",{cwd:root})]){
 for(const match of readFileSync(resolve(root,file),"utf8").matchAll(component))known.add(match[0])
}
function offenders(pattern:RegExp):string[]{return files.filter(file=>pattern.test(readFileSync(resolve(import.meta.dirname,file),"utf8")))}
test("admin keeps strict CSP and generated API boundaries",()=>{
 expect(offenders(/(?:\s:style=|\sv-bind:style=|\sstyle="|\sv-html=)/)).toEqual([])
 expect(offenders(/\bfetch\s*\(|["'`}]\/api\//)).toEqual([])
 expect(offenders(/(?::\s*any\b|<any>|\bas any\b|any\[\])/)).toEqual([])
})
test("admin endpoint adapters consume generated functions",()=>{
 expect(sourceFiles.filter(file=>/\bapi\s*<[^>]+>\s*\(|\bapi\s*\(\s*["'](?:GET|POST|PATCH|DELETE)["']/.test(readFileSync(resolve(import.meta.dirname,file),"utf8")))).toEqual([])
})
test("admin uses the existing semantic colour palette",()=>{
 expect(offenders(/(?:bg|text|border|fill|stroke|ring|outline)-(?:stone|slate|gray|zinc|neutral|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d/)).toEqual([])
})
test("admin component classes belong to the design system or legacy templates",()=>{
 const missing:string[]=[]
 for(const file of files){
  const source=readFileSync(resolve(import.meta.dirname,file),"utf8")
  const template=source.slice(source.indexOf("<template>"))
  for(const match of template.matchAll(component)){
   const after=template.slice((match.index||0)+match[0].length,(match.index||0)+match[0].length+3)
   if(after.startsWith("-${")||after.startsWith("-$")){if([...known].some(key=>key.startsWith(match[0]+"-")))continue}
   if(!known.has(match[0]))missing.push(file+": "+match[0])
  }
 }
 expect([...new Set(missing)]).toEqual([])
})
