"use strict";
// Cenas do f3 (plano 2026-10-03-motion): lista só leitura do que o Claude escolheu — componente,
// tempo e parâmetros — e das cenas descartadas, com o motivo (número que a fala não disse, ritmo,
// parâmetro inválido). "Refazer motion" apaga o cache e pede a prévia, que chama o Claude de novo.
const NOMES_COMPONENTE = { capa: "capa", contador: "contador", valor_cheio: "valor em tela cheia",
  comparacao: "comparação", chat: "chat", lista: "lista", rota: "rota" };

function textoParams(p) {
  // valores simples viram "campo: valor"; listas e colunas viram texto curto
  return Object.entries(p ?? {}).filter(([, v]) => v !== null && v !== "")
    .map(([k, v]) => `${k}: ${Array.isArray(v)
      ? v.map(x => typeof x === "object" ? `${x.rotulo} ${x.valor_texto}` : x).join(" · ") : v}`)
    .join(" | ");
}

function htmlCena(c, descartada) {
  const classe = descartada ? "motion-item fora" : "motion-item";
  const nome = esc(NOMES_COMPONENTE[c.componente] ?? c.componente);
  const motivo = descartada ? `<p class="sub erro-txt" title="${esc(c.motivo)}">${esc(c.motivo)}</p>` : "";
  return `<li class="${classe}"><span class="num">${tempo(c.inicio)}–${tempo(c.fim)}</span>
    <strong>${descartada ? "descartada · " : ""}${nome}</strong>
    <p class="sub" title="${esc(textoParams(c.params))}">${esc(textoParams(c.params))}</p>${motivo}</li>`;
}

function htmlListaMotion(ed) {
  if (ed.motion_erro) return `<p class="sub erro-txt" title="${esc(ed.motion_erro)}">não deu para
    ler o motion: ${esc(ed.motion_erro)}</p>`;
  if (!ed.motion) return `<p class="sub">As cenas aparecem quando a prévia ficar pronta.</p>`;
  const cenas = ed.motion.cenas.map(c => htmlCena(c, false));
  const fora = ed.motion.descartadas.map(c => htmlCena(c, true));
  return `<ul class="motion-lista">${[...cenas, ...fora].join("")}</ul>`;
}

function htmlMotion(ed) {
  const dis = ed.editavel ? "" : "disabled";
  return `${htmlListaMotion(ed)}
    <button class="botao mini refazer-motion" id="refazer-motion" ${dis}>Refazer motion</button>`;
}

const AVISO_REFAZER_MOTION = "Refazer o motion? As cenas atuais são descartadas e o Claude escolhe "
  + "tudo de novo.";

async function refazerMotion(b) {
  if (!confirm(AVISO_REFAZER_MOTION)) return;
  const ed = ED, meu = desenhar.n;
  b.disabled = true;
  try {
    const novo = await post(urlEditor(ed, "/motion/refazer"));
    if (meu === desenhar.n && ED === ed) aplicarEstado(novo);
  } catch (e) { avisar(e.message); b.disabled = false; }
}

function ligarMotion() {
  const b = $("#refazer-motion");
  if (b) b.onclick = () => refazerMotion(b);
}
