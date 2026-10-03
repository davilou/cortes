"use strict";
// Quem aparece (plano C): um bloco por plano de câmera do trecho com a miniatura de cada pessoa
// detectada; clicar escolhe quem fica na tela naquele plano (padrão: o rosto mais confiável).
// Plano sem rosto segue o enquadramento do anterior (render/rosto.py trilha_fixa).
// f7: plano aberto com 2 pessoas alterna entre elas (render/conversa.py); a escolha manual fixa o
// plano, e "alternar" desfaz a escolha (rosto [k, -1]). O ritmo mostra as trocas por 10 s.
const dec = (x, n) => x.toLocaleString("pt-BR", { maximumFractionDigits: n });

function htmlRitmo(ed) {
  const r = ed.ritmo;
  if (!r) return "";
  const fora = r.trocas_10s < r.alvo[0] || r.trocas_10s > r.alvo[1];
  return `<p class="sub ${fora ? "erro-txt" : ""}">ritmo: ${dec(r.trocas_10s, 2)} trocas/10 s
    (alvo ${dec(r.alvo[0], 1)}–${dec(r.alvo[1], 1)}) · ${r.reais} de câmera + ${r.alternancias} alternando</p>`;
}

function htmlAlterna(ed, p) {
  if (p.alterna) return `<span class="sub">alterna entre as pessoas</span>`;
  if (ed.corte.formato !== "f7" || !p.manual) return "";
  return `<button class="botao mini alternar" data-plano="${p.k}" ${ed.editavel ? "" : "disabled"}
    title="desfaz a escolha: o plano volta a alternar se tiver 2 pessoas">alternar</button>`;
}
function htmlPessoas(ed, p) {
  if (!p.pessoas.length) return `<span class="sub">sem rosto — segue o plano anterior</span>`;
  const dis = ed.editavel ? "" : "disabled";
  return p.pessoas.map(s => `<button class="pessoa ${s.j === p.escolha ? "sel" : ""}" data-plano="${p.k}"
      data-pessoa="${s.j}" aria-pressed="${s.j === p.escolha}" title="${s.n} detecções${s.j === p.padrao ? " · padrão" : ""}" ${dis}>
      <img src="${esc(s.miniatura)}" alt="pessoa ${s.j + 1} no plano ${p.k + 1}" loading="lazy"></button>`).join("");
}

function htmlPlanos(ed) {
  if (ed.rosto_erro) return `<p class="sub erro-txt" title="${esc(ed.rosto_erro)}">não deu para ler os
    rostos: ${esc(ed.rosto_erro)} — a prévia refaz a medição</p>`;
  if (!ed.planos.length) return `<p class="sub">Os planos aparecem quando a prévia ficar pronta.</p>`;
  return `${htmlRitmo(ed)}<div class="planos">${ed.planos.map(p => `<div class="plano">
      <span class="num">${tempo(p.ini)}–${tempo(p.fim)}</span>
      <div class="pessoas">${htmlPessoas(ed, p)}</div>
      ${htmlAlterna(ed, p)}
      ${p.escolha_invalida ? `<span class="sub erro-txt">escolha antiga não vale mais — escolha de novo</span>` : ""}
      </div>`).join("")}</div>`;
}

// rosto: [plano, pessoa] (API: PedidoEdicao.rosto). Clicar na já escolhida não faz nada.
function ligarPlanos() {
  $$("#ed-ajustes .pessoa").forEach(b => {
    b.onclick = () => {
      if (b.getAttribute("aria-pressed") === "true") return;
      editar({ rosto: [Number(b.dataset.plano), Number(b.dataset.pessoa)] });
    };
  });
  $$("#ed-ajustes .alternar").forEach(b => {
    b.onclick = () => editar({ rosto: [Number(b.dataset.plano), -1] });
  });
}
