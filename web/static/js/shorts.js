"use strict";
// Tela Shorts: pendências de ligação no topo, ligados embaixo; gaveta para ligar Short → corte.

function idade(l) {
  return Math.floor((Date.now() - new Date(l.publicado_em + "T00:00")) / 864e5) + "d";
}

function views7d(l) {
  const m = l.medida;
  if (m.estado === "maturando") return "maturando";
  return mil(m.views_7d) + (m.estado === "estimado" ? " ≈" : "");
}

function chipsEtiquetas(l) {
  const e = l.etiquetas;
  return `<button class="chips" data-ligar="${esc(l.video_id)}" title="religar"><span class="chip f">${esc(e.formato)}</span>${
    e.temas.map(t => `<span class="chip">${esc(t)}</span>`).join("")}<span class="chip">${esc(e.podcast)}</span></button>`;
}

function tabelaShorts(ls) {
  return `<section class="grupos">
    <div class="linha-s cab"><span></span><span>Título</span><span>Conta</span><span class="num">Idade</span>
      <span class="num">Views 7d</span><span class="num">Relativo</span><span class="num">Assist.</span><span>Etiquetas</span></div>
    ${ls.map(l => `<div class="linha-s ${l.medida.estado === "maturando" ? "matura" : ""}">
      <img class="mini" src="${thumb(l.video_id)}" alt="" loading="lazy">
      <div class="nome" title="${esc(l.titulo)}">${esc(l.titulo)}</div>
      <div class="muted">${esc(handleDe(l.conta))}</div>
      <div class="num">${idade(l)}</div>
      <div class="num" title="${l.medida.estado}">${views7d(l)}</div>
      <div class="num ${l.rel == null ? "" : l.rel >= 1 ? "up" : "down"}">${fx(l.rel)}</div>
      <div class="num">${pct(l.pct_media)}</div>
      <div>${l.etiquetas ? chipsEtiquetas(l) : `<button class="botao" data-ligar="${esc(l.video_id)}">Ligar</button>`}</div>
    </div>`).join("")}</section>`;
}

async function telaShorts(meu) {
  await carregar();
  if (meu !== desenhar.n) return;   // uma renderização mais nova já começou: não pisa nela
  const sem = S.filter(l => !l.etiquetas), lig = S.filter(l => l.etiquetas);
  $("#tela").innerHTML = `<header><div><h1>Shorts <em>— ${S.length} nos retratos</em></h1>
    <p class="sub">Ligue cada Short ao corte que o gerou: só Short ligado entra na comparação.</p></div>
    <button class="botao" id="ligar-link">Ligar por link</button></header>
    ${S.length ? "" : vazio("Nenhum Short ainda", "Adicione uma conta e clique em Atualizar: os Shorts dela aparecem aqui.")}
    ${sem.length ? `<h3 class="secao">Sem ligação<span>${sem.length}</span></h3>${tabelaShorts(sem)}` : ""}
    ${lig.length ? `<h3 class="secao">Ligados<span>${lig.length}</span></h3>${tabelaShorts(lig)}` : ""}`;
  $$("[data-ligar]").forEach(b => { b.onclick = () => abrirLigar(b.dataset.ligar, b); });
  const ligarLink = $("#ligar-link");
  if (ligarLink) ligarLink.onclick = () => abrirLigar(null, ligarLink);
}

function opcoesCorte(sugeridos, todos) {
  const vistos = new Set(sugeridos.map(c => c.caminho));
  const resto = todos.filter(c => !vistos.has(c.caminho));
  const opt = c => `<option value="${esc(c.caminho)}">${esc(c.caminho)}</option>`;
  return (sugeridos.length ? `<optgroup label="Sugeridos pelo título">${sugeridos.map(opt).join("")}</optgroup>` : "")
    + `<optgroup label="Todos">${resto.map(opt).join("")}</optgroup>`;
}

function formGaveta(l, sugeridos, todos) {
  const e = l?.etiquetas;
  return `<div class="fundo"></div><form class="gaveta"><h2>Ligar Short</h2>
    ${l ? `<p class="sub">${esc(l.titulo)}</p>` : ""}
    <label>Link do Short<input name="link" required value="${l ? `https://youtube.com/shorts/${esc(l.video_id)}` : ""}"></label>
    <label>Conta<select name="conta">${E.contas.map(c => `<option value="${esc(c.id)}" ${l?.conta === c.id ? "selected" : ""}>${esc(c.handle)}</option>`).join("")}</select></label>
    <label>Corte<select name="corte" required>${opcoesCorte(sugeridos, todos)}</select></label>
    <label>Formato<select name="formato">${Object.entries(E.formatos).map(([id, f]) => `<option value="${esc(id)}">${esc(id)} · ${esc(f.nome)}</option>`).join("")}</select></label>
    <div><span class="rotulo-grupo">Temas</span><div class="temas">${E.temas.map(t => `<label><input type="checkbox" name="temas" value="${esc(t)}" ${e?.temas.includes(t) ? "checked" : ""}>${esc(t)}</label>`).join("")}</div></div>
    <label>Podcast<input name="podcast" required list="podcasts" value="${esc(e?.podcast ?? "")}"><datalist id="podcasts">${E.podcasts.map(p => `<option value="${esc(p)}">`).join("")}</datalist></label>
    <div class="acoes"><button type="button" class="botao" id="cancelar">Cancelar</button><button class="botao primario">Ligar</button></div></form>`;
}

function preencherDoCorte(form, todos, etiquetas) {
  const c = todos.find(x => x.caminho === form.corte.value);
  if (etiquetas) { form.formato.value = etiquetas.formato; return; }
  if (c?.formato) form.formato.value = c.formato;
  if (c?.podcast && !form.podcast.value) form.podcast.value = c.podcast;
}

async function abrirLigar(vid, gatilho) {
  const l = vid ? S.find(x => x.video_id === vid) : null;
  const [sugeridos, todos] = await Promise.all([vid ? api(`/api/sugestoes/${vid}`) : [], api("/api/cortes")]);
  const camada = $("#camada");
  camada.innerHTML = formGaveta(l, sugeridos, todos);
  const form = $("form", camada);
  if (l?.corte) form.corte.value = l.corte;
  preencherDoCorte(form, todos, l?.etiquetas);
  form.corte.onchange = () => preencherDoCorte(form, todos, null);
  const aoTeclar = ev => { if (ev.key === "Escape") fechar(); };
  function fechar() {
    camada.innerHTML = "";
    document.removeEventListener("keydown", aoTeclar);
    gatilho?.focus();
  }
  document.addEventListener("keydown", aoTeclar);
  $(".fundo", camada).onclick = fechar;
  $("#cancelar").onclick = fechar;
  form.link.focus();
  form.onsubmit = async ev => {
    ev.preventDefault();
    const corpo = { link: form.link.value.trim(), conta: form.conta.value, corte: form.corte.value,
      formato: form.formato.value, podcast: form.podcast.value,
      temas: $$("input[name=temas]:checked", form).map(i => i.value) };
    try { await post("/api/ligar", corpo); fechar(); desenhar(); } catch (e) { avisar(e.message); }
  };
}
TELAS.shorts = telaShorts;
