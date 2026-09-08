"""Ponto de entrada: python executar.py"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "analise"))

from caminhos import EXECUTAVEL, em_resultados


def perguntar_inteiro(rotulo, padrao):
    resposta = input(f"{rotulo} [{padrao}]: ").strip()
    if not resposta:
        return padrao
    try:
        valor = int(resposta)
        return valor if valor > 0 else padrao
    except ValueError:
        print(f"  valor invalido, usando {padrao}")
        return padrao


def execucao_unica():
    from experimento import compilar
    compilar()

    print("\n--- Execucao unica (modo demonstracao) ---")
    N = perguntar_inteiro("N  (tamanho da memoria compartilhada)", 8)
    Np = perguntar_inteiro("Np (threads produtoras)", 2)
    Nc = perguntar_inteiro("Nc (threads consumidoras)", 2)
    M = perguntar_inteiro("M  (numeros a processar)", 20)

    print()
    subprocess.run([EXECUTAVEL, str(N), str(Np), str(Nc), str(M), "--verbose"])


def experimento_completo():
    from experimento import compilar, rodar_estudo, M_PADRAO, REPETICOES_PADRAO
    compilar()
    print(f"\nEstudo completo: M={M_PADRAO}, {REPETICOES_PADRAO} repeticoes por combinacao.\n")
    rodar_estudo(M_PADRAO, REPETICOES_PADRAO,
                 em_resultados("resultados.csv"),
                 em_resultados("grafico_desempenho.png"))


def experimento_rapido():
    from experimento import compilar, rodar_estudo
    compilar()
    print("\nModo rapido: M=2000, 3 repeticoes por combinacao.\n")
    rodar_estudo(2_000, 3,
                 em_resultados("resultados_rapido.csv"),
                 em_resultados("grafico_rapido.png"))


def demonstracao_visual():
    from demo_visual import main as abrir_demo
    abrir_demo()


def gerar_documentacao():
    from gerar_pdf import main as gerar
    gerar()


OPCOES = {
    "1": ("Execucao unica - imprime cada numero e se e primo", execucao_unica),
    "2": ("Estudo de caso do enunciado - gera o CSV e o grafico", experimento_completo),
    "3": ("Estudo rapido - valida o ambiente em poucos segundos", experimento_rapido),
    "4": ("Demonstracao visual do buffer (opcional, em Python)", demonstracao_visual),
    "5": ("Gerar a documentacao em PDF", gerar_documentacao),
}


def main():
    print("=== Produtor-Consumidor com Semaforos ===")
    for chave, (descricao, _) in OPCOES.items():
        print(f"  {chave}) {descricao}")
    print("  0) Sair")

    escolha = input("\nEscolha uma opcao: ").strip()

    if escolha == "0":
        return 0
    if escolha not in OPCOES:
        print("Opcao invalida.")
        return 1

    _, acao = OPCOES[escolha]
    acao()
    return 0


if __name__ == "__main__":
    sys.exit(main())
