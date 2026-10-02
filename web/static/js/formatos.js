"use strict";
// Tela Formatos: galeria de referência com o que cada formato de edição faz, a evidência da
// pesquisa e o vídeo gravado na rodada de teste (quando existir — testes/ fica fora do git).

const CLASSE_NO_APP = { "plano B": "pb", "plano D": "pde", "plano E": "pde", "fora": "fora" };

function chipFormato(noApp) {
  if (!noApp) return "";
  const cls = CLASSE_NO_APP[noApp] ?? "pde";
  return `<span class="chip-no-app ${cls}">${esc(noApp === "fora" ? "fora" : `no app: ${noApp}`)}</span>`;
}

function demoFormato(fid, f) {
  if (!f.tem_demo) {
    return `<div class="demo-vazia"><p>demonstração não encontrada</p><small>testes/ fica fora do git</small></div>`;
  }
  return `<video controls preload="metadata" playsinline src="/api/formatos/${encodeURIComponent(fid)}/demo"></video>`;
}

function cartaoFormato(fid, f) {
  return `<div class="card formato-card">
    <div class="demo">${demoFormato(fid, f)}</div>
    <div class="formato-topo"><h2>${esc(f.nome)}</h2>${chipFormato(f.no_app)}</div>
    <p class="descricao">${esc(f.descricao)}</p>
    ${f.evidencia ? `<p class="evidencia">${esc(f.evidencia)}</p>` : ""}
  </div>`;
}

// Só um vídeo toca por vez: ao dar play num, os outros pausam — senão o áudio de vários
// tocando junto fica ilegível na galeria.
function ligarVideosFormatos() {
  const videos = $$(".formato-card video");
  videos.forEach(v => { v.onplay = () => videos.forEach(outro => { if (outro !== v) outro.pause(); }); });
}

async function telaFormatos(meu) {
  if (!E) await carregar();
  if (meu !== desenhar.n) return;
  const ids = Object.keys(E.formatos);
  $("#tela").innerHTML = `<header><div><h1>Formatos <em>— ${ids.length}</em></h1>
    <p class="sub">O que cada formato de edição faz, com a demonstração gravada na rodada de teste.</p></div></header>
    <div class="formatos-grid">${ids.map(fid => cartaoFormato(fid, E.formatos[fid])).join("")}</div>`;
  ligarVideosFormatos();
}
TELAS.formatos = telaFormatos;
