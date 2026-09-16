// Live preview for the typography settings page (design 13.12.3).
// Reads every region form and writes CSS variables on the preview box.
(function () {
  "use strict";

  var SANS = "var(--font-fallback)";
  var MONO = "var(--font-mono-fallback)";

  function start() {
    var preview = document.getElementById("typography-preview");
    var form = document.getElementById("typography-form");
    var dataNode = document.getElementById("font-weights-data");
    if (!preview || !form || !dataNode) {
      return;
    }

    var fonts = {};
    try {
      fonts = JSON.parse(dataNode.textContent || "{}");
    } catch (error) {
      fonts = {};
    }

    function field(row, name) {
      return row.querySelector('[name$="-' + name + '"]');
    }

    function value(row, name) {
      var element = field(row, name);
      return element ? element.value.trim() : "";
    }

    function familyValue(row, mode, varName) {
      var fallback = varName === "code" ? MONO : SANS;
      if (mode === "custom") {
        var entry = fonts[value(row, "family")];
        return entry ? '"' + entry.css_name + '", ' + fallback : fallback;
      }
      if (mode === "inherit") {
        return "var(--font-body)";
      }
      return fallback;
    }

    function limitWeights(row, mode) {
      var select = field(row, "weight");
      if (!select) {
        return;
      }
      var entry = mode === "custom" ? fonts[value(row, "family")] : null;
      Array.prototype.forEach.call(select.options, function (option) {
        if (!option.value) {
          return;
        }
        var weight = parseInt(option.value, 10);
        var allowed = !entry || entry.weights.indexOf(weight) !== -1;
        option.disabled = !allowed;
        option.hidden = !allowed;
      });
    }

    function setOrClear(style, name, newValue) {
      if (newValue) {
        style.setProperty(name, newValue);
      } else {
        style.removeProperty(name);
      }
    }

    function apply() {
      var style = preview.style;
      Array.prototype.forEach.call(
        form.querySelectorAll(".typography-row"),
        function (row) {
          var name = row.getAttribute("data-var");
          var mode = value(row, "mode");
          var size = value(row, "size_rem");
          var spacing = value(row, "letter_spacing_em");
          style.setProperty("--font-" + name, familyValue(row, mode, name));
          setOrClear(style, "--font-" + name + "-weight", value(row, "weight"));
          setOrClear(style, "--font-" + name + "-size", size ? size + "rem" : "");
          setOrClear(
            style,
            "--font-" + name + "-line-height",
            value(row, "line_height")
          );
          setOrClear(
            style,
            "--font-" + name + "-letter-spacing",
            spacing ? spacing + "em" : ""
          );
          limitWeights(row, mode);
        }
      );
    }

    form.addEventListener("change", apply);
    form.addEventListener("input", apply);
    apply();
  }

  // Wagtail renders extra_js near the top of <body>, before the form exists.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
