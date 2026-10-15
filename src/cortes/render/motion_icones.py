"""f3 Motion, os ícones de traço dos painéis (spec 2026-10-15-f3-denso §5). Puro.

Desenhados aqui, em grade de 24×24 com traço de 2 px e pontas redondas, sem preenchimento: a cor
vem do `currentColor` (o acento ou o texto do tema). O LLM escolhe pelo nome, numa lista fechada
(o schema leva o enum), e o nome nunca vai para o HTML sem passar por aqui.
"""
from cortes.render.processo import ErroRender

ICONES: dict[str, str] = {
    "casa": '<path d="M3 11 12 3l9 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
    "predio": '<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2'
              'M9 15h2M13 15h2"/><path d="M11 21v-3h2v3"/>',
    "dinheiro": '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="3"/>'
                '<path d="M6 9v.01M18 15v.01"/>',
    "moeda": '<circle cx="12" cy="12" r="9"/><path d="M15 9.5c-.6-1-1.7-1.5-3-1.5-1.7 0-3 .9-3 2s1.3 1.7 3 '
             '2 3 .9 3 2-1.3 2-3 2c-1.3 0-2.4-.5-3-1.5M12 6v12"/>',
    "cartao": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h4"/>',
    "banco": '<path d="M3 9 12 4l9 5"/><path d="M4 9h16M6 9v8M10 9v8M14 9v8M18 9v8M3 20h18"/>',
    "cofre": '<rect x="3" y="4" width="18" height="15" rx="2"/><circle cx="12" cy="11.5" r="3.5"/>'
             '<path d="M12 8v1M15.5 11.5h-1M6 19v2M18 19v2"/>',
    "grafico": '<path d="M4 20V4M4 20h16"/><rect x="7" y="12" width="3" height="5"/>'
               '<rect x="12" y="8" width="3" height="9"/><rect x="17" y="5" width="3" height="12"/>',
    "tendencia": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "queda": '<path d="M3 7l6 6 4-4 8 8"/><path d="M15 17h6v-6"/>',
    "relogio": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "calendario": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "pessoa": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/>',
    "pessoas": '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.9 3.1-6 7-6s7 2.1 7 6"/>'
               '<path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14c2.4.6 4 2.6 4 6"/>',
    "celular": '<rect x="6" y="2" width="12" height="20" rx="2"/><path d="M11 18h2"/>',
    "computador": '<rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M8 20h8M12 16v4"/>',
    "chat": '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/>',
    "microfone": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3'
                 'M9 21h6"/>',
    "documento": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
    "cadeado": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4'
               'M12 15v2"/>',
    "escudo": '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "alerta": '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17v.01"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/>',
    "x": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "estrela": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    "coracao": '<path d="M12 20s-8-4.6-8-10.2C4 7 6 5 8.4 5c1.5 0 2.8.8 3.6 2 .8-1.2 2.1-2 3.6-2C18 5 20 '
               '7 20 9.8 20 15.4 12 20 12 20z"/>',
    "saude": '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M12 8v8M8 12h8"/>',
    "raio": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "lampada": '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4'
               '-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    "alvo": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "globo": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.4 3.8 5.4 3.8 9s-1.3 6.6-3.8 9'
             'c-2.5-2.4-3.8-5.4-3.8-9S9.5 5.4 12 3z"/>',
    "mapa": '<path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z"/>'
            '<circle cx="12" cy="9.5" r="2.5"/>',
    "carro": '<path d="M5 16V11l2-5h10l2 5v5"/><path d="M3 16h18v3H3zM7 19v2M17 19v2M5 11h14"/>'
             '<circle cx="7.5" cy="13.5" r=".5"/><circle cx="16.5" cy="13.5" r=".5"/>',
    "aviao": '<path d="M2 13l8-2 4-7 2 1-2 6 6-1 1 2-6 2 2 6-2 1-4-6-8 1z"/>',
    "carrinho": '<path d="M3 4h2l2.5 11h11L21 8H6.5"/><circle cx="9" cy="19" r="1.5"/>'
                '<circle cx="17" cy="19" r="1.5"/>',
    "presente": '<rect x="3" y="9" width="18" height="12" rx="1"/><path d="M3 13h18M12 9v12'
                'M12 9c-1.5-3-5-4-5-1.5S12 9 12 9zM12 9c1.5-3 5-4 5-1.5S12 9 12 9z"/>',
}
NOMES_ICONES: tuple[str, ...] = tuple(ICONES)


def icone_svg(nome: str, classe: str) -> str:
    if nome not in ICONES:
        raise ErroRender(f"ícone '{nome}' não existe; use um de {NOMES_ICONES}")
    return (f'<svg class="{classe}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONES[nome]}</svg>')
