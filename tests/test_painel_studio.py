import zipfile
from datetime import date
from pathlib import Path

import pytest

from cortes.painel.dados import ErroPainel
from cortes.painel.studio import ler_tabela, texto_do_zip

CABECALHO = ("Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações,Impressões,"
             "Taxa de cliques de impressões (%),Duração média da visualização,"
             "Porcentagem visualizada média (%),Tempo de exibição (horas),Inscritos\n")
LINHA_A = 'J-QjHWdb7gQ,Pagava R$ 30 por mês #noticias,"Aug 11, 2026",40,1174,22,0,0:00:25,64.59,4.3204,2\n'
LINHA_B = ('xV9KDhdKFfw,"O que o banco não pode, te cobrar","Aug 12, 2026",44,309,19,5.26,0:01:02,'
           '60.68,0.9,-1\n')
CSV_REAL = (CABECALHO
            + "Total,,,,2640,5119,2.97,0:00:46,40.39,15.5082,9\n"
            + LINHA_A
            + LINHA_B)


def test_le_videos_e_pula_total() -> None:
    vs = ler_tabela(CSV_REAL)
    assert [v.video_id for v in vs] == ["J-QjHWdb7gQ", "xV9KDhdKFfw"]
    a, b = vs
    assert a.publicado_em == date(2026, 8, 11) and a.duracao_s == 40 and a.views == 1174
    assert a.pct_media == 64.59 and a.duracao_media_s == 25 and a.inscritos == 2
    assert b.titulo == "O que o banco não pode, te cobrar" and b.duracao_media_s == 62 and b.inscritos == -1


def test_coluna_faltando_diz_qual() -> None:
    sem_inscritos = "\n".join(linha.rsplit(",", 1)[0] for linha in CSV_REAL.splitlines())
    with pytest.raises(ErroPainel, match="Inscritos"):
        ler_tabela(sem_inscritos)


def test_data_em_formato_desconhecido() -> None:
    with pytest.raises(ErroPainel, match="11/08/2026"):
        ler_tabela(CSV_REAL.replace('"Aug 11, 2026"', "11/08/2026"))


def test_celula_vazia_com_zero_views_vira_zero() -> None:
    texto = CABECALHO + 'novovideo00,Novo,"Oct 1, 2026",30,0,0,,,,0,\n'
    v = ler_tabela(texto)[0]
    assert v.views == 0 and v.pct_media == 0 and v.inscritos == 0


def test_celula_vazia_com_views_e_erro() -> None:
    texto = CABECALHO + 'novovideo00,Novo,"Oct 1, 2026",30,50,0,,0:00:10,,0,1\n'
    with pytest.raises(ErroPainel, match="pct_media"):
        ler_tabela(texto)


def test_celula_nao_numerica_diz_video_e_campo() -> None:
    texto = CABECALHO + 'novovideo00,Novo,"Oct 1, 2026",30,abc,0,,0:00:10,50,0,1\n'
    with pytest.raises(ErroPainel, match="novovideo00.*views"):
        ler_tabela(texto)


def test_linha_curta_falha_com_contexto() -> None:
    texto = CABECALHO + "curto1,Titulo\n"
    with pytest.raises(ErroPainel, match=r"linha 2: 2 colunas, o cabeçalho tem 11"):
        ler_tabela(texto)


def test_valor_fracionario_falha_com_contexto() -> None:
    texto = CABECALHO + 'novovideo00,Novo,"Oct 1, 2026",30,12.9,0,,0:00:10,50,0,1\n'
    with pytest.raises(ErroPainel, match="novovideo00.*views"):
        ler_tabela(texto)


def test_id_vazio_falha() -> None:
    texto = CABECALHO + ',Novo,"Oct 1, 2026",30,10,0,,0:00:10,50,0,1\n'
    with pytest.raises(ErroPainel, match="linha 2.*vazio"):
        ler_tabela(texto)


def test_id_fora_do_padrao_falha() -> None:
    texto = CABECALHO + 'curto,Novo,"Oct 1, 2026",30,10,0,,0:00:10,50,0,1\n'
    with pytest.raises(ErroPainel, match="linha 2.*'curto'"):
        ler_tabela(texto)


def test_cabecalho_em_ingles() -> None:
    cabecalho_en = ("Content,Video title,Video publish time,Duration,Views,"
                    "Average view duration,Average percentage viewed (%),Subscribers\n")
    texto = cabecalho_en + 'abc1234567X,Hello World,"Sep 5, 2026",20,100,0:00:15,75.5,3\n'
    v = ler_tabela(texto)[0]
    assert v.video_id == "abc1234567X" and v.publicado_em == date(2026, 9, 5)
    assert v.views == 100 and v.duracao_media_s == 15 and v.pct_media == 75.5 and v.inscritos == 3


def test_texto_do_zip(tmp_path: Path) -> None:
    arq = tmp_path / "export.zip"
    with zipfile.ZipFile(arq, "w") as z:
        z.writestr("Dados da tabela.csv", CSV_REAL.encode("utf-8-sig"))
        z.writestr("Total.csv", "x")
    assert texto_do_zip(arq) == CSV_REAL


def test_zip_sem_tabela(tmp_path: Path) -> None:
    arq = tmp_path / "export.zip"
    with zipfile.ZipFile(arq, "w") as z:
        z.writestr("Total.csv", "x")
    with pytest.raises(ErroPainel, match="sem a tabela"):
        texto_do_zip(arq)
