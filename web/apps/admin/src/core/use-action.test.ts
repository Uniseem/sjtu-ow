import { expect, test, vi } from "vitest"
import { createClient } from "@sjtu-ow/api"
import { afterAdminWrite } from "./use-action"

test("held-letter navigation wins over a successful action's return-to-list callback", async () => {
  const assign = vi.fn()
  const success = vi.fn()
  const client = createClient({ location: () => "/admin/registrations/9/", assign, fetch: async () => Response.json({ saved: true, letters: { batch: "held-123", count: 2 } }) })
  const result = await client("POST", "/api/admin/registrations/9/approve", {})
  await afterAdminWrite(result, success)
  expect(assign).toHaveBeenCalledWith("/admin/letters/held-123/?back=%2Fadmin%2Fregistrations%2F9%2F")
  expect(success).not.toHaveBeenCalled()
  await afterAdminWrite({ saved: true }, success)
  expect(success).toHaveBeenCalledOnce()
})
