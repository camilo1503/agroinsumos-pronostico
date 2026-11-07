import { grafica, fechaUTC, numero, colores, formatoMes } from "./grafica.js";

const r = await (await fetch("data/resultados.json")).json();
const c = colores();

function dibujarPortada() {
  const hist = r.historico.map((p) => ({ x: fechaUTC(p.fecha), y: p.valor }));
  const ultimo = hist[hist.length - 1];
  const pron = r.pronostico.total.map((p) => ({ x: fechaUTC(p.fecha), y: p.valor }));
  const banda = r.pronostico.total.map((p) => ({ x: fechaUTC(p.fecha), lo: p.li80, hi: p.ls80 }));
  grafica(document.getElementById("g-portada"), {
    series: [
      { nombre: "Índice observado", color: c.pino, puntos: hist },
      { nombre: r.nombre_modelo, color: c.fosfato, punteada: true, puntos: [ultimo, ...pron] },
    ],
    bandas: [{ nombre: "Intervalo de 80 %", color: c.banda, puntos: [{ x: ultimo.x, lo: ultimo.y, hi: ultimo.y }, ...banda] }],
    alto: 360,
    descripcion: "Índice nacional de precios de insumos agrícolas con pronóstico a seis meses",
  });
}

function dibujarHorizonte() {
  const nombres = { naive: "Persistencia", ets: "ETS", sarima: "SARIMA", ridge: "Ridge" };
  const paleta = { naive: c.tinta2, ets: c.ocre, sarima: c.fosfato, ridge: c.potasa };
  const series = Object.keys(nombres).map((m) => ({
    nombre: nombres[m], color: paleta[m], punteada: m === "naive",
    puntos: r.metricas_horizonte.filter((f) => f.modelo === m && f.bloque === "prueba")
      .map((f) => ({ x: Date.UTC(2000, f.horizonte - 1, 1), y: f.mase })),
  }));
  grafica(document.getElementById("g-horizonte"), {
    series, alto: 260, decimales: 2, descripcion: "MASE por horizonte de pronóstico en el bloque de prueba",
  });
  // El eje representa horizontes, no fechas: se reemplaza el texto del eje por los meses adelante.
  const etiquetas = document.querySelectorAll("#g-horizonte svg text.eje[text-anchor='middle'], #g-horizonte svg text.eje[text-anchor='start'], #g-horizonte svg text.eje[text-anchor='end'][y='252']");
  etiquetas.forEach((t) => {
    const mes = ["ene", "feb", "mar", "abr", "may", "jun"].findIndex((m) => t.textContent.startsWith(m));
    if (mes >= 0) t.textContent = `${mes + 1} ${mes ? "meses" : "mes"}`;
  });
  document.querySelectorAll("#g-horizonte tbody td:first-child").forEach((td) => {
    const mes = ["ene", "feb", "mar", "abr", "may", "jun"].findIndex((m) => td.textContent.startsWith(m));
    if (mes >= 0) td.textContent = `${mes + 1} ${mes ? "meses" : "mes"}`;
  });
}

function tablaModelos() {
  const t = document.getElementById("t-modelos");
  const cab = t.createTHead().insertRow();
  ["Modelo", "MASE validación", "MAE validación", "MASE prueba", "MAE prueba", "RMSE prueba"].forEach((x) => {
    const th = document.createElement("th"); th.textContent = x; cab.appendChild(th);
  });
  const cuerpo = t.createTBody();
  for (const [k, m] of Object.entries(r.resumen)) {
    const f = cuerpo.insertRow();
    if (k === r.modelo_seleccionado) f.className = "elegido";
    [m.nombre + (k === r.modelo_seleccionado ? " (seleccionado)" : ""), numero(m.validacion.mase, 2), numero(m.validacion.mae, 2), numero(m.prueba.mase, 2), numero(m.prueba.mae, 2), numero(m.prueba.rmse, 2)]
      .forEach((v) => { f.insertCell().textContent = v; });
  }
}

function veredicto() {
  const e = r.resumen[r.modelo_seleccionado], n = r.resumen.naive;
  const v = document.getElementById("veredicto");
  const p1 = document.createElement("p");
  const b = document.createElement("strong");
  b.textContent = `Seleccionado: ${r.nombre_modelo}.`;
  p1.append(b, ` En validación obtuvo MASE ${numero(e.validacion.mase, 2)} frente a ${numero(n.validacion.mase, 2)} de persistencia.`);
  const p2 = document.createElement("p");
  p2.textContent = r.supera_persistencia_prueba
    ? `En el bloque de prueba también superó a persistencia (MASE ${numero(e.prueba.mase, 2)} frente a ${numero(n.prueba.mase, 2)}).`
    : `En el bloque de prueba no superó a persistencia (MASE ${numero(e.prueba.mase, 2)} frente a ${numero(n.prueba.mase, 2)}). El criterio de mejora consistente no se cumple, así que el pronóstico debe leerse como una señal de apoyo acompañada de sus intervalos.`;
  const dm = r.diebold_mariano_h6[r.modelo_seleccionado].prueba;
  const p3 = document.createElement("p");
  p3.textContent = `La prueba de Diebold-Mariano a seis meses (p = ${numero(dm.p_valor, 2)}, ${dm.n} orígenes) no permite afirmar que exista una diferencia. Los intervalos de 80 % calibrados en validación cubrieron ${numero(r.cobertura_prueba_pct["80"], 1)} % de los valores de prueba.`;
  v.append(p1, p2, p3);
}

function calidad() {
  const q = r.calidad;
  const items = [
    `${q.observaciones} meses continuos del índice total, de ${q.desde} a ${q.hasta}, sin meses ausentes. La diferencia máxima entre el anexo y Datos Abiertos es ${numero(q.comparacion_datos_abiertos.diferencia_maxima, 3)} puntos.`,
    `Los ceros del anexo se tratan como dato faltante: otros insumos existe desde ${q.primer_mes_otros_insumos}, clorpirifos llega hasta ${q.ultimo_mes_clorpirifos} y fipronil hasta ${q.ultimo_mes_fipronil}.`,
    `Los cambios de canasta no generan un salto atípico en el índice total: ${numero(q.cambios_de_canasta.ene_2024_amplia_canasta.variacion_mes_pct, 2)} % en enero de 2024 y ${numero(q.cambios_de_canasta.sep_2024_excluye_fipronil.variacion_mes_pct, 2)} % en septiembre de 2024. Por eso no se aplicó ningún empalme.`,
    `Los meses atípicos se conservan porque corresponden a movimientos reales del mercado, concentrados entre 2021 y 2023 y en abril y mayo de 2026.`,
    `Contraste con SIPSA-I: la variación a doce meses de un índice encadenado con precios observados tiene correlación de ${numero(q.correlacion_variacion_12m_sipsa_vs_upra.Fungicidas, 2)} a ${numero(q.correlacion_variacion_12m_sipsa_vs_upra.Herbicidas, 2)} con los subíndices de la UPRA.`,
  ];
  const ul = document.getElementById("l-calidad");
  items.forEach((t) => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });
  document.getElementById("f-preparacion").textContent = `Serie mensual de ${q.observaciones} observaciones, sin meses ausentes. Los ceros del anexo pasaron a ser faltantes y se comprobó que los cambios de canasta de 2024 no crean saltos atípicos.`;
  const o = r.origenes;
  document.getElementById("f-evaluacion").textContent = `Validación temporal progresiva con ${o.validacion} orígenes (${o.validacion_desde} a ${o.validacion_hasta}) y prueba final con ${o.prueba} orígenes (${o.prueba_desde} a ${o.prueba_hasta}). Métricas MAE, RMSE y MASE por horizonte.`;
  const v = r.versiones;
  document.getElementById("versiones").textContent = `Corrida con corte a ${formatoMes(fechaUTC(r.fecha_corte))}. Python ${v.python}, scikit-learn ${v["scikit-learn"]}, statsmodels ${v.statsmodels}, pandas ${v.pandas}. Huella de datos: ${r.huella_datos.indice_mensual}.`;
}

function dibujar() { dibujarPortada(); dibujarHorizonte(); }
tablaModelos(); veredicto(); calidad(); dibujar();
let espera;
addEventListener("resize", () => { clearTimeout(espera); espera = setTimeout(dibujar, 200); });
