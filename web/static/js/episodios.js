"use strict";
// Tela Episódios: entrada do link, lista de episódios com as etapas, fila no trilho.
// O detalhe do episódio selecionado é desenhado por blocoEpisodio() (episodio.js, Task 9) —
// enquanto esse arquivo não existe, a chamada é pulada (guarda typeof abaixo). O polling
// (atualizarProducao) é disparado uma vez na subida (inicio.js), não só quando esta tela está
// aberta — é assim que a pílula/fila do trilho aparece em qualquer tela.
let P = null;            // /api/producao
let epSel = null;        // id do episódio aberto
const NOMES_ETAPA = { video: "vídeo", legenda: "legenda", sinais: "sinais", momentos: "momentos" };

function duracaoFmt(s) {
  if (!s) return "";
  const total = Math.round(s);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const seg = total % 60;
  const ss = String(seg).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

// Continua o polling enquanto houver algo rodando/na fila — mas não enquanto a fila está
// pausada: nada muda até Davi clicar "retomar", então insistir a cada 3s não serve de nada.
function devoContinuarPolling() {
  return !!(P && (P.fila.atual || P.fila.na_fila.length) && !P.fila.pausada);
}

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
    const rotulo = et.situacao === "erro" ? "erro" : NOMES_ETAPA[nome];
    return `<div class="etapa ${cls}" title="${esc(et.erro ?? et.situacao)}"><i></i>${esc(rotulo)}</div>`;
  }).join("")}</div>`;
}

function htmlEpisodio(ep) {
  const erroEtapa = Object.values(ep.etapas).find(et => et.situacao === "erro")?.erro;
  const dur = duracaoFmt(ep.duracao_s);
  const resumo = erroEtapa
    ? `<span class="erro-txt" title="${esc(erroEtapa)}">${esc(erroEtapa)}</span><button class="botao mini" data-tentar="${esc(ep.id)}">tentar de novo</button>`
    : `<b>${ep.n_candidatos || "—"}</b>${ep.n_candidatos ? "candidatos" : "processando"}`;
  return `<div class="ep ${ep.id === epSel ? "sel" : ""}">
    <div class="ep-abrir" data-ep="${esc(ep.id)}" tabindex="0" role="button" aria-pressed="${ep.id === epSel}">
      <div class="capa" style="background-image:url('${thumb(ep.id)}')"><span>${esc(dur)}</span></div>
      <div><h3>${esc(ep.titulo ?? ep.url)}</h3><p>${esc(ep.canal ?? "")} · ${esc(dataHora(ep.criado_em))}</p></div>
    </div>
    ${htmlEtapas(ep)}<div class="resumo">${resumo}</div></div>`;
}

// Episódio cujo estado.json não deu pra ler (spec: {"id", "erro"}, sem `etapas`) — ainda
// aparece na lista e pode ser selecionado (pra mostrar o erro), só não tem barras de etapa.
function htmlEpisodioQuebrado(ep) {
  return `<div class="ep quebrado">
    <div class="ep-abrir" data-ep="${esc(ep.id)}" tabindex="0" role="button" aria-pressed="${ep.id === epSel}">
      <div class="capa" style="background-image:url('${thumb(ep.id)}')"></div>
      <div><h3>${esc(ep.id)}</h3><p class="erro-txt" title="${esc(ep.erro)}">${esc(ep.erro)}</p></div>
    </div>
  </div>`;
}

function htmlLista() {
  if (!P.episodios.length) return vazio("Nenhum episódio ainda", "Cole o link de um episódio do YouTube acima.");
  return P.episodios.map(ep => "erro" in ep ? htmlEpisodioQuebrado(ep) : htmlEpisodio(ep)).join("");
}

// Episódios com trabalho em curso (rodando ou na fila), com etapa em erro, ou ilegíveis —
// é esse número que aparece na pílula do trilho, não o total de episódios.
function contarPendencias() {
  return P.episodios.filter(ep => {
    if ("erro" in ep) return true;
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
  if (f.pausada) {
    const motivo = f.pausada.replace(/^fila pausada:\s*/i, "");
    el.innerHTML = `<b>Fila pausada</b><div>${esc(motivo)}</div><button class="botao mini" id="retomar">retomar</button>`;
    const b = $("#retomar");
    if (b) b.onclick = () => {
      b.disabled = true;
      post("/api/fila/retomar").then(atualizarProducao).catch(e => avisar(e.message)).finally(() => { b.disabled = false; });
    };
    return;
  }
  const atual = f.atual ? `${esc(f.atual.etapa)} · ${esc(P.episodios.find(e => e.id === f.atual.episodio)?.titulo ?? f.atual.episodio)}` : "parada";
  el.innerHTML = `<div><b>Fila</b> · ${f.na_fila.length} na fila</div><div>${atual}</div>`;
}

// Mostra o detalhe do episódio selecionado: blocoEpisodio() pros que estão ok (episodio.js,
// Task 9) ou a mensagem de erro pros ilegíveis — nunca os dois.
async function mostrarDetalhe(id, meu) {
  const ep = P.episodios.find(e => e.id === id);
  if (!ep) return;
  if ("erro" in ep) { detalheQuebrado(ep); return; }
  if (typeof blocoEpisodio === "function") await blocoEpisodio(id, meu);
}

function detalheQuebrado(ep) {
  const el = $("#detalhe-episodio");
  if (el) el.innerHTML = `<div class="detalhe-erro"><h2>Episódio ilegível</h2><p>${esc(ep.erro)}</p></div>`;
}

// Troca o episódio selecionado sem re-renderizar a tela inteira (desenhar() perderia o que
// Davi está digitando na entrada): só a lista e o detalhe, com o foco devolvido à linha aberta.
async function selecionarEpisodio(id) {
  epSel = id;
  if (typeof candSel !== "undefined") candSel = null;
  const lista = $("#lista-episodios");
  if (lista) { lista.innerHTML = htmlLista(); ligarLista(); }
  await mostrarDetalhe(id, desenhar.n);
  $(`[data-ep="${id}"]`)?.focus();
  if (devoContinuarPolling()) agendarProducao();
}

function ligarLista() {
  $$("[data-ep]").forEach(el => {
    const abrir = () => selecionarEpisodio(el.dataset.ep).catch(e => avisar(e.message));
    el.onclick = abrir;
    // O alvo pode ser este próprio elemento (ele é o role=button) — um filho não entra aqui
    // porque "tentar de novo" é irmão, nunca descendente, do role=button (ARIA não aninha
    // interativo dentro de interativo).
    el.onkeydown = ev => {
      if (ev.target !== el) return;
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); abrir(); }
    };
  });
  $$("[data-tentar]").forEach(b => {
    b.onclick = () => {
      b.disabled = true;
      post(`/api/episodios/${encodeURIComponent(b.dataset.tentar)}/tentar`)
        .then(atualizarProducao)
        .catch(e => avisar(e.message))
        .finally(() => { b.disabled = false; });
    };
  });
}

let erroProducaoAnterior = null;   // evita repetir o aviso a cada poll de 3s enquanto o erro persiste

function agendarProducao() {
  clearTimeout(atualizarProducao.t);
  atualizarProducao.t = setTimeout(() => { atualizarProducao(); }, 3000);
}

// Atualiza a fila do trilho (em qualquer tela) e, se a tela Episódios estiver aberta, a lista
// e o detalhe — nunca a entrada, pra não perder o que Davi está digitando. Chamado uma vez na
// subida (inicio.js) e depois se reagenda sozinho enquanto houver trabalho.
async function atualizarProducao() {
  const antes = epSel ? P?.episodios.find(e => e.id === epSel)?.etapas?.momentos?.situacao : undefined;
  try {
    P = await api("/api/producao");
    trilhoFila();
    const lista = $("#lista-episodios");
    if (lista) { lista.innerHTML = htmlLista(); ligarLista(); }
    // Quando a etapa `momentos` do episódio aberto muda de situação (ex. rodando → ok), o
    // detalhe precisa aparecer — mas só nesse caso: refazer blocoEpisodio a cada 3s reiniciaria
    // o vídeo tocando. E só se a tela Episódios estiver com o detalhe montado.
    const depois = epSel ? P.episodios.find(e => e.id === epSel)?.etapas?.momentos?.situacao : undefined;
    if (epSel && depois !== undefined && depois !== antes && $("#detalhe-episodio")) {
      await mostrarDetalhe(epSel, desenhar.n);
    }
    erroProducaoAnterior = null;
  } catch (e) {
    if (e.message !== erroProducaoAnterior) avisar(e.message);
    erroProducaoAnterior = e.message;
  } finally {
    if (devoContinuarPolling()) agendarProducao();
  }
}

async function telaEpisodios(meu) {
  if (!E) await carregar();
  P = await api("/api/producao");
  if (meu !== desenhar.n) return;
  if (!epSel && P.episodios.length) epSel = P.episodios.find(e => !("erro" in e))?.id ?? null;
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
  if (epSel) await mostrarDetalhe(epSel, meu);
  if (devoContinuarPolling()) agendarProducao();
}
TELAS.episodios = telaEpisodios;
