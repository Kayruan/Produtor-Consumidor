"""Caminhos do projeto, resolvidos a partir da localizacao deste arquivo."""

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC = os.path.join(RAIZ, "src")
BUILD = os.path.join(RAIZ, "build")
ANALISE = os.path.join(RAIZ, "analise")
RESULTADOS = os.path.join(RAIZ, "resultados")
DOCS = os.path.join(RAIZ, "docs")

FONTE_C = os.path.join(SRC, "produtor_consumidor.c")

EXECUTAVEL = os.path.join(
    BUILD, "produtor_consumidor.exe" if os.name == "nt" else "produtor_consumidor"
)


def garantir_pastas():
    for pasta in (BUILD, RESULTADOS, DOCS):
        os.makedirs(pasta, exist_ok=True)


def em_resultados(nome_arquivo):
    return os.path.join(RESULTADOS, nome_arquivo)
