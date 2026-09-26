// Motion and the masthead (design 13.2.5, 13.3). An external file because the
// content security policy allows no inline scripts.
(function () {
  "use strict";
  var d = document;
  var root = d.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- Masthead: bar at the top, capsule past 80px, hides on the way down,
  // comes back on the way up (13.3). ----
  var bar = d.querySelector("[data-masthead]");
  var TOP = 80;
  var NUDGE = 6;
  var MORPH_MS = 320;
  var lastY = window.scrollY;
  var travel = 0;
  var capsuleSince = 0;
  var hideTimer = 0;

  function setHidden(hidden) {
    if (!bar) {
      return;
    }
    if (hidden && bar.contains(d.activeElement)) {
      return;
    }
    bar.classList.toggle("is-hidden", hidden);
  }

  function masthead(y) {
    if (!bar) {
      return;
    }
    var dy = y - lastY;
    lastY = y;
    if (y < TOP) {
      bar.classList.remove("is-capsule");
      setHidden(false);
      travel = 0;
      return;
    }
    if (!bar.classList.contains("is-capsule")) {
      bar.classList.add("is-capsule");
      capsuleSince = Date.now();
    }
    if (dy > 0) {
      travel = Math.max(travel, 0) + dy;
    } else if (dy < 0) {
      travel = Math.min(travel, 0) + dy;
    }
    if (travel < -NUDGE) {
      setHidden(false);
    } else if (travel > NUDGE) {
      // Become the capsule first, then slide it away.
      var wait = reduce ? 0 : capsuleSince + MORPH_MS - Date.now();
      if (wait > 0) {
        window.clearTimeout(hideTimer);
        hideTimer = window.setTimeout(requestFrame, wait);
      } else {
        setHidden(true);
      }
    }
  }

  if (bar) {
    bar.addEventListener("focusin", function () {
      setHidden(false);
    });
  }

  // ---- Parallax for elements marked data-parallax="0.4" (13.2.6). ----
  var parallax = d.querySelectorAll("[data-parallax]");

  function drift(y) {
    if (reduce) {
      return;
    }
    for (var i = 0; i < parallax.length; i += 1) {
      var rate = parseFloat(parallax[i].getAttribute("data-parallax")) || 0;
      if (y < window.innerHeight * 1.5) {
        parallax[i].style.transform = "translate3d(0," + (y * rate).toFixed(1) + "px,0)";
      }
    }
  }

  var ticking = false;
  function frame() {
    ticking = false;
    var y = window.scrollY;
    masthead(y);
    drift(y);
  }
  function requestFrame() {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(frame);
    }
  }
  window.addEventListener("scroll", requestFrame, { passive: true });
  frame();

  // ---- "/" jumps to the search box (13.3). ----
  var searchBox = d.querySelector("[data-search] input");
  d.addEventListener("keydown", function (event) {
    if (event.key !== "/" || !searchBox || event.ctrlKey || event.metaKey || event.altKey) {
      return;
    }
    var target = event.target;
    var tag = target && target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (target && target.isContentEditable)) {
      return;
    }
    if (searchBox.offsetParent === null) {
      return;
    }
    event.preventDefault();
    searchBox.focus();
  });

  // ---- Count-up figures: data-count-to="312" (13.2.5). ----
  function countUp(el) {
    var target = parseInt(el.getAttribute("data-count-to"), 10);
    if (isNaN(target) || reduce) {
      return;
    }
    var start = null;
    var duration = 1700;
    el.textContent = "0";
    function step(now) {
      if (start === null) {
        start = now;
      }
      var p = Math.min((now - start) / duration, 1);
      var eased = p === 1 ? 1 : 1 - Math.pow(2, -10 * p);
      el.textContent = String(Math.round(target * eased));
      if (p < 1) {
        window.requestAnimationFrame(step);
      }
    }
    window.setTimeout(function () {
      window.requestAnimationFrame(step);
    }, parseInt(el.getAttribute("data-count-delay"), 10) || 0);
  }

  // ---- Scroll reveal: [data-reveal] lifts its children in turn (13.2.5). ----
  var groups = d.querySelectorAll("[data-reveal]");
  for (var g = 0; g < groups.length; g += 1) {
    var kids = groups[g].children;
    for (var k = 0; k < kids.length; k += 1) {
      kids[k].style.setProperty("--reveal-i", String(k));
    }
  }

  function reveal(el) {
    el.classList.add("is-in");
    var figures = el.querySelectorAll("[data-count-to]");
    for (var i = 0; i < figures.length; i += 1) {
      countUp(figures[i]);
    }
    // Once settled, hand the children back to their own styles so hover lifts
    // work (the reveal rules sit outside the component layer and would win).
    var settle = (el.children.length - 1) * 60 + 1150;
    window.setTimeout(function () {
      el.removeAttribute("data-reveal");
      el.classList.remove("is-in");
    }, settle);
  }

  if (!("IntersectionObserver" in window) || reduce) {
    for (var r = 0; r < groups.length; r += 1) {
      groups[r].classList.add("is-in");
    }
  } else {
    var seen = new IntersectionObserver(
      function (entries) {
        for (var i = 0; i < entries.length; i += 1) {
          if (entries[i].isIntersecting) {
            seen.unobserve(entries[i].target);
            reveal(entries[i].target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 }
    );
    for (var o = 0; o < groups.length; o += 1) {
      seen.observe(groups[o]);
    }
  }

  // Figures outside any reveal group count up once the page is ready.
  var loose = d.querySelectorAll("[data-count-to]");
  for (var f = 0; f < loose.length; f += 1) {
    if (!loose[f].closest("[data-reveal]")) {
      countUp(loose[f]);
    }
  }

  root.classList.add("motion-ready");
})();
