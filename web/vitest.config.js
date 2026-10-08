import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["styles.test.mjs"],
  },
});
