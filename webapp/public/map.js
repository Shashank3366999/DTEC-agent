// Draws the floor map with the live route. Used by /live and /walk.
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const make = (tag, attrs, text) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (text) e.textContent = text;
    return e;
  };
  window.drawMap = function (svg, profile, nav) {
    const nodes = Object.fromEntries(profile.floor.nodes.map((n) => [n.id, n]));
    const places = Object.fromEntries(profile.places.filter((p) => p.node).map((p) => [p.node, p]));
    const xs = profile.floor.nodes.map((n) => n.x), ys = profile.floor.nodes.map((n) => -n.y);
    const pad = 3.4, x0 = Math.min(...xs) - pad, y0 = Math.min(...ys) - pad;
    const w = Math.max(...xs) - x0 + pad, h = Math.max(...ys) - y0 + pad;
    svg.setAttribute("viewBox", `${x0} ${y0} ${w} ${h}`);
    svg.replaceChildren();
    const line = (a, b, cls) => svg.append(make("line", { x1: nodes[a].x, y1: -nodes[a].y, x2: nodes[b].x, y2: -nodes[b].y, class: cls }));
    for (const [a, b] of profile.floor.edges) line(a, b, "edge");
    const path = ((nav && nav.path) || []).filter((k) => nodes[k]);
    path.slice(1).forEach((k, i) => line(path[i], k, "path"));
    // Labels: alternate above/below where neighbours in a row would overlap
    const row = {};
    for (const n of [...profile.floor.nodes].sort((a, b) => a.x - b.x)) {
      const p = places[n.id], goal = nav && nav.destination_node === n.id;
      svg.append(make("circle", { cx: n.x, cy: -n.y, r: goal ? 0.62 : p ? 0.42 : 0.2, class: goal ? "goal" : p ? "place" : "way" }));
      const label = p ? p.label || p.names.en[0] : n.name.replace(/^the /, "");
      const up = (row[n.y] = !row[n.y]);
      svg.append(make("text", { x: n.x, y: -n.y + (up ? -0.95 : 1.4), class: goal ? "label goal" : "label" }, label));
    }
    let spot = null;
    if (nav && nav.between && nav.between.every((k) => nodes[k])) {
      const [a, b] = nav.between.map((k) => nodes[k]);
      spot = [(a.x + b.x) / 2, -(a.y + b.y) / 2];
    } else if (nav && nodes[nav.at]) spot = [nodes[nav.at].x, -nodes[nav.at].y];
    if (spot) {
      const g = make("g", { transform: `translate(${spot[0]} ${spot[1]}) rotate(${nav.heading || 0})`, class: "robot" });
      if (nav.heading !== null && nav.heading !== undefined) g.append(make("path", { d: "M0 -1.15 L0.5 -0.35 L-0.5 -0.35 Z" }));
      g.append(make("circle", { r: 0.5 }));
      svg.append(g);
    }
  };
})();
