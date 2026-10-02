"use strict";
// Player customizado do painel do candidato. Toca uma FAIXA — f = { src, classe, inicio, fim,
// preroll, fimDoArquivo, nome } — que é de um de dois tipos (montadas em episodio.js):
// - o trecho do vídeo original (16:9): [c.inicio, c.fim] dentro do episódio inteiro, com
//   "ouvir antes" (preroll) — a barra cobre só o trecho, nunca os 25 min do episódio;
// - o Short renderizado (9:16): 0 → duração do arquivo, sem preroll — o Short já é o corte
//   final, não há "antes" pra ouvir. A duração real só se sabe nos metadados (fimDoArquivo).
// Um player só pros dois: a velocidade salva, o play/pausa e o teclado valem igual em ambos.
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
// comeu o começo da frase. Só o início muda — o fim do trecho (f.fim) nunca se move.
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
// Preroll efetivo da faixa: o Short nunca tem, mesmo que o trecho tenha um salvo.
const prerollDa = f => (f.preroll ? prerollSalvo() : 0);

// Faixa tocável [ini, f.fim] com N segundos de preroll — clampada em 0 pra não pedir tempo
// antes do início do episódio. durTotal é o que a barra de progresso cobre (preroll + duração
// real da faixa); a duração sem preroll continua sendo o rótulo de tempo total ("… / 0:42").
function faixaComPreroll(f, segundos) {
  const preOffset = Math.min(segundos, f.inicio);
  return { ini: f.inicio - preOffset, preOffset, durTotal: (f.fim - f.inicio) + preOffset };
}

function htmlPlayer(f) {
  const { durTotal } = faixaComPreroll(f, prerollDa(f));
  const preroll = f.preroll ? `<div class="seg preroll" role="group" aria-label="Ouvir antes">
      ${PREROLLS.map(s => `<button type="button" data-preroll="${s}" aria-pressed="false">${esc(NOMES_PREROLL[s])}</button>`).join("")}
    </div>` : "";
  return `<div class="player">
    <video class="${esc(f.classe)}" preload="metadata" playsinline src="${esc(f.src)}"></video>
    <div class="player-ctrl">
      <button class="play" type="button" aria-label="Tocar ${esc(f.nome)}">▶</button>
      <div class="barra-wrap">
        <input class="barra" type="range" min="0" max="${durTotal.toFixed(1)}" step="0.1" value="0" aria-label="Posição no ${esc(f.nome)}">
        <div class="barra-pre" aria-hidden="true" hidden></div>
        <div class="barra-marca" aria-hidden="true" hidden></div>
      </div>
      <span class="tempo">0:00 / ${tempo(f.fim - f.inicio)}</span>
    </div>
    <div class="seg vel" role="group" aria-label="Velocidade">
      ${VELOCIDADES.map(v => `<button type="button" data-vel="${v}" aria-pressed="false">${String(v).replace(".", ",")}×</button>`).join("")}
    </div>
    ${preroll}
  </div>`;
}

// Loop de rAF do player atual — cancelado no início de ligarVideo() a cada redesenho do painel
// (blocoEpisodio troca o HTML inteiro a cada troca de candidato/decisão) e também se o próprio
// <video> saiu do DOM (troca de tela), pra nunca deixar um loop órfão rodando pra sempre.
let rafPlayer = null;

function marcarAtivo(seg, atributo, valor) {
  $$(`[data-${atributo}]`, seg).forEach(b => {
    const ativo = Number(b.dataset[atributo]) === valor;
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

// Rótulo de tempo sempre relativo ao início real da faixa (não ao início com preroll):
// negativo enquanto toca o preroll ("-0:03 / 0:42"), 0:00 no início real do trecho.
function rotuloTempo(relTrecho, dur) {
  return `${relTrecho < 0 ? "-" : ""}${tempo(Math.abs(relTrecho))} / ${tempo(dur)}`;
}

// O fragmento #t= só posiciona o vídeo na carga inicial; depois disso o navegador não respeita
// mais o recorte (pausar/arrastar a barra escapa do trecho) — por isso o play/pausa, a barra e
// a velocidade são tudo customizado aqui, sem <video controls> nativo. onplay reimpõe o início
// (dar play fora da faixa volta pro início); ontimeupdate pausa e trava no fim ao alcançá-lo.
// ini e durTotal ficam em `let`, fechados pelos handlers: mudam com o "ouvir antes" e, no Short,
// quando os metadados trazem a duração real — sem recriar o <video> nem o resto do player.
function ligarVideo(raiz, f) {
  const player = $(".player", raiz);
  const v = $("video", player);
  const btnPlay = $(".play", player);
  const barraWrap = $(".barra-wrap", player);
  const barra = $(".barra", player);
  const tempoEl = $(".tempo", player);
  const segVel = $(".seg.vel", player);
  const segPre = $(".seg.preroll", player);   // null no Short

  if (rafPlayer) cancelAnimationFrame(rafPlayer);

  const vel = velocidadeSalva();
  v.playbackRate = vel;
  v.preservesPitch = true;
  marcarAtivo(segVel, "vel", vel);

  let ini = f.inicio;
  let durTotal = f.fim - f.inicio;
  const atualizarBarra = () => {
    barra.value = Math.min(Math.max(v.currentTime - ini, 0), durTotal).toFixed(1);
    tempoEl.textContent = rotuloTempo(v.currentTime - f.inicio, f.fim - f.inicio);
  };
  const aplicarFaixa = segundos => {
    ({ ini, durTotal } = faixaComPreroll(f, segundos));
    barra.max = durTotal.toFixed(1);
    if (segPre) marcarAtivo(segPre, "preroll", segundos);
    atualizarMarcaPreroll(barraWrap, f.inicio - ini, durTotal);
    atualizarBarra();
  };
  aplicarFaixa(prerollDa(f));

  // Short: o fim provisório (teto) dá lugar à duração do arquivo assim que ela é conhecida.
  if (f.fimDoArquivo) {
    const ajustar = () => {
      if (!Number.isFinite(v.duration)) return;
      f.fim = v.duration;
      aplicarFaixa(0);
    };
    v.onloadedmetadata = ajustar;
    if (v.readyState >= 1) ajustar();
  }

  const loop = () => {
    if (!document.body.contains(v)) { rafPlayer = null; return; }
    if (!v.paused) atualizarBarra();
    rafPlayer = requestAnimationFrame(loop);
  };
  rafPlayer = requestAnimationFrame(loop);

  const alternar = () => { if (v.paused) v.play(); else v.pause(); };
  v.onplay = () => {
    if (v.currentTime < ini || v.currentTime >= f.fim) v.currentTime = ini;
    btnPlay.textContent = "❚❚";
    btnPlay.setAttribute("aria-label", `Pausar ${f.nome}`);
  };
  v.onpause = () => {
    btnPlay.textContent = "▶";
    btnPlay.setAttribute("aria-label", `Tocar ${f.nome}`);
  };
  v.ontimeupdate = () => {
    if (!v.paused && v.currentTime >= f.fim) { v.currentTime = f.fim; v.pause(); }
    atualizarBarra();
  };
  v.onclick = alternar;
  btnPlay.onclick = alternar;

  barra.oninput = () => {
    v.currentTime = ini + Math.min(Math.max(Number(barra.value), 0), durTotal);
    atualizarBarra();
  };

  $$("[data-vel]", segVel).forEach(b => {
    b.onclick = () => {
      const novaVel = Number(b.dataset.vel);
      v.playbackRate = novaVel;
      salvarVelocidade(novaVel);
      marcarAtivo(segVel, "vel", novaVel);
    };
  });

  // Troca de "ouvir antes": recalcula a faixa sem recriar o player. Pausado, reposiciona pro
  // novo início; tocando, só muda a faixa e deixa continuar tocando de onde está.
  if (segPre) $$("[data-preroll]", segPre).forEach(b => {
    b.onclick = () => {
      const segundos = Number(b.dataset.preroll);
      salvarPreroll(segundos);
      aplicarFaixa(segundos);
      if (v.paused) { v.currentTime = ini; atualizarBarra(); }
    };
  });

  // Espaço e ←/→ só quando o foco está no player — não quando está no select/input do motivo
  // de rejeição (ligarPainel vive no mesmo <aside>, e Espaço lá digita espaço num texto livre).
  player.onkeydown = ev => {
    if (ev.target.closest(".motivo") || ["SELECT", "INPUT"].includes(ev.target.tagName)) return;
    if (ev.key === " ") { ev.preventDefault(); alternar(); }
    else if (ev.key === "ArrowLeft") { ev.preventDefault(); v.currentTime = Math.max(ini, v.currentTime - 5); }
    else if (ev.key === "ArrowRight") { ev.preventDefault(); v.currentTime = Math.min(f.fim, v.currentTime + 5); }
  };
}
