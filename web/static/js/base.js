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
const thumb = id => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
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

function trilho() {
  $("#trilho-contas").innerHTML = E.contas.map(c => {
    const falhou = c.coleta && !c.coleta.ok;
    const alerta = falhou || !c.ultimo_retrato;
    const quando = falhou ? "falhou" : c.ultimo_retrato ? dataHora(c.ultimo_retrato) : "nunca";
    return `<div class="conta" title="${esc(falhou ? c.coleta.mensagem : "")}"><i class="${alerta ? "vencido" : ""}"></i>${esc(c.handle)}<small>${quando}</small></div>`;
  }).join("");
  const b = $("#atualizar-todas");
  b.disabled = E.rodando || !E.contas.length;
  b.textContent = E.rodando ? "atualizando…" : "↻ Atualizar todas";
  const sem = S.filter(l => !l.etiquetas).length;
  $("#sem-ligacao").hidden = !sem;
  $("#sem-ligacao").textContent = `${sem} sem ligação`;
}

async function carregar() {
  [E, S] = await Promise.all([api("/api/estado"), api("/api/shorts")]);
  trilho();
}
