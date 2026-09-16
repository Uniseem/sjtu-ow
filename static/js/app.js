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
