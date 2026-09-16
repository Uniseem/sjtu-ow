/* The admin split page (design 9.3, 9.5).
 *
 * Plain DOM plus SortableJS, no framework: the site ships Alpine's CSP build,
 * which does not evaluate expressions written in attributes. Everything here
 * is an ordinary listener in an external file, so script-src 'self' is enough.
 *
 * Capacity rule, as asked for: a full team refuses a drop. To swap someone in
 * you first drag someone out to the buffer. Rejecting the drop is friendlier
 * than silently accepting an eleventh player and flagging it afterwards --
 * the arrangement on screen is always one you could save.
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

  function each(nodes, fn) {
    Array.prototype.forEach.call(nodes, fn);
  }

  // --- picking who plays -----------------------------------------------------

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
      each(boxes, function (box) {
        if (box.checked) {
          picked += 1;
        }
      });
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

    each(boxes, function (box) {
      box.addEventListener("change", refresh);
    });
    refresh();
  }

  // --- the board -------------------------------------------------------------

  function zoneOf(node) {
    return node.closest("[data-zone]");
  }

  function teamOf(zone) {
    return zone.getAttribute("data-zone-team") || "";
  }

  function capacityOf(zone) {
    var raw = zone.getAttribute("data-zone-capacity");
    return raw ? parseInt(raw, 10) : 0;
  }

  function cardsIn(node) {
    return node.querySelectorAll("[data-card]");
  }

  function ratingFor(card, role) {
    var scores = {};
    try {
      scores = JSON.parse(card.getAttribute("data-ratings") || "{}");
    } catch (error) {
      scores = {};
    }
    if (role && scores[role]) {
      return scores[role];
    }
    if (role) {
      return 0;
    }
    return parseInt(card.getAttribute("data-best"), 10) || 0;
  }

  function teamCount(team) {
    var panel = document.querySelector('[data-team-panel="' + team + '"]');
    return panel ? cardsIn(panel).length : 0;
  }

  function wireBoard() {
    var form = document.querySelector("[data-teams-form]");
    if (!form || typeof window.Sortable === "undefined") {
      return;
    }
    var help = form.querySelector("[data-drag-help]");
    if (help) {
      help.hidden = false;
    }
    var teamSize = parseInt(form.getAttribute("data-team-size"), 10) || 0;
    var overWarning = document.querySelector("[data-over-capacity]");

    function refresh() {
      var totals = { a: 0, b: 0 };
      each(document.querySelectorAll("[data-zone]"), function (zone) {
        var team = teamOf(zone);
        var role = zone.getAttribute("data-zone-role") || "";
        var cards = cardsIn(zone);
        var count = zone.querySelector("[data-zone-count]");
        if (count) {
          count.textContent = String(cards.length);
        }
        var capacity = capacityOf(zone);
        zone.classList.toggle(
          "is-over",
          capacity > 0 && cards.length !== capacity
        );
        each(cards, function (card) {
          var rating = ratingFor(card, role);
          card.querySelector("[data-card-team]").value = team;
          card.querySelector("[data-card-role]").value = role;
          var shown = card.querySelector("[data-card-rank]");
          if (shown) {
            shown.textContent = rating ? String(rating) : "—";
          }
          if (team === "a" || team === "b") {
            totals[team] += rating;
          }
        });
      });

      each(document.querySelectorAll("[data-team-total]"), function (node) {
        node.textContent = String(totals[node.getAttribute("data-team-total")] || 0);
      });
      var totalA = document.querySelector("[data-total-a]");
      var totalB = document.querySelector("[data-total-b]");
      var gap = document.querySelector("[data-gap]");
      if (totalA) {
        totalA.textContent = String(totals.a);
      }
      if (totalB) {
        totalB.textContent = String(totals.b);
      }
      if (gap) {
        gap.textContent = String(Math.abs(totals.a - totals.b));
      }
      if (overWarning) {
        overWarning.hidden = !(
          teamCount("a") > teamSize || teamCount("b") > teamSize
        );
      }
    }

    // Design 9.5 still allows saving a split whose role counts are wrong, so
    // only the team size is enforced here; role zones just turn red.
    function accepts(targetZone, card) {
      var team = teamOf(targetZone);
      if (team !== "a" && team !== "b") {
        return true; // the buffer always accepts
      }
      var from = zoneOf(card);
      if (from && teamOf(from) === team) {
        return true; // moving between roles inside the same team
      }
      return teamCount(team) < teamSize;
    }

    each(form.querySelectorAll("[data-list]"), function (list) {
      window.Sortable.create(list, {
        group: "scrim-split",
        animation: 120,
        ghostClass: "is-dragging",
        onMove: function (event) {
          var target = zoneOf(event.to);
          return target ? accepts(target, event.dragged) : false;
        },
        onEnd: refresh,
      });
    });

    // Keyboard and touch path: same rules, no dragging required.
    form.addEventListener("click", function (event) {
      var button = event.target.closest("[data-move]");
      if (!button) {
        return;
      }
      event.preventDefault();
      var card = button.closest("[data-card]");
      var wanted = button.getAttribute("data-move");
      var target = document.querySelector(
        '[data-zone][data-zone-team="' + wanted + '"]'
      );
      if (!target || !accepts(target, card)) {
        return;
      }
      target.querySelector("[data-list]").appendChild(card);
      refresh();
    });

    refresh();
  }

  ready(function () {
    wirePicker();
    wireBoard();
  });
})();
