// Colour mode (design 13.2.1, v5.1): 跟随系统 by default; 浅色 or 深色 picked
// in the masthead is kept in this browser. Runs in <head>, so the page paints
// in the chosen mode at once; the stylesheet reads data-theme on <html>.
// The menu component reads and writes window.owTheme (12-architecture 6.6).
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
    announce();
  }

  function current() {
    return root.getAttribute("data-theme") || "system";
  }

  function announce() {
    document.dispatchEvent(new CustomEvent("owthemechange"));
  }

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

  function paintNow(choice) {
    apply(choice);
    paintBar();
  }

  // The whole page cross-fades into the new mode (design 13.2.4, v6.4); at
  // once when the browser cannot or the visitor asked for less motion.
  function switchTo(choice) {
    var still =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!document.startViewTransition || still) {
      paintNow(choice);
      return;
    }
    root.classList.add("is-theme-switch");
    var transition = document.startViewTransition(function () {
      paintNow(choice);
    });
    var done = function () {
      root.classList.remove("is-theme-switch");
    };
    transition.finished.then(done, done);
  }

  apply(stored());

  window.owTheme = {
    current: current,
    set: function (choice) {
      try {
        if (choice === "system") {
          window.localStorage.removeItem(KEY);
        } else {
          window.localStorage.setItem(KEY, choice);
        }
      } catch (error) {
        // Private mode: the choice holds for this page only.
      }
      switchTo(choice);
    },
  };

  // Another tab changed it.
  window.addEventListener("storage", function (event) {
    if (event.key === KEY) {
      apply(event.newValue);
      paintBar();
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    paintBar();
    // Under 跟随系统 the page follows the system as it changes; the bar too.
    if (window.matchMedia) {
      var query = window.matchMedia("(prefers-color-scheme: dark)");
      if (query.addEventListener) {
        query.addEventListener("change", paintBar);
      }
    }
  });
})();
