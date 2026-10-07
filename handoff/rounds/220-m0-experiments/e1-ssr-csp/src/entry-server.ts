import { renderSSRHead } from "@unhead/vue/server";
import { renderToString } from "vue/server-renderer";
import { createApp } from "./main";

const API = process.env.API_BASE ?? "http://127.0.0.1:5173";

export async function render(url: string) {
  const { app, router, head, holder } = createApp(true);
  await router.push(url);
  await router.isReady();
  const route = router.currentRoute.value;
  if (!route.matched.length) return { status: 404, html: "<h1>404</h1>", head: "", state: null };
  // The route's loader runs before the page is drawn (12-architecture 6.3).
  holder.data = await (route.meta.load as any)(route.params, API);
  const html = await renderToString(app);
  const { headTags, htmlAttrs } = await renderSSRHead(head);
  return { status: 200, html, head: headTags, htmlAttrs, state: { url, data: holder.data } };
}
