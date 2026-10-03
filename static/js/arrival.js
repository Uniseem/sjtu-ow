// The page the loading bar was waiting for (design 13.2.4, v6.6): the bar
// runs on from where the last page left it to the end, then fades. Runs in
// <head>, before the first paint, so the bar never jumps.
(function () {
  "use strict";
  var KEY = "ow-loading";
  var FRESH = 20000; // ms; an older note belongs to some other visit
  var root = document.documentElement;

  function arrive() {
    var note = null;
    try {
      note = JSON.parse(window.sessionStorage.getItem(KEY) || "null");
      window.sessionStorage.removeItem(KEY);
    } catch (error) {
      return;
    }
    if (!note || typeof note.at !== "number" || Date.now() - note.at > FRESH) {
      return;
    }
    var from = Number(note.from);
    if (!(from > 0 && from < 1)) {
      from = 0.6; // the last page went before it could say
    }
    root.style.setProperty("--loadbar-from", String(from));
    root.classList.add("is-arriving");
  }

  // A page the browser prepared ahead of the click looks once it is shown.
  if (document.prerendering) {
    document.addEventListener("prerenderingchange", arrive, { once: true });
  } else {
    arrive();
  }
})();
