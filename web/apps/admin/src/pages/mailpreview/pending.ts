import type { GetApiAdminMailSamplesOut, GetApiAdminMailSamplesKeyOut } from "@sjtu-ow/api"

export {
  getApiAdminMailSamples as getMailSamples,
  getApiAdminMailSamplesKey as getMailSample,
} from "@sjtu-ow/api"
export type MailSample = GetApiAdminMailSamplesKeyOut
export type MailSampleGroup = GetApiAdminMailSamplesOut["groups"][number]
export type MailSamples = GetApiAdminMailSamplesOut

// The raw HTML document is separately authenticated and sandboxed by Go.
// Only the generated sample's own same-origin document may enter this iframe.
export function sampleDocumentURL(sample: MailSample, kind: "preview" | "text"): string | null {
  if (!/^[a-z][a-z0-9-]{0,63}$/.test(sample.key)) return null
  const expected = `/api/admin/mail-samples/${sample.key}/${kind}`
  const supplied = kind === "preview" ? sample.preview_url : sample.text_url
  return supplied === expected ? expected : null
}
