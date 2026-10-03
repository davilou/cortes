<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      /* Formato 3 — Motion automático (plano 2026-10-03-motion): painéis que mostram o que a pessoa
         diz, escolhidos pelo Claude (render/motion.py) e montados pelo código
         (render/motion_componentes.py). Dois estados em corte seco: "cheio" (o rosto em tela cheia,
         ou o cartão na tela inteira) e "div" (o painel na faixa de cima, 680 px, e o rosto na janela
         de baixo). Tema, faixa, cartões e entradas do protótipo testes/short-400mil-dinamica, sem o
         zoom lento da capa e sem flash (Davi, 2026-10-02). A câmera não segue o rosto: posição fixa
         por plano de câmera, nas duas janelas. */
      :root {
        --bg: #0e1411; --bg2: #141c17; --fg: #eef2ec; --muted: #9aa69d;
        --brand: #5fd39a; --perda: #ff5d4f;
      }
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1080px; height: 1920px; overflow: hidden; background: var(--bg); }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; background: var(--bg); color: var(--fg); font-family: "Montserrat", sans-serif; }

      /* ---------- câmeras: tela cheia e janela abaixo da faixa ---------- */
      #cam-cheio, #cam-div { position: absolute; left: 0; width: 1080px; overflow: hidden; background: #000; }
      #cam-cheio { top: 0; height: 1920px; }
      #cam-div { top: 680px; height: 1240px; opacity: 0; }
      #q-cheio { position: absolute; left: 0; top: 0; width: {{QW}}px; height: 1920px; }
      #v-cheio { width: {{QW}}px; height: 1920px; display: block; }
      #q-div { position: absolute; left: 0; top: 0; width: {{QD_W}}px; height: {{QD_H}}px; }
      #v-div { width: {{QD_W}}px; height: {{QD_H}}px; display: block; }
      .vinheta { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 35%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%); }

      .rotulo { font-family: "JetBrains Mono", monospace; font-size: 30px; font-weight: 700; letter-spacing: 0.14em; color: var(--muted); text-transform: uppercase; }

      /* ---------- faixa (35% = 680 px) ---------- */
      .faixa { position: absolute; left: 0; top: 0; width: 1080px; height: 680px; overflow: hidden; background: var(--bg2); }
      .faixa::before { content: ""; position: absolute; width: 1000px; height: 1000px; left: 40px; top: -420px; border-radius: 50%; background: radial-gradient(circle, rgba(95,211,154,0.22) 0%, rgba(95,211,154,0) 62%); }
      .faixa::after { content: ""; position: absolute; inset: 0; opacity: 0.16; background-image: linear-gradient(rgba(238,242,236,0.25) 2px, transparent 2px), linear-gradient(90deg, rgba(238,242,236,0.25) 2px, transparent 2px); background-size: 90px 90px; }
      .faixa .costura { position: absolute; left: 0; bottom: 0; width: 1080px; height: 8px; background: var(--brand); transform-origin: 0 50%; z-index: 2; }
      .faixa .conteudo { position: absolute; inset: 0; z-index: 1; }

      /* contagem (contador e valor cheio) */
      .contagem { position: absolute; left: 40px; width: 1000px; display: flex; align-items: center; justify-content: center; gap: 0.14em; color: var(--brand); font-weight: 800; letter-spacing: -0.045em; line-height: 1; white-space: nowrap; font-variant-numeric: tabular-nums; transform-origin: 50% 58%; }
      .contagem .afixo { font-size: 0.55em; font-weight: 700; letter-spacing: -0.02em; color: color-mix(in srgb, var(--brand) 72%, var(--fg)); }
      .contador .rotulo { position: absolute; left: 64px; right: 64px; top: 70px; text-align: center; }
      .contador .contagem { top: 150px; height: 400px; }
      .contador.com-marcos .contagem { top: 120px; height: 300px; }
      .contador .linha { position: absolute; left: 120px; top: 470px; width: 840px; height: 14px; border-radius: 7px; background: rgba(238,242,236,0.15); }
      .contador .prog { width: 840px; height: 14px; border-radius: 7px; background: var(--brand); transform-origin: 0 50%; transform: scaleX(0); }
      .contador .marcos { position: absolute; left: 120px; top: 506px; width: 840px; display: flex; justify-content: space-between; font-family: "JetBrains Mono", monospace; font-size: 28px; font-weight: 700; color: var(--muted); text-transform: uppercase; }

      /* chat */
      .chat { position: absolute; left: 64px; top: 70px; width: 952px; height: 540px; border-radius: 36px; background: #1b2520; border: 3px solid rgba(238,242,236,0.12); }
      .chat .rotulo { position: absolute; left: 48px; top: 34px; color: var(--fg); }
      .chat .pergunta { position: absolute; right: 48px; top: 110px; width: 700px; padding: 32px 40px; border-radius: 40px 40px 10px 40px; background: var(--brand); color: var(--bg); font-weight: 700; font-size: 46px; line-height: 1.2; transform-origin: 100% 100%; }
      .chat .pergunta.longa { font-size: 38px; }
      .chat .digitando { position: absolute; left: 48px; top: 410px; width: 190px; height: 96px; border-radius: 48px 48px 48px 10px; background: rgba(238,242,236,0.12); display: flex; align-items: center; justify-content: center; gap: 18px; transform-origin: 0 100%; transform: scale(0); }
      .chat .digitando i { display: block; width: 22px; height: 22px; border-radius: 50%; background: var(--fg); }

      /* lista */
      .lista .titulo { position: absolute; left: 64px; top: 64px; width: 952px; font-size: 62px; font-weight: 900; line-height: 1.02; letter-spacing: -0.035em; }
      .lista .item { position: absolute; left: 64px; width: 952px; display: flex; align-items: center; gap: 36px; padding: 0 36px; border-radius: 28px; background: #1b2520; border: 3px solid rgba(95,211,154,0.5); opacity: 0; }
      .lista .n { flex: 0 0 auto; border-radius: 50%; background: var(--brand); color: var(--bg); font-weight: 900; display: flex; align-items: center; justify-content: center; }
      .lista .txt { font-weight: 900; letter-spacing: -0.03em; white-space: nowrap; }

      /* rota */
      .rota .mapa { position: absolute; left: 0; top: 0; width: 1080px; height: 680px; }
      .rota .mapa path { fill: none; stroke: var(--brand); stroke-width: 10; stroke-linecap: round; stroke-dasharray: 26 22; opacity: 0; }
      .rota .pino { position: absolute; width: 60px; height: 60px; opacity: 0; }
      .rota .pino i { display: block; width: 60px; height: 60px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); background: var(--brand); }
      .rota .p1 { left: 170px; top: 380px; } .rota .p2 { left: 840px; top: 230px; } .rota .p2 i { background: var(--fg); }
      .rota .cidade { position: absolute; font-weight: 900; font-size: 50px; white-space: nowrap; opacity: 0; }
      .rota .n1 { left: 64px; top: 470px; } .rota .n2 { right: 64px; top: 130px; text-align: right; }
      .rota .selo-rota { position: absolute; left: 64px; top: 570px; padding: 8px 24px; border-radius: 40px; border: 4px solid var(--perda); color: var(--perda); font-family: "JetBrains Mono", monospace; font-weight: 700; font-size: 32px; white-space: nowrap; opacity: 0; }

      /* ---------- cartões em tela cheia ---------- */
      .cartao { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; background: var(--bg2); }
      .cartao::before { content: ""; position: absolute; width: 1400px; height: 1400px; left: -160px; top: 260px; border-radius: 50%; background: radial-gradient(circle, rgba(95,211,154,0.2) 0%, rgba(95,211,154,0) 62%); }
      .valor-cheio .rotulo { position: absolute; left: 64px; right: 64px; top: 560px; text-align: center; font-size: 38px; }
      .valor-cheio .contagem { top: 640px; height: 420px; }
      .valor-cheio .selo { position: absolute; left: 0; right: 0; top: 1110px; display: flex; justify-content: center; }
      .valor-cheio .selo span { display: block; padding: 14px 34px; border-radius: 60px; background: var(--brand); color: var(--bg); font-weight: 900; font-size: 64px; transform: scale(0); }

      .comparacao .base { position: absolute; left: 150px; top: 1240px; width: 780px; height: 5px; background: rgba(238,242,236,0.35); }
      .comparacao .coluna { position: absolute; top: 1240px; width: 270px; }
      .comparacao .c0 { left: 200px; } .comparacao .c1 { left: 610px; }
      .comparacao .barra { position: absolute; left: 0; bottom: 0; width: 270px; border-radius: 18px 18px 0 0; transform-origin: 50% 100%; }
      .comparacao .c0 .barra { background: rgba(238,242,236,0.85); }
      .comparacao .c1 .barra { background: var(--brand); }
      .comparacao .valor { position: absolute; left: -60px; right: -60px; text-align: center; font-weight: 900; font-size: 50px; }
      .comparacao .coluna .rotulo { position: absolute; left: -60px; right: -60px; top: 28px; text-align: center; color: var(--fg); }
      .comparacao .carimbo { position: absolute; left: 0; right: 0; top: 330px; display: flex; justify-content: center; }
      .comparacao .carimbo span { display: block; padding: 18px 40px; border: 9px solid var(--perda); border-radius: 18px; color: var(--perda); font-weight: 900; font-size: 96px; letter-spacing: 0.02em; white-space: nowrap; opacity: 0; }

      /* ---------- capa (gancho, 0–2,2 s) ---------- */
      .capa { position: absolute; inset: 0; }
      .capa .escurece { position: absolute; inset: 0; background: rgba(8, 12, 10, 0.55); }
      .capa .titulo { position: absolute; left: 64px; right: 64px; top: 150px; font-weight: 900; line-height: 1.02; letter-spacing: -0.035em; text-transform: uppercase; }
      .capa .titulo b { color: var(--brand); font-weight: 900; }
      .capa .rotulo { position: absolute; left: 64px; top: 92px; color: var(--fg); }

      /* ---------- legenda: branca, sem destaque colorido (R1+R2) ---------- */
      .leg { position: absolute; left: 60px; right: 60px; top: 1500px; display: flex; justify-content: center; }
      .leg span { display: block; max-width: 960px; text-align: center; font-weight: 900; font-size: 76px; line-height: 1.08; letter-spacing: -0.02em; color: #fff; text-transform: uppercase; text-shadow: 0 6px 0 rgba(0,0,0,0.85), 0 0 26px rgba(0,0,0,0.7); }
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
        <div class="vinheta"></div>
      </div>
      <audio id="cam-audio" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="10" data-volume="1" data-audio-group="voz"></audio>
{{CENAS}}
{{LEGENDAS}}
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });

      // número pt-BR (1.500 · 37,5) e a contagem quadro a quadro, como o count-up do registry
      function fmt(v, casas) {
        const [i, f] = v.toFixed(casas).split(".");
        const milhar = i.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        return f ? milhar + "," + f : milhar;
      }
      function contar(sel, de, ate, casas, t0, dur) {
        const el = document.querySelector(sel);
        const n = Math.max(1, Math.round(dur * 30));
        const ease = gsap.parseEase("sine.inOut");
        for (let q = 0; q <= n; q++) tl.set(el, { textContent: fmt(de + (ate - de) * ease(q / n), casas) }, t0 + dur * q / n);
      }

      // estados: cada troca entre "cheio" e "div" é um corte seco
      for (const [t, e] of {{ESTADOS}}) {
        tl.set("#cam-div", { opacity: e === "div" ? 1 : 0 }, t);
        tl.set("#cam-cheio", { opacity: e === "div" ? 0 : 1 }, t);
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
