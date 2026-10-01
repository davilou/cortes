"use strict";
// Estado e utilidades compartilhados pelas telas. Cada tela registra a sua função em TELAS.
const TELAS = {};
let E = null;   // /api/estado
let S = [];     // /api/shorts

const $ = (seletor, el = document) => el.querySelector(seletor);
const $$ = (seletor, el = document) => [...el.querySelectorAll(seletor)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fx = v => v == null ? "—" : v.toFixed(1).replace(".", ",") + "×";
const pct = v => Math.round(v) + "%";
const mil = v => Math.round(v).toLocaleString("pt-BR");
const thumb = id => `https://i.ytimg.com/vi/${esc(id)}/hqdefault.jpg`;
const handleDe = id => E.contas.find(c => c.id === id)?.handle ?? id;
const nomeFormato = id => E.formatos[id]?.nome ?? id;
const dataHora = iso => new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

function mediana(xs) {
  if (!xs.length) return null;
  const a = [...xs].sort((p, q) => p - q), m = a.length >> 1;
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

async function api(caminho, opcoes = {}) {
  const r = await fetch(caminho, { headers: { "Content-Type": "application/json" }, ...opcoes });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = corpo.detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : `HTTP ${r.status}`);
  }
  return corpo;
}
const post = (caminho, corpo) => api(caminho, { method: "POST", body: JSON.stringify(corpo ?? {}) });

function avisar(msg) {
  const a = $("#aviso");
  a.textContent = msg;
  a.hidden = false;
  clearTimeout(avisar.t);
  avisar.t = setTimeout(() => { a.hidden = true; }, 9000);
}

function vazio(titulo, texto) {
  return `<div class="vazio"><h2>${esc(titulo)}</h2><p>${esc(texto)}</p></div>`;
}

// Trilho (nav) e barra mobile compartilham estado: cada elemento existe em dobro (um id "-m"
// para a versão mobile) e os dois são atualizados juntos; $() devolve null se o elemento não
// existir nesta tela, então cada trecho confere antes de usar.
function trilho() {
  $("#trilho-contas").innerHTML = E.contas.map(c => {
    const falhou = c.coleta && !c.coleta.ok;
    const alerta = falhou || !c.ultimo_retrato;
    const quando = falhou ? "falhou" : c.ultimo_retrato ? dataHora(c.ultimo_retrato) : "nunca";
    return `<div class="conta" title="${esc(falhou ? c.coleta.mensagem : "")}"><i class="${alerta ? "vencido" : ""}"></i>${esc(c.handle)}<small>${quando}</small></div>`;
  }).join("");
  for (const [sel, rotulo] of [["#atualizar-todas", "↻ Atualizar todas"], ["#atualizar-todas-m", "↻ Atualizar"]]) {
    const b = $(sel);
    if (!b) continue;
    b.disabled = E.rodando || !E.contas.length;
    b.textContent = E.rodando ? "atualizando…" : rotulo;
  }
  $$("[data-atualizar]").forEach(b => { b.disabled = E.rodando; });
  const sem = S.filter(l => !l.etiquetas).length;
  for (const sel of ["#sem-ligacao", "#sem-ligacao-m"]) {
    const el = $(sel);
    if (!el) continue;
    el.hidden = !sem;
    el.textContent = `${sem} sem ligação`;
  }
  const erroEl = $("#erro-coleta");
  if (erroEl) {
    erroEl.hidden = !E.erro_coleta;
    if (E.erro_coleta) erroEl.textContent = E.erro_coleta;
  }
}

let ultimoErroColeta = null;   // evita repetir o aviso a cada poll de 3s enquanto o erro persiste

async function carregar() {
  [E, S] = await Promise.all([api("/api/estado"), api("/api/shorts")]);
  trilho();
  if (E.erro_coleta && E.erro_coleta !== ultimoErroColeta) avisar(E.erro_coleta);
  ultimoErroColeta = E.erro_coleta;
}
