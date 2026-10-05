// 自动保存（design 13.17, v7.6）: a form with data-autosave saves itself.
//
// Text waits for a pause (0.8 s), ticks, picks and pictures go at once; the
// whole form is posted to the address it submits to, with X-Autosave: 1, one
// request at a time. The server answers with JSON (core/autosave.py): what
// was saved, which fields were not and why, a new address once something new
// exists, and pieces of the page to swap. A line above the form says where
// things stand; errors sit under their fields. Unsaved changes are flushed
// before another form on the page submits (publish, send a test email) and
// the browser asks before leaving. The form's own 保存 button
// (data-autosave-button) is hidden; without this script it still submits.
//
// A form with data-autosubmit-file sends itself as soon as a file is chosen
// (the avatar: 「上传后自动就保存替换」).
(function () {
  "use strict";

  var TEXT_PAUSE = 800;
  var PICK_PAUSE = 60;
  var RETRY = 5000;
  var savers = [];

  function token(form) {
    var input = form.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input) {
      return input.value;
    }
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function isText(control) {
    if (control.tagName === "TEXTAREA") {
      return true;
    }
    if (control.tagName !== "INPUT") {
      return false;
    }
    var type = (control.getAttribute("type") || "text").toLowerCase();
    return ["text", "email", "url", "number", "search", "tel", "date",
      "datetime-local", "time"].indexOf(type) >= 0;
  }

  function isSecret(control) {
    return control.tagName === "INPUT" && (control.getAttribute("type") || "") === "password";
  }

  function fieldBox(control) {
    return control.closest(".c-field") || control.parentElement;
  }

  function labelOf(form, name) {
    var control = form.elements[name];
    if (control && control.length && !control.tagName) {
      control = control[0];
    }
    if (!control || !control.closest) {
      return "";
    }
    var box = control.closest(".c-field");
    var label = box && box.querySelector(".c-field__label, legend, label span");
    return label ? label.textContent.replace("*", "").trim() : "";
  }

  function Saver(form) {
    this.form = form;
    this.timer = null;
    this.busy = null;
    this.again = false;
    this.dirty = false;
    this.failed = false;
    this.status = form.querySelector("[data-autosave-status]");
    if (!this.status) {
      this.status = document.createElement("p");
      this.status.className = "c-autosave";
      this.status.setAttribute("data-autosave-status", "");
      this.status.setAttribute("role", "status");
      this.status.setAttribute("aria-live", "polite");
      form.insertBefore(this.status, form.firstChild);
    }
    this.show(
      "idle",
      form.hasAttribute("data-autosave-idle") ? form.getAttribute("data-autosave-idle") : "改了就自动保存"
    );
    var buttons = form.querySelectorAll("[data-autosave-button]");
    for (var i = 0; i < buttons.length; i += 1) {
      buttons[i].hidden = true;
    }
  }

  Saver.prototype.show = function (state, text) {
    this.status.setAttribute("data-state", state);
    this.status.textContent = text;
  };

  Saver.prototype.later = function (pause) {
    var self = this;
    this.dirty = true;
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(function () {
      self.save();
    }, pause);
  };

  Saver.prototype.pending = function () {
    // A form htmx swapped out is gone; whatever it had is no longer ours.
    if (!document.contains(this.form)) {
      return false;
    }
    return this.dirty || this.busy !== null || this.failed;
  };

  Saver.prototype.save = function () {
    var self = this;
    window.clearTimeout(this.timer);
    if (this.busy) {
      this.again = true;
      return this.busy;
    }
    this.dirty = false;
    this.show("saving", "正在保存…");
    var body = new FormData(this.form);
    this.busy = window
      .fetch(this.form.getAttribute("action") || window.location.href, {
        method: "POST",
        body: body,
        credentials: "same-origin",
        headers: { "X-Autosave": "1", "X-CSRFToken": token(this.form), Accept: "application/json" },
      })
      .then(function (response) {
        var type = response.headers.get("Content-Type") || "";
        if (!response.ok || type.indexOf("json") < 0) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        self.failed = false;
        self.apply(data);
      })
      .catch(function () {
        self.failed = true;
        self.show("failed", "保存失败，5 秒后重试");
        window.clearTimeout(self.timer);
        self.timer = window.setTimeout(function () {
          self.save();
        }, RETRY);
      })
      .then(function () {
        self.busy = null;
        if (self.again) {
          self.again = false;
          return self.save();
        }
        return null;
      });
    return this.busy;
  };

  Saver.prototype.clearErrors = function () {
    var old = this.form.querySelectorAll("[data-autosave-error]");
    for (var i = 0; i < old.length; i += 1) {
      var box = old[i].parentElement;
      old[i].remove();
      if (box && !box.querySelector(".c-field__error")) {
        box.classList.remove("is-invalid");
      }
    }
  };

  Saver.prototype.apply = function (data) {
    var form = this.form;
    if (data.location && data.location !== window.location.pathname) {
      window.history.replaceState(null, "", data.location);
      form.setAttribute("action", data.location);
    }
    Object.keys(data.replace || {}).forEach(function (selector) {
      var target = document.querySelector(selector);
      if (!target) {
        return;
      }
      var focused = document.activeElement;
      var name = focused && form.contains(focused) ? focused.getAttribute("name") : "";
      target.outerHTML = data.replace[selector];
      if (name) {
        var again = form.querySelector('[name="' + name + '"]');
        if (again) {
          again.focus();
        }
      }
    });
    this.clearErrors();
    var problems = [];
    var errors = data.errors || {};
    Object.keys(errors).forEach(function (name) {
      var text = errors[name].join(" ");
      if (name === "__all__") {
        problems.push(text);
        return;
      }
      var control = form.elements[name];
      if (control && control.length && !control.tagName) {
        control = control[0];
      }
      var label = labelOf(form, name);
      problems.push(label ? label + "：" + text : text);
      if (!control || !control.closest) {
        return;
      }
      var box = fieldBox(control);
      var note = document.createElement("p");
      note.className = "c-field__error";
      note.setAttribute("data-autosave-error", "");
      note.setAttribute("role", "alert");
      note.textContent = text;
      box.classList.add("is-invalid");
      box.appendChild(note);
    });
    if (problems.length) {
      this.show("partial", "有 " + problems.length + " 项没存（其余已保存 " + data.saved_at + "）：" + problems.join("；"));
    } else {
      this.show("saved", "已保存 " + data.saved_at);
    }
  };

  function saverFor(form) {
    for (var i = 0; i < savers.length; i += 1) {
      if (savers[i].form === form) {
        return savers[i];
      }
    }
    return null;
  }

  function anyPending() {
    return savers.some(function (saver) {
      return saver.pending();
    });
  }

  function flushAll() {
    return Promise.all(
      savers.map(function (saver) {
        if (!document.contains(saver.form)) {
          return null;
        }
        return saver.dirty ? saver.save() : saver.busy || null;
      })
    );
  }

  function setUp(root) {
    var uploads = (root || document).querySelectorAll("form[data-autosubmit-file] [data-autosave-button]");
    for (var u = 0; u < uploads.length; u += 1) {
      uploads[u].hidden = true;
    }
    var forms = (root || document).querySelectorAll("form[data-autosave]");
    for (var i = 0; i < forms.length; i += 1) {
      if (!saverFor(forms[i])) {
        savers.push(new Saver(forms[i]));
      }
    }
  }

  document.addEventListener("input", function (event) {
    var control = event.target;
    var form = control.form;
    var saver = form && saverFor(form);
    if (!saver || control.hasAttribute("data-autosave-skip") || isSecret(control)) {
      return;
    }
    if (isText(control)) {
      saver.later(TEXT_PAUSE);
    }
  });

  document.addEventListener("change", function (event) {
    var control = event.target;
    var form = control.form;
    if (form && form.hasAttribute("data-autosubmit-file") && control.type === "file") {
      if (control.files && control.files.length) {
        var status = form.querySelector("[data-autosubmit-status]");
        if (status) {
          status.hidden = false;
        }
        form.submit();
      }
      return;
    }
    var saver = form && saverFor(form);
    if (!saver || control.hasAttribute("data-autosave-skip")) {
      return;
    }
    // A text box's change is its blur: whatever was typed goes now.
    saver.later(isText(control) ? 0 : PICK_PAUSE);
  });

  // Another form on the page (an action) waits for unsaved changes first;
  // pressing Enter in an autosave form saves it instead of leaving the page.
  document.addEventListener(
    "submit",
    function (event) {
      var form = event.target;
      var submitter = event.submitter;
      var saver = saverFor(form);
      if (saver && (!submitter || submitter.hasAttribute("data-autosave-button"))) {
        event.preventDefault();
        event.stopPropagation();
        saver.save();
        return;
      }
      if (form.__owFlushed || !anyPending()) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      flushAll().then(function () {
        form.__owFlushed = true;
        if (form.requestSubmit) {
          form.requestSubmit(submitter || undefined);
        } else {
          form.submit();
        }
      });
    },
    true
  );

  window.addEventListener("beforeunload", function (event) {
    if (anyPending()) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  // Pages that swap in new forms (htmx) get them set up too.
  document.addEventListener("htmx:afterSwap", function (event) {
    setUp(event.target);
  });

  window.owAutosave = { flush: flushAll, setUp: setUp };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      setUp();
    });
  } else {
    setUp();
  }
})();
