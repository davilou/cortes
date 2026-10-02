"use strict";
// Tela Episódios: entrada do link, lista de episódios com as etapas, fila no trilho.
// O detalhe do episódio selecionado é desenhado por blocoEpisodio() (episodio.js, Task 9) —
// enquanto esse arquivo não existe, a chamada é pulada (guarda typeof abaixo). O polling
// (atualizarProducao) é disparado uma vez na subida (inicio.js), não só quando esta tela está
// aberta — é assim que a pílula/fila do trilho aparece em qualquer tela.
let P = null;            // /api/producao
let epSel = null;        // id do episódio aberto
const NOMES_ETAPA = { video: "vídeo", legenda: "legenda", sinais: "sinais", momentos: "momentos" };
// Formato do que "Mostrar transcrição" copia: linha de tempo, depois o texto do bloco.
const DICA_TRANSCRICAO = "Use quando o YouTube bloquear a legenda: copie em 'Mostrar transcrição' com os tempos.";
const EXEMPLO_TRANSCRICAO = "0:10\nFala galera, tudo beleza pessoal?\n0:18\nHoje tem, hoje o bicho vai pegar…";

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
    <button class="botao primario">Gerar Shorts</button>
    <details class="colar-transcricao"><summary>Colar transcrição do YouTube (opcional)</summary>
      <p>${esc(DICA_TRANSCRICAO)}</p>
      <textarea name="transcricao" rows="8" spellcheck="false" aria-label="Transcrição do YouTube com os tempos"
        placeholder="${esc(EXEMPLO_TRANSCRICAO)}"></textarea>
    </details></form>`;
}

// Corpo do POST /api/episodios: `transcricao` só vai se tiver algo além de espaço — vazia
// não é "sem transcrição" pro servidor (ele recusaria com "sem palavras").
function pedidoNovoEpisodio(form) {
  const { transcricao, ...d } = Object.fromEntries(new FormData(form));
  const corpo = { ...d, n_shorts: Number(d.n_shorts) };
  if (transcricao.trim()) corpo.transcricao = transcricao;
  return corpo;
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
  // Legenda em erro (ex.: 429) num episódio que já está na produção: a entrada recusaria o
  // link repetido, então colar a transcrição mora aqui, ao lado do "tentar de novo".
  const podeColar = ep.etapas.legenda?.situacao === "erro" && ep.fonte_legenda !== "colada";
  const colar = podeColar ? `<button class="botao mini" data-colar="${esc(ep.id)}">colar transcrição</button>` : "";
  const dur = duracaoFmt(ep.duracao_s);
  const colada = ep.fonte_legenda === "colada" ? `<span class="chip colada">transcrição colada</span>` : "";
  const resumo = erroEtapa
    ? `<span class="erro-txt" title="${esc(erroEtapa)}">${esc(erroEtapa)}</span><button class="botao mini" data-tentar="${esc(ep.id)}">tentar de novo</button>${colar}`
    : `<b>${ep.n_candidatos || "—"}</b>${ep.n_candidatos ? "candidatos" : "processando"}`;
  return `<div class="ep ${ep.id === epSel ? "sel" : ""}">
    <div class="ep-abrir" data-ep="${esc(ep.id)}" tabindex="0" role="button" aria-pressed="${ep.id === epSel}">
      <div class="capa" style="background-image:url('${thumb(ep.id)}')"><span>${esc(dur)}</span></div>
      <div><h3>${esc(ep.titulo ?? ep.url)}</h3><p>${esc(ep.canal ?? "")} · ${esc(dataHora(ep.criado_em))}</p>${colada}</div>
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
  $(`[data-ep="${CSS.escape(id)}"]`)?.focus();
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
  $$("[data-colar]").forEach(b => { b.onclick = () => abrirColar(b.dataset.colar, b); });
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

// Gaveta "colar transcrição" — reusa a gaveta da tela Shorts (#camada, fecharGaveta e o
// estado aoTeclarGaveta/gatilhoGaveta de shorts.js). O polling pode redesenhar a lista com a
// gaveta aberta e o botão de origem some do DOM: o foco volta pelo seletor, não pela referência.
function formColar(ep) {
  return `<div class="fundo"></div><form class="gaveta" role="dialog" aria-modal="true" aria-labelledby="gaveta-titulo">
    <h2 id="gaveta-titulo">Colar transcrição</h2>
    <p class="dica">${esc(ep.titulo ?? ep.id)}</p>
    <label>Transcrição do YouTube com os tempos<textarea name="transcricao" rows="14" required spellcheck="false"
      placeholder="${esc(EXEMPLO_TRANSCRICAO)}"></textarea></label>
    <p class="dica">${esc(DICA_TRANSCRICAO)}</p>
    <p class="dica" id="colar-aviso" role="status" hidden>Há texto colado: use Cancelar para descartar ou Enviar.</p>
    <div class="acoes"><button type="button" class="botao" id="cancelar">Cancelar</button><button type="submit" class="botao primario" id="gaveta-enviar">Enviar</button></div></form>`;
}

function abrirColar(id, gatilho) {
  const ep = P.episodios.find(e => e.id === id);
  if (!ep) return;
  fecharGaveta();
  const fechar = (alvo = `[data-colar="${CSS.escape(id)}"]`) => { fecharGaveta(); $(alvo)?.focus(); };
  gatilhoGaveta = gatilho;
  const camada = $("#camada");
  camada.innerHTML = formColar(ep);
  const form = $("form", camada), enviar = $("#gaveta-enviar", camada);
  // Escape e clique no fundo são fáceis de acertar sem querer: com texto colado (2 h de
  // transcrição) eles não fecham — só Cancelar ou Enviar. O aviso diz isso.
  const fecharSeVazio = () => {
    if (!form.transcricao.value.trim()) { fechar(); return; }
    $("#colar-aviso", camada).hidden = false;
    form.transcricao.focus();
  };
  aoTeclarGaveta = ev => { if (ev.key === "Escape") fecharSeVazio(); };
  document.addEventListener("keydown", aoTeclarGaveta);
  $(".fundo", camada).onclick = fecharSeVazio;
  $("#cancelar", camada).onclick = () => fechar();
  form.transcricao.focus();
  form.onsubmit = async ev => {
    ev.preventDefault();
    enviar.disabled = true;
    try {
      const r = await post(`/api/episodios/${encodeURIComponent(id)}/transcricao`, { transcricao: form.transcricao.value });
      if (!r.enfileirado) avisar("transcrição salva; o episódio não estava em erro, nada foi reenfileirado");
      gatilhoGaveta = null;   // o botão some na lista nova: o foco vai pra linha do episódio
      fechar(`[data-ep="${CSS.escape(id)}"]`);
      await atualizarProducao();
      $(`[data-ep="${CSS.escape(id)}"]`)?.focus();
    } catch (e) {
      avisar(e.message);
    } finally {
      enviar.disabled = false;
    }
  };
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
  const anteriorP = P;   // snapshot de antes do fetch — comparado contra o P novo pelo epSel de AGORA
  try {
    P = await api("/api/producao");
    trilhoFila();
    const lista = $("#lista-episodios");
    if (lista) { lista.innerHTML = htmlLista(); ligarLista(); }
    // Comparar a ASSINATURA inteira de `etapas` (não só a situação de `momentos`): qualquer
    // etapa que mude — inclusive uma que vire erro — precisa reabrir o detalhe. `antes`/`depois`
    // leem epSel só agora, depois do await: se Davi trocou de episódio enquanto o fetch estava
    // em voo, a comparação é sobre o episódio selecionado na resposta, não o de quando ela saiu.
    const antes = epSel ? JSON.stringify(anteriorP?.episodios.find(e => e.id === epSel)?.etapas) : undefined;
    const depois = epSel ? JSON.stringify(P.episodios.find(e => e.id === epSel)?.etapas) : undefined;
    // Refazer blocoEpisodio a cada 3s reiniciaria o vídeo tocando — só dispara quando a
    // assinatura muda de fato, e só se a tela Episódios estiver com o detalhe montado.
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
    try {
      const r = await post("/api/episodios", pedidoNovoEpisodio(ev.target));
      epSel = r.id; ev.target.reset(); $(".colar-transcricao", ev.target).open = false; await desenhar();
    } catch (e) { avisar(e.message); } finally { b.disabled = false; }
  };
  if (epSel) await mostrarDetalhe(epSel, meu);
  if (devoContinuarPolling()) agendarProducao();
}
TELAS.episodios = telaEpisodios;
