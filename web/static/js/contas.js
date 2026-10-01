"use strict";
// Tela Contas: estado de cada conta, atualizar, login manual e nova conta.

function cartaoConta(c) {
  const falhou = c.coleta && !c.coleta.ok;
  // mediana_7d/medidos vêm prontos do servidor (metodo.bases): mesma regra que o relativo usa,
  // sem recalcular aqui (e sem o viés de só olhar os Shorts já ligados que S filtraria).
  const base = c.mediana_7d != null ? mil(c.mediana_7d) : `sem base · ${c.medidos}/3`;
  return `<div class="card conta-card">
    <div class="topo"><div><h2>${esc(c.nome)}</h2><p class="sub">${esc(c.handle)} · ${esc(c.nicho)}</p></div>
      <i class="estado ${falhou || !c.ultimo_retrato ? "vencido" : ""}"></i></div>
    <dl><div><dt>Último retrato</dt><dd>${c.ultimo_retrato ? dataHora(c.ultimo_retrato) : "nunca"}</dd></div>
      <div><dt>Ligados</dt><dd>${c.ligados}</dd></div>
      <div><dt>Mediana 7d</dt><dd>${esc(base)}</dd></div></dl>
    ${falhou ? `<p class="erro">${esc(c.coleta.mensagem)}</p>` : ""}
    <div class="acoes"><button class="botao" data-atualizar="${esc(c.id)}" ${E.rodando ? "disabled" : ""}>↻ Atualizar</button>
      ${falhou || !c.ultimo_retrato ? `<button class="botao" data-login="${esc(c.id)}">Fazer login</button>` : ""}</div></div>`;
}

function cartaoNova() {
  if (!E.nichos.length) {
    return `<div class="card"><h2>Nova conta</h2><p class="sub">nenhum perfil de nicho em nichos/</p></div>`;
  }
  const campo = (nome, rotulo, dica, extra = "") =>
    `<label>${esc(rotulo)}<input name="${esc(nome)}" required placeholder="${esc(dica)}" ${extra}></label>`;
  return `<div class="card"><h2>Nova conta</h2><p class="sub">Depois de criar, clique em Fazer login e entre na janela do Chrome.</p>
    <form class="nova">${campo("id", "Id (a-z, 0-9, -)", "grana", 'pattern="[a-z0-9-]+" title="minúsculas, dígitos e hífen"')}
    ${campo("nome", "Nome", "Grana Cortes")}
    ${campo("handle", "Handle", "@grana.cortes")}
    <label>Nicho<select name="nicho">${E.nichos.map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join("")}</select></label>
    ${campo("perfil_studio", "Perfil de login", "grana")}
    <div class="acoes"><button class="botao primario">Criar conta</button></div></form></div>`;
}

async function telaContas(meu) {
  await carregar();
  if (meu !== desenhar.n) return;   // uma renderização mais nova já começou: não pisa nela
  $("#tela").innerHTML = `<header><div><h1>Contas <em>— ${E.contas.length}</em></h1>
    <p class="sub">Um perfil de login por conta. O app nunca vê senha: o login é feito na janela do Chrome.</p></div></header>
    ${E.erro_coleta ? `<div class="nota">${esc(E.erro_coleta)}</div>` : ""}
    <div class="cartoes">${E.contas.map(cartaoConta).join("")}${cartaoNova()}</div>`;
  $$("[data-atualizar]").forEach(b => { b.onclick = () => atualizar(b.dataset.atualizar); });
  $$("[data-login]").forEach(b => {
    b.onclick = async () => {
      try { await post(`/api/login/${b.dataset.login}`); avisar("Janela do Chrome aberta: entre na conta e feche a janela quando o Studio abrir."); }
      catch (e) { avisar(e.message); }
    };
  });
  const form = $("form.nova");
  if (!form) return;
  form.onsubmit = async ev => {
    ev.preventDefault();
    const corpo = Object.fromEntries(new FormData(form));
    for (const k in corpo) corpo[k] = corpo[k].trim();
    if (Object.values(corpo).some(v => !v)) { avisar("preencha todos os campos."); return; }
    const botao = $("button", form);
    botao.disabled = true;
    try { await post("/api/contas", corpo); desenhar(); }
    catch (e) { avisar(e.message); }
    finally { botao.disabled = false; }
  };
}
TELAS.contas = telaContas;
