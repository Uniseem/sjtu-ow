<script setup lang="ts">
import { useRouter } from "vue-router"

// A link that goes through the router when the address is one of our pages
// and falls back to a full page load while the route table is still being
// filled in. Both sides resolve the same table, so SSR and the browser
// paint the same <a>. `current` (aria-current) is decided by the caller —
// the masthead nav uses sectionOf().
const props = defineProps<{ to: string; current?: boolean }>()
const router = useRouter()

function plain(event: MouseEvent) {
  return (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  )
}

function onClick(event: MouseEvent) {
  if (plain(event)) return
  if (!router.resolve(props.to).matched.length) return
  event.preventDefault()
  router.push(props.to)
}
</script>
<template>
  <a :href="to" :aria-current="current ? 'page' : undefined" @click="onClick"><slot /></a>
</template>
