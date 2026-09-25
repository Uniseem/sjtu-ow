// Homepage 焦点图 (design 5.2, 13.2.7 c-feature). A plain script: Alpine is
// the CSP build and does not evaluate expressions. Markup:
//   [data-carousel] > [data-slide]*, [data-caption]*, [data-dot]* (same order)
// The progress bar is CSS; this script only says which slide is current and
// whether it is playing ([data-playing]) or held ([data-paused]).
(function () {
  "use strict";

  var INTERVAL = 5000;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function setup(root) {
    var slides = root.querySelectorAll("[data-slide]");
    var captions = root.querySelectorAll("[data-caption]");
    var dots = root.querySelectorAll("[data-dot]");
    if (slides.length < 2) return;
    var current = 0;
    var timer = null;
    var held = false;

    function show(index) {
      current = (index + slides.length) % slides.length;
      for (var i = 0; i < slides.length; i++) {
        var active = i === current;
        slides[i].classList.toggle("is-active", active);
        slides[i].setAttribute("aria-hidden", active ? "false" : "true");
        if (captions[i]) {
          captions[i].classList.toggle("is-active", active);
          captions[i].querySelectorAll("a").forEach(function (link) {
            link.tabIndex = active ? 0 : -1;
          });
        }
        if (dots[i]) dots[i].setAttribute("aria-current", active ? "true" : "false");
      }
    }

    function schedule() {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        show(current + 1);
        schedule();
      }, INTERVAL);
    }

    function play() {
      if (reduceMotion || held) return;
      root.removeAttribute("data-paused");
      root.setAttribute("data-playing", "");
      schedule();
    }

    function pause() {
      window.clearTimeout(timer);
      timer = null;
      root.removeAttribute("data-playing");
      root.setAttribute("data-paused", "");
    }

    dots.forEach(function (dot, i) {
      dot.addEventListener("click", function () {
        show(i);
        if (!held) {
          // Restart the bar for the chosen slide.
          root.removeAttribute("data-playing");
          window.requestAnimationFrame(play);
        }
      });
    });
    root.addEventListener("mouseenter", function () { held = true; pause(); });
    root.addEventListener("mouseleave", function () { held = false; play(); });
    root.addEventListener("focusin", function () { held = true; pause(); });
    root.addEventListener("focusout", function (event) {
      if (!root.contains(event.relatedTarget)) {
        held = false;
        play();
      }
    });
    root.addEventListener("keydown", function (event) {
      if (event.key === "ArrowRight") show(current + 1);
      if (event.key === "ArrowLeft") show(current - 1);
    });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) pause(); else play();
    });

    show(0);
    play();
  }

  document.querySelectorAll("[data-carousel]").forEach(setup);
})();
