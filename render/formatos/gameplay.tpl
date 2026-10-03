<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      /* Formato 5 — falante em cima, vídeo de retenção (gameplay) embaixo; legenda na costura.
         Formato clássico de corte; R2: sem efeito (10% em todos os grupos). */
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1080px; height: 1920px; overflow: hidden; background: #0e1411; }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; background: #000; font-family: "Montserrat", sans-serif; }
      #cam { position: absolute; left: 0; top: 0; width: 1080px; height: 960px; overflow: hidden; }
      /* quadro da fonte a 1080 de altura, qualquer resolução (render/rosto.py: quadro_metade) */
      #q-meio { position: absolute; left: 0; top: 0; width: {{QM_W}}px; height: {{QM_H}}px; }
      #v-meio { width: {{QM_W}}px; height: {{QM_H}}px; display: block; }
      #jogo { position: absolute; left: 0; top: 960px; width: 1080px; height: 960px; overflow: hidden; }
      #v-jogo { position: absolute; left: -314px; top: 0; width: 1708px; height: 960px; display: block; }
      .leg { position: absolute; left: 60px; right: 60px; top: 880px; display: flex; justify-content: center; }
      .leg span { display: block; max-width: 960px; text-align: center; font-weight: 900; font-size: 72px; line-height: 1.08; letter-spacing: -0.02em; color: #fff; text-transform: uppercase; -webkit-text-stroke: 8px #000; paint-order: stroke fill; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-width="1080" data-height="1920" data-duration="{{DUR}}" data-fps="30">
      <div id="cam">
        <div id="q-meio" data-layout-allow-overflow><video id="v-meio" class="clip" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="0" muted playsinline></video></div>
      </div>
      <div id="jogo" data-layout-allow-overflow>
        <video id="v-jogo" class="clip" src="assets/gameplay.mp4" data-start="0" data-duration="{{DUR}}" data-media-start="0" data-track-index="1" muted playsinline></video>
      </div>
      <audio id="cam-audio" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="10" data-volume="1" data-audio-group="voz"></audio>
{{LEGENDAS}}
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });
      const TR = {{TRILHA_METADE}};
      tl.set("#q-meio", { x: TR[0][1], y: TR[0][2] }, 0);
      for (let k = 1; k < TR.length; k++) {
        if (TR[k][3]) { tl.set("#q-meio", { x: TR[k][1], y: TR[k][2] }, TR[k][0]); continue; }
        tl.to("#q-meio", { x: TR[k][1], y: TR[k][2], duration: TR[k][0] - TR[k - 1][0], ease: "sine.inOut" }, TR[k - 1][0]);
      }
      document.querySelectorAll(".leg span").forEach((el) => {
        tl.fromTo(el, { scale: 0.9, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.12, ease: "power2.out" }, parseFloat(el.parentElement.dataset.start));
      });
      // emendas das pausas em corte seco, sem zoom (Davi, 2026-10-02)
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
