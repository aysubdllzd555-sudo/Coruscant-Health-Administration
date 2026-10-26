/* Coruscant Health — progressive enhancement. Every page works without JS. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  /* ---- theme toggle ---- */
  $$("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var root = document.documentElement;
      var cur = root.getAttribute("data-theme") ||
        (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      var next = cur === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("cha-theme", next); } catch (e) {}
    });
  });

  /* ---- mobile menu ---- */
  var sidebar = $("#sidebar");
  $$("[data-menu]").forEach(function (b) {
    b.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = sidebar.classList.toggle("open");
      b.setAttribute("aria-expanded", open);
    });
  });
  document.addEventListener("click", function (e) {
    if (sidebar && sidebar.classList.contains("open") && !sidebar.contains(e.target)) sidebar.classList.remove("open");
  });

  /* ---- clock (Galactic Standard ≈ local) ---- */
  var clock = $("[data-clock]");
  function tick() {
    if (!clock) return;
    var d = new Date();
    clock.textContent = d.toLocaleDateString(undefined, { weekday: "short", day: "2-digit", month: "short" }) + " · " +
      d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  tick(); setInterval(tick, 15000);

  /* ---- toasts ---- */
  $$("[data-dismiss]").forEach(function (b) { b.addEventListener("click", function () { b.parentNode.remove(); }); });
  setTimeout(function () { $$(".toast-success, .toast-info").forEach(function (t) { t.style.transition = "opacity .4s"; t.style.opacity = 0; setTimeout(function () { t.remove(); }, 450); }); }, 6000);

  /* ---- localise timestamps ---- */
  $$("time[data-local]").forEach(function (t) {
    var d = new Date(t.getAttribute("datetime"));
    if (!isNaN(d)) t.textContent = d.toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  });

  /* ---- keyboard shortcuts ---- */
  document.addEventListener("keydown", function (e) {
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select" || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "/") { var s = $(".search input[name=q]"); if (s) { e.preventDefault(); s.focus(); } }
    if (e.key === "n" || e.key === "N") { var link = $('a[href$="/ed/intake/"]'); if (link) { e.preventDefault(); location.href = link.href; } }
  });

  /* ---- tabs ---- */
  $$("[data-tabs]").forEach(function (group) {
    var tabs = $$('[role="tab"]', group);
    function show(id, push) {
      tabs.forEach(function (t) {
        var on = t.getAttribute("aria-controls") === id;
        t.setAttribute("aria-selected", on);
        t.tabIndex = on ? 0 : -1;
        var panel = document.getElementById(t.getAttribute("aria-controls"));
        if (panel) panel.hidden = !on;
      });
      if (push) history.replaceState(null, "", "#" + id);
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { show(t.getAttribute("aria-controls"), true); });
      t.addEventListener("keydown", function (e) {
        var d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (d) { var n = tabs[(i + d + tabs.length) % tabs.length]; n.focus(); n.click(); }
      });
    });
    var hash = location.hash.slice(1);
    var initial = tabs.filter(function (t) { return t.getAttribute("aria-controls") === hash; })[0] || tabs[0];
    if (initial) show(initial.getAttribute("aria-controls"), false);
  });

  /* ---- vitals chart (dependency-free SVG) ---- */
  var METRICS = {
    hr:    { label: "Heart rate", unit: "bpm", band: [51, 90] },
    spo2:  { label: "SpO₂", unit: "%", band: [96, 100] },
    temp:  { label: "Temperature", unit: "°C", band: [36.1, 38.0] },
    bp:    { label: "Blood pressure", unit: "mmHg", band: [111, 140], keys: ["sys", "dia"] },
    rr:    { label: "Resp. rate", unit: "/min", band: [12, 20] },
    news2: { label: "NEWS2", unit: "score", band: [0, 4] },
    glu:   { label: "Glucose", unit: "mmol/L", band: [4, 7.8] }
  };
  var NS = "http://www.w3.org/2000/svg";
  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function drawChart(box, series, metric) {
    var m = METRICS[metric];
    var keys = m.keys || [metric];
    var pts = series.filter(function (r) { return r[keys[0]] !== null && r[keys[0]] !== undefined; });
    box.innerHTML = "";
    if (pts.length < 2) { box.innerHTML = '<p class="empty">Not enough ' + m.label.toLowerCase() + " data yet.</p>"; return; }
    var W = box.clientWidth || 600, H = box.clientHeight || 260, L = 40, R = 12, T = 12, B = 26;
    var vals = [];
    pts.forEach(function (p) { keys.forEach(function (k) { if (p[k] !== null) vals.push(p[k]); }); });
    var lo = Math.min.apply(null, vals.concat([m.band[0]])), hi = Math.max.apply(null, vals.concat([m.band[1]]));
    var pad = (hi - lo) * 0.12 || 1; lo -= pad; hi += pad;
    var t0 = new Date(pts[0].t).getTime(), t1 = new Date(pts[pts.length - 1].t).getTime();
    var x = function (t) { return L + (W - L - R) * ((new Date(t).getTime() - t0) / Math.max(1, t1 - t0)); };
    var y = function (v) { return T + (H - T - B) * (1 - (v - lo) / (hi - lo)); };
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": m.label + " over time" }, box);
    var defs = el("defs", {}, svg);
    var g = el("linearGradient", { id: "chartFill", x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
    var accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#C9731F";
    el("stop", { offset: "0", "stop-color": accent, "stop-opacity": ".22" }, g);
    el("stop", { offset: "1", "stop-color": accent, "stop-opacity": "0" }, g);
    el("rect", { class: "band", x: L, width: W - L - R, y: y(m.band[1]), height: Math.max(0, y(m.band[0]) - y(m.band[1])) }, svg);
    for (var i = 0; i <= 4; i++) {
      var v = lo + (hi - lo) * i / 4, yy = y(v);
      el("line", { class: "gridline", x1: L, x2: W - R, y1: yy, y2: yy }, svg);
      el("text", { class: "axis", x: L - 8, y: yy + 4, "text-anchor": "end" }, svg).textContent = (hi - lo < 10 ? v.toFixed(1) : Math.round(v));
    }
    var days = Math.max(1, Math.round((t1 - t0) / 864e5));
    var step = Math.max(1, Math.ceil(days / 7));
    for (var d = 0; d <= days; d += step) {
      var tt = t0 + d * 864e5; if (tt > t1) break;
      var xx = L + (W - L - R) * ((tt - t0) / Math.max(1, t1 - t0));
      el("text", { class: "axis", x: xx, y: H - 6, "text-anchor": "middle" }, svg).textContent =
        new Date(tt).toLocaleDateString([], { day: "2-digit", month: "short" });
    }
    keys.forEach(function (k, ki) {
      var line = pts.filter(function (p) { return p[k] !== null; }).map(function (p) { return [x(p.t), y(p[k])]; });
      var dstr = line.map(function (p, j) { return (j ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
      if (ki === 0) el("path", { class: "area", d: dstr + " L" + line[line.length - 1][0] + " " + (H - B) + " L" + line[0][0] + " " + (H - B) + " Z" }, svg);
      el("path", { class: ki ? "line2" : "line", d: dstr }, svg);
    });
    var cursor = el("line", { class: "cursor", y1: T, y2: H - B, x1: -10, x2: -10 }, svg);
    var dot = el("circle", { class: "pt", r: 4, cx: -10, cy: -10 }, svg);
    var tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true; box.appendChild(tip);
    function move(ev) {
      var rect = svg.getBoundingClientRect();
      var px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - rect.left) * (W / rect.width);
      var best = pts[0], bd = Infinity;
      pts.forEach(function (p) { var dd = Math.abs(x(p.t) - px); if (dd < bd) { bd = dd; best = p; } });
      var cx = x(best.t), cy = y(best[keys[0]]);
      cursor.setAttribute("x1", cx); cursor.setAttribute("x2", cx);
      dot.setAttribute("cx", cx); dot.setAttribute("cy", cy);
      var val = keys.map(function (k) { return best[k]; }).join("/");
      tip.textContent = val + " " + m.unit + " · " + new Date(best.t).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
      tip.hidden = false;
      tip.style.left = (cx / W * rect.width) + "px"; tip.style.top = (cy / H * rect.height) + "px";
    }
    svg.addEventListener("mousemove", move); svg.addEventListener("touchmove", move, { passive: true });
    svg.addEventListener("mouseleave", function () { tip.hidden = true; cursor.setAttribute("x1", -10); cursor.setAttribute("x2", -10); dot.setAttribute("cx", -10); });
  }
  $$("[data-chart]").forEach(function (card) {
    var src = document.getElementById(card.getAttribute("data-chart"));
    if (!src) return;
    var series = JSON.parse(src.textContent);
    var box = $(".chart", card);
    var current = card.getAttribute("data-metric") || "hr";
    var buttons = $$("[data-metric-btn]", card);
    function render() { drawChart(box, series, current); buttons.forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-metric-btn") === current); }); }
    buttons.forEach(function (b) { b.addEventListener("click", function () { current = b.getAttribute("data-metric-btn"); render(); }); });
    render();
    var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(render, 120); });
  });

  /* ---- drag & drop upload zones ---- */
  $$(".dropzone").forEach(function (z) {
    var input = $("input[type=file]", z), label = $("[data-filename]", z);
    ["dragenter", "dragover"].forEach(function (ev) { z.addEventListener(ev, function (e) { e.preventDefault(); z.classList.add("drag"); }); });
    ["dragleave", "drop"].forEach(function (ev) { z.addEventListener(ev, function (e) { e.preventDefault(); z.classList.remove("drag"); }); });
    z.addEventListener("drop", function (e) { if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; input.dispatchEvent(new Event("change")); } });
    if (input && label) input.addEventListener("change", function () { label.textContent = input.files.length ? input.files[0].name : ""; });
  });

  /* ---- registration: show fields for the selected role ---- */
  var roleInputs = $$('input[name="role"]');
  if (roleInputs.length) {
    var sync = function () {
      var r = (roleInputs.filter(function (i) { return i.checked; })[0] || {}).value;
      $$("[data-role-section]").forEach(function (s) { s.hidden = s.getAttribute("data-role-section").split(" ").indexOf(r) === -1; });
    };
    roleInputs.forEach(function (i) { i.addEventListener("change", sync); });
    sync();
  }

  /* ---- demo account quick fill ---- */
  $$("[data-fill]").forEach(function (b) {
    b.addEventListener("click", function () {
      var u = $("#id_username"), p = $("#id_password");
      if (u) u.value = b.getAttribute("data-fill");
      if (p) { p.value = b.getAttribute("data-pw"); p.focus(); }
    });
  });

  /* ---- bay picker ---- */
  $$("[data-bay-picker]").forEach(function (wrap) {
    var target = document.getElementById(wrap.getAttribute("data-bay-picker"));
    $$("button", wrap).forEach(function (b) {
      b.addEventListener("click", function () {
        var same = target.value === b.textContent;
        target.value = same ? "" : b.textContent;
        $$("button", wrap).forEach(function (x) { x.setAttribute("aria-pressed", !same && x === b); });
      });
    });
  });

  /* ---- copy buttons ---- */
  $$("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var t = document.getElementById(b.getAttribute("data-copy"));
      if (navigator.clipboard && t) navigator.clipboard.writeText(t.textContent.trim()).then(function () { b.textContent = "Copied"; });
    });
  });

  /* ---- live ED timers & board refresh ---- */
  function fmt(min) { var h = Math.floor(min / 60), m = min % 60; return h + ":" + (m < 10 ? "0" : "") + m; }
  function timers() {
    $$("[data-since]").forEach(function (t) {
      var min = Math.max(0, Math.floor((Date.now() - new Date(t.getAttribute("data-since")).getTime()) / 60000));
      t.textContent = fmt(min);
      t.classList.toggle("long", min >= (parseInt(t.getAttribute("data-limit"), 10) || 240));
    });
  }
  timers(); setInterval(timers, 30000);
  if (document.body.classList.contains("auto-refresh")) {
    setInterval(function () {
      var a = document.activeElement;
      if (a && /input|textarea|select/i.test(a.tagName)) return;
      if (document.visibilityState === "visible") location.reload();
    }, 60000);
  }
})();
