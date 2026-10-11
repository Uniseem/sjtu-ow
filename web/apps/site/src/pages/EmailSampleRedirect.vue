<script lang="ts">
import { PageRedirect } from "@sjtu-ow/shared/navigation"
import { httpError,type LoadCtx } from "../router"
export async function load(ctx:LoadCtx):Promise<never>{
 const viewer=await ctx.viewer()
 if(!viewer.user?.admin)throw httpError(404)
 const key=ctx.params.key
 if(key&&!/^[a-z][a-z0-9-]{0,63}$/.test(key))throw httpError(404)
 throw new PageRedirect("/admin/settings/email-samples/"+(key?encodeURIComponent(key)+"/":""),302)
}
export default {}
</script>
<template><main id="main" class="flex-1" /></template>
