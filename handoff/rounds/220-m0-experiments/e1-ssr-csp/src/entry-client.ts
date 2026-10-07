import { createApp } from "./main";

// Read what the server saw; nothing is requested again for the first page.
const raw = document.getElementById("ow-state")?.textContent ?? "null";
const state = JSON.parse(raw);
const { app, router, holder } = createApp(false, state);
router.isReady().then(() => {
  app.mount("#app");
  document.documentElement.classList.add("js-ready");
});
// Later navigations run the loader in the browser.
router.beforeResolve(async (to, from) => {
  if (!from.matched.length) return; // the first one: the server already did it
  holder.data = await (to.meta.load as any)(to.params, "");
});
