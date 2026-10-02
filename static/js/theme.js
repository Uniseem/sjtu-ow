// Colour mode (design 13.2.1, v5.1): 跟随系统 by default; 浅色 or 深色 picked
// in the masthead is kept in this browser. Runs in <head>, so the page paints
// in the chosen mode at once; the stylesheet reads data-theme on <html>.
(function () {
  "use strict";
  var KEY = "ow-theme";
  var root = document.documentElement;

  function stored() {
    try {
      return window.localStorage.getItem(KEY);
    } catch (error) {
      return null;
    }
  }

  function apply(choice) {
    if (choice === "light" || choice === "dark") {
      root.setAttribute("data-theme", choice);
    } else {
      root.removeAttribute("data-theme");
    }
  }

  apply(stored());

  // Another tab changed it.
  window.addEventListener("storage", function (event) {
    if (event.key === KEY) {
      apply(event.newValue);
      mark();
    }
  });

  // The masthead menu and, on phones, the row in the drawer.
  var menus = [];

  // The browser bar takes the masthead's colour, whichever mode is in use.
  function paintBar() {
    var bar = document.querySelector(".c-masthead");
    if (!bar) {
      return;
    }
    var colour = window.getComputedStyle(bar).backgroundColor;
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    for (var i = 0; i < metas.length; i += 1) {
      metas[i].setAttribute("content", colour);
    }
  }

  function mark() {
    var current = root.getAttribute("data-theme") || "system";
    for (var m = 0; m < menus.length; m += 1) {
      var buttons = menus[m].querySelectorAll("[data-theme-choice]");
      for (var i = 0; i < buttons.length; i += 1) {
        var on = buttons[i].getAttribute("data-theme-choice") === current;
        buttons[i].setAttribute("aria-pressed", on ? "true" : "false");
      }
    }
    paintBar();
  }

  function choose(event) {
    var button = event.target.closest("[data-theme-choice]");
    if (!button) {
      return;
    }
    var choice = button.getAttribute("data-theme-choice");
    try {
      if (choice === "system") {
        window.localStorage.removeItem(KEY);
      } else {
        window.localStorage.setItem(KEY, choice);
      }
    } catch (error) {
      // Private mode: the choice holds for this page only.
    }
    apply(choice);
    mark();
    // The masthead menu closes; the drawer stays open to show the change.
    if (event.currentTarget.tagName === "DETAILS") {
      event.currentTarget.open = false;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    menus = document.querySelectorAll("[data-theme-menu]");
    for (var i = 0; i < menus.length; i += 1) {
      menus[i].hidden = false;
      menus[i].addEventListener("click", choose);
    }
    mark();
    // Under 跟随系统 the page follows the system as it changes; the bar too.
    if (window.matchMedia) {
      var query = window.matchMedia("(prefers-color-scheme: dark)");
      if (query.addEventListener) {
        query.addEventListener("change", paintBar);
      } else if (query.addListener) {
        query.addListener(paintBar);
      }
    }
  });
})();
