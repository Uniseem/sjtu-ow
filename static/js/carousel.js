// Homepage photo carousel (焦点图, round 065). A plain script because the CSP
// build of Alpine does not evaluate expressions. Markup:
//   [data-carousel] > [data-slide]* and [data-dot]* (same order)
(function () {
  "use strict";

  var INTERVAL = 5000;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function setup(root) {
    var slides = root.querySelectorAll("[data-slide]");
    var dots = root.querySelectorAll("[data-dot]");
    if (slides.length < 2) return;
    var current = 0;
    var timer = null;

    function show(index) {
      current = (index + slides.length) % slides.length;
      for (var i = 0; i < slides.length; i++) {
        var active = i === current;
        slides[i].classList.toggle("is-active", active);
        slides[i].setAttribute("aria-hidden", active ? "false" : "true");
        slides[i].querySelectorAll("a").forEach(function (link) {
          link.tabIndex = active ? 0 : -1;
        });
        if (dots[i]) dots[i].setAttribute("aria-current", active ? "true" : "false");
      }
    }

    function start() {
      if (reduceMotion || timer) return;
      timer = window.setInterval(function () { show(current + 1); }, INTERVAL);
    }

    function stop() {
      window.clearInterval(timer);
      timer = null;
    }

    dots.forEach(function (dot, i) {
      dot.addEventListener("click", function () { show(i); });
    });
    root.addEventListener("mouseenter", stop);
    root.addEventListener("mouseleave", start);
    root.addEventListener("focusin", stop);
    root.addEventListener("focusout", start);
    root.addEventListener("keydown", function (event) {
      if (event.key === "ArrowRight") show(current + 1);
      if (event.key === "ArrowLeft") show(current - 1);
    });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stop(); else start();
    });

    show(0);
    start();
  }

  document.querySelectorAll("[data-carousel]").forEach(setup);
})();
