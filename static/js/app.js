(function () {
  "use strict";

  function readCookie(name) {
    var prefix = name + "=";
    var parts = document.cookie.split(";");
    for (var i = 0; i < parts.length; i += 1) {
      var part = parts[i].trim();
      if (part.indexOf(prefix) === 0) {
        return decodeURIComponent(part.slice(prefix.length));
      }
    }
    return "";
  }

  // WeChat may block or warn on this unregistered overseas domain (design 16.9).
  if (/MicroMessenger/i.test(navigator.userAgent)) {
    var wechatHint = document.getElementById("wechat-hint");
    if (wechatHint) {
      wechatHint.hidden = false;
    }
  }

  // Scrolling tab strips (c-tabs) open on the current item, so on a phone the
  // account centre's 「账号安全」 is not hidden past the right edge.
  var strips = document.querySelectorAll(".c-tabs");
  for (var s = 0; s < strips.length; s += 1) {
    var current = strips[s].querySelector('[aria-current="page"], [aria-current="true"]');
    if (current && strips[s].scrollWidth > strips[s].clientWidth) {
      strips[s].scrollLeft = current.offsetLeft - strips[s].offsetLeft - 16;
    }
  }

  // The masthead's <details> dropdowns (design 13.2.6, v6.65): a click
  // outside, Esc, or opening another one closes them, so only one is ever
  // open. They still open and close by their own button without this. The
  // account menu is swapped in after load, hence one listener on document.
  var DROPDOWNS = "details.c-menu, details.c-theme, details.c-drawer";

  function closeDropdowns(except) {
    var open = document.querySelectorAll(DROPDOWNS);
    for (var d = 0; d < open.length; d += 1) {
      if (open[d] !== except && open[d].open) {
        open[d].open = false;
      }
    }
  }

  // "toggle" does not bubble, but a capturing listener still sees it.
  document.addEventListener(
    "toggle",
    function (event) {
      var target = event.target;
      if (target.matches && target.matches(DROPDOWNS) && target.open) {
        closeDropdowns(target);
      }
    },
    true
  );

  document.addEventListener("click", function (event) {
    var inside = event.target.closest && event.target.closest(DROPDOWNS);
    closeDropdowns(inside);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") {
      return;
    }
    var open = document.querySelector(
      "details.c-menu[open], details.c-theme[open], details.c-drawer[open]"
    );
    if (open) {
      open.open = false;
      var summary = open.querySelector("summary");
      if (summary) {
        summary.focus();
      }
    }
  });

  // Forms that delete, cancel or email people ask first (round 115). Inline
  // onsubmit is blocked by the site's CSP, so the question lives in the
  // form's data-confirm; HTMX forms use hx-confirm instead.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    var question = form && form.getAttribute && form.getAttribute("data-confirm");
    if (question && !window.confirm(question)) {
      event.preventDefault();
    }
  });

  if (window.htmx) {
    window.htmx.config.allowEval = false;
    window.htmx.config.includeIndicatorStyles = false;
    document.body.addEventListener("htmx:configRequest", function (event) {
      var token = readCookie("csrftoken");
      if (token) {
        event.detail.headers["X-CSRFToken"] = token;
      }
    });
  }
})();
