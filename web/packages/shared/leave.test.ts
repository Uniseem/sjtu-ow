import { afterEach, expect, test, vi } from "vitest"
import { permitProgrammaticLeave, programmaticLeavePermitted } from "./src/leave"

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

test("a delayed mandatory unload covers all listeners and then restores the dirty guard", async () => {
  const events = new EventTarget()
  vi.stubGlobal("window", events)
  vi.useFakeTimers()
  permitProgrammaticLeave()
  await vi.advanceTimersByTimeAsync(10)
  expect(programmaticLeavePermitted()).toBe(true)
  const observed: boolean[] = []
  events.addEventListener("beforeunload", () => observed.push(programmaticLeavePermitted()))
  events.addEventListener("beforeunload", () => observed.push(programmaticLeavePermitted()))
  events.dispatchEvent(new Event("beforeunload", { cancelable: true }))
  expect(observed).toEqual([true, true])
  await vi.runOnlyPendingTimersAsync()
  expect(programmaticLeavePermitted()).toBe(false)
})

test("failed assignment, restored documents and resumed editing revoke the permission", () => {
  const events = new EventTarget()
  vi.stubGlobal("window", events)
  for (const event of ["pageshow", "pointerdown", "keydown"]) {
    permitProgrammaticLeave()
    events.dispatchEvent(new Event(event))
    expect(programmaticLeavePermitted()).toBe(false)
  }
  const cancel = permitProgrammaticLeave()
  cancel()
  expect(programmaticLeavePermitted()).toBe(false)
})
