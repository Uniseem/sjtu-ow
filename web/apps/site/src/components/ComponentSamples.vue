<script lang="ts">
import { createStaticVNode, defineComponent, h, type Component } from "vue"
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import CPager from "@sjtu-ow/ui/CPager.vue"
import CRank from "@sjtu-ow/ui/CRank.vue"
import CRoleIcon from "@sjtu-ow/ui/CRoleIcon.vue"
import CPlay from "@sjtu-ow/ui/CPlay.vue"
import CProfileGaps from "@sjtu-ow/ui/CProfileGaps.vue"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CRegStatus from "@sjtu-ow/ui/CRegStatus.vue"
import CSeats from "@sjtu-ow/ui/CSeats.vue"
import CPagehead from "@sjtu-ow/ui/CPagehead.vue"
import PostCard from "@sjtu-ow/ui/PostCard.vue"
import TeamTile from "@sjtu-ow/ui/TeamTile.vue"
import CTournamentCard from "@sjtu-ow/ui/CTournamentCard.vue"
import CScrimRow from "@sjtu-ow/ui/CScrimRow.vue"
import CStartsAt from "@sjtu-ow/ui/CStartsAt.vue"
import CTeamLogo from "@sjtu-ow/ui/CTeamLogo.vue"
import AuthWhy from "@sjtu-ow/ui/AuthWhy.vue"
import AuthBack from "@sjtu-ow/ui/AuthBack.vue"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import MeLayout from "@sjtu-ow/ui/MeLayout.vue"
import primitiveCases from "../testdata/legacy-ui.json"
import cardCases from "../testdata/legacy-cards.json"

type Case = { component: string; props: Record<string, unknown>; control?: string; help?: string }
const components: Record<string, Component> = { CAvatar, CEmpty, CField, CPager, CRank, CRoleIcon, CPlay, CProfileGaps, CStatus, CRegStatus, CSeats, CPagehead, PostCard, TeamTile, CTournamentCard, CScrimRow, CStartsAt, CTeamLogo, AuthWhy, AuthBack, AuthLayout, MeLayout }
// The specimen and the old-template oracle use the same fixed input, rather
// than another handwritten approximation of the component markup.
export default defineComponent({
  props: { imageId: Number },
  setup(props) {
    const cases: Case[] = [...primitiveCases, ...cardCases]
    return () => h("div", { class: "flex flex-col gap-16", "data-component-samples": "" }, [...cases.map((sample, index) =>
      h("section", { "data-sample": index }, [
        h("h2", { class: "mb-4" }, `${sample.component} ${index + 1}`),
        h('div', sample.component === 'CPagehead' ? { class: 'c-pagehead c-pagehead--picture' } : {}, [h(components[sample.component], sample.props, sample.control ? {
          // Only static repository-owned sample controls, never user content.
          default: () => createStaticVNode(sample.control!, 1),
          ...(sample.help ? { help: () => sample.help } : {}),
        } : undefined)]),
      ]),
    ), ...(props.imageId ? [h("section", { "data-real-image-sample": "" }, [
      h("h2", "真实图片"),
      h(CAvatar, { person: { id: 7, nickname: "小满", avatar_image_id: props.imageId }, size: "lg" }),
      h(PostCard, { article: { id: 37, slug: "weekend", title: "真实封面", cover_image_id: props.imageId } }),
      h(CTeamLogo, { team: { id: 7, name: "思源", logo_image_id: props.imageId } }),
    ]), h("section", { "data-default-image-sample": "" }, [
      h("h2", "默认图片池"),
      h(CAvatar, { person: { id: 7, nickname: "小满", default_avatar_image_id: props.imageId }, size: "lg" }),
      h(PostCard, { article: { id: 37, slug: "weekend", title: "默认封面池", default_cover_image_id: props.imageId } }),
    ])] : [])])
  },
})
</script>
