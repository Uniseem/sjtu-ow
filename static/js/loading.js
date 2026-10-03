// The next page is on its way (design 13.2.4, v6.4): show the masthead's
// loading bar from a click on a link to another page of this site, or a
// form that leaves the page, until the browser replaces the page. On the
// way out it notes where the bar got to, and arrival.js on the next page
// runs it to the end from there (v6.6).
(function () {
  "use strict";
  var KEY = "ow-loading";
  var SHOWN_AFTER = 150; // ms, the bar's delay in the stylesheet
  var root = document.documentElement;
  var timer = null;
  var shown = null;

  function note(value) {
    try {
      if (value) {
        window.sessionStorage.setItem(KEY, JSON.stringify(value));
      } else {
        window.sessionStorage.removeItem(KEY);
      }
    } catch (error) {
      // Storage switched off: the next page simply has no bar to finish.
    }
  }

  function noted() {
    try {
      return JSON.parse(window.sessionStorage.getItem(KEY) || "null");
    } catch (error) {
      return null;
    }
  }

  function stop() {
    root.classList.remove("is-loading");
    window.clearTimeout(timer);
    window.clearTimeout(shown);
    note(null);
  }

  function start() {
    root.classList.remove("is-arriving");
    root.classList.add("is-loading");
    window.clearTimeout(timer);
    window.clearTimeout(shown);
    note(null);
    // Only a bar the visitor has seen is finished on the next page; a page
    // that comes within the delay never shows one.
    shown = window.setTimeout(function () {
      note({ at: Date.now(), from: 0 });
    }, SHOWN_AFTER);
    // A download or a cancelled navigation leaves this page in place.
    timer = window.setTimeout(stop, 15000);
  }

  // How far the bar has got: the x scale of its transform.
  function progress() {
    var bar = document.querySelector(".c-loadbar");
    var matrix = bar && window.getComputedStyle(bar).transform;
    var parts = /^matrix\(([^,]+),/.exec(matrix || "");
    return parts ? Number(parts[1]) : 0;
  }

  function leaves(url) {
    if (url.origin !== window.location.origin) {
      return false; // other sites keep the browser's own behaviour
    }
    // An anchor on this same page only scrolls.
    return (
      url.pathname !== window.location.pathname ||
      url.search !== window.location.search
    );
  }

  document.addEventListener("click", function (event) {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    var link = event.target.closest && event.target.closest("a[href]");
    if (
      !link ||
      link.target ||
      link.hasAttribute("download") ||
      link.hasAttribute("data-no-loading")
    ) {
      return;
    }
    if (leaves(new URL(link.href, window.location.href))) {
      start();
    }
  });

  document.addEventListener("submit", function (event) {
    var form = event.target;
    // HTMX forms swap part of the page and never leave it.
    if (
      event.defaultPrevented ||
      form.target ||
      form.hasAttribute("hx-post") ||
      form.hasAttribute("hx-get") ||
      form.hasAttribute("data-no-loading")
    ) {
      return;
    }
    start();
  });

  // Leaving with the bar showing: note where it got to.
  window.addEventListener("pagehide", function () {
    var current = noted();
    if (!root.classList.contains("is-loading") || !current) {
      return;
    }
    current.from = progress();
    note(current);
  });

  // Back to this page from the back-forward cache: it is shown as it was.
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      stop();
    }
  });
})();
