"use strict";
// Cenas do f3 (plano 2026-10-03-motion; estilo denso: spec 2026-10-15-f3-denso): lista só leitura
// do que o Claude escolheu — componente, tempo e parâmetros — e das cenas descartadas, com o motivo
// (número que a fala não disse, ritmo, parâmetro inválido); a ilustração sem desenho mostra por quê.
// O tema (cores do Short) é escolhido pelo Claude e pode ser trocado aqui. "Refazer motion" apaga o
// cache e pede a prévia, que chama o Claude de novo.
const NOMES_COMPONENTE = { capa: "capa", contador: "contador", valor: "valor", comparacao: "comparação",
  chat: "chat", lista: "lista", rota: "rota", grafico: "gráfico", fluxo: "fluxo", timer: "timer",
  check: "check", grade: "grade", destaque: "frase-chave", planta: "planta", ilustracao: "ilustração",
  respiro: "respiro (rosto cheio)" };
const NOMES_TEMA = { escuro: "escuro", noite: "noite (imóvel, luxo)", clinico: "clínico (saúde)",
  dados: "dados (investimento)" };

function textoParams(p) {
  // valores simples viram "campo: valor"; listas e colunas viram texto curto
  return Object.entries(p ?? {}).filter(([, v]) => v !== null && v !== "")
    .map(([k, v]) => `${k}: ${Array.isArray(v)
      ? v.map(x => typeof x === "object" ? Object.values(x).filter(y => y !== null).join(" ") : x).join(" · ") : v}`)
    .join(" | ");
}

function htmlCena(c, descartada) {
  const classe = descartada ? "motion-item fora" : "motion-item";
  const nome = esc(NOMES_COMPONENTE[c.componente] ?? c.componente);
  const porque = descartada ? c.motivo : c.falha_svg ? `sem desenho, mostra o ícone — ${c.falha_svg}` : "";
  const motivo = porque ? `<p class="sub erro-txt" title="${esc(porque)}">${esc(porque)}</p>` : "";
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

function htmlTema(ed) {
  if (!ed.motion) return "";
  const m = ed.motion, dis = ed.editavel ? "" : "disabled";
  const ops = [["auto", `Automático (${NOMES_TEMA[m.tema_llm] ?? m.tema_llm})`],
    ...m.temas.map(t => [t, NOMES_TEMA[t] ?? t])];
  return `<label>Tema<select id="ed-tema" ${dis}>${ops.map(([v, r]) =>
    `<option value="${esc(v)}" ${v === m.tema_escolha ? "selected" : ""}>${esc(r)}</option>`).join("")}</select></label>`;
}

function htmlMotion(ed) {
  const dis = ed.editavel ? "" : "disabled";
  return `${htmlTema(ed)}${htmlListaMotion(ed)}
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
  const tema = $("#ed-tema");
  if (tema) tema.onchange = () => editar({ tema: tema.value });
}
