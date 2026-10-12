<script lang="ts">
import { getApiAdminScrimsIdBoard } from "@sjtu-ow/api"
import { httpError, type LoadCtx, type PageData } from "../router"
export async function load(ctx: LoadCtx): Promise<PageData> {
  const board = await getApiAdminScrimsIdBoard(ctx.api, ctx.params.id!)
  if (!board.copy_text) throw httpError(500)
  return { title: '', document: { kind: 'plain', text: board.copy_text } }
}
export default {}
</script>
<template><main /></template>
