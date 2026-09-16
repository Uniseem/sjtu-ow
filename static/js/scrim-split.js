/* Live counts on the admin split page (design 9.3, 9.5).
 *
 * Plain DOM, no framework: the site ships Alpine's CSP build, which does not
 * evaluate expressions written in attributes. Everything here is an ordinary
 * event listener in an external file, so script-src 'self' is enough.
 */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function wirePicker() {
    var form = document.querySelector("[data-split-form]");
    if (!form) {
      return;
    }
    var boxes = form.querySelectorAll("[data-pick]");
    var output = form.querySelector("[data-picked]");
    var button = form.querySelector("[data-generate]");
    var warning = form.querySelector("[data-pick-warning]");
    var needed = button ? parseInt(button.getAttribute("data-needed"), 10) : 0;

    function refresh() {
      var picked = 0;
      for (var i = 0; i < boxes.length; i += 1) {
        if (boxes[i].checked) {
          picked += 1;
        }
      }
      if (output) {
        output.textContent = String(picked);
      }
      if (button) {
        button.disabled = picked !== needed;
      }
      if (warning) {
        warning.hidden = picked === needed;
      }
    }

    for (var i = 0; i < boxes.length; i += 1) {
      boxes[i].addEventListener("change", refresh);
    }
    refresh();
  }

  function ratingFor(row) {
    var roleSelect = row.querySelector("[data-role-select]");
    if (!roleSelect) {
      var cell = row.querySelector("[data-rating]");
      var shown = cell ? parseInt(cell.textContent, 10) : 0;
      return isNaN(shown) ? 0 : shown;
    }
    var scores = {};
    try {
      scores = JSON.parse(roleSelect.getAttribute("data-ratings") || "{}");
    } catch (error) {
      scores = {};
    }
    return scores[roleSelect.value] || 0;
  }

  function wireTeams() {
    var form = document.querySelector("[data-teams-form]");
    if (!form) {
      return;
    }
    var rows = form.querySelectorAll("[data-member]");
    var totalA = document.querySelector("[data-total-a]");
    var totalB = document.querySelector("[data-total-b]");
    var gap = document.querySelector("[data-gap]");

    function refresh() {
      var sums = { a: 0, b: 0 };
      for (var i = 0; i < rows.length; i += 1) {
        var row = rows[i];
        var teamSelect = row.querySelector("[data-team-select]");
        var team = teamSelect ? teamSelect.value : "";
        var rating = ratingFor(row);
        var cell = row.querySelector("[data-rating]");
        if (cell) {
          cell.textContent = rating ? String(rating) : "—";
        }
        if (team === "a" || team === "b") {
          sums[team] += rating;
        }
      }
      if (totalA) {
        totalA.textContent = String(sums.a);
      }
      if (totalB) {
        totalB.textContent = String(sums.b);
      }
      if (gap) {
        gap.textContent = String(Math.abs(sums.a - sums.b));
      }
      var perTeam = document.querySelectorAll("[data-team-total]");
      for (var j = 0; j < perTeam.length; j += 1) {
        var side = perTeam[j].getAttribute("data-team-total");
        perTeam[j].textContent = String(sums[side] || 0);
      }
    }

    form.addEventListener("change", function (event) {
      if (event.target.matches("[data-team-select], [data-role-select]")) {
        refresh();
      }
    });
    refresh();
  }

  ready(function () {
    wirePicker();
    wireTeams();
  });
})();
