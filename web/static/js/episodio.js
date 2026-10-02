"use strict";
// Detalhe do episódio: candidatos (nota 0–10), painel com o trecho tocando, rubrica, justificativa,
// tags e aprovar/rejeitar. No plano A ainda não há Shorts renderizados: o trecho toca do vídeo
// original (16:9) via /api/episodios/{id}/video — o fragmento #t=início,fim é só uma dica inicial
// pro navegador; quem garante o recorte de verdade (não passar do início, parar no fim) é o
// listener de timeupdate em ligarVideo(), porque o fragmento #t= não é respeitado de forma
// confiável depois que o usuário pausa/retoma ou arrasta a barra.
let candSel = 0;
const NOMES_RUBRICA = { gancho_3s: "Gancho 3 s", autocontido: "Autocontido", espanto: "Espanto",
  historia_ou_virada: "História/virada", fechamento: "Fechamento" };
const nota10 = n => (n / 10).toFixed(1).replace(".", ",");
// notas vão de 1 a 5: a barra usa 0%–100% nos extremos (1 → 0%, 5 → 100%), não um múltiplo de n.
const rubPct = n => (n == null ? 0 : Math.max(0, (n - 1) * 25));
function tempo(s) {
  const iso = new Date(s * 1000).toISOString();
  // h:mm:ss sem zero à esquerda na hora (1:23:45, não 01:23:45); abaixo de 1h fica mm:ss.
  return s >= 3600 ? iso.slice(11, 19).replace(/^0/, "") : iso.slice(14, 19);
}

function htmlCandidatos(D) {
  return `<div class="candidatos">
    <div class="cand cab"><span>Nota</span><span>Início</span><span>Dur.</span>
      <span>Candidato<span class="cand-justif-extra"> e justificativa</span></span><span></span></div>
    ${D.candidatos.map(c => `<div class="cand ${c.indice === candSel ? "sel" : ""}" data-cand="${c.indice}" tabindex="0" role="button" aria-pressed="${c.indice === candSel}">
      <span class="n ${c.nota_final >= 80 ? "up" : ""}">${nota10(c.nota_final)}</span>
      <span class="num">${tempo(c.inicio)}</span><span class="num">${tempo(c.fim - c.inicio)}</span>
      <div><div class="t">${esc(c.titulo)}</div><div class="j">${esc(c.justificativa)}</div></div>
      <span class="decisao ${esc(c.decisao ?? "")}"${c.decisao ? ` title="${esc(c.decisao)}" aria-label="${esc(c.decisao)}"` : ""}>${c.decisao ? esc(c.decisao) : ""}</span></div>`).join("")}</div>`;
}

const VELOCIDADES = [1, 1.25, 1.5, 2];
const CHAVE_VELOCIDADE = "cortes_velocidade";

function velocidadeSalva() {
  try {
    const v = Number(localStorage.getItem(CHAVE_VELOCIDADE));
    return VELOCIDADES.includes(v) ? v : 1;
  } catch { return 1; }
}
function salvarVelocidade(v) {
  try { localStorage.setItem(CHAVE_VELOCIDADE, String(v)); } catch { /* localStorage indisponível: segue só na sessão */ }
}

// "Ouvir antes": estende o início tocável pra trás do candidato, pra checar se o corte não
// comeu o começo da frase. Só o início muda — o fim do trecho (c.fim) nunca se move.
const PREROLLS = [0, 3, 5];
const NOMES_PREROLL = { 0: "não", 3: "3 s", 5: "5 s" };
const CHAVE_PREROLL = "cortes_preroll";

function prerollSalvo() {
  try {
    const v = Number(localStorage.getItem(CHAVE_PREROLL));
    return PREROLLS.includes(v) ? v : 0;
  } catch { return 0; }
}
function salvarPreroll(v) {
  try { localStorage.setItem(CHAVE_PREROLL, String(v)); } catch { /* localStorage indisponível: segue só na sessão */ }
}
// Faixa tocável [ini, c.fim] pro candidato com N segundos de preroll — clampada em 0 pra não
// pedir tempo antes do início do episódio. durTotal é o que a barra de progresso cobre
// (preroll + duração real do trecho); dur continua sendo só a duração do trecho, usada no
// rótulo de tempo total ("… / 0:42") independente do preroll escolhido.
function faixaComPreroll(c, segundos) {
  const preOffset = Math.min(segundos, c.inicio);
  return { ini: c.inicio - preOffset, preOffset, durTotal: (c.fim - c.inicio) + preOffset };
}

function htmlPlayer(D, c) {
  const dur = c.fim - c.inicio;
  const { durTotal } = faixaComPreroll(c, prerollSalvo());
  return `<div class="player">
    <video class="trecho" preload="metadata" playsinline src="/api/episodios/${encodeURIComponent(D.id)}/video#t=${c.inicio},${c.fim}"></video>
    <div class="player-ctrl">
      <button class="play" type="button" aria-label="Tocar trecho">▶</button>
      <div class="barra-wrap">
        <input class="barra" type="range" min="0" max="${durTotal.toFixed(1)}" step="0.1" value="0" aria-label="Posição no trecho">
        <div class="barra-pre" aria-hidden="true" hidden></div>
        <div class="barra-marca" aria-hidden="true" hidden></div>
      </div>
      <span class="tempo">0:00 / ${tempo(dur)}</span>
    </div>
    <div class="seg vel" role="group" aria-label="Velocidade">
      ${VELOCIDADES.map(v => `<button type="button" data-vel="${v}" aria-pressed="false">${String(v).replace(".", ",")}×</button>`).join("")}
    </div>
    <div class="seg preroll" role="group" aria-label="Ouvir antes">
      ${PREROLLS.map(s => `<button type="button" data-preroll="${s}" aria-pressed="false">${esc(NOMES_PREROLL[s])}</button>`).join("")}
    </div>
  </div>`;
}

function htmlPainel(D, c) {
  const rub = D.rubrica.map(k => `<div class="rub"><span>${esc(NOMES_RUBRICA[k] ?? k)}</span>
    <div class="b"><i style="width:${rubPct(c.notas[k])}%"></i></div><span>${c.notas[k] ?? "—"}</span></div>`).join("");
  const decidido = c.decisao ? `<p class="sub">Decidido: <b>${esc(c.decisao)}</b></p>` :
    `<div class="decide"><button class="botao mini ok" data-decide="aprovado">✓ Aprovar</button>
      <button class="botao mini no" data-decide="rejeitado">✕ Rejeitar</button></div>
     <div class="motivo" hidden><select id="motivo-cat">${D.motivos.map(m => `<option>${esc(m)}</option>`).join("")}</select>
      <input id="motivo-txt" placeholder="detalhe (opcional)"><button class="botao mini no" id="motivo-ok">Rejeitar</button></div>`;
  return `<aside class="painel">
    ${htmlPlayer(D, c)}
    <h3>${esc(c.titulo)}</h3>
    <p class="meta">${esc(D.titulo ?? D.id)} · ${tempo(c.inicio)} → ${tempo(c.fim)} · nota ${nota10(c.nota_final)}</p>
    <div class="rubrica">${rub}</div>
    <p class="porque">${esc(c.justificativa)}</p>
    <div class="tags">${c.bonus.map(t => `<span class="chip">${esc(t)}</span>`).join("")}${c.penalidades.map(t => `<span class="chip no">${esc(t)}</span>`).join("")}</div>
    ${decidido}</aside>`;
}

// Loop de rAF do player atual — cancelado no início de ligarVideo() a cada redesenho do painel
// (blocoEpisodio troca o HTML inteiro a cada troca de candidato/decisão) e também se o próprio
// <video> saiu do DOM (troca de tela), pra nunca deixar um loop órfão rodando pra sempre.
let rafPlayer = null;

function marcarVelocidadeAtiva(seg, vel) {
  $$("[data-vel]", seg).forEach(b => {
    const ativo = Number(b.dataset.vel) === vel;
    b.classList.toggle("ativo", ativo);
    b.setAttribute("aria-pressed", String(ativo));
  });
}

function marcarPrerollAtiva(seg, segundos) {
  $$("[data-preroll]", seg).forEach(b => {
    const ativo = Number(b.dataset.preroll) === segundos;
    b.classList.toggle("ativo", ativo);
    b.setAttribute("aria-pressed", String(ativo));
  });
}

// Desenha o trecho de preroll na barra (tracejado) e a marca do início real do candidato.
// Sem preroll (preOffset 0) os dois ficam escondidos — não há o que distinguir na barra.
function atualizarMarcaPreroll(wrap, preOffset, durTotal) {
  const pre = $(".barra-pre", wrap);
  const marca = $(".barra-marca", wrap);
  if (preOffset <= 0) { pre.hidden = true; marca.hidden = true; return; }
  const pct = `${(preOffset / durTotal) * 100}%`;
  pre.hidden = false; pre.style.width = pct;
  marca.hidden = false; marca.style.left = pct;
}

// Rótulo de tempo sempre relativo ao início real do candidato (não ao início da faixa com
// preroll): negativo enquanto toca o preroll ("-0:03 / 0:42"), 0:00 no início real do trecho.
function rotuloTempo(relTrecho, dur) {
  return `${relTrecho < 0 ? "-" : ""}${tempo(Math.abs(relTrecho))} / ${tempo(dur)}`;
}

// Mantém a barra de progresso e o relógio sincronizados com v.currentTime via rAF, porque
// arrastar a barra ou tocar não dispara timeupdate com frequência suficiente pra uma barra
// fluida. ini é o início da faixa tocável (c.inicio menos o preroll); durTotal é o que a
// barra cobre (preroll + duração do trecho); dur é só a duração do trecho (rótulo "/ 0:42").
function atualizarBarra(v, c, ini, dur, durTotal, barra, tempoEl) {
  const p = Math.min(Math.max(v.currentTime - ini, 0), durTotal);
  barra.value = p.toFixed(1);
  tempoEl.textContent = rotuloTempo(v.currentTime - c.inicio, dur);
}

// O fragmento #t= só posiciona o vídeo na carga inicial; depois disso o navegador não respeita
// mais o recorte (pausar/arrastar a barra escapa do trecho) — por isso o play/pausa, a barra e
// a velocidade são tudo customizado aqui, sem <video controls> nativo. onplay reimpõe o início
// (dar play fora do trecho volta pro início); ontimeupdate pausa e trava no fim ao alcançá-lo.
function ligarVideo(painel, c) {
  const v = $("video.trecho", painel);
  const dur = c.fim - c.inicio;
  const btnPlay = $(".play", painel);
  const barraWrap = $(".barra-wrap", painel);
  const barra = $(".barra", painel);
  const tempoEl = $(".tempo", painel);
  const segVel = $(".seg.vel", painel);
  const segPre = $(".seg.preroll", painel);

  if (rafPlayer) cancelAnimationFrame(rafPlayer);

  const vel = velocidadeSalva();
  v.playbackRate = vel;
  v.preservesPitch = true;
  marcarVelocidadeAtiva(segVel, vel);

  // ini e durTotal mudam quando o botão "ouvir antes" é clicado (ver abaixo), sem recriar o
  // <video> nem o resto do player — por isso ficam em `let`, fechados sobre pelos handlers.
  let { ini, durTotal } = faixaComPreroll(c, prerollSalvo());
  barra.max = durTotal.toFixed(1);
  marcarPrerollAtiva(segPre, prerollSalvo());
  atualizarMarcaPreroll(barraWrap, c.inicio - ini, durTotal);

  const loop = () => {
    if (!document.body.contains(v)) { rafPlayer = null; return; }
    if (!v.paused) atualizarBarra(v, c, ini, dur, durTotal, barra, tempoEl);
    rafPlayer = requestAnimationFrame(loop);
  };
  rafPlayer = requestAnimationFrame(loop);

  v.onplay = () => {
    if (v.currentTime < ini || v.currentTime >= c.fim) v.currentTime = ini;
    btnPlay.textContent = "❚❚";
    btnPlay.setAttribute("aria-label", "Pausar trecho");
  };
  v.onpause = () => {
    btnPlay.textContent = "▶";
    btnPlay.setAttribute("aria-label", "Tocar trecho");
  };
  v.ontimeupdate = () => {
    if (!v.paused && v.currentTime >= c.fim) { v.currentTime = c.fim; v.pause(); }
    atualizarBarra(v, c, ini, dur, durTotal, barra, tempoEl);
  };
  v.onclick = () => { if (v.paused) v.play(); else v.pause(); };
  btnPlay.onclick = () => { if (v.paused) v.play(); else v.pause(); };

  barra.oninput = () => {
    v.currentTime = ini + Math.min(Math.max(Number(barra.value), 0), durTotal);
    atualizarBarra(v, c, ini, dur, durTotal, barra, tempoEl);
  };

  $$("[data-vel]", segVel).forEach(b => {
    b.onclick = () => {
      const novaVel = Number(b.dataset.vel);
      v.playbackRate = novaVel;
      salvarVelocidade(novaVel);
      marcarVelocidadeAtiva(segVel, novaVel);
    };
  });

  // Troca de "ouvir antes": recalcula a faixa sem recriar o player. Pausado, reposiciona pro
  // novo início; tocando, só muda a faixa e deixa continuar tocando de onde está.
  $$("[data-preroll]", segPre).forEach(b => {
    b.onclick = () => {
      const segundos = Number(b.dataset.preroll);
      salvarPreroll(segundos);
      ({ ini, durTotal } = faixaComPreroll(c, segundos));
      barra.max = durTotal.toFixed(1);
      marcarPrerollAtiva(segPre, segundos);
      atualizarMarcaPreroll(barraWrap, c.inicio - ini, durTotal);
      if (v.paused) v.currentTime = ini;
      atualizarBarra(v, c, ini, dur, durTotal, barra, tempoEl);
    };
  });

  // Espaço e ←/→ só quando o foco está no player — não quando está no select/input do motivo
  // de rejeição (ligarPainel vive no mesmo <aside>, e Espaço lá digita espaço num texto livre).
  $(".player", painel).onkeydown = ev => {
    if (ev.target.closest(".motivo") || ["SELECT", "INPUT"].includes(ev.target.tagName)) return;
    if (ev.key === " ") { ev.preventDefault(); if (v.paused) v.play(); else v.pause(); }
    else if (ev.key === "ArrowLeft") { ev.preventDefault(); v.currentTime = Math.max(ini, v.currentTime - 5); }
    else if (ev.key === "ArrowRight") { ev.preventDefault(); v.currentTime = Math.min(c.fim, v.currentTime + 5); }
  };

  atualizarBarra(v, c, ini, dur, durTotal, barra, tempoEl);
}

// Todos os controles de decisão do painel (aprovar, rejeitar, e os do motivo) — desabilitados
// juntos durante o POST, porque qualquer um que ficasse ativo daria pra disparar uma segunda
// decisão (ou trocar o motivo) enquanto a primeira ainda está em voo.
function controlesDecisao(painel) {
  return [...$$("[data-decide]", painel), $("#motivo-ok", painel), $("#motivo-cat", painel), $("#motivo-txt", painel)]
    .filter(Boolean);
}

async function decidir(D, c, decisao, motivo, botoes) {
  const meu = desenhar.n;   // lido ANTES do await: uma navegação durante o POST não deve redesenhar aqui
  botoes.forEach(b => { b.disabled = true; });
  try {
    await post(`/api/episodios/${encodeURIComponent(D.id)}/candidatos/${c.indice}/decisao`, { decisao, motivo });
    if (meu !== desenhar.n || D.id !== epSel) return;
    await blocoEpisodio(D.id, desenhar.n);
  } catch (e) {
    if (meu !== desenhar.n || D.id !== epSel) return;
    avisar(e.message);
    botoes.forEach(b => { b.disabled = false; });
  }
}

function ligarPainel(D, c) {
  const painel = $(".painel");
  $$("[data-decide]", painel).forEach(b => {
    b.onclick = () => {
      if (b.dataset.decide === "aprovado") {
        decidir(D, c, "aprovado", null, controlesDecisao(painel));
      } else {
        $(".motivo", painel).hidden = false;
        $("#motivo-cat").focus();
      }
    };
  });
  const ok = $("#motivo-ok");
  if (ok) ok.onclick = () => {
    const txt = $("#motivo-txt").value.trim();
    const motivo = txt ? `${$("#motivo-cat").value}: ${txt}` : $("#motivo-cat").value;
    decidir(D, c, "rejeitado", motivo, controlesDecisao(painel));
  };
  ligarVideo(painel, c);
}

async function blocoEpisodio(id, meu) {
  let D;
  try {
    D = await api(`/api/episodios/${encodeURIComponent(id)}`);
  } catch (e) {
    // Falha no fetch não deixa o detalhe antigo (de outro episódio) na tela — limpa e mostra o erro.
    if (meu !== desenhar.n || id !== epSel) return;
    const alvo = $("#detalhe-episodio");
    if (alvo) alvo.innerHTML = `<div class="detalhe-erro"><h2>Não foi possível carregar o episódio</h2><p>${esc(e.message)}</p></div>`;
    return;
  }
  // meu !== desenhar.n descarta resposta de navegação anterior; id !== epSel descarta resposta
  // de um episódio que não é mais o selecionado (ex. troca rápida enquanto o fetch está em voo).
  if (meu !== desenhar.n || id !== epSel) return;
  const alvo = $("#detalhe-episodio");
  if (!alvo) return;
  if (!D.candidatos.length) {
    alvo.innerHTML = Object.values(D.etapas).some(et => et.situacao === "erro") ? ""
      : vazio("Procurando os momentos…", "Os candidatos aparecem aqui quando a etapa 'momentos' terminar.");
    return;
  }
  if (!D.candidatos.some(c => c.indice === candSel)) candSel = D.candidatos[0].indice;
  const c = D.candidatos.find(x => x.indice === candSel);
  alvo.innerHTML = `<div class="detalhe"><div><div class="secao"><h2>Candidatos <em>— ${esc(D.titulo ?? id)}</em></h2>
    <span class="num">${D.candidatos.length} momentos · nota = rubrica do detector (0–10)</span></div>${htmlCandidatos(D)}</div>
    ${htmlPainel(D, c)}</div>`;
  $$("[data-cand]", alvo).forEach(el => {
    const abrir = () => { candSel = Number(el.dataset.cand); blocoEpisodio(id, desenhar.n).catch(e => avisar(e.message)); };
    el.onclick = abrir;
    // Guarda ev.target === el pelo mesmo motivo de ligarLista (episodios.js): um controle
    // aninhado dentro da linha não deve reabrir o mesmo candidato ao receber Enter/Espaço.
    el.onkeydown = ev => {
      if (ev.target !== el) return;
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); abrir(); }
    };
  });
  ligarPainel(D, c);
  // Todo redesenho local (seleção de candidato, decisão) troca o HTML inteiro do detalhe — sem
  // isso o foco cairia pro <body> a cada clique/Enter, quebrando a navegação por teclado.
  $(`[data-cand="${candSel}"]`, alvo)?.focus();
}
