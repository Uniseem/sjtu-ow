import { defaultKeymap, history, historyKeymap, undo } from "@codemirror/commands";
import { markdown } from "@codemirror/lang-markdown";
import { defaultHighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";

const doc = "## 标题\n\n这是**正文**，可以输入中文。\n\n> 引用——出处\n";

// CodeMirror's style-mod writes a <style> element into a Document root, which
// `style-src 'self'` blocks. Into a ShadowRoot it uses a constructable
// stylesheet instead, which the policy does not touch.
const host = document.getElementById("editor")!;
const shadow = location.search.includes("shadow") ? host.attachShadow({ mode: "open" }) : null;
const root: Document | ShadowRoot = shadow ?? document;

const view = new EditorView({
  root,
  parent: shadow ?? host,
  state: EditorState.create({
    doc,
    extensions: [
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      markdown(),
      syntaxHighlighting(defaultHighlightStyle),
      EditorView.lineWrapping,
      EditorView.theme({ "&": { minHeight: "14rem" }, ".cm-content": { fontFamily: "ui-monospace, monospace" } }),
      EditorView.updateListener.of((u) => {
        if (u.docChanged) document.getElementById("status")!.textContent = `${u.state.doc.length} 字`;
      }),
    ],
  }),
});

function wrap(left: string, right = left) {
  const { from, to } = view.state.selection.main;
  const text = view.state.sliceDoc(from, to);
  view.dispatch({ changes: { from, to, insert: left + text + right }, selection: { anchor: from + left.length, head: from + left.length + text.length } });
  view.focus();
}
function prefixLine(prefix: string) {
  const line = view.state.doc.lineAt(view.state.selection.main.head);
  view.dispatch({ changes: { from: line.from, insert: prefix } });
  view.focus();
}
document.querySelector(".bar")!.addEventListener("click", (event) => {
  const act = (event.target as HTMLElement).dataset.act;
  if (act === "bold") wrap("**");
  if (act === "h2") prefixLine("## ");
  if (act === "quote") prefixLine("> ");
  if (act === "undo") undo(view);
});
(window as any).__view = view; // for the check script
(window as any).__root = root;
