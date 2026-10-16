# Efeitos sonoros do f10 (Motion v2)

Sintetizados no ffmpeg (sem licença de terceiros). Durações em `src/cortes/render/motion2.py` (`SFX`):
mudar um arquivo pede conferir a duração lá.

    ffmpeg -f lavfi -i "anoisesrc=d=0.55:c=pink:a=0.9" -af "highpass=f=300,lowpass=f=5000,afade=t=in:d=0.3:curve=exp,afade=t=out:st=0.3:d=0.25,volume=0.8" -ar 48000 whoosh.wav
    ffmpeg -f lavfi -i "sine=f=880:d=0.12" -af "afade=t=out:st=0.02:d=0.1,volume=0.7" -ar 48000 pop.wav
