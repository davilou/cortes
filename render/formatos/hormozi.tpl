<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      /* Formato 6 — estilo Hormozi: palavra falada em destaque colorido.
         Padrão do mercado; a pesquisa (R1+R2) associou destaque colorido a PIOR desempenho — teste de contraprova.
         O zoom punch a cada frase do protótipo saiu: nenhum template tem zoom nem flash (Davi, 2026-10-02). */
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1080px; height: 1920px; overflow: hidden; background: #0e1411; }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; background: #000; font-family: "Montserrat", sans-serif; }
      #cam { position: absolute; inset: 0; overflow: hidden; }
      #q-cheio { position: absolute; left: 0; top: 0; width: {{QW}}px; height: 1920px; }
      #v-cheio { width: {{QW}}px; height: 1920px; display: block; }
      .leg { position: absolute; left: 50px; right: 50px; top: 1330px; display: flex; justify-content: center; }
      .leg span { display: block; max-width: 980px; text-align: center; font-weight: 900; font-size: 92px; line-height: 1.1; letter-spacing: -0.01em; color: #fff; text-transform: uppercase; -webkit-text-stroke: 10px #000; paint-order: stroke fill; }
      .leg i { display: inline-block; font-style: normal; margin: 0 0.14em; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-width="1080" data-height="1920" data-duration="{{DUR}}" data-fps="30">
      <div id="cam">
        <div id="q-cheio" data-layout-allow-overflow><video id="v-cheio" class="clip" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="0" muted playsinline></video></div>
      </div>
      <audio id="cam-audio" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="10" data-volume="1" data-audio-group="voz"></audio>
{{LEGENDAS}}
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });
      const DESTAQUE = "#ffd23f";
      const TR = {{TRILHA_CHEIO}};
      tl.set("#q-cheio", { x: TR[0][1], y: TR[0][2] }, 0);
      for (let k = 1; k < TR.length; k++) {
        if (TR[k][3]) { tl.set("#q-cheio", { x: TR[k][1], y: TR[k][2] }, TR[k][0]); continue; }
        tl.to("#q-cheio", { x: TR[k][1], y: TR[k][2], duration: TR[k][0] - TR[k - 1][0], ease: "sine.inOut" }, TR[k - 1][0]);
      }
      // palavra falada em amarelo, com leve pulo; volta ao branco quando a próxima começa
      document.querySelectorAll(".leg").forEach((g) => {
        const fimGrupo = parseFloat(g.dataset.start) + parseFloat(g.dataset.duration);
        const ws = [...g.querySelectorAll("i")];
        ws.forEach((w, k) => {
          const t = parseFloat(w.dataset.t);
          const fim = k + 1 < ws.length ? parseFloat(ws[k + 1].dataset.t) : fimGrupo;
          tl.set(w, { color: DESTAQUE, scale: 1.12 }, t);
          if (fim > t) tl.set(w, { color: "#ffffff", scale: 1 }, fim);
        });
        tl.fromTo(g.querySelector("span"), { scale: 0.8, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.1, ease: "back.out(2)" }, parseFloat(g.dataset.start));
      });
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
