"use strict";
// Detalhe do episódio: candidatos (nota 0–10), painel com o trecho tocando, rubrica, justificativa,
// tags e aprovar/rejeitar. No plano A ainda não há Shorts renderizados: o trecho toca do vídeo
// original (16:9) via /api/episodios/{id}/video — o fragmento #t=início,fim é só uma dica inicial
// pro navegador; quem garante o recorte de verdade (não passar do início, parar no fim) é o
// listener de timeupdate em ligarVideo(), porque o fragmento #t= não é respeitado de forma
// confiável depois que o usuário pausa/retoma ou arrasta a barra.
let candSel = 0;
const NOMES_RUBRICA = { gancho_3s: "Gancho 3 s", autocontido: "Autocontido", espanto: "Espanto",
  historia_ou_virada: "História/virada", fechamento: "Fechamento" };
const nota10 = n => (n / 10).toFixed(1).replace(".", ",");
const tempo = s => new Date(s * 1000).toISOString().slice(s >= 3600 ? 11 : 14, 19);

function htmlCandidatos(D) {
  return `<div class="candidatos">
    <div class="cand cab"><span>Nota</span><span>Início</span><span>Dur.</span><span>Candidato e justificativa</span><span></span></div>
    ${D.candidatos.map(c => `<div class="cand ${c.indice === candSel ? "sel" : ""}" data-cand="${c.indice}" tabindex="0" role="button" aria-pressed="${c.indice === candSel}">
      <span class="n ${c.nota_final >= 80 ? "up" : ""}">${nota10(c.nota_final)}</span>
      <span class="num">${tempo(c.inicio)}</span><span class="num">${tempo(c.fim - c.inicio)}</span>
      <div><div class="t">${esc(c.titulo)}</div><div class="j">${esc(c.justificativa)}</div></div>
      <span class="decisao ${esc(c.decisao ?? "")}">${c.decisao ? esc(c.decisao) : ""}</span></div>`).join("")}</div>`;
}

function htmlPainel(D, c) {
  const rub = D.rubrica.map(k => `<div class="rub"><span>${esc(NOMES_RUBRICA[k] ?? k)}</span>
    <div class="b"><i style="width:${(c.notas[k] ?? 0) * 20}%"></i></div><span>${c.notas[k] ?? "—"}</span></div>`).join("");
  const decidido = c.decisao ? `<p class="sub">Decidido: <b>${esc(c.decisao)}</b></p>` :
    `<div class="decide"><button class="botao mini ok" data-decide="aprovado">✓ Aprovar</button>
      <button class="botao mini no" data-decide="rejeitado">✕ Rejeitar</button></div>
     <div class="motivo" hidden><select id="motivo-cat">${D.motivos.map(m => `<option>${esc(m)}</option>`).join("")}</select>
      <input id="motivo-txt" placeholder="detalhe (opcional)"><button class="botao mini no" id="motivo-ok">Rejeitar</button></div>`;
  return `<aside class="painel">
    <video class="trecho" controls preload="metadata" src="/api/episodios/${encodeURIComponent(D.id)}/video#t=${c.inicio},${c.fim}"></video>
    <h3>${esc(c.titulo)}</h3>
    <p class="meta">${esc(D.titulo ?? D.id)} · ${tempo(c.inicio)} → ${tempo(c.fim)} · nota ${nota10(c.nota_final)}</p>
    <div class="rubrica">${rub}</div>
    <p class="porque">${esc(c.justificativa)}</p>
    <div class="tags">${c.bonus.map(t => `<span class="chip">${esc(t)}</span>`).join("")}${c.penalidades.map(t => `<span class="chip no">${esc(t)}</span>`).join("")}</div>
    ${decidido}</aside>`;
}

// O fragmento #t= só posiciona o vídeo na carga inicial; depois disso o navegador não respeita
// mais o recorte (pausar/arrastar a barra escapa do trecho). timeupdate reimpõe os dois limites
// o tempo todo: ao dar play fora do trecho, volta pro início; ao alcançar o fim, pausa ali.
function ligarVideo(v, c) {
  v.onplay = () => { if (v.currentTime < c.inicio || v.currentTime >= c.fim) v.currentTime = c.inicio; };
  v.ontimeupdate = () => { if (v.currentTime >= c.fim) { v.pause(); v.currentTime = c.fim; } };
}

async function decidir(D, c, decisao, motivo, botoes) {
  botoes.forEach(b => { b.disabled = true; });
  try {
    await post(`/api/episodios/${encodeURIComponent(D.id)}/candidatos/${c.indice}/decisao`, { decisao, motivo });
    await blocoEpisodio(D.id, desenhar.n);
  } catch (e) {
    avisar(e.message);
    botoes.forEach(b => { b.disabled = false; });
  }
}

function ligarPainel(D, c) {
  const painel = $(".painel");
  $$("[data-decide]", painel).forEach(b => {
    b.onclick = () => {
      if (b.dataset.decide === "aprovado") {
        decidir(D, c, "aprovado", null, $$("[data-decide]", painel));
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
    decidir(D, c, "rejeitado", motivo, [ok, $("#motivo-cat"), $("#motivo-txt")]);
  };
  ligarVideo($("video.trecho", painel), c);
}

async function blocoEpisodio(id, meu) {
  const D = await api(`/api/episodios/${encodeURIComponent(id)}`);
  if (meu !== desenhar.n) return;
  const alvo = $("#detalhe-episodio");
  if (!D.candidatos.length) {
    alvo.innerHTML = Object.values(D.etapas).some(et => et.situacao === "erro") ? ""
      : vazio("Procurando os momentos…", "Os candidatos aparecem aqui quando a etapa 'momentos' terminar.");
    return;
  }
  if (!D.candidatos.some(c => c.indice === candSel)) candSel = D.candidatos[0].indice;
  const c = D.candidatos.find(x => x.indice === candSel);
  alvo.innerHTML = `<div class="detalhe"><div><div class="secao"><h2>Candidatos <em>— ${esc(D.titulo ?? id)}</em></h2>
    <span class="num">${D.candidatos.length} momentos · nota = rubrica do detector (0–10)</span></div>${htmlCandidatos(D)}</div>
    ${htmlPainel(D, c)}</div>`;
  $$("[data-cand]", alvo).forEach(el => {
    const abrir = () => { candSel = Number(el.dataset.cand); blocoEpisodio(id, desenhar.n).catch(e => avisar(e.message)); };
    el.onclick = abrir;
    // Guarda ev.target === el pelo mesmo motivo de ligarLista (episodios.js): um controle
    // aninhado dentro da linha não deve reabrir o mesmo candidato ao receber Enter/Espaço.
    el.onkeydown = ev => {
      if (ev.target !== el) return;
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); abrir(); }
    };
  });
  ligarPainel(D, c);
}
