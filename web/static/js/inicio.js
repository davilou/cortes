"use strict";
// Roteador por hash e acompanhamento da coleta. Carregado por último.
async function desenhar() {
  const nome = TELAS[location.hash.slice(1)] ? location.hash.slice(1) : "comparar";
  $$("nav a").forEach(a => a.classList.toggle("ativo", a.dataset.tela === nome));
  try {
    await TELAS[nome]();
  } catch (e) {
    avisar(e.message);
  }
}

async function acompanhar() {
  await carregar();
  if (E.rodando) setTimeout(acompanhar, 3000);
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
carregar().then(() => (E.rodando ? acompanhar() : desenhar())).catch(e => avisar(e.message));
