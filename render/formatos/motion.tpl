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

      /* contagem (contador e valor) */
      .contagem { position: absolute; left: 40px; width: 920px; display: flex; align-items: center; justify-content: center; gap: 0.14em; color: var(--brand); font-weight: 800; letter-spacing: -0.045em; line-height: 1; white-space: nowrap; font-variant-numeric: tabular-nums; transform-origin: 50% 58%; }
      .contagem .afixo { font-size: 0.5em; font-weight: 700; letter-spacing: -0.02em; color: color-mix(in srgb, var(--brand) 70%, var(--fg)); }
      .contador .contagem { top: 150px; height: 400px; }
      .contador.com-marcos .contagem { top: 120px; height: 320px; }
      .contador .linha { position: absolute; left: 100px; top: 520px; width: 800px; height: 14px; border-radius: 7px; background: var(--linha); }
      .contador .prog { width: 800px; height: 14px; border-radius: 7px; background: var(--brand); transform-origin: 0 50%; transform: scaleX(0); }
      .contador .marcos { position: absolute; left: 100px; top: 556px; width: 800px; display: flex; justify-content: space-between; font-family: "JetBrains Mono", monospace; font-size: 26px; font-weight: 700; color: var(--muted); text-transform: uppercase; }
      .valor .contagem { top: 120px; height: 420px; }
      .valor .selo { position: absolute; left: 0; right: 0; top: 560px; display: flex; justify-content: center; }
      .valor .selo span { display: block; padding: 12px 32px; border-radius: 60px; background: var(--brand); color: var(--bg); font-weight: 900; font-size: 56px; transform: scale(0); }

      /* comparação */
      .comparacao .base { position: absolute; left: 150px; top: 620px; width: 700px; height: 4px; background: var(--linha); }
      .comparacao .coluna { position: absolute; top: 620px; width: 240px; }
      .comparacao .c0 { left: 230px; } .comparacao .c1 { left: 530px; }
      .comparacao .barra { position: absolute; left: 0; bottom: 0; width: 240px; border-radius: 18px 18px 0 0; transform-origin: 50% 100%; }
      .comparacao .c0 .barra { background: color-mix(in srgb, var(--fg) 75%, transparent); }
      .comparacao .c1 .barra { background: var(--brand); }
      .comparacao .cval { position: absolute; left: -60px; right: -60px; text-align: center; font-weight: 900; font-size: 46px; }
      .comparacao .crot { position: absolute; left: -60px; right: -60px; top: 22px; text-align: center; font-family: "JetBrains Mono", monospace; font-size: 26px; font-weight: 700; color: var(--muted); text-transform: uppercase; }
      .comparacao .carimbo { position: absolute; left: 0; right: 0; top: 70px; display: flex; justify-content: center; z-index: 2; }
      .comparacao .carimbo span { display: block; padding: 14px 34px; border: 8px solid var(--perda); border-radius: 16px; color: var(--perda); font-weight: 900; font-size: 76px; letter-spacing: 0.02em; white-space: nowrap; opacity: 0; background: color-mix(in srgb, var(--cartao) 85%, transparent); }

      /* chat */
      .chat .pergunta { position: absolute; right: 44px; top: 130px; width: 660px; padding: 30px 38px; border-radius: 40px 40px 10px 40px; background: var(--brand); color: var(--bg); font-weight: 700; font-size: 44px; line-height: 1.2; transform-origin: 100% 100%; }
      .chat .pergunta.longa { font-size: 36px; }
      .chat .digitando { position: absolute; left: 44px; top: 500px; width: 180px; height: 92px; border-radius: 46px 46px 46px 10px; background: var(--linha); display: flex; align-items: center; justify-content: center; gap: 18px; transform-origin: 0 100%; transform: scale(0); }
      .chat .digitando i { display: block; width: 20px; height: 20px; border-radius: 50%; background: var(--fg); }

      /* lista */
      .lista .titulo { position: absolute; left: 44px; top: 70px; width: 912px; font-size: 54px; font-weight: 900; line-height: 1.02; letter-spacing: -0.03em; font-family: var(--fonte-titulo); }
      .lista .item { position: absolute; left: 44px; width: 912px; display: flex; align-items: center; gap: 32px; padding: 0 32px; border-radius: 26px; background: var(--bg); border: 2px solid var(--linha); opacity: 0; }
      .lista .n { flex: 0 0 auto; border-radius: 50%; background: var(--brand); color: var(--bg); font-weight: 900; display: flex; align-items: center; justify-content: center; }
      .lista .txt { font-weight: 900; letter-spacing: -0.03em; white-space: nowrap; }

      /* rota */
      .rota .mapa { position: absolute; left: 0; top: 0; width: 1000px; height: 724px; }
      .rota .mapa path { fill: none; stroke: var(--brand); stroke-width: 10; stroke-linecap: round; stroke-dasharray: 1; stroke-dashoffset: 1; }
      .rota .pino { position: absolute; width: 56px; height: 56px; opacity: 0; }
      .rota .pino i { display: block; width: 56px; height: 56px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); background: var(--brand); }
      .rota .p1 { left: 162px; top: 410px; } .rota .p2 { left: 782px; top: 220px; } .rota .p2 i { background: var(--fg); }
      .rota .cidade { position: absolute; font-weight: 900; font-size: 48px; white-space: nowrap; opacity: 0; font-family: var(--fonte-titulo); }
      .rota .n1 { left: 60px; top: 500px; } .rota .n2 { right: 60px; top: 120px; text-align: right; }
      .rota .selo-rota { position: absolute; left: 60px; top: 600px; padding: 8px 22px; border-radius: 40px; border: 4px solid var(--perda); color: var(--perda); font-family: "JetBrains Mono", monospace; font-weight: 700; font-size: 30px; white-space: nowrap; opacity: 0; }

      /* gráfico */
      .graf { position: absolute; left: 0; top: 110px; width: 1000px; height: 460px; overflow: visible; }
      .graf .gbase { stroke: var(--linha); stroke-width: 3; }
      .graf .garea { fill: color-mix(in srgb, var(--brand) 14%, transparent); stroke: none; opacity: 0; }
      .graf .glinha { fill: none; stroke: var(--brand); stroke-width: 8; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 1; stroke-dashoffset: 1; }
      .graf .gp { fill: var(--fg); }
      .graf .gdest { fill: none; stroke: var(--brand); stroke-width: 6; }
      .graf .gx { fill: var(--muted); font-family: "JetBrains Mono", monospace; font-size: 26px; font-weight: 700; text-anchor: middle; }
      .gvalor { position: absolute; transform: translate(-50%, -100%); padding: 8px 22px; border-radius: 16px; background: var(--brand); color: var(--bg); font-weight: 900; font-size: 42px; white-space: nowrap; }

      /* fluxo */
      .fluxo { position: absolute; left: 20px; right: 20px; top: 130px; height: 480px; display: flex; align-items: flex-start; justify-content: center; }
      .fluxo .passo { display: flex; flex-direction: column; align-items: center; width: 230px; opacity: 0; }
      .fluxo .bola { width: 200px; height: 200px; border-radius: 50%; border: 4px solid var(--linha); background: var(--bg); color: var(--fg); display: flex; align-items: center; justify-content: center; }
      .fluxo .bola .ic { width: 100px; height: 100px; }
      .fluxo .ativo .bola { background: var(--brand); border-color: var(--brand); color: var(--bg); }
      .fluxo .ptxt { margin-top: 26px; font-size: 42px; font-weight: 800; text-align: center; line-height: 1.1; }
      .fluxo .ativo .ptxt { color: var(--brand); }
      .fluxo .seta { width: 40px; height: 6px; margin-top: 97px; border-radius: 3px; background: var(--linha); transform-origin: 0 50%; }
      .fluxo.n4 .passo { width: 200px; } .fluxo.n4 .bola { width: 160px; height: 160px; } .fluxo.n4 .ptxt { font-size: 36px; } .fluxo.n4 .seta { margin-top: 77px; width: 26px; }

      /* timer */
      .anel { position: absolute; left: 300px; top: 140px; width: 400px; height: 400px; }
      .anel circle { fill: none; stroke-width: 18; }
      .anel .anel-fundo { stroke: var(--linha); }
      .anel .anel-prog { stroke: var(--brand); stroke-linecap: round; stroke-dasharray: 1; stroke-dashoffset: 1; transform: rotate(-90deg); transform-origin: 200px 200px; }
      .relogio { position: absolute; left: 0; right: 0; top: 280px; text-align: center; font-size: 112px; font-weight: 800; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; line-height: 1; }
      .unidade { position: absolute; left: 0; right: 0; top: 590px; text-align: center; font-family: "JetBrains Mono", monospace; font-size: 30px; font-weight: 700; color: var(--muted); text-transform: uppercase; }

      /* check */
      .selo-check { position: absolute; left: 300px; top: 60px; width: 400px; height: 400px; }
      .selo-check circle, .selo-check path { fill: none; stroke: var(--brand); stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 1; stroke-dashoffset: 1; }
      .selo-check circle { stroke-width: 18; } .selo-check path { stroke-width: 28; }
      .check.nao .selo-check circle, .check.nao .selo-check path { stroke: var(--perda); }
      .check .ctxt { position: absolute; left: 50px; right: 50px; top: 500px; text-align: center; font-size: 52px; font-weight: 900; line-height: 1.08; font-family: var(--fonte-titulo); }

      /* grade */
      .grade { position: absolute; left: 44px; right: 44px; top: 90px; bottom: 44px; display: grid; gap: 22px; grid-auto-rows: 250px; align-content: center; }
      .grade.c2 { grid-template-columns: 1fr 1fr; } .grade.c3 { grid-template-columns: 1fr 1fr 1fr; }
      .grade .bloco { border-radius: 26px; background: var(--bg); border: 2px solid var(--linha); display: flex; flex-direction: column; align-items: center; justify-content: center; opacity: 0; }
      .grade .bloco .ic { width: 88px; height: 88px; color: var(--brand); }
      .grade .btxt { margin-top: 18px; font-size: 36px; font-weight: 800; text-align: center; padding: 0 12px; line-height: 1.1; }

      /* destaque (frase-chave digitando) */
      .destaque { position: absolute; left: 60px; right: 60px; top: 60px; bottom: 60px; display: flex; flex-wrap: wrap; align-content: center; justify-content: center; text-align: center; font-weight: 900; line-height: 1.08; letter-spacing: -0.03em; font-family: var(--fonte-titulo); }
      .destaque .w { display: inline-block; margin: 0 0.12em; opacity: 0; }
      .destaque .w.on { color: var(--brand); }

      /* planta */
      .planta { position: absolute; left: 50px; top: 140px; width: 900px; height: 520px; }
      .planta svg { width: 900px; height: 520px; overflow: visible; }
      .planta .pl-comodo { opacity: 0; }
      .planta .pl-piso { fill: color-mix(in srgb, var(--brand) 12%, var(--cartao)); stroke: var(--linha); stroke-width: 2; }
      .planta .pl-parede line, .planta .pl-parede polygon { fill: none; stroke: var(--brand); stroke-width: 3; }
      .planta .pl-nome { fill: var(--fg); font-size: 26px; font-weight: 800; text-anchor: middle; }
      .planta .pl-area { fill: var(--muted); font-family: "JetBrains Mono", monospace; font-size: 22px; font-weight: 700; text-anchor: middle; }

      /* ilustração */
      .ilus { position: absolute; left: 40px; top: 40px; width: 920px; height: 540px; display: flex; align-items: center; justify-content: center; }
      .ilus svg { max-width: 100%; max-height: 100%; width: 920px; height: 540px; }
      .ilus-icone .ic { width: 280px; height: 280px; color: var(--brand); }
      .ilus-rot { position: absolute; left: 40px; right: 40px; bottom: 50px; text-align: center; font-size: 46px; font-weight: 900; font-family: var(--fonte-titulo); opacity: 0; }

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

      // número pt-BR (1.500 · 37,5) e a contagem quadro a quadro, como o count-up do registry
      function fmt(v, casas) {
        const [i, f] = v.toFixed(casas).split(".");
        const milhar = i.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        return f ? milhar + "," + f : milhar;
      }
      // O texto vai com um espaço de largura zero na frente: sem ele o GSAP lê "1.500" como o número
      // 1,5 e escreve "1.5" (o teste cego do plano E pegou isso no "mil e quinhentos").
      const SEM_NUMERO = "​";
      function contar(sel, de, ate, casas, t0, dur) {
        const el = document.querySelector(sel);
        const n = Math.max(1, Math.round(dur * 30));
        const ease = gsap.parseEase("sine.inOut");
        for (let q = 0; q <= n; q++) {
          tl.set(el, { textContent: SEM_NUMERO + fmt(de + (ate - de) * ease(q / n), casas) }, t0 + dur * q / n);
        }
      }
      // relógio do timer, quadro a quadro, mostrando o valor dito sem converter (motion_params_novos):
      // modo 0 (segundos) → "00:SS"; 1 (minutos) e 2 (horas) → "VV:00"
      function doisDigitos(n) { return String(Math.floor(n)).padStart(2, "0"); }
      function relogio(sel, valor, modo, t0, dur) {
        const el = document.querySelector(sel);
        const n = Math.max(1, Math.round(dur * 30));
        const ease = gsap.parseEase("sine.inOut");
        for (let q = 0; q <= n; q++) {
          const v = Math.round(valor * ease(q / n));
          const txt = modo === 0 ? "00:" + doisDigitos(v) : doisDigitos(v) + ":00";
          tl.set(el, { textContent: SEM_NUMERO + txt }, t0 + dur * q / n);
        }
      }

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
