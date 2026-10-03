"use strict";
// Ilustrações do f9 (plano 2026-10-02-ilustrado), só leitura: uma linha por deixa com a miniatura
// da imagem escolhida pela conferência, ou "sem imagem" com o motivo. Trocar ou tirar fica para depois.
function htmlIlustracao(i) {
  const fonte = i.fonte_url
    ? ` · <a href="${esc(i.fonte_url)}" target="_blank" rel="noopener noreferrer">fonte</a>` : "";
  const img = i.imagem
    ? `<img src="${esc(i.imagem)}" alt="${esc(i.coisa)}" loading="lazy">`
    : `<span class="sem-imagem">sem imagem</span>`;
  return `<li class="ilustracao">${img}<div>
      <span class="num">${tempo(i.inicio)}–${tempo(i.fim)}</span> <strong>${esc(i.coisa)}</strong>
      <p class="sub" title="${esc(i.motivo)}">${esc(i.motivo)}${fonte}</p></div></li>`;
}

function htmlIlustracoes(ed) {
  if (ed.ilustracao_erro) return `<p class="sub erro-txt" title="${esc(ed.ilustracao_erro)}">não deu para
    ler as ilustrações: ${esc(ed.ilustracao_erro)}</p>`;
  if (!ed.ilustracoes.length) return `<p class="sub">As ilustrações aparecem quando a prévia ficar pronta.</p>`;
  return `<ul class="ilustracoes">${ed.ilustracoes.map(htmlIlustracao).join("")}</ul>`;
}
