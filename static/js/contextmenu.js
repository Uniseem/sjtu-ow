// The site's own right-click menu (design 13.2.6 c-ctxmenu, v6.65).
//
// The browser's menu stays where it is needed: Shift + right click, inside
// form fields and editable areas (paste, spell check), on touch screens
// (long press), and in the admin, which does not load this file. Without
// the script the browser's menu is all there is.
(function () {
  "use strict";

  if (!window.matchMedia || !window.matchMedia("(pointer: fine)").matches) {
    return;
  }

  var NATIVE = "input, textarea, select, [contenteditable=''], [contenteditable='true'], [data-native-contextmenu]";
  var menu = null;
  var opener = null;

  function close() {
    if (menu) {
      menu.remove();
      menu = null;
    }
    if (opener && opener.focus) {
      opener.focus({ preventScroll: true });
    }
    opener = null;
  }

  function toast(text, x, y) {
    var note = document.createElement("div");
    note.className = "c-ctxmenu-toast";
    note.setAttribute("role", "status");
    note.textContent = text;
    note.style.left = x + 12 + "px";
    note.style.top = y + 12 + "px";
    document.body.appendChild(note);
    window.setTimeout(function () {
      note.remove();
    }, 1400);
  }

  function copy(text, x, y) {
    function done() {
      toast("已复制", x, y);
    }
    function fallback() {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand("copy");
        done();
      } catch (error) {
        toast("复制失败", x, y);
      }
      area.remove();
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else {
      fallback();
    }
  }

  function shorten(text, most) {
    text = text.replace(/\s+/g, " ").trim();
    return text.length > most ? text.slice(0, most) + "…" : text;
  }

  // What to offer where the click landed: groups of [label, action, hint].
  function entries(target, x, y) {
    var groups = [];
    var link = target.closest("a[href]");
    var href = link && link.href;
    if (href && !/^javascript:/i.test(link.getAttribute("href"))) {
      groups.push([
        ["在新标签页打开", function () { window.open(href, "_blank", "noopener"); }],
        ["复制链接", function () { copy(href, x, y); }],
      ]);
    }
    var image = target.closest("img");
    if (image && (image.currentSrc || image.src)) {
      var src = image.currentSrc || image.src;
      groups.push([
        ["在新标签页打开图片", function () { window.open(src, "_blank", "noopener"); }],
        ["复制图片地址", function () { copy(src, x, y); }],
      ]);
    }
    var selected = window.getSelection ? String(window.getSelection()).trim() : "";
    if (selected) {
      groups.push([
        ["复制", function () { copy(selected, x, y); }, "Ctrl+C"],
        [
          "在站内搜索“" + shorten(selected, 10) + "”",
          function () {
            window.location.href = "/search/?q=" + encodeURIComponent(shorten(selected, 60));
          },
        ],
      ]);
    }
    var page = [
      ["后退", function () { window.history.back(); }, "Alt+←"],
      ["前进", function () { window.history.forward(); }, "Alt+→"],
      ["刷新", function () { window.location.reload(); }, "F5"],
    ];
    groups.push(page);
    var more = [["复制本页链接", function () { copy(window.location.href, x, y); }]];
    if (window.scrollY > 0) {
      var calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      more.push(["回到顶部", function () { window.scrollTo({ top: 0, behavior: calm ? "auto" : "smooth" }); }]);
    }
    groups.push(more);
    return groups;
  }

  function build(groups) {
    var panel = document.createElement("div");
    panel.className = "c-ctxmenu";
    panel.setAttribute("role", "menu");
    panel.setAttribute("aria-label", "右键菜单");
    groups.forEach(function (group, index) {
      if (index > 0) {
        var line = document.createElement("hr");
        line.setAttribute("role", "separator");
        panel.appendChild(line);
      }
      group.forEach(function (entry) {
        var item = document.createElement("button");
        item.type = "button";
        item.className = "c-ctxmenu__item";
        item.setAttribute("role", "menuitem");
        item.tabIndex = -1;
        var label = document.createElement("span");
        label.textContent = entry[0];
        item.appendChild(label);
        if (entry[2]) {
          var hint = document.createElement("kbd");
          hint.textContent = entry[2];
          item.appendChild(hint);
        }
        item.addEventListener("click", function () {
          var action = entry[1];
          close();
          action();
        });
        panel.appendChild(item);
      });
    });
    var foot = document.createElement("p");
    foot.className = "c-ctxmenu__foot";
    foot.textContent = "按住 Shift 再右键：浏览器自带的菜单";
    panel.appendChild(foot);
    return panel;
  }

  function place(panel, x, y) {
    var gap = 8;
    var width = panel.offsetWidth;
    var height = panel.offsetHeight;
    var left = Math.min(x, window.innerWidth - width - gap);
    var top = y + height + gap > window.innerHeight ? y - height : y;
    panel.style.left = Math.max(gap, left) + "px";
    panel.style.top = Math.max(gap, top) + "px";
  }

  function items() {
    return menu ? Array.prototype.slice.call(menu.querySelectorAll(".c-ctxmenu__item")) : [];
  }

  document.addEventListener("contextmenu", function (event) {
    var target = event.target;
    var touch = event.pointerType === "touch" || event.pointerType === "pen";
    if (event.shiftKey || touch || !target.closest || target.closest(NATIVE)) {
      close();
      return;
    }
    if (target.closest(".c-ctxmenu")) {
      event.preventDefault();
      return;
    }
    event.preventDefault();
    close();
    var x = event.clientX;
    var y = event.clientY;
    if (!x && !y) {
      // The keyboard's menu key: open by the focused element.
      var box = target.getBoundingClientRect();
      x = box.left + 8;
      y = box.bottom;
    }
    opener = document.activeElement;
    menu = build(entries(target, x, y));
    document.body.appendChild(menu);
    place(menu, x, y);
    var first = items()[0];
    if (first) {
      first.focus({ preventScroll: true });
    }
  });

  document.addEventListener("keydown", function (event) {
    if (!menu) {
      return;
    }
    var list = items();
    var at = list.indexOf(document.activeElement);
    if (event.key === "Escape" || event.key === "Tab") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      list[(at + 1) % list.length].focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      list[(at - 1 + list.length) % list.length].focus();
    } else if (event.key === "Home") {
      event.preventDefault();
      list[0].focus();
    } else if (event.key === "End") {
      event.preventDefault();
      list[list.length - 1].focus();
    }
  });

  document.addEventListener(
    "pointerdown",
    function (event) {
      if (menu && !menu.contains(event.target)) {
        opener = null;
        close();
      }
    },
    true
  );
  window.addEventListener("scroll", function () { opener = null; close(); }, true);
  window.addEventListener("resize", close);
  window.addEventListener("blur", function () { opener = null; close(); });
  document.addEventListener("htmx:beforeRequest", close);
})();
