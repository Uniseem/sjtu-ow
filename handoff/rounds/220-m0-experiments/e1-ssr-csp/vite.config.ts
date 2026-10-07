import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  // Say what a hydration mismatch is even in the production build, so the
  // experiment can see one (the default is a silent patch-up).
  define: { __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: "true" },
  build: { ssrManifest: true, target: "es2020", cssCodeSplit: true },
});
