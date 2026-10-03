"use strict";
// Grade de Shorts do episódio (plano B): um cartão 9:16 por corte, com nota, formato, status do
// render e a decisão da curadoria — que é por índice do candidato, o mesmo índice do corte.
// O cartão usa o mesmo data-cand da tabela, então clicar nele seleciona o candidato no painel
// (blocoEpisodio liga os dois de uma vez). O vídeo do cartão é só vitrine (muted, sem
// controles); quem toca de verdade é o player do painel. Na fila, o cartão tem "Cancelar"
// (htmlCancelar em episodio.js, ligado por ligarAcoesCorte em blocoEpisodio).
const NOMES_STATUS = { na_fila: "na fila", renderizando: "renderizando…", pronto: "pronto", erro: "erro no render" };

// ?v=<versao>: a URL do vídeo do corte não muda entre versões — sem isso o navegador mostraria
// o MP4 antigo do cache depois de um "tentar de novo" ou de um novo formato.
const srcShort = k => `${k.video}?v=${k.versao}`;

function htmlCartao(D, k) {
  const c = D.candidatos.find(x => x.indice === k.indice);
  const midia = k.video
    ? `<video src="${esc(srcShort(k))}" preload="metadata" muted playsinline></video>`
    : `<div class="sem-video">${esc(NOMES_STATUS[k.status])}</div>`;
  return `<div class="short ${k.indice === candSel ? "sel" : ""}" data-cand="${k.indice}" tabindex="0" role="button" aria-pressed="${k.indice === candSel}">
    ${midia}
    <div class="short-info">
      <div><span class="n">${nota10(c.nota_final)}</span><span class="chip f">${esc(k.formato)}</span></div>
      <span class="status ${esc(k.status)}"${k.erro ? ` title="${esc(k.erro)}"` : ""}>${esc(NOMES_STATUS[k.status])}</span>
      <div class="t" title="${esc(k.titulo)}">${esc(k.titulo)}</div>
      ${c.decisao ? `<span class="decisao ${esc(c.decisao)}">${esc(c.decisao)}</span>` : ""}
      ${k.status === "na_fila" ? htmlCancelar(D, k.indice) : ""}
    </div></div>`;
}

function htmlGrade(D) {
  if (!D.cortes.length) return "";
  return `<div class="secao"><h2>Shorts</h2><span class="num">${D.render.prontos}/${D.render.total} prontos</span></div>
    <div class="grade-shorts">${D.cortes.map(k => htmlCartao(D, k)).join("")}</div>`;
}
