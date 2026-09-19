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
