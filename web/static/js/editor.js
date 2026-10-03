"use strict";
// Editor do Short (plano C, spec produção §5 "Editor"): três colunas — prévia 9:16 tocando o
// próprio projeto HyperFrames no navegador (<hyperframes-player>), transcrição palavra a palavra
// (transcricao.js) e ajustes: título, formato, quem aparece (planos.js), as ilustrações do f9
// (ilustracoes.js, só leitura), renderizar e versões.
// Toda edição vai por POST .../editar, que devolve o estado novo; a prévia é refeita fora da fila
// do render e a tela acompanha até ela ficar pronta.
let ED = null;   // /api/episodios/{id}/cortes/{n}/editor + {id, n}
const urlCorte = (id, n) => `/api/episodios/${encodeURIComponent(id)}/cortes/${n}`;
const NOMES_PREVIA = { preparando: "preparando a prévia…", erro: "a prévia falhou",
  desatualizada: "atualizando a prévia…", ausente: "gerando a prévia…" };
// Prévia que a tela pede sozinha: sem arquivo ou mais velha que o corte.json (decisão 6 do plano C).
const previaVelha = ed => ["ausente", "desatualizada"].includes(ed.previa.situacao) && ed.editavel;

function htmlPrevia(ed) {
  const p = ed.previa;
  if (p.situacao === "pronta") return `<hyperframes-player class="previa" src="${esc(p.url)}" controls></hyperframes-player>`;
  const erro = p.situacao === "erro"
    ? `<p class="erro-txt" title="${esc(p.erro)}">${esc(p.erro)}</p><button class="botao mini" id="refazer-previa">tentar de novo</button>` : "";
  return `<div class="previa vazia" role="status"><span>${esc(NOMES_PREVIA[p.situacao])}</span>${erro}</div>`;
}

function htmlVersoes(ed) {
  if (!ed.versoes.length) return `<p class="sub">Nenhuma versão renderizada ainda.</p>`;
  return `<ul class="versoes">${ed.versoes.slice().reverse().map(v => `<li>
    <a href="${esc(v.url)}" target="_blank" rel="noopener">v${v.versao}</a>
    <a class="botao mini" href="${esc(v.url)}&baixar=true" download>baixar</a></li>`).join("")}</ul>`;
}

function htmlAjustes(ed) {
  const c = ed.corte;
  const dis = ed.editavel ? "" : "disabled";
  const formatos = ed.formatos.map(f => `<option value="${esc(f)}" ${f === c.formato ? "selected" : ""}>${esc(f)} · ${esc(nomeFormato(f))}</option>`).join("");
  const situacao = c.alterado ? "edições ainda não renderizadas" : c.versao ? `v${c.versao} renderizada` : "ainda não renderizado";
  return `<label>Título<input id="ed-titulo" maxlength="100" value="${esc(c.titulo)}" ${dis}></label>
    <label>Formato<select id="ed-formato" ${dis}>${formatos}</select></label>
    <div class="ed-render"><button class="botao primario" id="ed-renderizar" ${dis}>Renderizar</button>
      <span class="num">${esc(NOMES_CORTE[c.status] ?? c.status)} · ${esc(situacao)}</span></div>
    ${c.erro ? `<p class="erro-txt" title="${esc(c.erro)}">${esc(c.erro)}</p>` : ""}
    <h3>Quem aparece</h3>${htmlPlanos(ed)}
    ${c.formato === "f9" ? `<h3>Ilustrações</h3>${htmlIlustracoes(ed)}` : ""}
    <h3>Versões</h3>${htmlVersoes(ed)}`;
}

function htmlEditor(ed) {
  return `<header><div><a class="voltar" href="#episodios">← Episódios</a>
      <h1>Editor <em>— ${esc(ed.corte.titulo)}</em></h1>
      <p class="sub">${esc(ed.episodio.titulo ?? ed.episodio.id)} · candidato ${ed.corte.indice}</p></div></header>
    <div class="editor">
      <div class="col-previa" id="ed-previa">${htmlPrevia(ed)}</div>
      <div class="col-transcricao" id="ed-transcricao">${htmlTranscricao(ed)}</div>
      <div class="col-ajustes" id="ed-ajustes">${htmlAjustes(ed)}</div>
    </div>`;
}

async function editar(pedido) {
  const ed = ED, meu = desenhar.n;
  try {
    const novo = await post(`${urlCorte(ed.id, ed.n)}/editar`, pedido);
    if (meu === desenhar.n && ED === ed) aplicarEstado(novo);
  } catch (e) { avisar(e.message); }
}

async function pedirPrevia() {
  const ed = ED, meu = desenhar.n;
  try {
    const novo = await post(`${urlCorte(ed.id, ed.n)}/previa`);
    if (meu === desenhar.n && ED === ed) aplicarEstado(novo);
  } catch (e) { avisar(e.message); }
}

async function renderizarDoEditor(b) {
  const ed = ED, meu = desenhar.n;
  b.disabled = true;
  try {
    await post(`${urlCorte(ed.id, ed.n)}/renderizar`, {});
    atualizarProducao();   // religa o polling da fila
    const novo = await api(`${urlCorte(ed.id, ed.n)}/editor`);
    if (meu === desenhar.n && ED === ed) aplicarEstado(novo);
  } catch (e) { avisar(e.message); b.disabled = false; }
}

// Transcrição e ajustes são redesenhados sempre; a prévia só quando a URL (que leva a versão do
// arquivo) ou a situação mudou — recriar o player à toa reiniciaria o vídeo que Davi está vendo.
// O foco que estava numa palavra volta para a palavra selecionada (o HTML da coluna é trocado).
function aplicarEstado(novo) {
  const antes = ED;
  ED = { ...novo, id: antes.id, n: antes.n };
  const focoNaTranscricao = !!document.activeElement?.closest("#ed-transcricao");
  const rolagem = $("#ed-transcricao .palavras")?.scrollTop ?? 0;
  $("#ed-transcricao").innerHTML = htmlTranscricao(ED);
  const box = $("#ed-transcricao .palavras");
  if (box) box.scrollTop = rolagem;
  $("#ed-ajustes").innerHTML = htmlAjustes(ED);
  if (antes.previa.url !== ED.previa.url || antes.previa.situacao !== ED.previa.situacao) {
    $("#ed-previa").innerHTML = htmlPrevia(ED);
  }
  ligarEditor();
  if (focoNaTranscricao) $(`#ed-transcricao .pal[data-i="${palSel}"]`)?.focus({ preventScroll: true });
  acompanharEditor();
}

// Enquanto a prévia prepara ou o corte está no render, relê o estado a cada 2 s. Quando o render
// termina, a prévia fica mais velha que o corte.json — aí ela é pedida de novo, sem clique.
// (Nome próprio: `acompanhar` já é o polling da coleta, em inicio.js.)
function acompanharEditor() {
  clearTimeout(acompanharEditor.t);
  if (!ED) return;
  const ocupado = ED.previa.situacao === "preparando" || ["na_fila", "renderizando"].includes(ED.corte.status);
  if (!ocupado) return;
  const ed = ED, meu = desenhar.n;
  acompanharEditor.t = setTimeout(async () => {
    if (meu !== desenhar.n || ED !== ed) return;   // saiu do editor: não relê à toa
    try {
      const novo = await api(`${urlCorte(ed.id, ed.n)}/editor`);
      if (meu !== desenhar.n || ED !== ed) return;
      aplicarEstado(novo);
      if (previaVelha(ED)) pedirPrevia();
    } catch (e) { avisar(e.message); }
  }, 2000);
}

function ligarEditor() {
  ligarTranscricao();
  ligarPlanos();
  const t = $("#ed-titulo");
  if (t) t.onchange = () => { const v = t.value.trim(); if (v && v !== ED.corte.titulo) editar({ titulo: v }); };
  const f = $("#ed-formato");
  if (f) f.onchange = () => editar({ formato: f.value });
  const r = $("#ed-renderizar");
  if (r) r.onclick = () => renderizarDoEditor(r);
  const refazer = $("#refazer-previa");
  if (refazer) refazer.onclick = pedirPrevia;
}

async function telaEditor(meu, id, n) {
  if (!id || n === undefined) { location.hash = "#episodios"; return; }
  if (!E) await carregar();
  const novo = await api(`${urlCorte(id, n)}/editor`);
  if (meu !== desenhar.n) return;
  ED = { ...novo, id, n: Number(n) };
  palSel = null;
  $("#tela").innerHTML = htmlEditor(ED);
  ligarEditor();
  rolarParaInicio();
  if (previaVelha(ED)) pedirPrevia();
  else acompanharEditor();
}
TELAS.editor = telaEditor;
