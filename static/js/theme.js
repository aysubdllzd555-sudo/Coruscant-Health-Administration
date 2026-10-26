(function () {
  try {
    var t = localStorage.getItem("cha-theme");
    if (t) document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* storage unavailable */ }
})();
