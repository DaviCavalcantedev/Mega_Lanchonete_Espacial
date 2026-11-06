"""Lê o arquivo .env (se existir) e coloca os valores nas variáveis de ambiente.

Formato: uma configuração por linha, CHAVE=valor. Linhas começando com # são comentários.
Variáveis já definidas no sistema têm prioridade sobre o arquivo.
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def carregar(caminho=RAIZ / ".env"):
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        os.environ.setdefault(chave.strip(), valor)


carregar()
