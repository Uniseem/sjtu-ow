// The next page is on its way (design 13.2.4, v6.4): show the masthead's
// loading bar from a click on a link to another page of this site, or a
// form that leaves the page, until the browser replaces the page.
(function () {
  "use strict";
  var root = document.documentElement;
  var timer = null;

  function stop() {
    root.classList.remove("is-loading");
    window.clearTimeout(timer);
  }

  function start() {
    root.classList.add("is-loading");
    window.clearTimeout(timer);
    // A download or a cancelled navigation leaves this page in place.
    timer = window.setTimeout(stop, 15000);
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

  // Back to this page from the back-forward cache: it is shown as it was.
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      stop();
    }
  });
})();
