<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      /* Formato 8 — quadro 16:9 inteiro no meio, fundo com o próprio vídeo desfocado (pré-processado
         no ffmpeg). Anti-controle: zero virais nas rodadas R1 e R2. */
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1080px; height: 1920px; overflow: hidden; background: #0e1411; }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; background: #000; font-family: "Montserrat", sans-serif; }
      #fundo { position: absolute; inset: 0; }
      #v-fundo { width: 1080px; height: 1920px; display: block; }
      #escurece { position: absolute; inset: 0; background: rgba(6, 10, 8, 0.45); }
      #quadro { position: absolute; left: 0; top: 656px; width: 1080px; height: 608px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      #v-quadro { width: 1080px; height: 608px; display: block; }
      #titulo { position: absolute; left: 70px; right: 70px; top: 300px; text-align: center; font-weight: 900; font-size: 84px; line-height: 1.05; letter-spacing: -0.03em; color: #fff; text-transform: uppercase; text-shadow: 0 6px 0 rgba(0,0,0,0.6); }
      .leg { position: absolute; left: 60px; right: 60px; top: 1360px; display: flex; justify-content: center; }
      .leg span { display: block; max-width: 960px; text-align: center; font-weight: 900; font-size: 70px; line-height: 1.08; letter-spacing: -0.02em; color: #fff; text-transform: uppercase; text-shadow: 0 6px 0 rgba(0,0,0,0.85), 0 0 26px rgba(0,0,0,0.7); }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-width="1080" data-height="1920" data-duration="{{DUR}}" data-fps="30">
      <!-- fundo: o próprio trecho, desfocado e escurecido no ffmpeg (assets/fundo.mp4, 540x960).
           O blur em tempo real do HyperFrames sobre o vídeo cheio estourava o tempo de carga. -->
      <div id="fundo"><video id="v-fundo" class="clip" src="assets/fundo.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="0" muted playsinline></video></div>
      <div id="escurece"></div>
      <div id="quadro"><video id="v-quadro" class="clip" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="1" muted playsinline></video></div>
      <div id="titulo">{{TITULO}}</div>
      <audio id="cam-audio" src="assets/trecho.mp4" data-start="0" data-duration="{{DUR}}" data-track-index="10" data-volume="1" data-audio-group="voz"></audio>
{{LEGENDAS}}
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });
      tl.fromTo("#titulo", { y: -30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4, ease: "power3.out" }, 0.1);
      document.querySelectorAll(".leg span").forEach((el) => {
        tl.fromTo(el, { scale: 0.9, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.12, ease: "power2.out" }, parseFloat(el.parentElement.dataset.start));
      });
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
