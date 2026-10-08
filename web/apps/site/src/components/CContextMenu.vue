<script setup lang="ts">
// The site's own right-click menu (design 13.2.6), as a global component
// that owns the listeners (12-architecture 6.6). The browser's menu stays
// where it is needed: Shift + right click, form fields and editable areas
// (paste, spell check), touch screens (long press). The panel is built by
// hand like the old contextmenu.js: it never renders on the server, and
// placing it sets el.style (CSSOM, which the CSP allows — not a style
// attribute in the HTML).
import { onBeforeUnmount, onMounted } from "vue"
import { planGroups, type MenuEntry } from "../contextmenu-entries"

const NATIVE = "input, textarea, select, [contenteditable=''], [contenteditable='true'], [data-native-contextmenu]"

let menu: HTMLDivElement | null = null
let opener: HTMLElement | null = null
let x = 0
let y = 0

function close() {
  if (menu) {
    menu.remove()
    menu = null
  }
  if (opener && opener.focus) {
    opener.focus({ preventScroll: true })
  }
  opener = null
}

function note(text: string) {
  const el = document.createElement("div")
  el.className = "c-ctxmenu-toast"
  el.setAttribute("role", "status")
  el.textContent = text
  el.style.left = x + 12 + "px"
  el.style.top = y + 12 + "px"
  document.body.appendChild(el)
  setTimeout(() => el.remove(), 1400)
}

function copy(text: string) {
  const done = () => note("已复制")
  const fallback = () => {
    const area = document.createElement("textarea")
    area.value = text
    area.setAttribute("readonly", "")
    area.style.position = "fixed"
    area.style.opacity = "0"
    document.body.appendChild(area)
    area.select()
    try {
      document.execCommand("copy")
      done()
    } catch {
      note("复制失败")
    }
    area.remove()
  }
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done, fallback)
  } else {
    fallback()
  }
}

function run(entry: MenuEntry) {
  close()
  switch (entry.kind) {
    case "open-url":
      window.open(entry.arg, "_blank", "noopener")
      break
    case "copy":
      copy(entry.arg ?? "")
      break
    case "search":
      window.location.href = "/search/?q=" + encodeURIComponent(entry.arg ?? "")
      break
    case "back":
      window.history.back()
      break
    case "forward":
      window.history.forward()
      break
    case "reload":
      window.location.reload()
      break
    case "scroll-top": {
      const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      window.scrollTo({ top: 0, behavior: calm ? "auto" : "smooth" })
      break
    }
  }
}

function context(target: HTMLElement) {
  const link = target.closest("a[href]")
  const href = link && !/^javascript:/i.test(link.getAttribute("href") ?? "") ? link.href : null
  const image = target.closest("img")
  const imageSrc = image ? image.currentSrc || image.src : null
  const selection = window.getSelection ? String(window.getSelection()).trim() : ""
  return {
    href,
    imageSrc: imageSrc || null,
    selection,
    scrolled: window.scrollY > 0,
    pageUrl: window.location.href,
  }
}

function build(groups: ReturnType<typeof planGroups>) {
  const panel = document.createElement("div")
  panel.className = "c-ctxmenu"
  panel.setAttribute("role", "menu")
  panel.setAttribute("aria-label", "右键菜单")
  groups.forEach((group, index) => {
    if (index > 0) {
      const line = document.createElement("hr")
      line.setAttribute("role", "separator")
      panel.appendChild(line)
    }
    for (const entry of group) {
      const item = document.createElement("button")
      item.type = "button"
      item.className = "c-ctxmenu__item"
      item.setAttribute("role", "menuitem")
      item.tabIndex = -1
      const label = document.createElement("span")
      label.textContent = entry.label
      item.appendChild(label)
      if (entry.hint) {
        const hint = document.createElement("kbd")
        hint.textContent = entry.hint
        item.appendChild(hint)
      }
      item.addEventListener("click", () => run(entry))
      panel.appendChild(item)
    }
  })
  const foot = document.createElement("p")
  foot.className = "c-ctxmenu__foot"
  foot.textContent = "按住 Shift 再右键：浏览器自带的菜单"
  panel.appendChild(foot)
  return panel
}

function place(panel: HTMLDivElement) {
  const gap = 8
  const width = panel.offsetWidth
  const height = panel.offsetHeight
  const left = Math.min(x, window.innerWidth - width - gap)
  const top = y + height + gap > window.innerHeight ? y - height : y
  panel.style.left = Math.max(gap, left) + "px"
  panel.style.top = Math.max(gap, top) + "px"
}

function items() {
  return menu ? Array.from(menu.querySelectorAll<HTMLButtonElement>(".c-ctxmenu__item")) : []
}

function onContextMenu(event: MouseEvent) {
  const target = event.target as HTMLElement
  const touch = event.pointerType === "touch" || event.pointerType === "pen"
  if (event.shiftKey || touch || !target.closest || target.closest(NATIVE)) {
    close()
    return
  }
  if (target.closest(".c-ctxmenu")) {
    event.preventDefault()
    return
  }
  event.preventDefault()
  close()
  x = event.clientX
  y = event.clientY
  if (!x && !y) {
    // The keyboard's menu key: open by the focused element.
    const box = target.getBoundingClientRect()
    x = box.left + 8
    y = box.bottom
  }
  opener = document.activeElement as HTMLElement | null
  menu = build(planGroups(context(target)))
  document.body.appendChild(menu)
  place(menu)
  const first = items()[0]
  if (first) {
    first.focus({ preventScroll: true })
  }
}

function onKeyDown(event: KeyboardEvent) {
  if (!menu) {
    return
  }
  const list = items()
  const at = list.indexOf(document.activeElement as HTMLButtonElement)
  if (event.key === "Escape" || event.key === "Tab") {
    event.preventDefault()
    close()
  } else if (event.key === "ArrowDown") {
    event.preventDefault()
    list[(at + 1) % list.length].focus()
  } else if (event.key === "ArrowUp") {
    event.preventDefault()
    list[(at - 1 + list.length) % list.length].focus()
  } else if (event.key === "Home") {
    event.preventDefault()
    list[0].focus()
  } else if (event.key === "End") {
    event.preventDefault()
    list[list.length - 1].focus()
  }
}

function onPointerDown(event: PointerEvent) {
  if (menu && !menu.contains(event.target as Node)) {
    opener = null
    close()
  }
}

function onScroll() {
  opener = null
  close()
}

onMounted(() => {
  if (!window.matchMedia("(pointer: fine)").matches) {
    return // touch screens keep the browser's long-press menu
  }
  document.addEventListener("contextmenu", onContextMenu)
  document.addEventListener("keydown", onKeyDown)
  document.addEventListener("pointerdown", onPointerDown, true)
  window.addEventListener("scroll", onScroll, true)
  window.addEventListener("resize", close)
  window.addEventListener("blur", onScroll)
})

onBeforeUnmount(() => {
  document.removeEventListener("contextmenu", onContextMenu)
  document.removeEventListener("keydown", onKeyDown)
  document.removeEventListener("pointerdown", onPointerDown, true)
  window.removeEventListener("scroll", onScroll, true)
  window.removeEventListener("resize", close)
  window.removeEventListener("blur", onScroll)
  close()
})
</script>
<template>
  <!-- 该组件只装监听器，不画东西；这个隐藏的空元素让模板有一个根 -->
  <span hidden aria-hidden="true"></span>
</template>
