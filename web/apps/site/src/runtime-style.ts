// Mutate rules in the external same-origin stylesheet, never a style attribute.
// WebKit enforces style-src-attr even for HTMLElement.style CSSOM writes.
type Selector = ':root' | '.c-ctxmenu' | '.c-ctxmenu-toast'
const rules = new Map<Selector, CSSStyleDeclaration>()
export function runtimeStyle(selector: Selector): CSSStyleDeclaration {
  const previous = rules.get(selector)
  if (previous) return previous
  const sheet = [...document.styleSheets].find(candidate => {
    const owner = candidate.ownerNode
    return Boolean(candidate.href && new URL(candidate.href).origin === location.origin
      && owner instanceof HTMLLinkElement && !owner.hasAttribute('data-site-font-css'))
  })
  if (!sheet) throw new Error('本站样式表尚未加载')
  const index = sheet.insertRule(`${selector}{}`, sheet.cssRules.length)
  const style = (sheet.cssRules[index] as CSSStyleRule).style
  rules.set(selector, style)
  return style
}
