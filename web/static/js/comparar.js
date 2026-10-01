"use strict";
// Tela Comparar: grupos com strip plot, matriz formato × conta, Shorts do grupo selecionado.
let dim = "formato";
let selecionado = null;
const TITULOS = { formato: "por formato", conta: "por conta", tema: "por tema", podcast: "por podcast" };

// escala log de 0,1× a 10×: "metade" e "dobro" ficam à mesma distância de 1×
const px = (v, w) => (Math.log10(Math.min(10, Math.max(.1, v))) + 1) / 2 * w;

function eixo() {
  const marcas = [[.2, "0,2×"], [.5, "0,5×"], [1, "1×"], [2, "2×"], [5, "5×"]];
  return `<svg class="strip" style="height:14px" viewBox="0 0 400 14" preserveAspectRatio="none">${marcas.map(([t, r]) =>
    `<text x="${px(t, 400)}" y="11" text-anchor="middle">${r}</text>`).join("")}</svg>`;
}

function strip(rels, med) {
  const W = 400, H = 34;
  const grade = [.2, .5, 1, 2, 5].map(t => `<line class="grade" x1="${px(t, W)}" x2="${px(t, W)}" y1="4" y2="30"/>`).join("");
  const pontos = rels.map((v, i) =>
    `<circle class="${v >= 1 ? "up" : "down"}" cx="${px(v, W)}" cy="${17 + ((i % 3) - 1) * 5}" r="4.2"/>`).join("");
  return `<svg class="strip" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${grade}
    <line class="base" x1="${px(1, W)}" x2="${px(1, W)}" y1="0" y2="${H}"/>${pontos}
    <rect class="med" x="${px(med, W) - 1.5}" y="2" width="3" height="30" rx="1"/></svg>`;
}

function nomeGrupo(k) {
  return dim === "formato" ? nomeFormato(k) : dim === "conta" ? handleDe(k) : k;
}
function subGrupo(k) {
  if (dim === "formato") return `${k} · ${E.formatos[k]?.obs ?? ""}`;
  if (dim === "conta") return E.contas.find(c => c.id === k)?.nicho ?? "";
  return "";
}
function chavesDe(l) {
  const e = l.etiquetas;
  return dim === "formato" ? [e.formato] : dim === "conta" ? [l.conta] : dim === "tema" ? e.temas : [e.podcast];
}

function linhaGrupo(g) {
  const insc = g.insc_por_mil == null ? "—" : g.insc_por_mil.toFixed(1).replace(".", ",");
  return `<div class="linha ${g.chave === selecionado ? "sel" : ""}" data-chave="${esc(g.chave)}">
    <div class="nome">${esc(nomeGrupo(g.chave))}<small>${esc(subGrupo(g.chave))}</small>${g.pista ? '<span class="selo">pista · n&lt;5</span>' : ""}</div>
    <div class="num">${g.n}</div>
    <div class="rel ${g.rel_mediana >= 1 ? "up" : "down"}">${fx(g.rel_mediana)}</div>
    <div>${strip(g.rels, g.rel_mediana)}</div>
    <div class="num">${pct(g.pct_mediana)}</div>
    <div class="num">${insc}</div></div>`;
}

function tabelaGrupos(C) {
  if (!C.grupos.length) return vazio("Nenhum Short medido ainda", "Ligue os Shorts na tela Shorts. Cada um entra aqui 7 dias depois de publicado, quando a conta tiver 3 Shorts medidos.");
  return `<div class="legenda"><span><i class="pt" style="background:var(--up)"></i>acima da base da conta</span>
    <span><i class="pt" style="background:var(--down)"></i>abaixo</span><span>│ tracejado = 1× (mediana da conta)</span>
    <span>▮ traço claro = mediana do grupo</span></div>
    <section class="grupos"><div class="linha cab"><span>${esc(dim)}</span><span class="num">n</span><span class="num">Mediana</span>
    <span>${eixo()}</span><span class="num">assist.</span><span class="num">insc/1k</span></div>${C.grupos.map(linhaGrupo).join("")}</section>`;
}

function corCelula(v) {
  return v >= 1 ? `rgba(255,122,47,${Math.min(.75, .14 + (v - 1) * .3)})` : `rgba(125,147,184,${Math.min(.6, .14 + (1 - v) * .6)})`;
}

function textoConfusao(c) {
  return c.tipo === "formato" ? `${nomeFormato(c.chave)} só rodou em ${handleDe(c.unico)}`
                              : `${handleDe(c.chave)} só postou ${nomeFormato(c.unico)}`;
}

// Com uma conta só, toda matriz é confusa por definição (formato e conta não se separam):
// listar cada formato seria repetir a mesma causa linha a linha. Com 2+ contas, a lista de
// confusões pontuais continua útil.
function notaConfusao(C) {
  if (E.contas.length < 2) {
    return `<div class="nota">Uma conta só: formato e conta não se separam. Crie uma segunda conta e poste `
      + `o mesmo formato nas duas para comparar.</div>`;
  }
  if (!C.confusoes.length) return "";
  return `<div class="nota"><b>Confusão</b> — o número mistura formato com conta:
    <ul>${C.confusoes.map(c => `<li>${esc(textoConfusao(c))}</li>`).join("")}</ul>Postar o mesmo formato em outra conta separa os dois.</div>`;
}

function blocoMatriz(C) {
  const formatos = Object.keys(E.formatos).filter(f => C.matriz.some(c => c.formato === f));
  if (!formatos.length) return `<h2>Formato × conta</h2>${vazio("Matriz vazia", "Aparece quando houver Shorts medidos.")}`;
  const cel = new Map(C.matriz.map(c => [`${c.formato}|${c.conta}`, c]));
  const linhas = formatos.map(f => `<tr><td class="rot">${esc(nomeFormato(f))}</td>${E.contas.map(conta => {
    const c = cel.get(`${f}|${conta.id}`);
    return c ? `<td style="background:${corCelula(c.rel_mediana)}"><span class="v">${fx(c.rel_mediana)}</span><span class="n">n${c.n}</span></td>`
             : `<td class="vazia">falta</td>`;
  }).join("")}</tr>`).join("");
  return `<h2>Formato × conta</h2><p class="sub">Mediana relativa por célula · n no canto · hachura = teste que falta</p>
    <table class="matriz"><tr><th></th>${E.contas.map(c => `<th>${esc(c.handle)}</th>`).join("")}</tr>${linhas}</table>${notaConfusao(C)}`;
}

function cartaoShort(l, matura = false) {
  const up = l.rel != null && l.rel >= 1;
  return `<a class="thumb ${matura ? "matura" : up ? "up" : ""}" href="https://youtube.com/shorts/${l.video_id}" target="_blank" rel="noopener">
    <img src="${thumb(l.video_id)}" alt="" loading="lazy"><div class="t">${esc(l.titulo)}</div>
    <div><div class="x ${up ? "up" : "down"}">${matura ? "" : fx(l.rel)}</div>
    <div class="c">${matura ? "maturando · " : ""}${esc(handleDe(l.conta))}</div></div></a>`;
}

function blocoGrupo(C) {
  const g = C.grupos.find(x => x.chave === selecionado);
  if (!g) return "";
  const porId = new Map(S.map(l => [l.video_id, l]));
  const medidos = g.video_ids.map(id => porId.get(id)).filter(Boolean).sort((a, b) => b.rel - a.rel);
  const maturando = S.filter(l => l.etiquetas && l.medida.estado === "maturando" && chavesDe(l).includes(g.chave));
  return `<h2>${esc(nomeGrupo(g.chave))}</h2>
    <p class="sub">${medidos.length} medidos · ${maturando.length} em maturação · ordenados pelo relativo à conta</p>
    <div class="shorts">${medidos.map(l => cartaoShort(l)).join("")}${maturando.map(l => cartaoShort(l, true)).join("")}</div>`;
}

async function telaComparar() {
  const C = await api(`/api/comparar?dim=${dim}`);
  if (!C.grupos.some(g => g.chave === selecionado)) selecionado = C.grupos[0]?.chave ?? null;
  const aviso = dim === "tema" ? " · um Short entra em todos os seus temas: os grupos não somam o total" : "";
  $("#tela").innerHTML = `<header><div><h1>O que está funcionando <em>— ${TITULOS[dim]}</em></h1>
    <p class="sub">Views aos 7 dias ÷ mediana da própria conta · ${C.medidos} Shorts medidos · ${C.maturando} em maturação${aviso}</p></div>
    <div class="seg">${Object.keys(TITULOS).map(d => `<button data-dim="${d}" class="${d === dim ? "ativo" : ""}">${d[0].toUpperCase() + d.slice(1)}</button>`).join("")}</div></header>
    ${tabelaGrupos(C)}
    <div class="baixo"><div class="card">${blocoMatriz(C)}</div><div class="card">${blocoGrupo(C)}</div></div>`;
  $$(".seg button").forEach(b => { b.onclick = () => { dim = b.dataset.dim; selecionado = null; desenhar(); }; });
  $$(".linha[data-chave]").forEach(el => { el.onclick = () => { selecionado = el.dataset.chave; desenhar(); }; });
}
TELAS.comparar = telaComparar;
