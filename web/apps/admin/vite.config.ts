import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  base: "/admin/",
  build: {
    target: "es2022",
    manifest: true,
    cssCodeSplit: true,
  },
})
