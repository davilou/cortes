"use strict";
// Coluna de transcrição do editor: palavras em volta do corte (as de fora apagadas); clique
// seleciona e a barra de ações move início/fim para a palavra (sempre por palavra — spec §5),
// corrige o texto da legenda ou mascara (p*rra, só na legenda). Aviso quando o início depende de
// contexto (cortes.regra_inicio, pesquisa R1: erro nº 1 dos fracassos).
let palSel = null;   // índice global (palavras.json) da palavra selecionada — só local

function htmlPalavra(ed, p) {
  const cls = ["pal", p.dentro ? "dentro" : "fora", p.i === palSel ? "sel" : "", p.mascarada ? "masc" : "",
    p.editada ? "edit" : "", p.i === ed.inicio_palavra ? "ini" : "", p.i === ed.fim_palavra ? "fim" : ""]
    .filter(Boolean).join(" ");
  const dica = `${tempo(p.inicio)}${p.editada ? ` · original: ${p.original}` : ""}`;
  return `<span class="${cls}" data-i="${p.i}" tabindex="0" role="button" aria-pressed="${p.i === palSel}" title="${esc(dica)}">${esc(p.texto || "∅")}</span>`;
}

function htmlAcoesPalavra(ed) {
  const p = ed.palavras.find(x => x.i === palSel);
  if (!p) return `<p class="sub">Clique numa palavra para mover o início/fim, corrigir o texto ou mascarar.</p>`;
  const dis = ed.editavel ? "" : "disabled";
  return `<div class="acoes-pal">
    <button class="botao mini" data-acao="inicio" ${dis}>Começa aqui</button>
    <button class="botao mini" data-acao="fim" ${dis}>Termina aqui</button>
    <button class="botao mini" data-acao="mascarar" ${dis}>${p.mascarada ? "Desmascarar" : "Mascarar"}</button>
    <input id="pal-texto" value="${esc(ed.corte.edicoes.legenda[p.i] ?? p.original)}" aria-label="Texto da palavra na legenda" ${dis}>
    <button class="botao mini" data-acao="texto" ${dis}>Salvar texto</button>
    ${p.editada ? `<button class="botao mini" data-acao="original" ${dis}>Original</button>` : ""}</div>`;
}

function htmlTranscricao(ed) {
  const aviso = ed.aviso_inicio
    ? `<p class="aviso-inicio">O início parece depender de contexto (abre com conectivo). Tente começar uma frase antes ou depois.</p>` : "";
  return `<div class="secao"><h2>Transcrição</h2>
      <button class="botao mini" id="mascarar-palavroes" ${ed.editavel ? "" : "disabled"}>Mascarar palavrões</button></div>
    ${aviso}${htmlAcoesPalavra(ed)}
    <div class="palavras">${ed.palavras.map(p => htmlPalavra(ed, p)).join(" ")}</div>`;
}

// legenda: null volta ao texto original; "" tira a palavra da legenda (API: PedidoEdicao).
function acaoPalavra(acao) {
  const p = ED.palavras.find(x => x.i === palSel);
  if (!p) return;
  const pedidos = {
    inicio: () => ({ inicio_palavra: p.i }),
    fim: () => ({ fim_palavra: p.i }),
    mascarar: () => ({ mascarar: { [p.i]: !p.mascarada } }),
    texto: () => ({ legenda: { [p.i]: $("#pal-texto").value } }),
    original: () => ({ legenda: { [p.i]: null } }),
  };
  editar(pedidos[acao]());
}

// A seleção é só local: redesenha a coluna mantendo rolagem e foco, sem ir ao servidor.
function redesenharTranscricao() {
  const col = $("#ed-transcricao");
  const rolagem = $(".palavras", col)?.scrollTop ?? 0;
  col.innerHTML = htmlTranscricao(ED);
  $(".palavras", col).scrollTop = rolagem;
  ligarTranscricao();
  $(`.pal[data-i="${palSel}"]`, col)?.focus({ preventScroll: true });
}

function ligarTranscricao() {
  const col = $("#ed-transcricao");
  $$(".pal", col).forEach(el => {
    const selecionar = () => { palSel = Number(el.dataset.i); redesenharTranscricao(); };
    el.onclick = selecionar;
    el.onkeydown = ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); selecionar(); } };
  });
  const mp = $("#mascarar-palavroes", col);
  if (mp) mp.onclick = () => editar({ mascarar_palavroes: true });
  $$("[data-acao]", col).forEach(b => { b.onclick = () => acaoPalavra(b.dataset.acao); });
  const inp = $("#pal-texto", col);
  if (inp) inp.onkeydown = ev => { if (ev.key === "Enter") acaoPalavra("texto"); };
}

// Ao abrir, a primeira palavra do corte fica a um terço da altura da caixa (sem rolar a página).
// .palavras é position: relative, então offsetTop da palavra já é medido dentro da caixa.
function rolarParaInicio() {
  const box = $("#ed-transcricao .palavras");
  const el = box && $(".pal.ini", box);
  if (el) box.scrollTop = el.offsetTop - box.clientHeight / 3;
}
