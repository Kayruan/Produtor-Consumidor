"""
Estudo de caso: roda src/produtor_consumidor.c para cada combinacao (N, Np, Nc),
coleta os tempos e gera resultados/resultados.csv + grafico_desempenho.png.

Uso:
    python analise/experimento.py            estudo completo do enunciado
    python analise/experimento.py --rapido   versao reduzida, so valida o setup
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from caminhos import EXECUTAVEL, FONTE_C, em_resultados, garantir_pastas

N_VALORES = [2, 8, 32]

COMBINACOES = [
    (1, 1), (1, 2), (1, 4), (1, 8), (1, 16),
    (2, 1), (4, 1), (8, 1), (16, 1),
]

M_PADRAO = 10_000
REPETICOES_PADRAO = 10


def compilar(forcar=False):
    """Compila src/produtor_consumidor.c se estiver desatualizado. -static so no
    Windows (evita depender de libwinpthread-1.dll); no Linux e desnecessario e
    pode falhar em sistemas sem a libc estatica instalada."""
    garantir_pastas()

    atualizado = (
        os.path.exists(EXECUTAVEL)
        and os.path.getmtime(EXECUTAVEL) >= os.path.getmtime(FONTE_C)
    )
    if atualizado and not forcar:
        return

    gcc = shutil.which("gcc")
    if gcc is None:
        sys.exit("Erro: gcc nao encontrado no PATH. Instale-o "
                 "(MinGW-w64 no Windows, pacote gcc no Linux) "
                 "ou compile manualmente:\n"
                 "  gcc -O2 -Wall -Wextra -o build/produtor_consumidor "
                 "src/produtor_consumidor.c -pthread")

    flags_extra = ["-static"] if os.name == "nt" else []
    comando = [gcc, "-O2", "-Wall", "-Wextra", *flags_extra,
               "-o", EXECUTAVEL, FONTE_C, "-pthread"]
    print("Compilando:", " ".join(comando))

    processo = subprocess.run(comando, capture_output=True, text=True)
    if processo.returncode != 0:
        print(processo.stderr, file=sys.stderr)
        sys.exit("Erro: falha ao compilar o programa em C")

    print("Compilado com sucesso.\n")


def executar_uma_vez(N, Np, Nc, M):
    """Roda o executavel e le a linha 'RESULT ...' da saida padrao.
    O tempo e cronometrado dentro do C para nao incluir o custo do SO criar o processo."""
    processo = subprocess.run(
        [EXECUTAVEL, str(N), str(Np), str(Nc), str(M)],
        capture_output=True, text=True,
    )
    if processo.returncode != 0:
        raise RuntimeError(f"produtor_consumidor falhou (codigo {processo.returncode}): "
                           f"{processo.stderr.strip()}")

    for linha in processo.stdout.splitlines():
        if linha.startswith("RESULT"):
            _, tempo, primos, nao_primos, consumidos = linha.split()
            return {
                "tempo": float(tempo),
                "primos": int(primos),
                "nao_primos": int(nao_primos),
                "consumidos": int(consumidos),
            }

    raise RuntimeError("Nao encontrei a linha RESULT na saida do programa em C.")


def formatar_tempo(segundos):
    minutos, segundos = divmod(int(segundos), 60)
    return f"{minutos}m{segundos:02d}s"


def rodar_estudo(M, repeticoes, arquivo_csv, arquivo_png):
    linhas = []
    total_execucoes = len(N_VALORES) * len(COMBINACOES) * repeticoes
    feitas = 0
    inicio = time.perf_counter()

    for N in N_VALORES:
        for (Np, Nc) in COMBINACOES:
            tempos = []

            for r in range(repeticoes):
                medida = executar_uma_vez(N, Np, Nc, M)

                if medida["consumidos"] != M:
                    raise RuntimeError(
                        f"Inconsistencia em N={N} (Np,Nc)=({Np},{Nc}): "
                        f"esperava {M} itens, obtive {medida['consumidos']}."
                    )

                tempos.append(medida["tempo"])
                feitas += 1

                decorrido = time.perf_counter() - inicio
                restante = (decorrido / feitas) * (total_execucoes - feitas)
                print(f"\r[{100 * feitas / total_execucoes:5.1f}%] "
                      f"N={N:>2} (Np,Nc)=({Np:>2},{Nc:>2}) rep {r + 1}/{repeticoes}"
                      f"  faltam {formatar_tempo(restante)}   ",
                      end="", flush=True)

            media = sum(tempos) / len(tempos)
            desvio = (sum((t - media) ** 2 for t in tempos) / len(tempos)) ** 0.5

            linhas.append({
                "N": N,
                "Np": Np,
                "Nc": Nc,
                "combinacao": f"({Np},{Nc})",
                "threads_total": Np + Nc,
                "tempo_medio": media,
                "desvio_padrao": desvio,
                "tempo_minimo": min(tempos),
                "tempo_maximo": max(tempos),
            })

    print("\n")

    dados = pd.DataFrame(linhas)
    dados.to_csv(arquivo_csv, index=False, sep=";", decimal=",")
    print(f"Dados salvos em : {arquivo_csv}")

    gerar_grafico(dados, arquivo_png, M, repeticoes)
    resumir_resultados(dados)

    return dados


CORES = {2: "#2a78d6", 8: "#eb6834", 32: "#1baf7a"}
MARCADORES = {2: "o", 8: "s", 32: "^"}
TINTA_FORTE = "#0b0b0b"
TINTA_FRACA = "#52514e"
FUNDO = "#fcfcfb"


def gerar_grafico(dados, arquivo_png, M, repeticoes):
    """Tempo medio x combinacao de threads, uma curva por N. O eixo X segue a
    ordem do enunciado: primeiro Np=1 e Nc cresce, depois Nc=1 e Np cresce."""
    import matplotlib.pyplot as plt

    ordem = [f"({Np},{Nc})" for (Np, Nc) in COMBINACOES]

    figura, eixo = plt.subplots(figsize=(11, 6.5), facecolor=FUNDO)
    eixo.set_facecolor(FUNDO)

    fins = []
    for N in N_VALORES:
        serie = dados[dados["N"] == N].set_index("combinacao").reindex(ordem)
        cor = CORES[N]
        eixo.fill_between(
            ordem,
            serie["tempo_medio"] - serie["desvio_padrao"],
            serie["tempo_medio"] + serie["desvio_padrao"],
            color=cor, alpha=0.12, linewidth=0,
        )
        eixo.plot(
            ordem, serie["tempo_medio"],
            color=cor, marker=MARCADORES[N], markersize=8,
            linewidth=2, label=f"N = {N}",
            markeredgecolor=FUNDO, markeredgewidth=1.5,
        )
        fins.append((serie["tempo_medio"].iloc[-1], N))

    limite_inferior, limite_superior = eixo.get_ylim()
    separacao_minima = 0.045 * (limite_superior - limite_inferior)

    fins.sort()
    y_anterior = None
    for valor_final, N in fins:
        y_rotulo = valor_final
        if y_anterior is not None and y_rotulo - y_anterior < separacao_minima:
            y_rotulo = y_anterior + separacao_minima
        y_anterior = y_rotulo

        eixo.annotate(
            f"N = {N}",
            xy=(len(ordem) - 1, valor_final),
            xytext=(len(ordem) - 1 + 0.25, y_rotulo),
            color=CORES[N], fontsize=10, fontweight="bold",
            va="center", ha="left", annotation_clip=False,
        )

    eixo.axvline(4.5, color=TINTA_FRACA, linewidth=1, linestyle=":", alpha=0.5)
    eixo.text(2.0, 1.02, "Np fixo = 1, cresce Nc", transform=eixo.get_xaxis_transform(),
              ha="center", fontsize=9, color=TINTA_FRACA)
    eixo.text(6.75, 1.02, "Nc fixo = 1, cresce Np", transform=eixo.get_xaxis_transform(),
              ha="center", fontsize=9, color=TINTA_FRACA)

    melhor = dados.loc[dados["tempo_medio"].idxmin()]
    eixo.annotate(
        f"melhor: N={int(melhor['N'])}, (Np,Nc)=({int(melhor['Np'])},{int(melhor['Nc'])})"
        f" - {melhor['tempo_medio']:.4f} s",
        xy=(ordem.index(melhor["combinacao"]), melhor["tempo_medio"]),
        xytext=(18, 34), textcoords="offset points",
        ha="left", va="center", fontsize=9, color=TINTA_FORTE,
        arrowprops=dict(arrowstyle="-", color=TINTA_FRACA,
                        linewidth=1, shrinkA=0, shrinkB=6),
    )

    eixo.set_title("Produtor-Consumidor: tempo medio de execucao por combinacao de threads",
                   fontsize=13, color=TINTA_FORTE, pad=28, loc="left")
    eixo.set_xlabel("(Np, Nc) - threads produtoras / consumidoras",
                    fontsize=10, color=TINTA_FRACA, labelpad=10)
    eixo.set_ylabel("Tempo medio de execucao (s)",
                    fontsize=10, color=TINTA_FRACA, labelpad=10)

    eixo.grid(True, axis="y", linestyle="-", linewidth=0.6, color="#e5e4e0")
    eixo.set_axisbelow(True)
    for lado in ("top", "right"):
        eixo.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        eixo.spines[lado].set_color("#d6d5d0")
    eixo.tick_params(colors=TINTA_FRACA, labelsize=9)

    legenda = eixo.legend(title="Tamanho da memoria compartilhada",
                          frameon=False, loc="upper left", fontsize=9)
    legenda.get_title().set_fontsize(9)
    legenda.get_title().set_color(TINTA_FRACA)

    figura.text(0.01, 0.01,
                f"M = {M} numeros processados  |  {repeticoes} execucoes por ponto  |  "
                f"faixa sombreada = +-1 desvio padrao",
                fontsize=8, color=TINTA_FRACA)

    figura.tight_layout(rect=(0, 0.03, 0.97, 1))
    figura.savefig(arquivo_png, dpi=150, facecolor=FUNDO)
    print(f"Grafico salvo em: {arquivo_png}")
    plt.show()


def resumir_resultados(dados):
    """Resumo curto no terminal: melhor/pior combinacao e tabela completa.
    A analise de fato fica no PDF (analise/gerar_pdf.py)."""
    melhor = dados.loc[dados["tempo_medio"].idxmin()]
    pior = dados.loc[dados["tempo_medio"].idxmax()]

    print(f"Melhor: N={int(melhor['N'])}, (Np,Nc)=({int(melhor['Np'])},{int(melhor['Nc'])})"
          f"  ->  {melhor['tempo_medio']:.4f} s")
    print(f"Pior  : N={int(pior['N'])}, (Np,Nc)=({int(pior['Np'])},{int(pior['Nc'])})"
          f"  ->  {pior['tempo_medio']:.4f} s"
          f"  ({pior['tempo_medio'] / melhor['tempo_medio']:.2f}x mais lento)")

    tabela = dados.pivot(index="combinacao", columns="N", values="tempo_medio")
    tabela = tabela.reindex([f"({Np},{Nc})" for (Np, Nc) in COMBINACOES])
    print("\nTempo medio (s):")
    print(tabela.to_string(float_format=lambda v: f"{v:.4f}"))
    print("\nAnalise completa: python analise/gerar_pdf.py")


def main():
    analisador = argparse.ArgumentParser(
        description="Estudo de desempenho do Produtor-Consumidor em C.")
    analisador.add_argument("--rapido", action="store_true",
                            help="versao reduzida (M=2000, 3 repeticoes) para validar o setup")
    analisador.add_argument("--recompilar", action="store_true",
                            help="forca a recompilacao do programa em C antes de medir")
    analisador.add_argument("--M", type=int, default=None, metavar="N",
                            help=f"quantidade de numeros processados (padrao: {M_PADRAO})")
    analisador.add_argument("--repeticoes", type=int, default=None, metavar="N",
                            help=f"execucoes por combinacao (padrao: {REPETICOES_PADRAO})")
    argumentos = analisador.parse_args()

    compilar(forcar=argumentos.recompilar)

    if argumentos.rapido:
        M, repeticoes = 2_000, 3
        csv, png = "resultados_rapido.csv", "grafico_rapido.png"
        print("Modo rapido: M=2000, 3 repeticoes por combinacao.\n")
    else:
        M, repeticoes = M_PADRAO, REPETICOES_PADRAO
        csv, png = "resultados.csv", "grafico_desempenho.png"

    if argumentos.M is not None or argumentos.repeticoes is not None:
        M = argumentos.M if argumentos.M is not None else M
        repeticoes = argumentos.repeticoes if argumentos.repeticoes is not None else repeticoes
        csv = f"resultados_M{M}.csv"
        png = f"grafico_M{M}.png"

    total = len(N_VALORES) * len(COMBINACOES) * repeticoes
    print(f"Estudo: M={M}, {repeticoes} repeticoes por combinacao, {total} execucoes.\n")

    rodar_estudo(M, repeticoes, em_resultados(csv), em_resultados(png))


if __name__ == "__main__":
    sys.exit(main())
