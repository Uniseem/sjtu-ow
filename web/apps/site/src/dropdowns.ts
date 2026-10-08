// The masthead's <details> dropdowns (design 13.2.6, v6.65): a click
// outside, Esc, or opening another one closes them, so only one is ever
// open. They still open and close by their own button without this —
// installed once from the client entry, like the old app.js.
const DROPDOWNS = "details.c-menu, details.c-theme, details.c-drawer"

function closeDropdowns(except: Element | null) {
  for (const open of document.querySelectorAll(DROPDOWNS)) {
    if (open !== except && (open as HTMLDetailsElement).open) {
      ;(open as HTMLDetailsElement).open = false
    }
  }
}

function onToggle(event: Event) {
  const target = event.target as Element
  if (target.matches && target.matches(DROPDOWNS) && (target as HTMLDetailsElement).open) {
    closeDropdowns(target)
  }
}

function onClick(event: MouseEvent) {
  const inside = (event.target as HTMLElement).closest?.(DROPDOWNS) ?? null
  closeDropdowns(inside)
}

function onKeyDown(event: KeyboardEvent) {
  if (event.key !== "Escape") {
    return
  }
  const open = document.querySelector("details.c-menu[open], details.c-theme[open], details.c-drawer[open]")
  if (open) {
    ;(open as HTMLDetailsElement).open = false
    open.querySelector("summary")?.focus()
  }
}

export function installDropdowns() {
  // "toggle" does not bubble, but a capturing listener still sees it.
  document.addEventListener("toggle", onToggle, true)
  document.addEventListener("click", onClick)
  document.addEventListener("keydown", onKeyDown)
}
