"use strict";
// Roteador por hash e acompanhamento da coleta. Carregado por último.
// desenhar.n é o contador de renderização: cada chamada pega o número seguinte e as telas
// (ex. telaComparar) recebem esse número para conferir, depois do await, se ainda são a
// renderização mais recente — uma resposta antiga que chega depois de uma mais nova não
// deve pintar a tela com o dado velho.
async function desenhar() {
  const meu = ++desenhar.n;
  const nome = TELAS[location.hash.slice(1)] ? location.hash.slice(1) : "episodios";
  $$("[data-tela]").forEach(a => a.classList.toggle("ativo", a.dataset.tela === nome));
  try {
    await TELAS[nome](meu);
  } catch (e) {
    if (meu === desenhar.n) avisar(e.message);
  }
}
desenhar.n = 0;

async function acompanhar() {
  await carregar();
  if (E.rodando) setTimeout(() => acompanhar().catch(e => avisar(e.message)), 3000);
  else desenhar();
}

async function atualizar(conta) {
  try {
    await post("/api/atualizar", { conta: conta ?? null });
    await acompanhar();
  } catch (e) {
    avisar(e.message);
  }
}

window.addEventListener("hashchange", desenhar);
$("#atualizar-todas").onclick = () => atualizar(null);
$("#atualizar-todas-m").onclick = () => atualizar(null);
carregar().then(() => {
  if (E.rodando) { desenhar(); acompanhar().catch(e => avisar(e.message)); }
  else desenhar();
  // A fila da Produção roda em qualquer tela (pílula e caixa no rodapé do trilho), não só
  // em Episódios — dispara uma vez aqui; atualizarProducao() se reagenda sozinha enquanto
  // houver trabalho (episodios.js).
  atualizarProducao().catch(e => avisar(e.message));
}).catch(e => avisar(e.message));
