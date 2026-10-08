import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  define: { __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: "true" },
  build: { ssrManifest: true, target: "es2020", cssCodeSplit: true },
});
