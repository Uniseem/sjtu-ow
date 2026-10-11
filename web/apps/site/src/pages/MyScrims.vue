<script lang="ts">
import type { LoadCtx } from "../router"
import { httpError } from "../router"
import { getPersonalScrims } from "../pending-api"
import { personalScrims } from "../personal-list-schema"

// [BE-14] Kept ready for the missing private endpoint; route stays absent.
export async function load(ctx: LoadCtx) {
  const viewer = await ctx.viewer()
  if (!viewer.user) throw httpError(401)
  return { title: "我的内战", user: viewer.user, scrims: personalScrims(await getPersonalScrims(ctx.api)) }
}
</script>

<script setup lang="ts">
import { inject } from "vue"
import { useHead } from "@unhead/vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CRoleIcon from "@sjtu-ow/ui/CRoleIcon.vue"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import { owDate, owTime } from "@sjtu-ow/shared/time"
import PersonalSessionLayout from "../components/PersonalSessionLayout.vue"
import type { PersonalScrims } from "../pending-api"
import type { ViewerUser } from "../viewer"
import { requirePageData } from "../personal"

const data = requirePageData(inject<{ user: ViewerUser; scrims: PersonalScrims }>("page-data"))

function state(status: string): { kind: string; label: string } {
  if (status === "cancelled") return { kind: "off", label: "已取消" }
  if (status === "finished") return { kind: "done", label: "已结束" }
  return { kind: "ok", label: "已报名" }
}

useHead({ title: "我的内战 · SJTU-OW", meta: [{ name: "robots", content: "noindex" }] })
</script>

<template>
  <PersonalSessionLayout title="我的内战" current="/me/scrims/" :user="data.user">
    <table v-if="data.scrims.signups.length" class="c-table c-table--stack">
      <thead>
        <tr>
          <th scope="col">内战</th>
          <th scope="col">开始</th>
          <th scope="col">位置</th>
          <th scope="col">分队</th>
          <th scope="col" class="is-num">状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="signup in data.scrims.signups" :key="signup.id">
          <td data-label="内战">
            <a :href="'/scrims/' + signup.scrim_id + '/'" class="font-semibold hover:text-primary-text">{{ signup.title }}</a>
          </td>
          <td data-label="开始" class="font-numeric">
            {{ owDate(new Date(signup.starts_at)) }} {{ owTime(new Date(signup.starts_at)) }}
          </td>
          <td data-label="位置"><CRoleIcon :tank="signup.role_tank" :damage="signup.role_damage" :support="signup.role_support" /></td>
          <td data-label="分队" data-placement>
            <template v-if="signup.placement">{{ signup.placement }}</template>
            <span v-else class="text-fg-3">还没分队</span>
          </td>
          <td data-label="状态" class="is-num"><CStatus :kind="state(signup.status).kind" :label="state(signup.status).label" /></td>
        </tr>
      </tbody>
    </table>
    <CEmpty
      v-else
      title="还没有报名内战"
      message="在内战页面报名后会出现在这里。"
      action-url="/scrims/"
      action-label="去看看内战"
    />
  </PersonalSessionLayout>
</template>
