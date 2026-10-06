// The back office's few behaviours (docs/admin.md 2): the picture dialog,
// select-all, filters that submit themselves, confirmations, buttons that
// change a block in place and the people search of member groups. Everything works without it except the picture
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

  // --- buttons that change a block in place (member groups, v7.7) ------------------
  //
  // A form with data-inline posts without leaving the page; the server sends
  // the block back (JSON {replace: {selector: html}}) and it is swapped in,
  // its own autosave forms set up again. Without this script the same forms
  // post and come back to the page.

  function csrfToken() {
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function swapBlocks(data, focusSelector) {
    Object.keys(data.replace || {}).forEach(function (selector) {
      var old = document.querySelector(selector);
      if (!old) {
        return;
      }
      old.outerHTML = data.replace[selector];
      var fresh = document.querySelector(selector);
      if (fresh && window.owAutosave) {
        window.owAutosave.setUp(fresh);
      }
      var focus = fresh && focusSelector && fresh.querySelector(focusSelector);
      if (focus) {
        focus.focus();
      }
    });
  }

  function sendInline(form, focusSelector) {
    var buttons = form.querySelectorAll("button");
    for (var i = 0; i < buttons.length; i += 1) {
      buttons[i].disabled = true;
    }
    window
      .fetch(form.getAttribute("action"), {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-CSRFToken": csrfToken() },
      })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        swapBlocks(data, focusSelector);
      })
      .catch(function () {
        form.submit();
      });
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (event.defaultPrevented || !form.hasAttribute) {
      return;
    }
    if (form.hasAttribute("data-inline")) {
      event.preventDefault();
      sendInline(form, '[data-person-search] [name="q"]');
    } else if (form.hasAttribute("data-person-search")) {
      event.preventDefault();
      searchPeople(form);
    }
  });

  // --- 搜人, as you type (member groups, v7.7) --------------------------------------

  var searchTimer = null;

  function searchPeople(form) {
    var box = form.querySelector('[name="q"]');
    var results = form.parentElement.querySelector("[data-person-results]");
    var query = box.value.trim();
    if (!results) {
      return;
    }
    if (!query) {
      results.innerHTML = "";
      return;
    }
    window
      .fetch(form.getAttribute("data-search-url") + "?q=" + encodeURIComponent(query), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (box.value.trim() !== query) {
          return; // typed on meanwhile; a newer search follows
        }
        results.innerHTML = "";
        if (!data.results.length) {
          var none = document.createElement("li");
          var text = document.createElement("span");
          text.textContent = "没有找到「" + query + "」：只列已加入、还不在组里的人。";
          none.appendChild(text);
          results.appendChild(none);
          return;
        }
        data.results.forEach(function (person) {
          var row = document.createElement("li");
          var name = document.createElement("span");
          name.textContent = person.label;
          var add = document.createElement("form");
          add.method = "post";
          add.action = form.getAttribute("data-add-url");
          add.setAttribute("data-inline", "");
          var user = document.createElement("input");
          user.type = "hidden";
          user.name = "user";
          user.value = person.id;
          var button = document.createElement("button");
          button.type = "submit";
          button.className = "c-btn c-btn--secondary c-btn--sm";
          button.textContent = "加入";
          add.appendChild(user);
          add.appendChild(button);
          row.appendChild(name);
          row.appendChild(add);
          results.appendChild(row);
        });
      });
  }

  document.addEventListener("input", function (event) {
    var box = event.target;
    var form = box.form;
    if (!form || !form.hasAttribute("data-person-search") || box.name !== "q") {
      return;
    }
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(function () {
      searchPeople(form);
    }, 250);
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
        // A lost session answers with the login page (a redirect); shown in
        // here, its form looked like the upload (216, F5).
        if (!response.ok || response.redirected) {
          var gone = new Error("HTTP " + response.status);
          gone.signedOut = response.redirected || response.status === 403;
          throw gone;
        }
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
      .catch(function (error) {
        dialogBody.innerHTML = error && error.signedOut
          ? '<p class="c-notice c-notice--error">登录状态已失效或没有权限，重新登录后再选图片。</p>'
          : '<p class="c-notice c-notice--error">图片没有加载出来，关掉再试一次。</p>';
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
