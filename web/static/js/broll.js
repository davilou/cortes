"use strict";
// B-roll do f4 (plano 2026-10-03-broll-automatico): uma linha por deixa com o tipo do clipe
// escolhido pela conferência (vídeo, foto ou "sem visual") e a miniatura (um quadro do vídeo ou a
// foto). "Refazer B-roll" apaga o cache (deixas, candidatos e escolhas) e pede a prévia, que roda
// LLM, buscas e conferência de novo.
const NOMES_MIDIA = { video: "vídeo", foto: "foto" };
const NOMES_TIPO = { literal: "coisa", acontecimento: "cena" };

function htmlClipeBroll(b) {
  // fonte_url só chega http/https (rotas_editor._link); o canal só existe no vídeo do YouTube
  const fonte = b.fonte_url
    ? ` · <a href="${esc(b.fonte_url)}" target="_blank" rel="noopener noreferrer">${
      b.canal ? `fonte: ${esc(b.canal)}` : "fonte"}</a>` : "";
  const mini = b.miniatura
    ? `<img src="${esc(b.miniatura)}" alt="${esc(b.coisa)}" loading="lazy">`
    : `<span class="sem-visual">sem visual</span>`;
  const midia = b.midia ? NOMES_MIDIA[b.midia] ?? b.midia : "sem visual";
  return `<li class="broll-item">${mini}<div>
      <span class="num">${tempo(b.inicio)}–${tempo(b.fim)} · ${esc(NOMES_TIPO[b.tipo] ?? b.tipo)} · ${
        esc(midia)}</span> <strong title="busca: ${esc(b.busca)}">${esc(b.coisa)}</strong>
      <p class="sub" title="${esc(b.motivo)}">${esc(b.motivo)}${fonte}</p></div></li>`;
}

function htmlListaBroll(ed) {
  if (ed.broll_erro) return `<p class="sub erro-txt" title="${esc(ed.broll_erro)}">não deu para
    ler o B-roll: ${esc(ed.broll_erro)}</p>`;
  if (!ed.broll.length) return `<p class="sub">O B-roll aparece quando a prévia ficar pronta.</p>`;
  return `<ul class="broll-lista">${ed.broll.map(htmlClipeBroll).join("")}</ul>`;
}

function htmlBroll(ed) {
  const dis = ed.editavel ? "" : "disabled";
  return `${htmlListaBroll(ed)}
    <button class="botao mini refazer-broll" id="refazer-broll" ${dis}>Refazer B-roll</button>`;
}

const AVISO_REFAZER_BROLL = "Refazer o B-roll? Os clipes escolhidos são descartados e o Claude "
  + "marca, busca e confere tudo de novo (o YouTube leva perto de 1 min por vídeo).";

async function refazerBroll(b) {
  if (!confirm(AVISO_REFAZER_BROLL)) return;
  const ed = ED, meu = desenhar.n;
  b.disabled = true;
  try {
    const novo = await post(`${urlCorte(ed.id, ed.n)}/broll/refazer`);
    if (meu === desenhar.n && ED === ed) aplicarEstado(novo);
  } catch (e) { avisar(e.message); b.disabled = false; }
}

function ligarBroll() {
  const b = $("#refazer-broll");
  if (b) b.onclick = () => refazerBroll(b);
}
