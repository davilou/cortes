"use strict";
// Ilustrações do f9 (plano 2026-10-02-ilustrado): uma linha por deixa com a miniatura da imagem
// escolhida pela conferência, ou "sem imagem" com o motivo. "Refazer ilustração" apaga o cache
// (deixas, imagens e escolhas) e pede a prévia, que roda LLM, busca e conferência de novo.
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

function htmlListaIlustracoes(ed) {
  if (ed.ilustracao_erro) return `<p class="sub erro-txt" title="${esc(ed.ilustracao_erro)}">não deu para
    ler as ilustrações: ${esc(ed.ilustracao_erro)}</p>`;
  if (!ed.ilustracoes.length) return `<p class="sub">As ilustrações aparecem quando a prévia ficar pronta.</p>`;
  return `<ul class="ilustracoes">${ed.ilustracoes.map(htmlIlustracao).join("")}</ul>`;
}

function htmlIlustracoes(ed) {
  const dis = ed.editavel ? "" : "disabled";
  return `${htmlListaIlustracoes(ed)}
    <button class="botao mini refazer-ilustracao" id="refazer-ilustracao" ${dis}>
      Refazer ilustração</button>`;
}

const AVISO_REFAZER = "Refazer a ilustração? As imagens escolhidas são descartadas e o Claude "
  + "marca, busca e confere tudo de novo.";

async function refazerIlustracao(b) {
  if (!confirm(AVISO_REFAZER)) return;
  const ed = ED, meu = desenhar.n;
  b.disabled = true;
  try {
    const novo = await post(`${urlCorte(ed.id, ed.n)}/ilustracao/refazer`);
    if (meu === desenhar.n && ED === ed) aplicarEstado(novo);
  } catch (e) { avisar(e.message); b.disabled = false; }
}

function ligarIlustracoes() {
  const b = $("#refazer-ilustracao");
  if (b) b.onclick = () => refazerIlustracao(b);
}
