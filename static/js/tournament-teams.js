/* The admin board that forms ad-hoc teams from the pool (design 8.8.2).
 *
 * Derived from scrim-split.js (round 032): plain DOM plus SortableJS, no
 * framework, so script-src 'self' is enough. Dragging only moves cards and
 * rewrites their hidden inputs; the server validates the whole layout again.
 *
 * Capacity rule: a full team refuses a drop; take someone out first. Teams
 * below the minimum turn red but can still be saved (design 8.8.2). A card
 * marked data-blocked (already on a real team's roster) stays in the pool.
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

  function minimumOf(zone) {
    var raw = zone.getAttribute("data-zone-min");
    return raw ? parseInt(raw, 10) : 0;
  }

  function cardsIn(node) {
    return node.querySelectorAll("[data-card]");
  }

  function wireBoard() {
    var form = document.querySelector("[data-teams-form]");
    if (!form) {
      return;
    }
    var help = form.querySelector("[data-drag-help]");
    if (help && typeof window.Sortable !== "undefined") {
      help.hidden = false;
    }

    function refresh() {
      each(form.querySelectorAll("[data-zone]"), function (zone) {
        var team = teamOf(zone);
        var cards = cardsIn(zone);
        var count = zone.querySelector("[data-zone-count]");
        if (count) {
          count.textContent = String(cards.length);
        }
        var capacity = capacityOf(zone);
        var minimum = minimumOf(zone);
        zone.classList.toggle("is-over", capacity > 0 && cards.length > capacity);
        zone.classList.toggle(
          "is-under",
          minimum > 0 && cards.length > 0 && cards.length < minimum
        );
        each(cards, function (card) {
          card.querySelector("[data-card-team]").value = team;
        });
        var problem = form.querySelector('[data-team-problem="' + team + '"]');
        if (problem && team !== "") {
          if (cards.length > 0 && cards.length < minimum) {
            problem.textContent = "人数不足：" + cards.length + " / 下限 " + minimum;
            problem.hidden = false;
          } else {
            problem.hidden = true;
          }
        }
      });
    }

    function accepts(targetZone, card) {
      var team = teamOf(targetZone);
      if (team === "") {
        return true; // the pool always accepts
      }
      if (card.getAttribute("data-blocked")) {
        return false; // already on a real team's roster
      }
      var from = zoneOf(card);
      if (from && teamOf(from) === team) {
        return true;
      }
      var capacity = capacityOf(targetZone);
      return capacity === 0 || cardsIn(targetZone).length < capacity;
    }

    if (typeof window.Sortable !== "undefined") {
      each(form.querySelectorAll("[data-list]"), function (list) {
        window.Sortable.create(list, {
          group: "tournament-teams",
          animation: 120,
          ghostClass: "is-dragging",
          onMove: function (event) {
            var target = zoneOf(event.to);
            return target ? accepts(target, event.dragged) : false;
          },
          onEnd: refresh,
        });
      });
    }

    // Keyboard and touch path: same rules, no dragging required.
    form.addEventListener("click", function (event) {
      var button = event.target.closest("[data-move]");
      if (!button) {
        return;
      }
      event.preventDefault();
      var card = button.closest("[data-card]");
      var wanted = button.getAttribute("data-move") || "";
      var target = form.querySelector(
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

  ready(wireBoard);
})();
