"use strict";
// Tela Comparar: grupos com strip plot, matriz formato × conta, Shorts do grupo selecionado.
let dim = "formato";
let selecionado = null;
const TITULOS = { formato: "por formato", conta: "por conta", tema: "por tema", podcast: "por podcast" };

// escala log de 0,1× a 10×: "metade" e "dobro" ficam à mesma distância de 1×. Devolve 0–100,
// pensado para "left:N%" — porcentagem não distorce (ao contrário de um viewBox de SVG com
// preserveAspectRatio="none" numa largura que não bate com o pixel real da célula).
const pctEixo = v => (Math.log10(Math.min(10, Math.max(.1, v))) + 1) / 2 * 100;

function eixo() {
  const marcas = [[.2, "0,2×"], [.5, "0,5×"], [1, "1×"], [2, "2×"], [5, "5×"]];
  return `<div class="eixo">${marcas.map(([t, r]) => `<span style="left:${pctEixo(t)}%">${r}</span>`).join("")}</div>`;
}

// Pontos fora de 0,1×–10× são clampados para caber na faixa; em vez de escondê-los no mesmo
// lugar que um valor dentro da faixa, marca com uma ponta triangular na borda — clamping visível.
// Estimado (views_7d interpolado com folga maior que o normal, metodo.views_7d) vem vazado —
// contorno em vez de preenchido — pra não se misturar visualmente com uma medida direta.
function ponto(v, estimado, i) {
  const esquerda = pctEixo(v), topo = 17 + ((i % 3) - 1) * 5;
  const titulo = esc((estimado ? "≈ estimado: " : "") + fx(v));
  const est = estimado ? " est" : "";
  if (v < .1) return `<i class="ponta esq down${est}" style="left:${esquerda}%;top:${topo}px" title="${titulo}"></i>`;
  if (v > 10) return `<i class="ponta dir up${est}" style="left:${esquerda}%;top:${topo}px" title="${titulo}"></i>`;
  return `<i class="pt-dot ${v >= 1 ? "up" : "down"}${est}" style="left:${esquerda}%;top:${topo}px" title="${titulo}"></i>`;
}

function strip(rels, estimados, med) {
  const grade = [.2, .5, 1, 2, 5].map(t => `<i class="grade" style="left:${pctEixo(t)}%"></i>`).join("");
  const pontos = rels.map((v, i) => ponto(v, estimados[i], i)).join("");
  return `<div class="strip">${grade}<i class="base" style="left:${pctEixo(1)}%"></i>${pontos}
    <i class="med" style="left:${pctEixo(med)}%"></i></div>`;
}

function nomeGrupo(k) {
  return dim === "formato" ? nomeFormato(k) : dim === "conta" ? handleDe(k) : k;
}
function subGrupo(k) {
  if (dim === "formato") {
    const obs = E.formatos[k]?.obs;
    return obs ? `${k} · ${obs}` : k;
  }
  if (dim === "conta") return E.contas.find(c => c.id === k)?.nicho ?? "";
  return "";
}
function chavesDe(l) {
  const e = l.etiquetas;
  return dim === "formato" ? [e.formato] : dim === "conta" ? [l.conta] : dim === "tema" ? e.temas : [e.podcast];
}

function linhaGrupo(g) {
  const sel = g.chave === selecionado;
  const insc = g.insc_por_mil == null ? "—" : g.insc_por_mil.toFixed(1).replace(".", ",");
  const notaEst = g.n_estimados > 0 ? `${g.n_estimados} estimado${g.n_estimados > 1 ? "s" : ""}` : "";
  const sub = [subGrupo(g.chave), notaEst].filter(Boolean).join(" · ");
  return `<div class="linha ${sel ? "sel" : ""}" data-chave="${esc(g.chave)}" tabindex="0" role="button" aria-pressed="${sel}">
    <div class="nome">${esc(nomeGrupo(g.chave))}${sub ? `<small>${esc(sub)}</small>` : ""}${g.pista ? '<span class="selo">pista · n&lt;5</span>' : ""}</div>
    <div class="num">${g.n}</div>
    <div class="rel ${g.rel_mediana >= 1 ? "up" : "down"}">${fx(g.rel_mediana)}</div>
    <div>${strip(g.rels, g.estimados, g.rel_mediana)}</div>
    <div class="num">${pct(g.pct_mediana)}</div>
    <div class="num">${insc}</div></div>`;
}

function tabelaGrupos(C) {
  if (!C.grupos.length) return vazio("Nenhum Short medido ainda", "Ligue os Shorts na tela Shorts. Cada um entra aqui 7 dias depois de publicado, quando a conta tiver 3 Shorts medidos.");
  return `<div class="legenda"><span><i class="pt" style="background:var(--up)"></i>acima da base da conta</span>
    <span><i class="pt" style="background:var(--down)"></i>abaixo</span><span>│ tracejado = 1× (mediana da conta)</span>
    <span>▮ traço claro = mediana do grupo</span><span>○ estimado</span></div>
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
    <div class="matriz-rolagem"><table class="matriz"><tr><th></th>${E.contas.map(c => `<th>${esc(c.handle)}</th>`).join("")}</tr>${linhas}</table></div>${notaConfusao(C)}`;
}

function cartaoShort(l, matura = false) {
  const up = l.rel != null && l.rel >= 1;
  const estimado = l.medida.estado === "estimado";
  return `<a class="thumb ${matura ? "matura" : up ? "up" : ""}" href="https://youtube.com/shorts/${esc(l.video_id)}" target="_blank" rel="noopener">
    <img src="${thumb(l.video_id)}" alt="" loading="lazy"><div class="t">${esc(l.titulo)}</div>
    <div><div class="x ${up ? "up" : "down"}">${matura ? "" : (estimado ? "≈" : "") + fx(l.rel)}</div>
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

async function telaComparar(meu) {
  const C = await api(`/api/comparar?dim=${dim}`);
  if (meu !== desenhar.n) return;   // uma renderização mais nova já começou: não pisa nela
  if (!C.grupos.some(g => g.chave === selecionado)) selecionado = C.grupos[0]?.chave ?? null;
  const aviso = dim === "tema" ? " · um Short entra em todos os seus temas: os grupos não somam o total" : "";
  $("#tela").innerHTML = `<header><div><h1>O que está funcionando <em>— ${TITULOS[dim]}</em></h1>
    <p class="sub">Views aos 7 dias ÷ mediana da própria conta · ${C.medidos} Shorts medidos · ${C.maturando} em maturação${aviso}</p></div>
    <div class="seg">${Object.keys(TITULOS).map(d => `<button data-dim="${d}" class="${d === dim ? "ativo" : ""}" aria-pressed="${d === dim}">${d[0].toUpperCase() + d.slice(1)}</button>`).join("")}</div></header>
    ${tabelaGrupos(C)}
    <div class="baixo"><div class="card">${blocoMatriz(C)}</div><div class="card">${blocoGrupo(C)}</div></div>`;
  $$(".seg button").forEach(b => { b.onclick = () => { dim = b.dataset.dim; selecionado = null; desenhar(); }; });
  $$(".linha[data-chave]").forEach(el => {
    const escolher = () => { selecionado = el.dataset.chave; desenhar(); };
    el.onclick = escolher;
    el.onkeydown = e => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); escolher(); }
    };
  });
}
TELAS.comparar = telaComparar;
