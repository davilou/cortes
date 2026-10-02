"use strict";
// Tela Episódios: entrada do link, lista de episódios com as etapas, fila no trilho.
// O detalhe do episódio selecionado é desenhado por blocoEpisodio() (episodio.js, Task 9) —
// enquanto esse arquivo não existe, a chamada é pulada (guarda typeof abaixo).
let P = null;            // /api/producao
let epSel = null;        // id do episódio aberto
const NOMES_ETAPA = { video: "vídeo", legenda: "legenda", sinais: "sinais", momentos: "momentos" };

const temTrabalho = () => !!(P && (P.fila.atual || P.fila.na_fila.length));

function htmlEntrada() {
  const nichos = (E?.nichos ?? []).map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
  const formatos = P.formatos.map(f => `<option value="${esc(f)}">${esc(f)} · ${esc(nomeFormato(f))}</option>`).join("");
  return `<form class="entrada" id="entrada">
    <label>Link do episódio<input class="link" name="link" required placeholder="https://www.youtube.com/watch?v=…"></label>
    <label>Nicho<select name="nicho">${nichos}</select></label>
    <label>Formato<select name="formato">${formatos}</select></label>
    <label>Shorts<select name="n_shorts"><option value="3">3 melhores</option><option value="5" selected>5 melhores</option><option value="10">10 melhores</option></select></label>
    <button class="botao primario">Gerar Shorts</button></form>`;
}

function htmlEtapas(ep) {
  return `<div class="etapas">${Object.entries(ep.etapas).map(([nome, et]) => {
    const cls = { ok: "ok", rodando: "roda", erro: "erro" }[et.situacao] ?? "";
    const rotulo = et.situacao === "erro" ? et.erro : NOMES_ETAPA[nome];
    return `<div class="etapa ${cls}" title="${esc(et.erro ?? et.situacao)}"><i></i>${esc(rotulo)}</div>`;
  }).join("")}</div>`;
}

function htmlEpisodio(ep) {
  const erro = Object.values(ep.etapas).some(et => et.situacao === "erro");
  const dur = ep.duracao_s ? new Date(ep.duracao_s * 1000).toISOString().slice(ep.duracao_s >= 3600 ? 11 : 14, 19) : "";
  const resumo = erro ? `<button class="botao mini" data-tentar="${esc(ep.id)}">tentar de novo</button>`
    : `<b>${ep.n_candidatos || "—"}</b>${ep.n_candidatos ? "candidatos" : "processando"}`;
  return `<div class="ep ${ep.id === epSel ? "sel" : ""}" data-ep="${esc(ep.id)}" tabindex="0" role="button" aria-pressed="${ep.id === epSel}">
    <div class="capa" style="background-image:url(${thumb(ep.id)})"><span>${esc(dur)}</span></div>
    <div><h3>${esc(ep.titulo ?? ep.url)}</h3><p>${esc(ep.canal ?? "")} · ${esc(dataHora(ep.criado_em))}</p></div>
    ${htmlEtapas(ep)}<div class="resumo">${resumo}</div></div>`;
}

function htmlLista() {
  if (!P.episodios.length) return vazio("Nenhum episódio ainda", "Cole o link de um episódio do YouTube acima.");
  return P.episodios.map(htmlEpisodio).join("");
}

// Episódios com trabalho em curso (rodando ou na fila) ou com etapa em erro — é esse número
// que aparece na pílula do trilho, não o total de episódios.
function contarPendencias() {
  return P.episodios.filter(ep => {
    const emErro = Object.values(ep.etapas).some(et => et.situacao === "erro");
    const emFila = P.fila.na_fila.includes(ep.id) || P.fila.atual?.episodio === ep.id;
    return emErro || emFila;
  }).length;
}

function trilhoFila() {
  const f = P?.fila;
  const n = f ? contarPendencias() : 0;
  for (const sel of ["#cont-episodios", "#cont-episodios-m"]) {
    const el = $(sel);
    if (!el) continue;
    el.hidden = !n;
    el.textContent = String(n);
  }
  const el = $("#fila-trilho");
  if (!el || !f) return;
  el.hidden = !(f.atual || f.na_fila.length || f.pausada);
  const atual = f.atual ? `${esc(f.atual.etapa)} · ${esc(P.episodios.find(e => e.id === f.atual.episodio)?.titulo ?? f.atual.episodio)}` : "parada";
  el.innerHTML = f.pausada
    ? `<b>Fila pausada</b><div>${esc(f.pausada)}</div><button class="botao mini" id="retomar">retomar</button>`
    : `<div><b>Fila</b> · ${f.na_fila.length} na fila</div><div>${atual}</div>`;
  const b = $("#retomar");
  if (b) b.onclick = () => post("/api/fila/retomar").then(atualizarProducao).catch(e => avisar(e.message));
}

function ligarLista() {
  $$("[data-ep]").forEach(el => {
    const abrir = () => { epSel = el.dataset.ep; desenhar(); };
    el.onclick = ev => { if (!ev.target.closest("[data-tentar]")) abrir(); };
    el.onkeydown = ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); abrir(); } };
  });
  $$("[data-tentar]").forEach(b => {
    b.onclick = () => post(`/api/episodios/${encodeURIComponent(b.dataset.tentar)}/tentar`)
      .then(atualizarProducao).catch(e => avisar(e.message));
  });
}

let erroProducaoAnterior = null;   // evita repetir o aviso a cada poll de 3s enquanto o erro persiste

function agendarProducao() {
  clearTimeout(atualizarProducao.t);
  atualizarProducao.t = setTimeout(() => { atualizarProducao(); }, 3000);
}

// Atualiza só a lista e a fila (nunca a entrada, pra não perder o que Davi está digitando).
async function atualizarProducao() {
  const situacaoMomentosAntes = epSel && P ? P.episodios.find(e => e.id === epSel)?.etapas.momentos.situacao : undefined;
  try {
    P = await api("/api/producao");
    erroProducaoAnterior = null;
  } catch (e) {
    if (e.message !== erroProducaoAnterior) avisar(e.message);
    erroProducaoAnterior = e.message;
    if (temTrabalho()) agendarProducao();
    return;
  }
  trilhoFila();
  const lista = $("#lista-episodios");
  if (lista) { lista.innerHTML = htmlLista(); ligarLista(); }
  // Quando a etapa `momentos` do episódio aberto muda de situação (ex. rodando → ok), o
  // detalhe precisa aparecer — mas só nesse caso: refazer blocoEpisodio a cada 3s reiniciaria
  // o vídeo tocando.
  const situacaoMomentosDepois = epSel ? P.episodios.find(e => e.id === epSel)?.etapas.momentos.situacao : undefined;
  if (epSel && situacaoMomentosDepois !== undefined && situacaoMomentosDepois !== situacaoMomentosAntes
      && typeof blocoEpisodio === "function") {
    await blocoEpisodio(epSel, desenhar.n);
  }
  if (temTrabalho()) agendarProducao();
}

async function telaEpisodios(meu) {
  if (!E) await carregar();
  P = await api("/api/producao");
  if (meu !== desenhar.n) return;
  if (!epSel && P.episodios.length) epSel = P.episodios[0].id;
  $("#tela").innerHTML = `<header><div><h1>Produção <em>— do episódio ao Short</em></h1>
    <p class="sub">Cole o link do episódio. O app baixa vídeo e legenda do YouTube e acha os momentos.</p></div></header>
    ${htmlEntrada()}<div class="episodios" id="lista-episodios">${htmlLista()}</div><div id="detalhe-episodio"></div>`;
  trilhoFila();
  ligarLista();
  $("#entrada").onsubmit = async ev => {
    ev.preventDefault();
    const b = ev.submitter; b.disabled = true;
    const d = Object.fromEntries(new FormData(ev.target));
    try {
      const r = await post("/api/episodios", { ...d, n_shorts: Number(d.n_shorts) });
      epSel = r.id; ev.target.reset(); await desenhar();
    } catch (e) { avisar(e.message); } finally { b.disabled = false; }
  };
  if (epSel && typeof blocoEpisodio === "function") await blocoEpisodio(epSel, meu);
  if (temTrabalho()) agendarProducao();
}
TELAS.episodios = telaEpisodios;
