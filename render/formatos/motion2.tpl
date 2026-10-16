<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      /* Formato 10 — Motion v2, o "bolo de camadas" (spec 2026-10-15-f10-motion-v2): as cenas do f3
         num layout que alterna fundo claro pontilhado e marinho com brilho roxo. Estados
         (render/motion2.py): gancho (capa em cima, card embaixo), escuro (painel sozinho no meio,
         rosto num avatar redondo), claro (painel em cima, card embaixo) e respiro (só o card). A
         cabeça sai por cima do card: a faixa acima dele mostra o recorte sem fundo
         (assets/recorte.webm) com a mesma câmera. Legenda palavra a palavra; um efeito sonoro em
         cada troca e em cada batida. */
      {{TEMA_CSS}}
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1080px; height: 1920px; overflow: hidden; background: #fbfbfd; }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; color: var(--fg); font-family: "Montserrat", sans-serif; }

      /* ---------- fundos ---------- */
      .fundo { position: absolute; inset: 0; }
      #fundo-claro { background-color: #fbfbfd; background-image: radial-gradient(circle, rgba(13, 11, 26, 0.09) 2px, transparent 2.5px); background-size: 36px 36px; }
      #fundo-escuro { opacity: 0; background: radial-gradient(60% 38% at 22% 18%, rgba(123, 92, 255, 0.34), transparent 70%), radial-gradient(55% 35% at 85% 88%, rgba(47, 107, 255, 0.26), transparent 70%), #070818; }

      /* ---------- o card de quem fala, com a faixa da cabeça por cima ---------- */
      #rig { position: absolute; left: 40px; top: 740px; width: 1000px; height: 1100px; }
      #cabeca { position: absolute; left: 0; top: 0; width: 1000px; height: 200px; overflow: hidden; }
      #card { position: absolute; left: 0; top: 200px; width: 1000px; height: 900px; overflow: hidden; border-radius: 44px; background: #000; box-shadow: 0 30px 80px rgba(60, 40, 160, 0.35), 0 0 0 10px rgba(123, 92, 255, 0.12); }
      #card::after { content: ""; position: absolute; inset: 0; border-radius: 44px; border: 4px solid var(--brand); pointer-events: none; }
      #q-card, #q-cabeca { position: absolute; left: 0; top: 0; width: {{QD_W}}px; height: {{QD_H}}px; }
      #v-card, #v-cabeca { width: {{QD_W}}px; height: {{QD_H}}px; display: block; }

      /* ---------- avatar redondo das cenas escuras ---------- */
      #avatar { position: absolute; right: 60px; top: 140px; width: 220px; height: 220px; border-radius: 50%; overflow: hidden; opacity: 0; background: #000; border: 4px solid #b9a6ff; box-shadow: 0 0 40px rgba(123, 92, 255, 0.55); }
      #q-avatar { position: absolute; left: 0; top: 0; width: {{QA_W}}px; height: {{QA_H}}px; }
      #v-avatar { width: {{QA_W}}px; height: {{QA_H}}px; display: block; }

      /* ---------- painéis: em cima no claro, no meio no escuro ---------- */
      #faixa-base, .faixa .painel { position: absolute; left: 40px; top: 48px; width: 1000px; height: 724px; border-radius: 36px; background: var(--cartao); border: 2px solid var(--linha); overflow: hidden; box-shadow: 0 30px 80px rgba(60, 40, 160, 0.16); }
      #faixa-base { opacity: 0; display: flex; align-items: center; justify-content: center; }
      #faixa-base span { font-family: "JetBrains Mono", monospace; font-size: 30px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; color: var(--brand); }
      .faixa { position: absolute; left: 0; top: 0; width: 1080px; height: 820px; }
      .faixa.solo { top: 560px; }
      .faixa.solo .painel { box-shadow: 0 0 80px rgba(123, 92, 255, 0.35); }
      .faixa .painel::before { content: ""; position: absolute; width: 900px; height: 900px; left: -300px; top: -520px; border-radius: 50%; background: radial-gradient(circle, color-mix(in srgb, var(--brand) 12%, transparent) 0%, transparent 62%); }
      .cab { position: absolute; left: 44px; right: 44px; top: 34px; display: flex; align-items: center; gap: 14px; font-family: "JetBrains Mono", monospace; font-size: 26px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); z-index: 1; }
      .cab .ponto { width: 14px; height: 14px; border-radius: 50%; background: var(--brand); }
      .cab .cab-dir { margin-left: auto; color: var(--fg); }
      .ic { display: block; }

      {{COMPONENTES_CSS}}

      /* ---------- capa do gancho: no fundo claro, em cima do card ---------- */
      .capa { position: absolute; left: 0; top: 0; width: 1080px; height: 740px; }
      .capa .escurece { display: none; }
      .capa .rotulo { position: absolute; left: 64px; right: 64px; top: 300px; text-align: center; font-family: "JetBrains Mono", monospace; font-size: 30px; font-weight: 700; letter-spacing: 0.2em; color: var(--brand); text-transform: uppercase; }
      .capa .titulo { position: absolute; left: 64px; right: 64px; top: 370px; text-align: center; font-weight: 900; line-height: 1.02; letter-spacing: -0.035em; text-transform: uppercase; color: var(--fg); }
      .capa .titulo b { color: var(--brand); font-weight: 900; }

      /* ---------- legenda: uma palavra por vez, grande ---------- */
      .leg { position: absolute; left: 60px; right: 60px; top: 1560px; height: 130px; }
      .leg span { position: relative; display: block; width: 100%; height: 130px; }
      .leg i { position: absolute; left: 0; right: 0; top: 0; text-align: center; font-style: normal; font-weight: 900; font-size: 92px; line-height: 1.2; letter-spacing: -0.02em; color: #fff; white-space: nowrap; opacity: 0; text-shadow: 0 4px 0 rgba(0, 0, 0, 0.55), 0 0 26px rgba(0, 0, 0, 0.55); }
      .leg i.num { color: #c9bbff; text-shadow: 0 0 30px rgba(123, 92, 255, 0.85), 0 4px 0 rgba(0, 0, 0, 0.5); }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-width="1080" data-height="1920" data-duration="{{DUR}}" data-fps="30">
      <div id="fundo-claro" class="fundo"></div>
      <div id="fundo-escuro" class="fundo"></div>
      <div id="faixa-base"><span>{{ROTULO_BASE}}</span></div>
{{CENAS}}
      <div id="rig">
        <div id="cabeca"><div id="q-cabeca" data-layout-allow-overflow><video id="v-cabeca" class="clip" src="assets/recorte.webm" data-start="0" data-duration="{{DUR}}" data-track-index="3" muted playsinline></video></div></div>
        <div id="card"><div id="q-card" data-layout-allow-overflow><video id="v-card" class="clip" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="1" muted playsinline></video></div></div>
      </div>
      <div id="avatar"><div id="q-avatar" data-layout-allow-overflow><video id="v-avatar" class="clip" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="5" muted playsinline></video></div></div>
      <audio id="cam-audio" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="10" data-volume="1" data-audio-group="voz"></audio>
{{SFX}}
{{TRILHA}}
{{LEGENDAS}}
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });

      {{MOTION_JS}}

      // estados (render/motion2.py): o fundo cruza em 0,2 s, o card desce/sobe e o avatar estala
      for (const [t, e] of {{ESTADOS}}) {
        const escuro = e === "escuro", respiro = e === "respiro";
        const t0 = Math.max(0, t - 0.12);
        tl.to("#fundo-escuro", { opacity: escuro ? 1 : 0, duration: 0.2, ease: "power2.inOut" }, t0);
        tl.to("#rig", { opacity: escuro ? 0 : 1, y: escuro ? 140 : (respiro ? -300 : 0), duration: 0.28, ease: escuro ? "power2.in" : "power3.out" }, t0);
        tl.to("#avatar", { opacity: escuro ? 1 : 0, scale: escuro ? 1 : 0.7, duration: 0.25, ease: escuro ? "back.out(2)" : "power2.in" }, t0);
        tl.set("#faixa-base", { opacity: e === "claro" ? 1 : 0 }, t);
        tl.set(".leg", { top: escuro ? 1480 : (respiro ? 1300 : 1560) }, t);
      }

      // câmeras: posição fixa por plano, troca seca no corte de câmera (rosto.py: trilha_fixa)
      function posicionar(sel, TR) {
        tl.set(sel, { x: TR[0][1], y: TR[0][2] }, 0);
        for (let k = 1; k < TR.length; k++) {
          if (TR[k][3]) { tl.set(sel, { x: TR[k][1], y: TR[k][2] }, TR[k][0]); continue; }
          tl.to(sel, { x: TR[k][1], y: TR[k][2], duration: TR[k][0] - TR[k - 1][0], ease: "sine.inOut" }, TR[k - 1][0]);
        }
      }
      posicionar("#q-card", {{TRILHA_CARD}});
      posicionar("#q-cabeca", {{TRILHA_CABECA}});
      posicionar("#q-avatar", {{TRILHA_AVATAR}});

      // cenas (render/motion_animacao.py) — a capa entra como no f3
{{ANIMACOES}}

      // legenda: cada palavra acende no seu início e apaga quando a seguinte entra; número em roxo
      document.querySelectorAll(".leg").forEach((g) => {
        const ws = [...g.querySelectorAll("i")];
        ws.forEach((w, j) => {
          if (/\d/.test(w.textContent)) w.classList.add("num");
          const t = parseFloat(w.dataset.t);
          tl.set(w, { opacity: 1 }, t);
          tl.fromTo(w, { scale: 1.12, y: 6 }, { scale: 1, y: 0, duration: 0.14, ease: "back.out(3)", immediateRender: false }, t);
          if (j + 1 < ws.length) tl.set(w, { opacity: 0 }, parseFloat(ws[j + 1].dataset.t));
        });
      });
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
