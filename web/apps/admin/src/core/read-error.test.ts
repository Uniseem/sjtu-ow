import { expect, test } from "vitest"
import { ApiError } from "@sjtu-ow/api"
import { readErrorDocument } from "./read-error"

test("page reads use the frozen scriptless403/404 rather than revealing API reasons", () => {
  for (const status of [403, 404]) {
    const body = readErrorDocument(new ApiError(status, "private", "private-object-name"))
    expect(body).toContain(`<p class="code" aria-hidden="true">${status}</p>`)
    expect(body).not.toContain("<script")
    expect(body).not.toContain("private-object-name")
    expect(body).toContain("/static/css/error.css")
  }
  for (const status of [401, 409, 422, 429, 500, 0]) expect(readErrorDocument(new ApiError(status, "other", "error"))).toBeNull()
})
