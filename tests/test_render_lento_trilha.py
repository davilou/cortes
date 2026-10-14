"""O render real do HyperFrames respeita `data-volume` da trilha (spec trilha §5): só a cama, com
volume 0,1 (−20 dB), comparada à mesma janela da fonte."""
import shutil
from pathlib import Path

import pytest

from cortes.render.hyperframes import criar_projeto, renderizar
from cortes.render.processo import rodar_processo
from cortes.render.trilha import ARQUIVO_ASSET, Clipe, html_trilha
from cortes.render.trilha_biblioteca import BIBLIOTECA, ler_plano, medir_lufs

REPO = Path(__file__).resolve().parents[1]
DUR = 10.0
HTML = """<!doctype html>
<html><head><meta charset="UTF-8" /></head><body>
<div id="root" data-composition-id="main" data-width="1080" data-height="1920"
     data-duration="{dur}" data-fps="30">
{trilha}
</div>
<script>window.__timelines = window.__timelines || {{}}; window.__timelines["main"] = null;</script>
</body></html>"""


@pytest.mark.lento
def test_render_poe_a_trilha_20_db_abaixo_com_volume_0_1(tmp_path: Path) -> None:
    npx = shutil.which("npx")
    assert npx, "npx no PATH"
    cama = ler_plano(REPO / BIBLIOTECA)[0]
    proj = tmp_path / "proj"
    (proj / "assets").mkdir(parents=True)
    shutil.copyfile(cama.arquivo, proj / "assets" / ARQUIVO_ASSET)
    criar_projeto(proj, HTML.format(dur=DUR, trilha=html_trilha([Clipe(0.0, DUR, 0.0, 0.0, 0.0)], 0.1)))
    saida = tmp_path / "s.mp4"
    renderizar(proj, saida, npx, rodar_processo)
    ref = tmp_path / "ref.wav"
    codigo, log = rodar_processo(["ffmpeg", "-y", "-v", "error", "-t", str(DUR), "-i", str(cama.arquivo),
                                  str(ref)], None)
    assert codigo == 0, log
    diferenca = medir_lufs(ref, rodar_processo).lufs - medir_lufs(saida, rodar_processo).lufs
    assert diferenca == pytest.approx(20.0, abs=1.0)
