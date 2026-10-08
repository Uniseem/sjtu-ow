import { readFileSync } from "node:fs";
import { test } from "vitest";
import assert from "node:assert/strict";

const css = readFileSync(new URL("./packages/styles/input.css", import.meta.url), "utf8");
const compiled = readFileSync(new URL("./packages/styles/dist/site.css", import.meta.url), "utf8");

const HEX = /--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g;
const DARK_HEAD = ":root {\n  @variant dark {";

function light(text) {
  const block = text.match(/@theme \{(.*?)\n\}/s);
  assert.ok(block, "input.css 没有 @theme");
  return Object.fromEntries([...block[1].matchAll(HEX)].map((m) => [m[1], m[2]]));
}

function darkBlock(text) {
  const start = text.indexOf(DARK_HEAD);
  assert.ok(start >= 0, "没有深色变体块");
  const rest = text.slice(start);
  const end = rest.indexOf("\n}\n");
  assert.ok(end > 0);
  return rest.slice(0, end);
}

test("only our palette exists", () => {
  assert.ok(css.includes("--color-*: initial;"));
  assert.equal(compiled.includes("--color-orange-500"), false);
  assert.ok(compiled.replaceAll(" ", "").includes("--color-primary:#9b3a33"));
});

test("every palette colour has a dark value", () => {
  const values = light(css);
  const fixed = new Set(["white", "black", ...Object.keys(values).filter((name) => name.startsWith("night"))]);
  const dark = new Set([...darkBlock(css).matchAll(HEX)].map((m) => m[1]));
  const missing = [...Object.keys(values)].filter((name) => !fixed.has(name) && !dark.has(name));
  assert.deepEqual(missing, []);
});

test("dark values follow the visitor or the system, not a raw media query", () => {
  assert.equal(css.split("prefers-color-scheme").length - 1, 1);
  assert.ok(css.indexOf("@custom-variant dark {") < css.indexOf("prefers-color-scheme"));
  const flat = compiled.replace(/[\s"]/g, "");
  const darkBg = "{color-scheme:dark;--color-bg:#141a24;";
  const system = "(?::root|&):not\\(\\[data-theme=light\\],\\[data-theme=light\\]\\*\\)";
  const chosen = "(?::root|&):is\\(\\[data-theme=dark\\],\\[data-theme=dark\\]\\*\\)";
  assert.match(flat, new RegExp("@media\\(prefers-color-scheme:dark\\)\\{" + system + darkBg));
  assert.match(flat, new RegExp(chosen + darkBg));
});

test("decorative images use the fixed /static/img addresses", () => {
  assert.equal(css.includes('url("../img/'), false);
  assert.ok(compiled.includes("/static/img/placeholders/ridge.svg"));
});

test("specimen colour chips are real utilities", () => {
  // These class names live in specimen.ts and are bound with :class.
  // A scan that only sees .vue files drops them, and the chip stays transparent.
  for (const name of ["bg-bg", "bg-surface", "bg-primary-hover", "bg-night-fg", "bg-on-accent-soft"]) {
    assert.match(compiled, new RegExp(`\\.${name}\\{`));
  }
});

test("the stylesheet does not load daisyUI", () => {
  assert.equal(css.includes("daisyui"), false);
  const flat = compiled.replaceAll(" ", "");
  assert.equal(flat.includes(".btn{"), false);
  assert.equal(compiled.includes("--color-base-100"), false);
});
