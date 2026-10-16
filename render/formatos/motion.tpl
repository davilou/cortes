<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      /* Formato 3 — Motion denso (spec 2026-10-15-f3-denso; pesquisa/05-reel-referencia-f3.md):
         painel na faixa de cima (0–820 px) e quem fala num card embaixo (x 40–1040, y 860–1840),
         quase o tempo todo; rosto cheio só no gancho (com a capa) e nos respiros. Corte seco
         entre os estados; os elementos de cada painel entram um a um. O tema vira variáveis CSS
         (render/motion_tema.py); os componentes só usam as variáveis. A câmera não segue o rosto:
         posição fixa por plano de câmera, nas duas janelas. */
      {{TEMA_CSS}}
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1080px; height: 1920px; overflow: hidden; background: var(--bg); }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; background: var(--bg); color: var(--fg); font-family: "Montserrat", sans-serif; }

      /* ---------- câmeras: tela cheia e o card de baixo ---------- */
      #cam-cheio { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; background: #000; }
      #cam-div { position: absolute; left: 40px; top: 860px; width: 1000px; height: 980px; overflow: hidden; background: #000; border-radius: 40px; box-shadow: 0 30px 80px rgba(0,0,0,0.45); opacity: 0; }
      #q-cheio { position: absolute; left: 0; top: 0; width: {{QW}}px; height: 1920px; }
      #v-cheio { width: {{QW}}px; height: 1920px; display: block; }
      #q-div { position: absolute; left: 0; top: 0; width: {{QD_W}}px; height: {{QD_H}}px; }
      #v-div { width: {{QD_W}}px; height: {{QD_H}}px; display: block; }
      .vinheta { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 35%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.4) 100%); }

      /* ---------- faixa de cima: o cartão do painel ---------- */
      #faixa-base, .faixa .painel { position: absolute; left: 40px; top: 48px; width: 1000px; height: 724px; border-radius: 36px; background: var(--cartao); border: 2px solid var(--linha); overflow: hidden; }
      #faixa-base { opacity: 0; display: flex; align-items: center; justify-content: center; }
      #faixa-base span { font-family: "JetBrains Mono", monospace; font-size: 30px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted); }
      .faixa { position: absolute; left: 0; top: 0; width: 1080px; height: 820px; }
      .faixa .painel::before { content: ""; position: absolute; width: 900px; height: 900px; left: -300px; top: -520px; border-radius: 50%; background: radial-gradient(circle, color-mix(in srgb, var(--brand) 16%, transparent) 0%, transparent 62%); }
      .cab { position: absolute; left: 44px; right: 44px; top: 34px; display: flex; align-items: center; gap: 14px; font-family: "JetBrains Mono", monospace; font-size: 26px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); z-index: 1; }
      .cab .ponto { width: 14px; height: 14px; border-radius: 50%; background: var(--brand); }
      .cab .cab-dir { margin-left: auto; color: var(--fg); }
      .ic { display: block; }

      {{COMPONENTES_CSS}}

      /* ---------- capa (gancho, 0–2 s, por cima do rosto cheio) ---------- */
      .capa { position: absolute; inset: 0; }
      .capa .escurece { position: absolute; inset: 0; background: linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.35) 32%, rgba(0,0,0,0) 52%); }
      .capa .rotulo { position: absolute; left: 64px; top: 150px; font-family: "JetBrains Mono", monospace; font-size: 30px; font-weight: 700; letter-spacing: 0.14em; color: var(--fg); text-transform: uppercase; }
      .capa .titulo { position: absolute; left: 64px; right: 64px; top: 210px; font-weight: 900; line-height: 1.02; letter-spacing: -0.035em; text-transform: uppercase; color: #fff; font-family: var(--fonte-titulo); }
      .capa .titulo b { color: var(--brand); font-weight: 900; }

      /* ---------- legenda: pequena, minúscula, dentro do card (pesquisa/05) ---------- */
      .leg { position: absolute; left: 80px; right: 80px; top: 1380px; display: flex; justify-content: center; }
      .leg span { display: block; max-width: 920px; text-align: center; font-weight: 800; font-size: 46px; line-height: 1.1; letter-spacing: -0.01em; color: #fff; text-shadow: 0 3px 0 rgba(0,0,0,0.75), 0 0 20px rgba(0,0,0,0.6); }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-width="1080" data-height="1920" data-duration="{{DUR}}" data-fps="30">
      <!-- as duas câmeras tocam o tempo todo; o estado decide qual aparece -->
      <div id="cam-cheio">
        <div id="q-cheio" data-layout-allow-overflow><video id="v-cheio" class="clip" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="0" muted playsinline></video></div>
        <div class="vinheta"></div>
      </div>
      <div id="cam-div">
        <div id="q-div" data-layout-allow-overflow><video id="v-div" class="clip" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="1" muted playsinline></video></div>
      </div>
      <div id="faixa-base"><span>{{ROTULO_BASE}}</span></div>
      <audio id="cam-audio" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="10" data-volume="1" data-audio-group="voz"></audio>
{{TRILHA}}
{{CENAS}}
{{LEGENDAS}}
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });

      {{MOTION_JS}}

      // estados: cada troca entre "cheio" e "div" é um corte seco; a legenda vai junto do rosto
      for (const [t, e] of {{ESTADOS}}) {
        const div = e === "div";
        tl.set("#cam-div, #faixa-base", { opacity: div ? 1 : 0 }, t);
        tl.set("#cam-cheio", { opacity: div ? 0 : 1 }, t);
        tl.set(".leg", { top: div ? 1560 : 1380 }, t);
      }

      // câmeras: posição fixa por plano, troca seca no corte de câmera (rosto.py: trilha_fixa)
      function posicionar(sel, TR) {
        tl.set(sel, { x: TR[0][1], y: TR[0][2] }, 0);
        for (let k = 1; k < TR.length; k++) {
          if (TR[k][3]) { tl.set(sel, { x: TR[k][1], y: TR[k][2] }, TR[k][0]); continue; }
          tl.to(sel, { x: TR[k][1], y: TR[k][2], duration: TR[k][0] - TR[k - 1][0], ease: "sine.inOut" }, TR[k - 1][0]);
        }
      }
      posicionar("#q-cheio", {{TRILHA_CHEIO}});
      posicionar("#q-div", {{TRILHA_DIV}});

      // cenas (render/motion_animacao.py)
{{ANIMACOES}}

      document.querySelectorAll(".leg span").forEach((el) => {
        tl.fromTo(el, { scale: 0.9, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.12, ease: "power2.out" }, parseFloat(el.parentElement.dataset.start));
      });
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
