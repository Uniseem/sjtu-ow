import { globSync, readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs"
import { dirname, join, resolve } from "node:path"

const root = resolve(import.meta.dirname, "../../..")
const output = resolve(process.argv[2] || "/tmp/sjtuow-305-inventory")
mkdirSync(output, { recursive: true })
const files = [...globSync("web/{apps/site/src,apps/admin/src,packages/ui/src}/**/*.vue", { cwd: root })].sort()
const sources = new Map(files.map(file => [file, readFileSync(join(root, file), "utf8")]))
function dependency(file, target) {
  const path = target.startsWith("@sjtu-ow/ui/") ? join(root, "web/packages/ui/src", target.slice(12)) : resolve(root, dirname(file), target)
  return existsSync(path) ? path.slice(root.length + 1) : null
}
const entries = files.map(file => {
  const source = sources.get(file)
  const dependencies = [...source.matchAll(/from\s+["']([^"']+\.vue)["']/g)].map(match => dependency(file, match[1])).filter(Boolean)
  const classes = [...new Set([...source.matchAll(/\b(?:[cbl]-[a-z0-9-]+(?:__[a-z0-9-]+)*(?:--[a-z0-9-]+)*|split-[a-z0-9-]+|markdown-editor(?:__[a-z0-9-]+)?|avatar-review(?:__[a-z0-9-]+)?)/g)].map(match => match[0]))].sort()
  const template = source.match(/<template>([\s\S]*)<\/template>/)?.[1] || ""
  const wrapper = Boolean(dependencies.length && !/<(?:div|span|section|main|header|button|input|form|nav|dialog)\b/.test(template))
  return { file, area: file.includes("/admin/") ? "admin" : file.includes("/ui/") ? "shared" : "site", kind: file.includes("/pages/") ? "page" : wrapper ? "delegate" : "component", classes, dependencies, scoped: /<style\b/.test(source), nativeControls: [...new Set([...template.matchAll(/<(button|input|select|textarea|dialog|details)\b/g)].map(match => match[1]))] }
})
writeFileSync(join(output, "inventory.json"), JSON.stringify({ total: entries.length, entries }, null, 2))
writeFileSync(join(output, "inventory.md"), "# Vue 文件与样式归属\n\n源码盘点不等于运行验收。类名动态拼接和组合组件需结合实际页面检查。\n\n| 文件 | 范围 | 类型 | 直接样式 | 复用组件 |\n|---|---|---|---|---|\n" + entries.map(entry => `| ${entry.file} | ${entry.area} | ${entry.kind} | ${entry.classes.join(", ") || "基础元素或工具类"} | ${entry.dependencies.join(", ") || "—"} |`).join("\n") + "\n")
console.log(JSON.stringify({ files: entries.length, scoped: entries.filter(entry => entry.scoped).map(entry => entry.file), output }))
