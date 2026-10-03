<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      /* Formato 4 — B-roll real, automático (plano 2026-10-03-broll-automatico): a base do f7 (tela
         cheia no rosto, corte seco na troca de câmera, legenda embaixo) e, quando a pessoa cita uma
         coisa ou um acontecimento, um clipe de 1,5–4 s em tela cheia. O clipe aparece e some seco
         (o runtime liga e desliga o .clip na janela dele): sem Ken Burns, sem flash, sem zoom, sem
         fade (Davi, 2026-10-03). A legenda fica por cima do clipe. */
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1080px; height: 1920px; overflow: hidden; background: #0e1411; }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; background: #000; font-family: "Montserrat", sans-serif; }
      #cam { position: absolute; inset: 0; overflow: hidden; }
      #q-cheio { position: absolute; left: 0; top: 0; width: {{QW}}px; height: 1920px; }
      #v-cheio { width: {{QW}}px; height: 1920px; display: block; }
      .vinheta { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 35%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%); }
      /* trecho e foto já vêm em 1080×1920 do ffmpeg (cover no vídeo; foto inteira sobre ela desfocada) */
      .broll { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; display: block; object-fit: cover; background: #000; }
      .broll img { display: block; width: 1080px; height: 1920px; object-fit: cover; }
      .leg { position: absolute; left: 60px; right: 60px; top: 1500px; display: flex; justify-content: center; }
      .leg span { display: block; max-width: 960px; text-align: center; font-weight: 900; font-size: 76px; line-height: 1.08; letter-spacing: -0.02em; color: #fff; text-transform: uppercase; text-shadow: 0 6px 0 rgba(0,0,0,0.85), 0 0 26px rgba(0,0,0,0.7); }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-width="1080" data-height="1920" data-duration="{{DUR}}" data-fps="30">
      <div id="cam">
        <div id="q-cheio" data-layout-allow-overflow><video id="v-cheio" class="clip" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="0" muted playsinline></video></div>
        <div class="vinheta"></div>
      </div>
      <audio id="cam-audio" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="10" data-volume="1" data-audio-group="voz"></audio>
{{BROLL}}
{{LEGENDAS}}
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });
      const TR = {{TRILHA_CHEIO}};
      tl.set("#q-cheio", { x: TR[0][1], y: TR[0][2] }, 0);
      for (let k = 1; k < TR.length; k++) {
        if (TR[k][3]) {
          // troca de câmera: corte seco, sem efeito (flash e zoom nas emendas saíram — Davi, 2026-10-02)
          tl.set("#q-cheio", { x: TR[k][1], y: TR[k][2] }, TR[k][0]);
          continue;
        }
        tl.to("#q-cheio", { x: TR[k][1], y: TR[k][2], duration: TR[k][0] - TR[k - 1][0], ease: "sine.inOut" }, TR[k - 1][0]);
      }
      document.querySelectorAll(".leg span").forEach((el) => {
        tl.fromTo(el, { scale: 0.9, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.12, ease: "power2.out" }, parseFloat(el.parentElement.dataset.start));
      });
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
