"use strict";
// Tela Shorts: pendências de ligação no topo, ligados embaixo; gaveta para ligar Short → corte.

function idade(l) {
  return Math.floor((Date.now() - new Date(l.publicado_em + "T00:00")) / 864e5) + "d";
}

const FADA = new Set(["maturando", "sem_dado"]);   // mesmo estilo esmaecido nas duas linhas

function celulaViews7d(l) {
  const m = l.medida;
  if (m.estado === "maturando") return `<div class="num" title="maturando">maturando</div>`;
  if (m.estado === "sem_dado") {
    return `<div class="num muted" title="o primeiro retrato chegou mais de 7 dias depois do dia 7 `
      + `— fica fora da comparação">sem dado</div>`;
  }
  return `<div class="num" title="${esc(m.estado)}">${mil(m.views_7d)}${m.estado === "estimado" ? " ≈" : ""}</div>`;
}

function celulaRelativo(l) {
  if (l.rel != null) return `<div class="num ${l.rel >= 1 ? "up" : "down"}">${fx(l.rel)}</div>`;
  if (l.medida.estado === "medido" || l.medida.estado === "estimado") {
    return `<div class="num muted" title="a conta tem menos de 3 Shorts medidos">sem base</div>`;
  }
  return `<div class="num">—</div>`;
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
    ${ls.map(l => `<div class="linha-s ${FADA.has(l.medida.estado) ? "matura" : ""}">
      <img class="mini" src="${thumb(l.video_id)}" alt="" loading="lazy">
      <div class="nome" title="${esc(l.titulo)}">${esc(l.titulo)}</div>
      <div class="muted">${esc(handleDe(l.conta))}</div>
      <div class="num">${idade(l)}</div>
      ${celulaViews7d(l)}
      ${celulaRelativo(l)}
      <div class="num">${pct(l.pct_media)}</div>
      <div>${l.etiquetas ? chipsEtiquetas(l) : `<button class="botao" data-ligar="${esc(l.video_id)}">Ligar</button>`}</div>
    </div>`).join("")}</section>`;
}

async function telaShorts(meu) {
  fecharGaveta();   // tela re-renderizada (ou revisitada): nada de gaveta velha ligada a outro Short
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

function opcoesCorte(sugeridos, todos, comPlaceholder) {
  const vistos = new Set(sugeridos.map(c => c.caminho));
  const resto = todos.filter(c => !vistos.has(c.caminho));
  const opt = c => `<option value="${esc(c.caminho)}">${esc(c.caminho)}</option>`;
  const placeholder = comPlaceholder ? `<option value="" disabled selected>escolha o corte</option>` : "";
  return placeholder
    + (sugeridos.length ? `<optgroup label="Sugeridos pelo título">${sugeridos.map(opt).join("")}</optgroup>` : "")
    + `<optgroup label="Todos">${resto.map(opt).join("")}</optgroup>`;
}

function formGaveta(l, sugeridos, todos, comPlaceholder) {
  const e = l?.etiquetas;
  return `<div class="fundo"></div><form class="gaveta" role="dialog" aria-modal="true" aria-labelledby="gaveta-titulo">
    <h2 id="gaveta-titulo">Ligar Short</h2>
    ${l ? `<p class="sub">${esc(l.titulo)}</p>` : ""}
    <label>Link do Short<input name="link" required value="${l ? `https://youtube.com/shorts/${esc(l.video_id)}` : ""}"></label>
    <label>Conta<select name="conta">${E.contas.map(c => `<option value="${esc(c.id)}" ${l?.conta === c.id ? "selected" : ""}>${esc(c.handle)}</option>`).join("")}</select></label>
    <label>Corte<select name="corte" required>${opcoesCorte(sugeridos, todos, comPlaceholder)}</select></label>
    <label>Formato<select name="formato" required><option value="">— escolha —</option>${
      Object.entries(E.formatos).map(([id, f]) => `<option value="${esc(id)}">${esc(id)} · ${esc(f.nome)}</option>`).join("")}</select></label>
    <div><span class="rotulo-grupo">Temas</span><div class="temas">${E.temas.map(t => `<label><input type="checkbox" name="temas" value="${esc(t)}" ${e?.temas.includes(t) ? "checked" : ""}>${esc(t)}</label>`).join("")}</div></div>
    <label>Podcast<input name="podcast" required list="podcasts" value="${esc(e?.podcast ?? "")}"><datalist id="podcasts">${E.podcasts.map(p => `<option value="${esc(p)}">`).join("")}</datalist></label>
    <div class="acoes"><button type="button" class="botao" id="cancelar">Cancelar</button><button type="submit" class="botao primario" id="gaveta-enviar">Ligar</button></div></form>`;
}

// `etiquetas` presente (abertura inicial, religando um Short já com formato/podcast): semeia
// formato e podcast com o que já estava gravado, e guarda em dataset.auto o que foi preenchido
// sem a pessoa escolher — assim uma troca de corte depois sabe se pode sobrescrever ou não.
// `etiquetas` null (abertura sem ligação, ou troca de corte): deriva do corte selecionado, mas só
// sobrescreve um campo que ainda está vazio ou que continua igual ao último valor automático —
// se a pessoa já editou o campo à mão, a troca de corte não apaga a escolha dela.
function preencherDoCorte(form, todos, etiquetas) {
  if (etiquetas) {
    form.formato.value = etiquetas.formato;
    form.formato.dataset.auto = etiquetas.formato;
    form.podcast.value = etiquetas.podcast;
    form.podcast.dataset.auto = etiquetas.podcast;
    return;
  }
  const c = todos.find(x => x.caminho === form.corte.value);
  if (!form.formato.value || form.formato.value === form.formato.dataset.auto) {
    const novoFormato = c?.formato ?? "";   // sem formato no corte: placeholder "— escolha —", nunca o valor antigo
    form.formato.value = novoFormato;
    form.formato.dataset.auto = novoFormato;
  }
  if (c?.podcast) {
    if (!form.podcast.value || form.podcast.value === form.podcast.dataset.auto) {
      form.podcast.value = c.podcast;
      form.podcast.dataset.auto = c.podcast;
    }
  } else if (form.podcast.value === form.podcast.dataset.auto) {
    // corte novo não tem podcast: limpa o que foi preenchido automaticamente (campo é
    // obrigatório, então a pessoa precisa digitar o podcast certo, em vez de ficar com o antigo).
    form.podcast.value = "";
    form.podcast.dataset.auto = "";
  }
}

let aoTeclarGaveta = null;
let gatilhoGaveta = null;
let tokenGaveta = 0;

// Fecha a gaveta (se houver uma aberta) e invalida qualquer abertura em andamento: uma
// `abrirLigar` cujo fetch ainda não voltou confere `tokenGaveta` antes de desenhar e desiste
// se alguém já fechou ou abriu outra gaveta nesse meio tempo.
function fecharGaveta() {
  tokenGaveta++;
  const camada = $("#camada");
  if (camada && camada.innerHTML) camada.innerHTML = "";
  if (aoTeclarGaveta) {
    document.removeEventListener("keydown", aoTeclarGaveta);
    aoTeclarGaveta = null;
  }
  gatilhoGaveta?.focus();
  gatilhoGaveta = null;
}

// Navegar para outra tela (inclusive via trás/avante do navegador) fecha a gaveta: #camada
// é global, fora de #tela, então troca de tela não a limpa por conta própria.
window.addEventListener("hashchange", fecharGaveta);

async function abrirLigar(vid, gatilho) {
  fecharGaveta();
  const meu = ++tokenGaveta;
  try {
    const l = vid ? S.find(x => x.video_id === vid) : null;
    const [sugeridos, todos] = await Promise.all([vid ? api(`/api/sugestoes/${vid}`) : [], api("/api/cortes")]);
    if (meu !== tokenGaveta) return;   // outra gaveta abriu (ou esta foi fechada) enquanto buscava
    const corteValido = l?.corte != null && todos.some(c => c.caminho === l.corte);
    if (l?.corte != null && !corteValido) avisar(`o corte antigo '${l.corte}' não existe mais; escolha outro`);
    // Sem ligação e com sugestão: a primeira opção do <select> já é a sugestão top (ver
    // opcoesCorte) e fica pré-selecionada por padrão — só força o placeholder "escolha o corte"
    // quando não há nada pra pré-selecionar (religação com corte apagado) ou nenhuma sugestão.
    const comPlaceholder = !corteValido && (l?.corte != null || !sugeridos.length);
    gatilhoGaveta = gatilho ?? null;
    const camada = $("#camada");
    camada.innerHTML = formGaveta(l, sugeridos, todos, comPlaceholder);
    const form = $("form", camada);
    if (corteValido) form.corte.value = l.corte;
    preencherDoCorte(form, todos, l?.etiquetas ?? null);
    form.corte.onchange = () => preencherDoCorte(form, todos, null);
    aoTeclarGaveta = ev => { if (ev.key === "Escape") fecharGaveta(); };
    document.addEventListener("keydown", aoTeclarGaveta);
    $(".fundo", camada).onclick = fecharGaveta;
    $("#cancelar").onclick = fecharGaveta;
    form.link.focus();
    const enviar = $("#gaveta-enviar", camada);
    form.onsubmit = async ev => {
      ev.preventDefault();
      const corpo = { link: form.link.value.trim(), conta: form.conta.value, corte: form.corte.value,
        formato: form.formato.value, podcast: form.podcast.value,
        temas: $$("input[name=temas]:checked", form).map(i => i.value) };
      enviar.disabled = true;
      try {
        await post("/api/ligar", corpo);
        fecharGaveta();
        desenhar();
      } catch (e) {
        avisar(e.message);
      } finally {
        enviar.disabled = false;
      }
    };
  } catch (e) {
    if (meu === tokenGaveta) avisar(e.message);
  }
}
TELAS.shorts = telaShorts;
