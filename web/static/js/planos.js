"use strict";
// Quem aparece (plano C): um bloco por plano de câmera do trecho com a miniatura de cada pessoa
// detectada; clicar escolhe quem fica na tela naquele plano (padrão: o rosto mais confiável).
// Plano sem rosto segue o enquadramento do anterior (render/rosto.py trilha_fixa).
function htmlPessoas(ed, p) {
  if (!p.pessoas.length) return `<span class="sub">sem rosto — segue o plano anterior</span>`;
  const dis = ed.editavel ? "" : "disabled";
  return p.pessoas.map(s => `<button class="pessoa ${s.j === p.escolha ? "sel" : ""}" data-plano="${p.k}"
      data-pessoa="${s.j}" aria-pressed="${s.j === p.escolha}" title="${s.n} detecções${s.j === p.padrao ? " · padrão" : ""}" ${dis}>
      <img src="${esc(s.miniatura)}" alt="pessoa ${s.j + 1} no plano ${p.k + 1}" loading="lazy"></button>`).join("");
}

function htmlPlanos(ed) {
  if (!ed.planos.length) return `<p class="sub">Os planos aparecem quando a prévia ficar pronta.</p>`;
  return `<div class="planos">${ed.planos.map(p => `<div class="plano">
      <span class="num">${tempo(p.ini)}–${tempo(p.fim)}</span>
      <div class="pessoas">${htmlPessoas(ed, p)}</div></div>`).join("")}</div>`;
}

// rosto: [plano, pessoa] (API: PedidoEdicao.rosto). Clicar na já escolhida não faz nada.
function ligarPlanos() {
  $$("#ed-ajustes .pessoa").forEach(b => {
    b.onclick = () => {
      if (b.getAttribute("aria-pressed") === "true") return;
      editar({ rosto: [Number(b.dataset.plano), Number(b.dataset.pessoa)] });
    };
  });
}
