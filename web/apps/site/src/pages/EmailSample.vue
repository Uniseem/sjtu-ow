<script lang="ts">
import { getApiAdminMailSamplesKey } from "@sjtu-ow/api"
import { httpError, type LoadCtx, type PageData } from "../router"
export async function load(ctx: LoadCtx): Promise<PageData> {
  const viewer = await ctx.viewer()
  if (!viewer.user?.admin) throw httpError(404)
  const key = ctx.params.key
  if (!/^[a-z][a-z0-9-]{0,63}$/.test(key)) throw httpError(404)
  const sample = await getApiAdminMailSamplesKey(ctx.api, key)
  if (!sample.html) throw httpError(500)
  return { title: sample.title, document: { kind: "mail", html: sample.html } }
}
export default {}
</script>
<template><main id="main" /></template>
