import { db } from "./cliente.js";
import { grafica, fechaUTC, formatoMes, numero, colores } from "./grafica.js";

const { data: { session } } = await db.auth.getSession();
if (!session) location.replace("login.html");

const vista = document.getElementById("vista");
const SERIES = { total: "Índice total", fertilizantes: "Fertilizantes", plaguicidas: "Plaguicidas" };
const COL_INDICE = { total: "indice_total", fertilizantes: "fertilizantes", plaguicidas: "plaguicidas" };
const pesos = (v) => Number(v).toLocaleString("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
const pct = (v) => `${v > 0 ? "+" : ""}${numero(v, 1)} %`;

// Construye nodos con textContent para que el contenido del usuario nunca se interprete como HTML.
function h(tag, attrs = {}, ...hijos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "class") n.className = v;
    else if (v === true) n.setAttribute(k, "");
    else if (v !== false && v != null) n.setAttribute(k, v);
  }
  hijos.flat().forEach((x) => n.append(x));
  return n;
}
const pagina = (...hijos) => { vista.replaceChildren(...hijos.flat()); vista.focus({ preventScroll: true }); };
const falla = (error) => pagina(h("h1", {}, "No se pudieron cargar los datos"), h("p", {}, `${error.message}. Recarga la página; si continúa, revisa tu conexión.`));
const q = async (consulta) => { const { data, error } = await consulta; if (error) throw error; return data; };

let cache = null;
async function base() {
  if (cache) return cache;
  const corrida = (await q(db.from("corrida_modelo").select("*").order("fecha_corte", { ascending: false }).limit(1)))[0];
  if (!corrida) throw new Error("Todavía no hay corridas del modelo publicadas");
  const [indice, pronostico] = await Promise.all([
    q(db.from("indice_mensual").select("*").order("fecha")),
    q(db.from("pronostico").select("*").eq("corrida_id", corrida.id).order("horizonte")),
  ]);
  cache = { corrida, indice, pronostico };
  return cache;
}

function resumen(b, serie) {
  const hist = b.indice.filter((f) => f[COL_INDICE[serie]] != null);
  const ultimo = Number(hist[hist.length - 1][COL_INDICE[serie]]);
  const pron = b.pronostico.filter((p) => p.serie === serie).map((p) => ({
    ...p, valor: +p.valor, li80: +p.li80, ls80: +p.ls80, li95: +p.li95, ls95: +p.ls95,
  }));
  return { hist, ultimo, pron, final: pron[pron.length - 1] };
}

// ---------- Proyeccion ----------
async function proyeccion() {
  const b = await base();
  const c = colores();
  const contenedor = h("div");
  const cifras = h("div", { class: "cifras" });
  const select = h("select", { onchange: () => dibujar(select.value) },
    Object.entries(SERIES).map(([k, v]) => h("option", { value: k }, v)));

  function dibujar(serie) {
    const r = resumen(b, serie);
    const pts = r.hist.slice(-48).map((f) => ({ x: fechaUTC(f.fecha), y: +f[COL_INDICE[serie]] }));
    const u = pts[pts.length - 1];
    const banda = (lo, hi) => [{ x: u.x, lo: u.y, hi: u.y }, ...r.pron.map((p) => ({ x: fechaUTC(p.fecha), lo: p[lo], hi: p[hi] }))];
    cifras.replaceChildren(
      h("div", { class: "cifra" }, h("span", {}, `Último dato, ${formatoMes(u.x)}`), h("strong", {}, numero(r.ultimo))),
      h("div", { class: "cifra" }, h("span", {}, `Estimado, ${formatoMes(fechaUTC(r.final.fecha))}`), h("strong", {}, numero(r.final.valor))),
      h("div", { class: "cifra" }, h("span", {}, "Variación estimada a 6 meses"), h("strong", {}, pct((r.final.valor / r.ultimo - 1) * 100))),
      h("div", { class: "cifra" }, h("span", {}, "Rango de 80 %"), h("strong", {}, `${pct((r.final.li80 / r.ultimo - 1) * 100)} a ${pct((r.final.ls80 / r.ultimo - 1) * 100)}`)),
    );
    grafica(contenedor, {
      series: [
        { nombre: "Observado", color: c.pino, puntos: pts },
        { nombre: "Pronóstico", color: c.fosfato, punteada: true, puntos: [u, ...r.pron.map((p) => ({ x: fechaUTC(p.fecha), y: p.valor }))] },
      ],
      bandas: [
        { nombre: "Intervalo de 95 %", color: c.banda2, puntos: banda("li95", "ls95") },
        { nombre: "Intervalo de 80 %", color: c.banda, puntos: banda("li80", "ls80") },
      ],
      descripcion: `${SERIES[serie]} observado y pronosticado a seis meses`,
    });
  }

  const nota = b.corrida.supera_persistencia_prueba
    ? "El modelo superó a la referencia de persistencia en la prueba final."
    : "En la prueba final este modelo no superó a la referencia de persistencia (mantener el último valor). Tome el pronóstico como una señal de apoyo y fíjese en el rango, no solo en el valor central.";

  pagina(
    h("h1", {}, "Proyección a seis meses"),
    h("p", {}, `Modelo vigente: ${b.corrida.nombre_modelo}. Datos oficiales hasta ${formatoMes(fechaUTC(b.corrida.fecha_corte))}.`),
    h("div", { class: "veredicto" }, h("p", {}, nota)),
    h("div", { class: "filtros" }, h("label", {}, "Serie", select)),
    cifras,
    h("div", { class: "panel" }, contenedor),
    h("p", { class: "pequeno" }, "Enero de 2021 = 100. El índice mide una variación promedio nacional: no es un precio en pesos ni reemplaza una cotización."),
  );
  dibujar("total");
}

// ---------- Presupuesto ----------
function escenario(b, p) {
  const v = (serie, campo) => { const r = resumen(b, serie); return r.final[campo] / r.ultimo; };
  const calc = (campo) => +p.fertilizantes * v("fertilizantes", campo) + +p.plaguicidas * v("plaguicidas", campo) + +p.otros * v("total", campo);
  const baseTotal = +p.fertilizantes + +p.plaguicidas + +p.otros;
  return { baseTotal, bajo: calc("li80"), central: calc("valor"), alto: calc("ls80") };
}

async function presupuesto() {
  const b = await base();
  const lista = await q(db.from("presupuesto").select("*").order("creado_en", { ascending: false }));
  const msg = h("p", { class: "mensaje", role: "status" });
  const campo = (nombre, etiqueta, tipo = "number") => h("label", {}, etiqueta,
    h("input", { name: nombre, type: tipo, required: true, ...(tipo === "number" ? { min: 0, step: "1000", value: 0 } : { maxlength: 80 }) }));

  const form = h("form", {
    onsubmit: async (e) => {
      e.preventDefault();
      const d = Object.fromEntries(new FormData(form));
      if (+d.fertilizantes + +d.plaguicidas + +d.otros <= 0) {
        msg.textContent = "Escriba un gasto mayor que cero en al menos un grupo."; msg.className = "mensaje error"; return;
      }
      const { error } = await db.from("presupuesto").insert(d);
      if (error) { msg.textContent = `No se guardó el presupuesto: ${error.message}`; msg.className = "mensaje error"; return; }
      presupuesto();
    },
  },
    h("div", { class: "fila-form" }, campo("nombre", "Nombre", "text"), campo("fertilizantes", "Fertilizantes (COP)"), campo("plaguicidas", "Plaguicidas (COP)"), campo("otros", "Otros insumos (COP)")),
    h("button", {}, "Guardar presupuesto"), msg);

  const filas = lista.map((p) => {
    const e = escenario(b, p);
    return h("tr", {},
      h("td", {}, p.nombre), h("td", {}, pesos(e.baseTotal)), h("td", {}, pesos(e.bajo)), h("td", {}, pesos(e.central)), h("td", {}, pesos(e.alto)),
      h("td", {}, h("button", { class: "secundario", onclick: async () => { await db.from("presupuesto").delete().eq("id", p.id); presupuesto(); } }, "Eliminar")));
  });

  pagina(
    h("h1", {}, "Presupuesto"),
    h("p", {}, "Escriba lo que hoy gastaría en insumos y vea cuánto cambiaría si cada grupo se moviera como el índice estimado a seis meses."),
    h("div", { class: "panel" }, h("h2", {}, "Nuevo presupuesto"), form),
    h("div", { class: "panel" }, h("h2", {}, "Escenarios guardados"),
      lista.length
        ? h("div", { class: "tabla-scroll" }, h("table", {},
            h("thead", {}, h("tr", {}, ["Nombre", "Hoy", "Escenario bajo", "Escenario central", "Escenario alto", ""].map((t) => h("th", {}, t)))),
            h("tbody", {}, filas)))
        : h("p", {}, "Aún no hay escenarios. Guarde el primero con el formulario de arriba.")),
    h("p", { class: "pequeno" }, "Los escenarios bajo y alto usan los límites del intervalo de 80 %. Otros insumos se mueve con el índice total porque su serie es más corta y no tiene pronóstico propio. Es un ejercicio ilustrativo: no sustituye una cotización."),
  );
}

// ---------- Alertas ----------
async function actualizarContador() {
  const { count } = await db.from("alerta_evento").select("id", { count: "exact", head: true }).eq("leida", false);
  document.getElementById("contador").textContent = count ? `(${count})` : "";
}

async function alertas() {
  const [reglas, eventos] = await Promise.all([
    q(db.from("regla_alerta").select("*").order("creado_en", { ascending: false })),
    q(db.from("alerta_evento").select("*").order("creado_en", { ascending: false }).limit(50)),
  ]);
  const msg = h("p", { class: "mensaje", role: "status" });
  const form = h("form", {
    onsubmit: async (e) => {
      e.preventDefault();
      const d = Object.fromEntries(new FormData(form));
      d.usar_limite_80 = form.elements.usar_limite_80.checked;
      const { error } = await db.from("regla_alerta").insert(d);
      if (error) { msg.textContent = `No se creó la alerta: ${error.message}`; msg.className = "mensaje error"; return; }
      alertas();
    },
  },
    h("div", { class: "fila-form" },
      h("label", {}, "Nombre", h("input", { name: "nombre", required: true, maxlength: 80 })),
      h("label", {}, "Serie", h("select", { name: "serie" }, Object.entries(SERIES).map(([k, v]) => h("option", { value: k }, v)))),
      h("label", {}, "Avisar si", h("select", { name: "direccion" }, h("option", { value: "sube" }, "sube al menos"), h("option", { value: "baja" }, "baja al menos"))),
      h("label", {}, "Porcentaje", h("input", { name: "umbral_pct", type: "number", min: "0.1", step: "0.1", value: "5", required: true })),
      h("label", {}, "Plazo", h("select", { name: "horizonte" }, [1, 2, 3, 4, 5, 6].map((n) => h("option", { value: n, selected: n === 6 }, `${n} ${n === 1 ? "mes" : "meses"}`))))),
    h("label", {}, h("input", { type: "checkbox", name: "usar_limite_80" }), "Usar el extremo del intervalo de 80 % en lugar del valor central"),
    h("button", {}, "Crear alerta"), msg);

  pagina(
    h("h1", {}, "Alertas"),
    h("p", {}, "Cree una regla y el sistema la revisará con el pronóstico vigente y con cada corrida nueva del modelo."),
    h("div", { class: "panel" }, h("h2", {}, "Alertas activadas"),
      eventos.length ? h("ul", { class: "lista-simple" }, eventos.map((ev) => h("li", {},
        h("span", { class: ev.leida ? "" : "estado alerta" }, ev.mensaje),
        ev.leida ? h("span", { class: "pequeno" }, "Leída") : h("button", { class: "secundario", onclick: async () => {
          await db.from("alerta_evento").update({ leida: true }).eq("id", ev.id);
          alertas(); actualizarContador();
        } }, "Marcar como leída"))))
      : h("p", {}, "Ninguna regla se ha activado con el pronóstico vigente.")),
    h("div", { class: "panel" }, h("h2", {}, "Nueva alerta"), form),
    h("div", { class: "panel" }, h("h2", {}, "Mis reglas"),
      reglas.length ? h("ul", { class: "lista-simple" }, reglas.map((r) => h("li", {},
        h("span", {}, `${r.nombre}: ${SERIES[r.serie]} ${r.direccion} ${numero(r.umbral_pct)} % a ${r.horizonte} ${r.horizonte === 1 ? "mes" : "meses"}${r.usar_limite_80 ? " (extremo del 80 %)" : ""}`),
        h("button", { class: "secundario", onclick: async () => { await db.from("regla_alerta").delete().eq("id", r.id); alertas(); actualizarContador(); } }, "Eliminar"))))
      : h("p", {}, "Aún no tiene reglas. Cree la primera con el formulario de arriba.")),
  );
  actualizarContador();
}

// ---------- Reportes ----------
function descargarCSV(nombre, filas) {
  const esc = (v) => {
    let s = String(v ?? "");
    if (/^[=+\-@]/.test(s)) s = `'${s}`; // evita que Excel lo ejecute como formula
    return `"${s.replace(/"/g, '""')}"`;
  };
  const cab = Object.keys(filas[0]);
  const txt = [cab.join(";"), ...filas.map((f) => cab.map((k) => esc(f[k])).join(";"))].join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿" + txt], { type: "text/csv;charset=utf-8" }));
  const a = h("a", { href: url, download: nombre });
  a.click();
  URL.revokeObjectURL(url);
}

async function datosReporte(tipo) {
  const b = await base();
  if (tipo === "proyeccion") {
    return b.pronostico.map((p) => ({ serie: SERIES[p.serie], mes: p.fecha, meses_adelante: p.horizonte, estimado: p.valor,
      limite_inf_80: p.li80, limite_sup_80: p.ls80, limite_inf_95: p.li95, limite_sup_95: p.ls95 }));
  }
  if (tipo === "presupuesto") {
    const l = await q(db.from("presupuesto").select("*").order("creado_en"));
    return l.map((p) => { const e = escenario(b, p); return { nombre: p.nombre, hoy: e.baseTotal, escenario_bajo: Math.round(e.bajo), escenario_central: Math.round(e.central), escenario_alto: Math.round(e.alto) }; });
  }
  const l = await q(db.from("alerta_evento").select("*").order("creado_en", { ascending: false }));
  return l.map((e) => ({ fecha: e.creado_en.slice(0, 10), mensaje: e.mensaje, variacion_pct: e.variacion_pct, leida: e.leida ? "sí" : "no" }));
}

const TITULOS = { proyeccion: "Proyección a seis meses", presupuesto: "Presupuesto", alertas: "Alertas activadas" };

async function reportes() {
  const b = await base();
  const historial = await q(db.from("reporte_generado").select("*").order("creado_en", { ascending: false }).limit(15));
  const salida = h("div");
  const msg = h("p", { class: "mensaje", role: "status" });
  const registrar = (tipo) => db.from("reporte_generado").insert({ tipo, corrida_id: b.corrida.id });

  async function generar(tipo, modo) {
    msg.textContent = "";
    let filas;
    try { filas = await datosReporte(tipo); } catch (e) { msg.textContent = `No se generó el reporte: ${e.message}`; msg.className = "mensaje error"; return; }
    if (!filas.length) { msg.textContent = `Aún no hay datos de ${TITULOS[tipo].toLowerCase()}. Créelos primero en su sección.`; msg.className = "mensaje"; return; }
    await registrar(tipo);
    if (modo === "csv") { descargarCSV(`reporte_${tipo}_${b.corrida.fecha_corte}.csv`, filas); return; }
    const cab = Object.keys(filas[0]);
    salida.replaceChildren(h("div", { class: "panel" },
      h("h2", {}, TITULOS[tipo]),
      h("p", { class: "pequeno" }, `Corte de datos: ${formatoMes(fechaUTC(b.corrida.fecha_corte))}. Modelo: ${b.corrida.nombre_modelo}. Generado el ${new Date().toLocaleDateString("es-CO")}.`),
      h("div", { class: "tabla-scroll" }, h("table", {},
        h("thead", {}, h("tr", {}, cab.map((k) => h("th", {}, k.replaceAll("_", " "))))),
        h("tbody", {}, filas.map((f) => h("tr", {}, cab.map((k) => h("td", {}, String(f[k])))))))),
      h("p", { class: "pequeno" }, "Estimaciones sujetas a incertidumbre. No constituyen asesoría financiera ni garantía de precios.")));
    requestAnimationFrame(() => window.print());
  }

  pagina(
    h("h1", {}, "Reportes"),
    h("div", { class: "panel no-imprimir" }, h("ul", { class: "lista-simple" }, Object.entries(TITULOS).map(([k, t]) => h("li", {},
      h("strong", {}, t),
      h("span", { class: "acciones" },
        h("button", { class: "secundario", onclick: () => generar(k, "csv") }, "Descargar CSV"),
        h("button", { class: "secundario", onclick: () => generar(k, "pdf") }, "Imprimir o guardar PDF"))))), msg),
    salida,
    h("div", { class: "panel no-imprimir" }, h("h2", {}, "Generados recientemente"),
      historial.length ? h("ul", { class: "lista-simple" }, historial.map((r) => h("li", {}, h("span", {}, TITULOS[r.tipo]), h("span", { class: "pequeno" }, new Date(r.creado_en).toLocaleString("es-CO")))))
        : h("p", {}, "Aún no ha generado reportes.")),
  );
}

// ---------- Precios SIPSA ----------
async function precios() {
  const c = colores();
  const catalogo = await q(db.from("sipsa_catalogo").select("*").order("grupo").order("producto"));
  const grupos = [...new Set(catalogo.map((f) => f.grupo))];
  const sGrupo = h("select", {}, grupos.map((g) => h("option", {}, g)));
  const sProd = h("select"), sDep = h("select");
  const g1 = h("div"), g2 = h("div"), cifras = h("div", { class: "cifras" });

  const clave = () => JSON.parse(sProd.value);
  function llenarProductos() {
    sProd.replaceChildren(...catalogo.filter((f) => f.grupo === sGrupo.value).map((f) =>
      h("option", { value: JSON.stringify(f) }, `${f.producto} (${f.presentacion})`)));
  }
  async function llenarDepartamentos() {
    const k = clave();
    const d = await q(db.from("sipsa_departamentos").select("departamento").match(k).order("departamento"));
    const nombres = d.map((f) => f.departamento).filter((n) => n !== "Nacional");
    sDep.replaceChildren(h("option", {}, "Nacional"), ...nombres.map((n) => h("option", {}, n)));
  }
  async function dibujar() {
    const filas = await q(db.from("sipsa_precio").select("fecha,precio").match({ ...clave(), departamento: sDep.value }).order("fecha"));
    const pts = filas.map((f) => ({ x: fechaUTC(f.fecha), y: +f.precio }));
    const u = pts[pts.length - 1], a = pts.find((p) => p.x === Date.UTC(new Date(u.x).getUTCFullYear() - 1, new Date(u.x).getUTCMonth(), 1));
    cifras.replaceChildren(
      h("div", { class: "cifra" }, h("span", {}, `Último precio mediano, ${formatoMes(u.x)}`), h("strong", {}, pesos(u.y))),
      ...(a ? [h("div", { class: "cifra" }, h("span", {}, "Cambio en doce meses"), h("strong", {}, pct((u.y / a.y - 1) * 100)))] : []),
    );
    grafica(g1, { series: [{ nombre: "Precio mediano", color: c.pino, puntos: pts }], alto: 280, decimales: 0, descripcion: `Precio mediano de ${clave().producto} en ${sDep.value}` });
  }
  const refrescar = async () => { await llenarDepartamentos(); await dibujar(); };
  sGrupo.addEventListener("change", () => { llenarProductos(); refrescar(); });
  sProd.addEventListener("change", refrescar);
  sDep.addEventListener("change", dibujar);

  async function contraste() {
    const col = { Fertilizantes: "fertilizantes", Herbicidas: "herbicidas", Fungicidas: "fungicidas", Insecticidas: "insecticidas" }[sGrupo.value];
    const [sip, b] = [await q(db.from("sipsa_contraste").select("fecha,valor").eq("grupo", sGrupo.value).order("fecha")), await base()];
    const upra = b.indice.filter((f) => f[col] != null);
    const inicio = upra.find((f) => sip.some((s) => s.fecha === f.fecha));
    const baseS = +sip.find((s) => s.fecha === inicio.fecha).valor, baseU = +inicio[col];
    grafica(g2, {
      series: [
        { nombre: `Subíndice UPRA: ${sGrupo.value}`, color: c.pino, puntos: upra.map((f) => ({ x: fechaUTC(f.fecha), y: +f[col] / baseU * 100 })) },
        { nombre: "Variación de precios SIPSA-I", color: c.fosfato, punteada: true, puntos: sip.filter((s) => s.fecha >= inicio.fecha).map((s) => ({ x: fechaUTC(s.fecha), y: +s.valor / baseS * 100 })) },
      ],
      alto: 280, descripcion: "Comparación del subíndice UPRA con precios observados de SIPSA-I",
    });
  }
  sGrupo.addEventListener("change", contraste);

  llenarProductos();
  pagina(
    h("h1", {}, "Precios SIPSA"),
    h("p", {}, "Precios observados por el DANE para los productos con mejor cobertura. Sirven para contrastar la tendencia del índice; no representan a todos los establecimientos del país."),
    h("div", { class: "filtros" }, h("label", {}, "Grupo", sGrupo), h("label", {}, "Producto", sProd), h("label", {}, "Departamento", sDep)),
    cifras,
    h("div", { class: "panel" }, g1),
    h("div", { class: "panel" }, h("h2", {}, "Índice frente a precios observados"), g2,
      h("p", { class: "pequeno" }, "Ambas series parten de 100 en su primer mes común, para comparar su evolución y no su nivel.")),
  );
  await refrescar();
  await contraste();
}

// ---------- Monitoreo ----------
async function monitoreo() {
  const b = await base();
  const c = colores();
  const [bt, publicados] = await Promise.all([
    q(db.from("backtest_modelo").select("fecha,bloque,real,pred,origen").eq("corrida_id", b.corrida.id).eq("modelo", b.corrida.modelo_seleccionado).eq("horizonte", 6).order("fecha")),
    q(db.from("monitoreo_pronostico").select("*").eq("serie", "total").order("fecha", { ascending: false }).limit(24)),
  ]);
  const prueba = bt.filter((f) => f.bloque === "prueba");
  const mae = (l) => l.reduce((a, f) => a + Math.abs(f.real - f.pred), 0) / l.length;
  const maeVal = mae(bt.filter((f) => f.bloque === "validacion"));
  const maeRec = mae(prueba.slice(-6));
  const degradado = maeRec > maeVal;
  const g = h("div");
  pagina(
    h("h1", {}, "Monitoreo"),
    h("p", {}, "Cada pronóstico publicado se compara con el valor oficial cuando se conoce. Si el error reciente supera al de validación, hay que revisar el modelo."),
    h("div", { class: "cifras" },
      h("div", { class: "cifra" }, h("span", {}, "MAE a 6 meses en validación"), h("strong", {}, numero(maeVal, 2))),
      h("div", { class: "cifra" }, h("span", {}, "MAE a 6 meses, últimos 6 pronósticos"), h("strong", {}, numero(maeRec, 2))),
      h("div", { class: "cifra" }, h("span", {}, "Cobertura del 80 % en prueba"), h("strong", {}, `${numero(b.corrida.cobertura_prueba["80"])} %`))),
    h("p", { class: degradado ? "estado alerta" : "estado" }, degradado ? "Atención: el error reciente supera al de validación. Revise el modelo y las fuentes." : "Sin señal de degradación: el error reciente está por debajo del de validación."),
    h("div", { class: "panel" }, h("h2", {}, "Pronóstico a 6 meses frente a observado"), g),
    h("div", { class: "panel" }, h("h2", {}, "Pronósticos publicados y verificados"),
      publicados.length ? h("div", { class: "tabla-scroll" }, h("table", {},
        h("thead", {}, h("tr", {}, ["Mes", "Corte", "Estimado", "Observado", "Error", "Dentro del 80 %"].map((t) => h("th", {}, t)))),
        h("tbody", {}, publicados.map((f) => h("tr", {}, h("td", {}, formatoMes(fechaUTC(f.fecha))), h("td", {}, formatoMes(fechaUTC(f.fecha_corte))), h("td", {}, numero(f.pronosticado)), h("td", {}, numero(f.observado)), h("td", {}, `${numero(f.error_pct)} %`), h("td", {}, f.dentro_80 ? "Sí" : "No")))))))
        : h("p", {}, `Aún no hay meses por verificar: el primer pronóstico publicado cubre desde el mes siguiente a ${formatoMes(fechaUTC(b.corrida.fecha_corte))}. Se llenará cuando la UPRA publique ese dato y se ejecute el pipeline.`)),
  );
  grafica(g, {
    series: [
      { nombre: "Observado", color: c.pino, puntos: bt.map((f) => ({ x: fechaUTC(f.fecha), y: +f.real })) },
      { nombre: "Estimado seis meses antes", color: c.fosfato, punteada: true, puntos: bt.map((f) => ({ x: fechaUTC(f.fecha), y: +f.pred })) },
    ],
    descripcion: "Valores observados frente a los pronosticados seis meses antes",
  });
}

// ---------- Navegacion ----------
const RUTAS = { proyeccion, presupuesto, alertas, reportes, precios, monitoreo };
async function navegar() {
  const ruta = RUTAS[location.hash.slice(1)] ? location.hash.slice(1) : "proyeccion";
  document.querySelectorAll(".riel nav a").forEach((a) => {
    if (a.getAttribute("href") === `#${ruta}`) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  document.title = `${ruta[0].toUpperCase()}${ruta.slice(1)} | Agroinsumos`;
  try { await RUTAS[ruta](); } catch (e) { falla(e); }
}
addEventListener("hashchange", navegar);

document.getElementById("usuario").textContent = session?.user?.email ?? "";
document.getElementById("salir").addEventListener("click", async () => { await db.auth.signOut(); location.replace("login.html"); });
db.auth.onAuthStateChange((evento) => { if (evento === "SIGNED_OUT") location.replace("login.html"); });

if (session) { navegar(); actualizarContador(); }
