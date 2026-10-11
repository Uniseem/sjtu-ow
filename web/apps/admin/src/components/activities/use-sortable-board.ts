import { nextTick, onMounted, onUnmounted, watch } from "vue"
import type { Ref } from "vue"

type SortableInstance = { destroy(): void }
type SortableEvent = { item: HTMLElement; to: HTMLElement; from: HTMLElement; oldIndex?: number }
type SortableConstructor = new (element: HTMLElement, options: Record<string, unknown>) => SortableInstance

/**
 * Sortable mutates DOM before Vue sees the edit. Restore that DOM first and
 * emit a semantic move; the parent state then renders the accepted placement.
 * All move validation is shared with keyboard and button controls.
 */
export function useSortableBoard(
  root: Ref<HTMLElement | null>,
  revision: () => unknown,
  enabled: () => boolean,
  move: (id: number, zone: string) => void,
  failed: (message: string) => void,
): void {
  const instances: SortableInstance[] = []
  let disposed = false
  let sequence = 0
  let Constructor: SortableConstructor | null = null

  function destroy(): void {
    for (const instance of instances.splice(0)) instance.destroy()
  }

  async function bind(): Promise<void> {
    const token = ++sequence
    await nextTick()
    if (disposed || !root.value || !Constructor || token !== sequence) return
    destroy()
    for (const zone of root.value.querySelectorAll<HTMLElement>("[data-board-zone]")) {
      const sortable = new Constructor(zone, {
        group: "activity-board",
        animation: 0,
        draggable: "[data-signup]",
        handle: "[data-drag-handle]",
        disabled: !enabled(),
        forceFallback: false,
        onEnd: (event: SortableEvent) => {
          const target = event.to.dataset.boardZone ?? ""
          const id = Number(event.item.dataset.signup)
          const siblings = [...event.from.children].filter((node) => node !== event.item)
          const reference = siblings[event.oldIndex ?? siblings.length] ?? null
          event.from.insertBefore(event.item, reference)
          if (Number.isSafeInteger(id) && id > 0 && enabled()) move(id, target)
        },
      })
      instances.push(sortable)
    }
  }

  onMounted(async () => {
    try {
      const module = await import("sortablejs")
      if (disposed) return
      Constructor = module.default as unknown as SortableConstructor
      await bind()
    } catch {
      if (!disposed) failed("拖拽暂时不可用，请用卡片上的按钮或键盘移动。")
    }
  })
  watch(revision, bind, { flush: "post" })
  watch(enabled, bind, { flush: "post" })
  onUnmounted(() => {
    disposed = true
    sequence += 1
    destroy()
  })
}
