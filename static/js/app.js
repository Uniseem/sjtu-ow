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

  function relativeTime(iso) {
    var target = new Date(iso).getTime();
    if (isNaN(target)) {
      return "";
    }
    var minutes = Math.round((target - Date.now()) / 60000);
    var ahead = minutes >= 0;
    var value = Math.abs(minutes);
    var text;
    if (value < 1) {
      return "现在";
    }
    if (value < 60) {
      text = value + " 分钟";
    } else if (value < 60 * 24) {
      text = Math.round(value / 60) + " 小时";
    } else {
      text = Math.round(value / (60 * 24)) + " 天";
    }
    return ahead ? text + "后" : text + "前";
  }

  function paintRelativeTimes(root) {
    var nodes = (root || document).querySelectorAll("time[data-relative]");
    for (var i = 0; i < nodes.length; i += 1) {
      var node = nodes[i];
      var text = relativeTime(node.getAttribute("datetime"));
      if (text) {
        if (!node.title) {
          node.title = node.textContent.trim();
        }
        node.textContent = text;
      }
    }
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy]");
    if (!button || !navigator.clipboard) {
      return;
    }
    navigator.clipboard.writeText(button.getAttribute("data-copy")).then(function () {
      var original = button.textContent;
      button.textContent = "已复制";
      window.setTimeout(function () {
        button.textContent = original;
      }, 1500);
    });
  });

  paintRelativeTimes(document);
  document.body.addEventListener("htmx:afterSwap", function (event) {
    paintRelativeTimes(event.target);
  });
  window.setInterval(function () {
    paintRelativeTimes(document);
  }, 60000);

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
