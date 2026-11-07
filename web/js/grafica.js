// Grafica de lineas en SVG con banda de incertidumbre, guia al pasar el cursor y tabla accesible.
const NS = "http://www.w3.org/2000/svg";
const MES = new Intl.DateTimeFormat("es-CO", { month: "short", year: "numeric", timeZone: "UTC" });

export const fechaUTC = (s) => { const [a, m, d] = s.split("-").map(Number); return Date.UTC(a, m - 1, d || 1); };
export const formatoMes = (t) => MES.format(new Date(t)).replace(".", "");
export const numero = (v, d = 1) => Number(v).toLocaleString("es-CO", { minimumFractionDigits: d, maximumFractionDigits: d });

function el(nombre, attrs = {}, padre) {
  const n = document.createElementNS(NS, nombre);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (padre) padre.appendChild(n);
  return n;
}

function marcasY(min, max) {
  const paso0 = (max - min) / 5;
  const mag = 10 ** Math.floor(Math.log10(paso0));
  const paso = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((p) => p >= paso0);
  const salida = [];
  const tope = Math.ceil(max / paso) * paso;
  for (let v = Math.floor(min / paso) * paso; v <= tope + 1e-9; v += paso) salida.push(v);
  return salida;
}

// series: [{ nombre, color, puntos:[{x,y}], punteada }]; bandas: [{ nombre, color, puntos:[{x,lo,hi}] }]
export function grafica(contenedor, { series, bandas = [], alto = 340, sufijo = "", decimales = 1, descripcion = "" }) {
  contenedor.replaceChildren();
  contenedor.classList.add("grafica");

  const leyenda = document.createElement("ul");
  leyenda.className = "leyenda";
  if (series.length + bandas.length > 1) {
    for (const s of series) {
      const li = document.createElement("li");
      const i = document.createElement("i");
      i.style.background = s.punteada
        ? `repeating-linear-gradient(90deg, ${s.color} 0 5px, transparent 5px 8px)` : s.color;
      li.append(i, s.nombre);
      leyenda.appendChild(li);
    }
    for (const b of bandas) {
      const li = document.createElement("li");
      const i = document.createElement("i");
      i.className = "area";
      i.style.background = b.color;
      li.append(i, b.nombre);
      leyenda.appendChild(li);
    }
    contenedor.appendChild(leyenda);
  }

  const ancho = Math.max(contenedor.clientWidth || 800, 320);
  const m = { sup: 12, der: 16, inf: 28, izq: 48 };
  const svg = el("svg", { viewBox: `0 0 ${ancho} ${alto}`, role: "img", "aria-label": descripcion });
  contenedor.appendChild(svg);

  const todosX = [...new Set(series.flatMap((s) => s.puntos.map((p) => p.x)))].sort((a, b) => a - b);
  const ys = series.flatMap((s) => s.puntos.map((p) => p.y)).concat(bandas.flatMap((b) => b.puntos.flatMap((p) => [p.lo, p.hi])));
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const marcas = marcasY(yMin - (yMax - yMin) * 0.04, yMax + (yMax - yMin) * 0.04);
  const y0 = marcas[0], y1 = marcas[marcas.length - 1];
  const x0 = todosX[0], x1 = todosX[todosX.length - 1];
  const X = (x) => m.izq + ((x - x0) / Math.max(x1 - x0, 1)) * (ancho - m.izq - m.der);
  const Y = (y) => alto - m.inf - ((y - y0) / (y1 - y0)) * (alto - m.sup - m.inf);

  for (const v of marcas) {
    el("line", { class: "rejilla", x1: m.izq, x2: ancho - m.der, y1: Y(v), y2: Y(v) }, svg);
    const t = el("text", { class: "eje", x: m.izq - 8, y: Y(v) + 4, "text-anchor": "end" }, svg);
    t.textContent = numero(v, 0);
  }
  const nEtiquetas = Math.max(2, Math.floor((ancho - m.izq - m.der) / 110));
  const pasoX = Math.max(1, Math.round((todosX.length - 1) / nEtiquetas));
  for (let i = 0; i < todosX.length; i += pasoX) {
    const t = el("text", { class: "eje", x: X(todosX[i]), y: alto - 8, "text-anchor": i === 0 ? "start" : X(todosX[i]) > ancho - m.der - 40 ? "end" : "middle" }, svg);
    t.textContent = formatoMes(todosX[i]);
  }

  for (const b of bandas) {
    const arriba = b.puntos.map((p) => `${X(p.x)},${Y(p.hi)}`);
    const abajo = [...b.puntos].reverse().map((p) => `${X(p.x)},${Y(p.lo)}`);
    el("polygon", { points: [...arriba, ...abajo].join(" "), fill: b.color }, svg);
  }
  for (const s of series) {
    const d = s.puntos.map((p, i) => `${i ? "L" : "M"}${X(p.x)} ${Y(p.y)}`).join(" ");
    el("path", { d, fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", ...(s.punteada ? { "stroke-dasharray": "6 5" } : {}) }, svg);
  }

  // Capa de cursor
  const guia = el("line", { class: "guia", y1: m.sup, y2: alto - m.inf, visibility: "hidden" }, svg);
  const puntos = series.map((s) => el("circle", { r: 4, fill: s.color, stroke: "var(--superficie)", "stroke-width": 2, visibility: "hidden" }, svg));
  const tip = document.createElement("div");
  tip.className = "tooltip";
  tip.hidden = true;
  contenedor.appendChild(tip);
  const zona = el("rect", { x: m.izq, y: m.sup, width: ancho - m.izq - m.der, height: alto - m.sup - m.inf, fill: "transparent" }, svg);

  const mostrar = (ev) => {
    const caja = svg.getBoundingClientRect();
    const px = ((ev.clientX - caja.left) / caja.width) * ancho;
    const x = todosX.reduce((a, b) => (Math.abs(X(b) - px) < Math.abs(X(a) - px) ? b : a));
    guia.setAttribute("x1", X(x)); guia.setAttribute("x2", X(x)); guia.setAttribute("visibility", "visible");
    tip.replaceChildren();
    const titulo = document.createElement("strong");
    titulo.textContent = formatoMes(x);
    tip.appendChild(titulo);
    series.forEach((s, i) => {
      const p = s.puntos.find((q) => q.x === x);
      puntos[i].setAttribute("visibility", p ? "visible" : "hidden");
      if (!p) return;
      puntos[i].setAttribute("cx", X(p.x)); puntos[i].setAttribute("cy", Y(p.y));
      const fila = document.createElement("div");
      fila.textContent = `${s.nombre}: ${numero(p.y, decimales)}${sufijo}`;
      tip.appendChild(fila);
    });
    for (const b of bandas) {
      const p = b.puntos.find((q) => q.x === x);
      if (!p) continue;
      const fila = document.createElement("div");
      fila.textContent = `${b.nombre}: ${numero(p.lo, decimales)} a ${numero(p.hi, decimales)}`;
      tip.appendChild(fila);
    }
    tip.hidden = false;
    const izq = (X(x) / ancho) * caja.width;
    tip.style.left = `${Math.min(Math.max(izq, 90), caja.width - 90)}px`;
    tip.style.top = `${svg.offsetTop + 34}px`;
  };
  zona.addEventListener("pointermove", mostrar);
  zona.addEventListener("pointerdown", mostrar);
  zona.addEventListener("pointerleave", () => {
    guia.setAttribute("visibility", "hidden");
    puntos.forEach((p) => p.setAttribute("visibility", "hidden"));
    tip.hidden = true;
  });

  // Vista en tabla para lectores de pantalla y para quien prefiera leer los valores.
  const det = document.createElement("details");
  det.className = "no-imprimir";
  const sum = document.createElement("summary");
  sum.textContent = "Ver los datos en tabla";
  const envoltura = document.createElement("div");
  envoltura.className = "tabla-scroll";
  const tabla = document.createElement("table");
  const cab = tabla.createTHead().insertRow();
  const celda = (fila, txt, tag = "td") => { const c = document.createElement(tag); c.textContent = txt; fila.appendChild(c); };
  celda(cab, "Mes", "th");
  series.forEach((s) => celda(cab, s.nombre, "th"));
  bandas.forEach((b) => celda(cab, b.nombre, "th"));
  const cuerpo = tabla.createTBody();
  for (const x of [...todosX].reverse()) {
    const f = cuerpo.insertRow();
    celda(f, formatoMes(x));
    series.forEach((s) => { const p = s.puntos.find((q) => q.x === x); celda(f, p ? numero(p.y, decimales) : ""); });
    bandas.forEach((b) => { const p = b.puntos.find((q) => q.x === x); celda(f, p ? `${numero(p.lo, decimales)} a ${numero(p.hi, decimales)}` : ""); });
  }
  envoltura.appendChild(tabla);
  det.append(sum, envoltura);
  contenedor.appendChild(det);
}

export const colores = () => {
  const s = getComputedStyle(document.documentElement);
  const v = (n) => s.getPropertyValue(n).trim();
  return { pino: v("--s-verde"), fosfato: v("--s-azul"), potasa: v("--s-rosa"), ocre: v("--s-ocre"), banda: v("--banda"), banda2: v("--banda-2"), tinta2: v("--tinta-2") };
};
