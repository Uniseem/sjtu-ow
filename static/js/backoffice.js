// The back office's few behaviours (docs/admin.md 2): the picture dialog,
// select-all, filters that submit themselves, confirmations, and adding a
// row to a list of forms. Everything works without it except the picture
// dialog, which needs it.
(function () {
  "use strict";

  // --- confirmations -----------------------------------------------------------

  document.addEventListener("submit", function (event) {
    var form = event.target;
    var submitter = event.submitter;
    var message =
      (submitter && submitter.getAttribute("data-confirm")) ||
      form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });

  // --- filters that apply as soon as they change ---------------------------------

  document.addEventListener("change", function (event) {
    var control = event.target;
    if (control.hasAttribute && control.hasAttribute("data-autosubmit") && control.form) {
      control.form.submit();
    }
    // 全选: the box names the checkboxes it ticks.
    var group = control.getAttribute && control.getAttribute("data-select-all");
    if (group) {
      var boxes = document.querySelectorAll('input[type="checkbox"][name="' + group + '"]');
      for (var i = 0; i < boxes.length; i += 1) {
        boxes[i].checked = control.checked;
      }
    }
  });

  // --- a row more in a list of forms (member groups) ------------------------------

  document.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest("[data-formset-add]");
    if (!button) {
      return;
    }
    var prefix = button.getAttribute("data-formset-add");
    var template = document.getElementById(prefix + "-template");
    var total = document.getElementById("id_" + prefix + "-TOTAL_FORMS");
    var list = document.getElementById(prefix + "-rows");
    if (!template || !total || !list) {
      return;
    }
    var index = parseInt(total.value, 10) || 0;
    var html = template.innerHTML.replace(/__prefix__/g, String(index));
    list.insertAdjacentHTML("beforeend", html);
    total.value = String(index + 1);
  });

  // --- the picture dialog ---------------------------------------------------------

  var dialog = document.querySelector("[data-image-dialog]");
  var dialogBody = dialog && dialog.querySelector("[data-image-dialog-body]");
  var activePicker = null;

  function load(url, options) {
    if (!dialogBody) {
      return;
    }
    dialogBody.setAttribute("aria-busy", "true");
    window
      .fetch(url, Object.assign({ credentials: "same-origin" }, options || {}))
      .then(function (response) {
        return response.text();
      })
      .then(function (html) {
        dialogBody.innerHTML = html;
        dialogBody.removeAttribute("aria-busy");
        var search = dialogBody.querySelector('input[type="search"]');
        if (search) {
          search.focus();
        }
      })
      .catch(function () {
        dialogBody.innerHTML = '<p class="c-notice c-notice--error">图片没有加载出来，关掉再试一次。</p>';
        dialogBody.removeAttribute("aria-busy");
      });
  }

  function choose(picker, id, title, thumb) {
    var input = picker.querySelector("[data-image-picker-input]");
    input.value = id || "";
    // Autosave (design 13.17) hears a picture chosen or cleared.
    input.dispatchEvent(new Event("change", { bubbles: true }));
    var preview = picker.querySelector("[data-image-picker-preview]");
    preview.innerHTML = "";
    if (thumb) {
      var img = document.createElement("img");
      img.src = thumb;
      img.alt = "";
      preview.appendChild(img);
    }
    picker.querySelector("[data-image-picker-title]").textContent = id ? title : "没有选图片";
    var clear = picker.querySelector("[data-image-picker-clear]");
    if (clear) {
      clear.hidden = !id;
    }
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    var chooseButton = target.closest && target.closest("[data-image-picker-choose]");
    if (chooseButton && dialog) {
      activePicker = chooseButton.closest("[data-image-picker]");
      load(activePicker.getAttribute("data-chooser-url"));
      dialog.showModal();
      return;
    }
    var clearButton = target.closest && target.closest("[data-image-picker-clear]");
    if (clearButton) {
      choose(clearButton.closest("[data-image-picker]"), "", "", "");
      return;
    }
    if (target.closest && target.closest("[data-dialog-close]") && dialog) {
      dialog.close();
      return;
    }
    if (!dialogBody || !dialogBody.contains(target)) {
      return;
    }
    var pick = target.closest("[data-pick-image]");
    if (pick && activePicker) {
      choose(
        activePicker,
        pick.getAttribute("data-pick-image"),
        pick.getAttribute("data-title"),
        pick.getAttribute("data-thumb")
      );
      dialog.close();
      return;
    }
    var link = target.closest("a[data-chooser-nav]");
    if (link) {
      event.preventDefault();
      load(link.href);
    }
  });

  if (dialogBody) {
    dialogBody.addEventListener("submit", function (event) {
      var form = event.target;
      event.preventDefault();
      if (form.method.toLowerCase() === "get") {
        var query = new URLSearchParams(new FormData(form)).toString();
        load(form.action + (form.action.indexOf("?") < 0 ? "?" : "&") + query);
        return;
      }
      // Upload one picture, then take it.
      var status = form.querySelector("[data-upload-status]");
      if (status) {
        status.textContent = "上传中…";
      }
      window
        .fetch(form.action, { method: "POST", body: new FormData(form), credentials: "same-origin" })
        .then(function (response) {
          return response.json();
        })
        .then(function (data) {
          if (data.error) {
            if (status) {
              status.textContent = data.error;
            }
            return;
          }
          if (activePicker) {
            choose(activePicker, String(data.id), data.title, data.thumb);
          }
          dialog.close();
        })
        .catch(function () {
          if (status) {
            status.textContent = "上传失败，再试一次。";
          }
        });
    });
  }
})();
