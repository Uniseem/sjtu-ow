import { computed, onMounted, onUnmounted, shallowRef } from "vue"
import { onBeforeRouteLeave, onBeforeRouteUpdate } from "vue-router"
import { Autosave, type SaveOptions } from "@sjtu-ow/shared/autosave"
import { registerUnsaved } from "./unsaved"

/** Vue bindings live here; the shared state machine needs no Vue dependency. */
export function useAutosave<T extends object>(options: SaveOptions<T>) {
  const controller = new Autosave(options)
  const snapshot = shallowRef(controller.snapshot())
  const unsubscribe = controller.subscribe((value) => { snapshot.value = value })
  const dirty = computed(() => snapshot.value.dirty)
  const pending = computed(() => snapshot.value.saving)
  const fields = computed(() => snapshot.value.fields)
  const values = computed(() => snapshot.value.values)
  let leaving = false
  let unregister: (() => void) | undefined

  async function leave(): Promise<boolean> {
    if (leaving) return false
    if (!controller.dirty()) return true
    leaving = true
    try {
      const saved = await controller.flush()
      if (!saved) focusError()
      return saved
    } finally {
      leaving = false
    }
  }

  function focusError(): void {
    const field = document.querySelector<HTMLElement>("#main .is-invalid input, #main .is-invalid select, #main .is-invalid textarea")
    if (field) {
      field.focus()
      return
    }
    const status = document.querySelector<HTMLElement>("#main [data-autosave-status]")
    if (status) {
      status.tabIndex = -1
      status.focus()
    }
  }

  async function save(): Promise<boolean> {
    const saved = await controller.retry()
    if (!saved) focusError()
    return saved
  }

  onBeforeRouteLeave(leave)
  onBeforeRouteUpdate(async (to, from) => {
    if (to.fullPath === from.fullPath) return true
    return leave()
  })
  onMounted(() => {
    unregister = registerUnsaved({ dirty: () => controller.dirty(), flush: () => controller.flush(), failed: focusError })
  })
  onUnmounted(() => {
    unregister?.()
    unsubscribe()
    controller.dispose()
  })

  return {
    controller,
    snapshot,
    values,
    fields,
    dirty,
    pending,
    save,
    flush: () => controller.flush(),
    set: controller.set.bind(controller),
    setMany: controller.setMany.bind(controller),
  }
}
