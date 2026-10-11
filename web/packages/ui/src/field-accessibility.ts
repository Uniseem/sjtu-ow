import { onMounted, onUpdated, onUnmounted } from "vue"
import type { Ref } from "vue"

type Original = {
  invalid: string | null
  describedBy: string | null
}

function restore(control: Element, name: string, value: string | null): void {
  if (value === null) control.removeAttribute(name)
  else control.setAttribute(name, value)
}

/**
 * Slot controls retain their own help text and ids. After mounting, associate
 * the rendered error with each control, including radio/checkbox groups.
 * No random id, client-only DOM read in setup, or inline style is needed.
 */
export function useFieldAccessibility(
  root: Ref<HTMLElement | null>,
  hasErrors: () => boolean,
  inputId: () => string | undefined,
): void {
  const original = new Map<Element, Original>()
  let errorId: string | null = null

  function synchronize(): void {
    const field = root.value
    if (!field) return
    const controls = [...field.querySelectorAll("input:not([type=hidden]),select,textarea")]
    for (const control of controls) {
      if (!original.has(control)) original.set(control, {
        invalid: control.getAttribute("aria-invalid"),
        describedBy: control.getAttribute("aria-describedby"),
      })
    }
    for (const [control, attrs] of original) {
      if (!field.contains(control)) {
        restore(control, "aria-invalid", attrs.invalid)
        restore(control, "aria-describedby", attrs.describedBy)
        original.delete(control)
      }
    }
    const error = field.querySelector<HTMLElement>(".c-field__error")
    const controlId = inputId() || controls.find((control) => control.id)?.id
    if (error && controlId) {
      errorId = controlId + "_error"
      error.id = errorId
    }
    for (const control of controls) {
      const attrs = original.get(control)
      if (!attrs) continue
      if (hasErrors()) {
        control.setAttribute("aria-invalid", "true")
        const descriptions = new Set((attrs.describedBy ?? "").split(/\s+/).filter(Boolean))
        if (error && errorId) descriptions.add(errorId)
        if (descriptions.size) control.setAttribute("aria-describedby", [...descriptions].join(" "))
      } else {
        restore(control, "aria-invalid", attrs.invalid)
        restore(control, "aria-describedby", attrs.describedBy)
      }
    }
    if (!error) errorId = null
  }

  onMounted(synchronize)
  onUpdated(synchronize)
  onUnmounted(() => {
    for (const [control, attrs] of original) {
      restore(control, "aria-invalid", attrs.invalid)
      restore(control, "aria-describedby", attrs.describedBy)
    }
    original.clear()
  })
}
