// Fill personalised slots on prerendered pages (design 13.13.3).
// Runs in <head>: no cookies means no request at all.
(function () {
  "use strict";
  var d = document;
  function has(name) {
    return d.cookie.indexOf(name + "=1") !== -1;
  }
  if (!has("ow_logged_in") && !has("ow_flash")) {
    return;
  }
  d.documentElement.className += " ow-state-pending";
  d.addEventListener("DOMContentLoaded", function () {
    // Django rendered this page for the signed-in visitor, so the slots are
    // already correct; only prerendered pages need the request.
    if (d.body.getAttribute("data-state-filled") === "1") {
      d.documentElement.className = d.documentElement.className.replace(
        " ow-state-pending",
        ""
      );
      return;
    }
    var names = [];
    var nodes = d.querySelectorAll("[data-slot]");
    for (var i = 0; i < nodes.length; i += 1) {
      names.push(nodes[i].getAttribute("data-slot"));
    }
    var url = "/_fragments/state/?slots=" + encodeURIComponent(names.join(","));
    function fill() {
      if (!window.htmx) {
        return;
      }
      window.htmx
        .ajax("GET", url, { source: d.body, swap: "none" })
        .then(function () {
          d.documentElement.className = d.documentElement.className.replace(
            " ow-state-pending",
            ""
          );
        });
    }
    if (window.htmx) {
      fill();
    } else {
      d.addEventListener("htmx:load", fill, { once: true });
      window.setTimeout(fill, 300);
    }
  });
})();
