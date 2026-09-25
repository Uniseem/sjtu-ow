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
