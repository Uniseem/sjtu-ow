<script lang="ts">
import { getApiLettersBatch } from "@sjtu-ow/api"
import { PageRedirect } from "@sjtu-ow/shared/navigation"
import { letterBatch,previewURL } from "@sjtu-ow/shared/letters"
import { httpError,type LoadCtx } from "../router"
export async function load(ctx:LoadCtx):Promise<never>{
 if(!(await ctx.viewer()).user)throw httpError(404)
 const batch=letterBatch(ctx.params.batch)
 const id=Number(ctx.params.id)
 if(!Number.isSafeInteger(id)||id<1)throw httpError(404)
 const detail=await getApiLettersBatch(ctx.api,batch)
 const letter=detail.letters.find(letter=>letter.id===id)
 const url=letter&&previewURL(letter.preview_url,batch,id)
 if(!url)throw httpError(404)
 throw new PageRedirect(url,302)
}
export default {}
</script>
<template><main id="main" class="flex-1" /></template>
