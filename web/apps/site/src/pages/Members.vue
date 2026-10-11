<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiMembers } from "@sjtu-ow/api"
export async function load(ctx: LoadCtx) {
  const roster = await getApiMembers(ctx.api, { role: ctx.query.role || undefined, free: ctx.query.free === "1" })
  return { title: "成员", roster }
}
</script>
<script setup lang="ts">
import { inject, onMounted, ref } from "vue"
import { useHead } from "@unhead/vue"
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import CPlay from "@sjtu-ow/ui/CPlay.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import MemberCard from "../components/MemberCard.vue"
import CPagehead from "@sjtu-ow/ui/CPagehead.vue"
import { requirePageData } from "../personal"
import { memberAvatar, memberPlay, memberTags, memberFilter, TEAM_ROLES, type MemberList } from "../member-domain"
const data = requirePageData(inject<{ roster: MemberList }>("page-data"))
useHead({ title: "成员 · SJTU-OW" })
const filterStrip = ref<HTMLElement | null>(null)
onMounted(() => {
  const strip = filterStrip.value
  const current = strip?.querySelector<HTMLElement>('[aria-current="page"], [aria-current="true"]')
  if (!strip || !current || strip.scrollWidth <= strip.clientWidth) return
  // Match the legacy tab strip: start on the selected filter on narrow
  // screens. The browser clamps the position to the actual content width.
  strip.scrollLeft += current.getBoundingClientRect().left - strip.getBoundingClientRect().left
})
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead c-pagehead--picture">
      <CPagehead section="members" :image-id="data.roster.banner_image_id" />
      <div class="l-container">
        <h1>成员展示</h1>
        <p class="c-pagehead__meta"><span>共 <span class="font-numeric">{{ data.roster.total }}</span> 位成员</span></p>
      </div>
    </header>
    <div class="l-container pt-10 pb-16 lg:pt-14 lg:pb-24">
      <nav class="c-tabs" aria-label="成员分组">
        <a v-for="section in data.roster.sections" :key="section.id" :href="'#group-' + section.id">{{ section.name }}<span class="c-tabs__count">{{ section.entries.length }}</span></a>
        <a href="#all-members">全部成员<span class="c-tabs__count">{{ data.roster.total }}</span></a>
      </nav>
      <div class="mt-12 flex flex-col gap-16">
        <template v-if="!data.roster.filtering">
          <section v-for="section in data.roster.sections" :id="'group-' + section.id" :key="section.id" class="c-group scroll-mt-6" data-member-group :aria-labelledby="'group-title-' + section.id">
            <div class="c-group__head">
              <SectionHead :title="section.name" :heading-id="'group-title-' + section.id" />
              <p v-if="section.description" class="c-group__about">{{ section.description }}</p>
            </div>
            <ul v-if="section.entries.length" class="c-people">
              <MemberCard v-for="entry in section.entries" :key="entry.member.user_id" :member="entry.member" :titles="entry.titles" />
            </ul>
            <p v-else class="text-fg-2">这个分组暂时没有成员。</p>
          </section>
        </template>
        <section id="all-members" class="c-group scroll-mt-6" aria-labelledby="all-members-title">
          <div class="c-group__head">
            <div class="c-sectionhead"><h2 id="all-members-title">全部成员</h2></div>
            <p class="c-group__about">
              <template v-if="data.roster.filtering">筛出 <span class="font-numeric">{{ data.roster.members.length }}</span> 位（共 <span class="font-numeric">{{ data.roster.total }}</span> 位），</template>
              <template v-else><span class="font-numeric">{{ data.roster.total }}</span> 位成员，</template>按加入先后编号
            </p>
            <nav ref="filterStrip" class="c-tabs mt-4 mb-6" aria-label="按常用位置筛选" data-member-filter>
              <a :href="memberFilter('', data.roster.free)" :aria-current="!data.roster.role ? 'page' : undefined">全部位置</a>
              <a v-for="role in TEAM_ROLES" :key="role.code" :href="memberFilter(role.code, data.roster.free)" :aria-current="data.roster.role === role.code ? 'page' : undefined">{{ role.label }}</a>
              <a :href="memberFilter(data.roster.role, !data.roster.free)" :aria-current="data.roster.free ? 'page' : undefined">只看还没进战队的<template v-if="data.roster.free"> ✕</template></a>
            </nav>
          </div>
          <ol v-if="data.roster.members.length" class="c-roster">
            <li v-for="member in data.roster.members" :key="member.user_id" class="c-roster__item" data-member>
              <CAvatar :person="memberAvatar(member)" size="md" />
              <span class="min-w-0">
                <a :href="'/members/' + member.user_id + '/'" class="c-roster__name c-stretch" :title="member.nickname">{{ member.nickname }}</a>
                <CPlay :profile="memberPlay(member)" compact />
                <span v-if="memberTags(member).length" class="c-roster__groups">
                  <span v-for="(tag, index) in memberTags(member).slice(0, 3)" :key="index" class="c-tag">{{ tag }}</span>
                  <span v-if="memberTags(member).length > 3" class="c-tag">+{{ memberTags(member).length - 3 }}</span>
                </span>
              </span>
              <span class="c-roster__no font-numeric" data-member-number>{{ String(member.number).padStart(3, '0') }}</span>
            </li>
          </ol>
          <p v-else-if="data.roster.filtering" class="text-fg-2" data-member-filter-empty>没有符合条件的成员。</p>
          <p v-else class="text-fg-2">还没有成员。</p>
        </section>
      </div>
    </div>
  </main>
</template>
