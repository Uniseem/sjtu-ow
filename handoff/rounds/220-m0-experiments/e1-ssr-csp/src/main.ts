import { createHead } from "@unhead/vue/client";
import { createHead as createServerHead } from "@unhead/vue/server";
import { createSSRApp, h } from "vue";
import { RouterView, createMemoryHistory, createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import { getHome, getTeam } from "./api";
import Home from "./pages/Home.vue";
import Team from "./pages/Team.vue";
import "./style.css";

export interface Loaded { [route: string]: unknown }

export const routes = [
  { path: "/", component: Home, meta: { load: (_p: Record<string, string>, base: string) => getHome(base) } },
  { path: "/teams/:id(\\d{1,18})/", component: Team, meta: { load: (p: Record<string, string>, base: string) => getTeam(p.id, base) } },
];

// One app per request on the server, one for the page in the browser.
export function createApp(server: boolean, state?: { data: unknown }) {
  const router = createRouter({ history: server ? createMemoryHistory() : createWebHistory(), routes });
  const holder = { data: state?.data };
  const Page = {
    setup() {
      return () => h(App, null, { default: () => h(RouterView, null, { default: ({ Component }: any) => h(Component, { data: holder.data }) }) });
    },
  };
  const app = createSSRApp(Page);
  const head = server ? createServerHead() : createHead();
  app.use(router).use(head);
  return { app, router, head, holder };
}
