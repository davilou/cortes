"use strict";
// Detalhe do episódio: grade de Shorts (grade.js), candidatos (nota 0–10), painel com o player,
// rubrica, justificativa, tags e aprovar/rejeitar. No plano B o painel toca o Short renderizado
// (9:16) quando ele existe; sem Short, toca o trecho do vídeo original (16:9) via
// /api/episodios/{id}/video, como no plano A. O player e o recorte do trecho moram em player.js.
let candSel = 0;
// De onde veio a seleção (grade ou tabela): o mesmo data-cand existe nos dois, e o foco tem que
// voltar pro elemento que Davi clicou, não sempre pro primeiro do DOM (o cartão da grade).
let focoCand = ".candidatos";
const NOMES_RUBRICA = { gancho_3s: "Gancho 3 s", autocontido: "Autocontido", espanto: "Espanto",
  historia_ou_virada: "História/virada", fechamento: "Fechamento" };
const nota10 = n => (n / 10).toFixed(1).replace(".", ",");
// notas vão de 1 a 5: a barra usa 0%–100% nos extremos (1 → 0%, 5 → 100%), não um múltiplo de n.
const rubPct = n => (n == null ? 0 : Math.max(0, (n - 1) * 25));
function tempo(s) {
  const iso = new Date(s * 1000).toISOString();
  // h:mm:ss sem zero à esquerda na hora (1:23:45, não 01:23:45); abaixo de 1h fica mm:ss.
  return s >= 3600 ? iso.slice(11, 19).replace(/^0/, "") : iso.slice(14, 19);
}

const NOMES_CORTE = { na_fila: "na fila do render", renderizando: "renderizando…", pronto: "Short pronto", erro: "erro no render" };
const corteDe = (D, indice) => D.cortes.find(k => k.indice === indice);

// Formato que Davi escolheu no seletor e ainda não mandou renderizar, por episódio e candidato
// ({id: {indice: formato}}): o polling redesenha o detalhe a cada mudança da fila, e sem isto o
// seletor voltaria ao formato padrão no meio da escolha. Sai quando o render é pedido.
const formatosEscolhidos = {};
const escolhaDe = (id, indice) => formatosEscolhidos[id]?.[indice];

// Seletor de formato + botão que pede o render nesse formato: "Renderizar" (candidato sem corte,
// com o formato padrão do episódio marcado), "tentar de novo" e "Renderizar de novo" (o do corte).
// A escolha ainda não pedida (formatosEscolhidos) vence o formato padrão.
function htmlRender(D, indice, rotulo, formato) {
  const marcado = escolhaDe(D.id, indice) ?? formato;
  return `<span class="render-escolha">
    <select data-formato-de="${indice}" aria-label="Formato do Short">${opcoesFormato(marcado)}</select>
    <button class="botao mini" type="button" data-renderizar="${indice}">${esc(rotulo)}</button></span>`;
}

const htmlCancelar = indice =>
  `<button class="botao mini" type="button" data-cancelar="${indice}">Cancelar</button>`;

// Quem não tem corte ganha o seletor e "Renderizar"; quem tem mostra o status do render (a decisão
// da curadoria continua na última coluna — são coisas diferentes, ver desvio 1 do plano B).
function htmlAcaoRender(D, c) {
  return c.corte ? `<span class="chip">${esc(NOMES_CORTE[c.corte])}</span>`
    : htmlRender(D, c.indice, "Renderizar", D.formato);
}

function htmlCandidatos(D) {
  return `<div class="candidatos">
    <div class="cand cab"><span>Nota</span><span>Início</span><span>Dur.</span>
      <span>Candidato<span class="cand-justif-extra"> e justificativa</span></span><span></span></div>
    ${D.candidatos.map(c => `<div class="cand ${c.indice === candSel ? "sel" : ""}" data-cand="${c.indice}" tabindex="0" role="button" aria-pressed="${c.indice === candSel}">
      <span class="n ${c.nota_final >= 80 ? "up" : ""}">${nota10(c.nota_final)}</span>
      <span class="num">${tempo(c.inicio)}</span><span class="num">${tempo(c.fim - c.inicio)}</span>
      <div><div class="t">${esc(c.titulo)}</div><div class="j">${esc(c.justificativa)}</div><div class="cand-render">${htmlAcaoRender(D, c)}</div></div>
      <span class="decisao ${esc(c.decisao ?? "")}"${c.decisao ? ` title="${esc(c.decisao)}" aria-label="${esc(c.decisao)}"` : ""}>${c.decisao ? esc(c.decisao) : ""}</span></div>`).join("")}</div>`;
}

// A faixa que o player toca (ver player.js): o Short pronto, se houver, senão o trecho original.
// O fim do Short começa no teto (duração do trecho — o render só tira pausas) e é trocado pela
// duração do arquivo quando os metadados chegam.
function faixaDe(D, c) {
  const k = corteDe(D, c.indice);
  if (k?.video) {
    return { src: srcShort(k), classe: "short-video", inicio: 0, fim: k.fim - k.inicio,
      preroll: false, fimDoArquivo: true, nome: "Short" };
  }
  return { src: `/api/episodios/${encodeURIComponent(D.id)}/video#t=${c.inicio},${c.fim}`, classe: "trecho",
    inicio: c.inicio, fim: c.fim, preroll: true, fimDoArquivo: false, nome: "trecho" };
}

// Player + o que acompanha o Short: baixar, copiar título, versão/formato (o da versão pronta,
// não o pedido na fila), "Renderizar de novo" (versão nova no formato escolhido), "Cancelar"
// enquanto está na fila, e a causa do erro com
// "tentar de novo" (um corte em erro pode ainda ter o MP4 da versão anterior). "Editar" só
// para quem já tem corte fora do render (plano C, decisão 4) — junto do Short, ou do erro se
// ainda não há Short.
function htmlMidia(D, c) {
  const k = corteDe(D, c.indice);
  const linkEditar = k && !["na_fila", "renderizando"].includes(k.status)
    ? `<a class="botao mini" href="#editor/${encodeURIComponent(D.id)}/${c.indice}">Editar</a>` : "";
  const erro = k?.status === "erro"
    ? `<p class="erro-txt corte-erro" title="${esc(k.erro)}">${esc(k.erro)}</p>
       <div class="short-acoes">${htmlRender(D, c.indice, "tentar de novo", k.formato)}
       ${k.video ? "" : linkEditar}</div>` : "";
  const acoes = k?.video
    ? `<div class="short-acoes"><a class="botao mini" href="${esc(k.video)}?baixar=true" download>Baixar MP4</a>
        <button class="botao mini" type="button" data-copiar>Copiar título</button>${linkEditar}
        <span class="num">v${k.versao} · ${esc(k.formato_pronto)}</span></div>` : "";
  const denovo = k?.status === "pronto"
    ? `<div class="short-acoes">${htmlRender(D, c.indice, "Renderizar de novo", k.formato)}</div>` : "";
  const cancelar = k?.status === "na_fila" ? `<div class="short-acoes">${htmlCancelar(c.indice)}</div>` : "";
  return `${htmlPlayer(faixaDe(D, c))}${acoes}${denovo}${cancelar}${erro}`;
}

function htmlPainel(D, c) {
  const rub = D.rubrica.map(k => `<div class="rub"><span>${esc(NOMES_RUBRICA[k] ?? k)}</span>
    <div class="b"><i style="width:${rubPct(c.notas[k])}%"></i></div><span>${c.notas[k] ?? "—"}</span></div>`).join("");
  const decidido = c.decisao ? `<p class="sub">Decidido: <b>${esc(c.decisao)}</b></p>` :
    `<div class="decide"><button class="botao mini ok" data-decide="aprovado">✓ Aprovar</button>
      <button class="botao mini no" data-decide="rejeitado">✕ Rejeitar</button></div>
     <div class="motivo" hidden><select id="motivo-cat">${D.motivos.map(m => `<option>${esc(m)}</option>`).join("")}</select>
      <input id="motivo-txt" placeholder="detalhe (opcional)"><button class="botao mini no" id="motivo-ok">Rejeitar</button></div>`;
  return `<aside class="painel">
    ${htmlMidia(D, c)}
    <h3>${esc(c.titulo)}</h3>
    <p class="meta">${esc(D.titulo ?? D.id)} · ${tempo(c.inicio)} → ${tempo(c.fim)} · nota ${nota10(c.nota_final)}</p>
    <div class="rubrica">${rub}</div>
    <p class="porque">${esc(c.justificativa)}</p>
    <div class="tags">${c.bonus.map(t => `<span class="chip">${esc(t)}</span>`).join("")}${c.penalidades.map(t => `<span class="chip no">${esc(t)}</span>`).join("")}</div>
    ${decidido}</aside>`;
}

// Todos os controles de decisão do painel (aprovar, rejeitar, e os do motivo) — desabilitados
// juntos durante o POST, porque qualquer um que ficasse ativo daria pra disparar uma segunda
// decisão (ou trocar o motivo) enquanto a primeira ainda está em voo.
function controlesDecisao(painel) {
  return [...$$("[data-decide]", painel), $("#motivo-ok", painel), $("#motivo-cat", painel), $("#motivo-txt", painel)]
    .filter(Boolean);
}

async function decidir(D, c, decisao, motivo, botoes) {
  const meu = desenhar.n;   // lido ANTES do await: uma navegação durante o POST não deve redesenhar aqui
  botoes.forEach(b => { b.disabled = true; });
  try {
    await post(`/api/episodios/${encodeURIComponent(D.id)}/candidatos/${c.indice}/decisao`, { decisao, motivo });
    if (meu !== desenhar.n || D.id !== epSel) return;
    await blocoEpisodio(D.id, desenhar.n);
  } catch (e) {
    if (meu !== desenhar.n || D.id !== epSel) return;
    avisar(e.message);
    botoes.forEach(b => { b.disabled = false; });
  }
}

// "Renderizar" (tabela), "tentar de novo" e "Renderizar de novo" (painel) mandam o formato do
// seletor ao lado; "Cancelar" (painel e grade) usa a ação "cancelar". atualizarProducao() religa
// o polling — é ele que move o cartão de "na fila" a "pronto".
async function acaoCorte(D, indice, botao, acao, corpo) {
  const meu = desenhar.n;   // lido ANTES do await, como em decidir()
  botao.disabled = true;
  try {
    await post(`/api/episodios/${encodeURIComponent(D.id)}/cortes/${indice}/${acao}`, corpo);
    if (acao === "renderizar") delete formatosEscolhidos[D.id]?.[indice];   // o corte já tem o formato
    atualizarProducao();
    if (meu !== desenhar.n || D.id !== epSel) return;
    await blocoEpisodio(D.id, desenhar.n);
  } catch (e) {
    if (meu !== desenhar.n || D.id !== epSel) return;
    avisar(e.message);
    botao.disabled = false;
  }
}

function ligarPainel(D, c) {
  const painel = $(".painel");
  $$("[data-decide]", painel).forEach(b => {
    b.onclick = () => {
      if (b.dataset.decide === "aprovado") {
        decidir(D, c, "aprovado", null, controlesDecisao(painel));
      } else {
        $(".motivo", painel).hidden = false;
        $("#motivo-cat").focus();
      }
    };
  });
  const ok = $("#motivo-ok");
  if (ok) ok.onclick = () => {
    const txt = $("#motivo-txt").value.trim();
    const motivo = txt ? `${$("#motivo-cat").value}: ${txt}` : $("#motivo-cat").value;
    decidir(D, c, "rejeitado", motivo, controlesDecisao(painel));
  };
  // Copia o título do CORTE (o que vai pro YouTube), não o do candidato.
  const copiar = $("[data-copiar]", painel);
  if (copiar) copiar.onclick = () => navigator.clipboard.writeText(corteDe(D, c.indice).titulo)
    .then(() => avisar("título copiado"), e => avisar(`não deu pra copiar: ${e.message}`));
  ligarVideo(painel, faixaDe(D, c));
}

function ligarSelecao(alvo, id) {
  $$("[data-cand]", alvo).forEach(el => {
    const abrir = () => {
      candSel = Number(el.dataset.cand);
      focoCand = el.closest(".grade-shorts") ? ".grade-shorts" : ".candidatos";
      blocoEpisodio(id, desenhar.n).catch(e => avisar(e.message));
    };
    el.onclick = abrir;
    // Guarda ev.target === el pelo mesmo motivo de ligarLista (episodios.js): um controle
    // aninhado dentro da linha (ex. "Renderizar") não deve reabrir o candidato com Enter/Espaço.
    el.onkeydown = ev => {
      if (ev.target !== el) return;
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); abrir(); }
    };
  });
}

// Os controles vivem dentro da linha/cartão clicável (role=button): stopPropagation impede que o
// clique no seletor ou no botão também reselecione o candidato e redesenhe o detalhe.
function ligarAcoesCorte(D, alvo) {
  $$("[data-formato-de]", alvo).forEach(s => {
    s.onclick = ev => ev.stopPropagation();
    s.onchange = () => { (formatosEscolhidos[D.id] ??= {})[Number(s.dataset.formatoDe)] = s.value; };
  });
  $$("[data-renderizar]", alvo).forEach(b => {
    b.onclick = ev => {
      ev.stopPropagation();
      const formato = $("[data-formato-de]", b.closest(".render-escolha")).value;
      acaoCorte(D, Number(b.dataset.renderizar), b, "renderizar", { formato });
    };
  });
  $$("[data-cancelar]", alvo).forEach(b => {
    b.onclick = ev => { ev.stopPropagation(); acaoCorte(D, Number(b.dataset.cancelar), b, "cancelar", {}); };
  });
}

async function blocoEpisodio(id, meu) {
  let D;
  try {
    D = await api(`/api/episodios/${encodeURIComponent(id)}`);
  } catch (e) {
    // Falha no fetch não deixa o detalhe antigo (de outro episódio) na tela — limpa e mostra o erro.
    if (meu !== desenhar.n || id !== epSel) return;
    const alvo = $("#detalhe-episodio");
    if (alvo) alvo.innerHTML = `<div class="detalhe-erro"><h2>Não foi possível carregar o episódio</h2><p>${esc(e.message)}</p></div>`;
    return;
  }
  // meu !== desenhar.n descarta resposta de navegação anterior; id !== epSel descarta resposta
  // de um episódio que não é mais o selecionado (ex. troca rápida enquanto o fetch está em voo).
  if (meu !== desenhar.n || id !== epSel) return;
  const alvo = $("#detalhe-episodio");
  if (!alvo) return;
  if (!D.candidatos.length) {
    alvo.innerHTML = Object.values(D.etapas).some(et => et.situacao === "erro") ? ""
      : vazio("Procurando os momentos…", "Os candidatos aparecem aqui quando a etapa 'momentos' terminar.");
    return;
  }
  if (!D.candidatos.some(c => c.indice === candSel)) candSel = D.candidatos[0].indice;
  const c = D.candidatos.find(x => x.indice === candSel);
  alvo.innerHTML = `<div class="detalhe"><div>${htmlGrade(D)}<div class="secao"><h2>Candidatos <em>— ${esc(D.titulo ?? id)}</em></h2>
    <span class="num">${D.candidatos.length} momentos · nota = rubrica do detector (0–10)</span></div>${htmlCandidatos(D)}</div>
    ${htmlPainel(D, c)}</div>`;
  ligarSelecao(alvo, id);   // liga a tabela E os cartões da grade (mesmo data-cand)
  ligarAcoesCorte(D, alvo);
  ligarPainel(D, c);
  // Todo redesenho local (seleção de candidato, decisão) troca o HTML inteiro do detalhe — sem
  // isso o foco cairia pro <body> a cada clique/Enter, quebrando a navegação por teclado.
  // Volta pra onde a seleção veio; se o candidato não tem cartão na grade, cai na tabela.
  const sel = `[data-cand="${candSel}"]`;
  ($(`${focoCand} ${sel}`, alvo) ?? $(sel, alvo))?.focus();
}
