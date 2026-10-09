import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  define: { __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: "true" },
  // manifest.json（块依赖图：入口、css、预加载）是 server.ts 拼页面用的
  build: { manifest: true, target: "es2020", cssCodeSplit: true },
  ssr: { noExternal: true },
});
