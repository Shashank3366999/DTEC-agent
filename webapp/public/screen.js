// Live reception screen: listens to /api/events and redraws.
(function () {
  const arrivalsEl = document.getElementById("arrivals");
  const emptyEl = document.getElementById("arrivals-empty");
  const routeBox = document.getElementById("route-box");
  const live = document.getElementById("live");

  const hasArabic = (s) => /[؀-ۿ]/.test(s || "");
  const timeAgo = (iso) => {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    if (hasArabic(text)) e.dir = "rtl";
    return e;
  }

  let checkins = [];

  function renderArrivals(freshId) {
    arrivalsEl.replaceChildren();
    emptyEl.style.display = checkins.length ? "none" : "block";
    for (const c of checkins.slice(0, 6)) {
      const li = el("li", "arrival" + (c.id === freshId ? " fresh" : ""));
      li.append(el("div", "who", c.visitor_name));
      li.append(el("div", "when", timeAgo(c.created_at)));
      li.append(el("div", "host", c.host_company + (c.meeting_time ? " · " + c.meeting_time : "")));
      li.append(el("div", "status", "Host notified ✓"));
      arrivalsEl.append(li);
    }
  }

  function qrInto(box, url) {
    box.replaceChildren();
    try {
      const qr = window.qrcode(0, "M");
      qr.addData(url);
      qr.make();
      box.innerHTML = qr.createSvgTag({ cellSize: 6, margin: 0, scalable: true });
    } catch (e) {
      box.append(el("div", "fallback", url));
    }
  }

  function renderRoute(r) {
    routeBox.className = "";
    routeBox.replaceChildren();
    if (!r) {
      routeBox.className = "empty";
      routeBox.textContent = "When the guide sends a route, it appears here.";
      return;
    }
    const rtl = /^ar/i.test(r.language || "") || hasArabic(r.destination);
    const wrap = el("div", "route");
    const qr = el("div", "qr");
    qrInto(qr, r.url);
    const right = el("div");
    if (rtl) right.dir = "rtl";
    right.append(el("p", "dest", r.destination));
    const ol = el("ol", "steps");
    for (const s of r.steps) ol.append(el("li", null, s));
    right.append(ol);
    right.append(el("div", "scan", rtl ? "امسح الرمز لفتح المسار على هاتفك" : "Scan the code to open this route on your phone"));
    wrap.append(qr, right);
    routeBox.append(wrap);
  }

  async function loadState() {
    const res = await fetch("/api/state", { cache: "no-store" });
    const s = await res.json();
    checkins = s.checkins || [];
    renderArrivals();
    renderRoute((s.routes || [])[0]);
  }

  function connect() {
    const es = new EventSource("/api/events");
    es.onopen = () => {
      live.classList.add("on");
      live.lastChild.textContent = "live";
      loadState().catch(() => {});
    };
    es.onerror = () => {
      live.classList.remove("on");
      live.lastChild.textContent = "reconnecting";
    };
    es.addEventListener("checkin", (e) => {
      const c = JSON.parse(e.data);
      checkins.unshift(c);
      renderArrivals(c.id);
    });
    es.addEventListener("route", (e) => renderRoute(JSON.parse(e.data)));
    es.addEventListener("reset", () => {
      checkins = [];
      renderArrivals();
      renderRoute(null);
    });
  }

  loadState().catch(() => {});
  connect();
})();
