"""
Gera a documentacao tecnica em PDF (docs/Documentacao.pdf) a partir de um HTML
montado com os dados de resultados/resultados.csv, convertido via Chrome/Edge
headless.

Uso:
    python analise/gerar_pdf.py
"""

import base64
import os
import platform
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from caminhos import DOCS, RESULTADOS, garantir_pastas

SAIDA_HTML = os.path.join(DOCS, "documentacao.html")
SAIDA_PDF = os.path.join(DOCS, "Documentacao.pdf")

NAVEGADORES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def carregar_dados():
    import pandas as pd

    caminho = os.path.join(RESULTADOS, "resultados.csv")
    if not os.path.exists(caminho):
        return None
    return pd.read_csv(caminho, sep=";", decimal=",")


def imagem_embutida(nome):
    """Data URI da imagem, para nao depender de caminho relativo no HTML temporario."""
    caminho = os.path.join(RESULTADOS, nome)
    if not os.path.exists(caminho):
        return None
    with open(caminho, "rb") as arquivo:
        dados = base64.b64encode(arquivo.read()).decode("ascii")
    return f"data:image/png;base64,{dados}"


def montar_tabela_resultados(dados):
    if dados is None:
        return "<p class='aviso'>Rode o experimento para preencher esta tabela.</p>"

    ordem = ["(1,1)", "(1,2)", "(1,4)", "(1,8)", "(1,16)",
             "(2,1)", "(4,1)", "(8,1)", "(16,1)"]
    pivo = dados.pivot(index="combinacao", columns="N",
                       values="tempo_medio").reindex(ordem)

    melhor_valor = dados["tempo_medio"].min()

    linhas = []
    for combinacao in ordem:
        celulas = []
        for N in pivo.columns:
            valor = pivo.loc[combinacao, N]
            destaque = " class='melhor'" if abs(valor - melhor_valor) < 1e-12 else ""
            celulas.append(f"<td{destaque}>{valor:.4f}</td>")
        linhas.append(f"<tr><th>{combinacao}</th>{''.join(celulas)}</tr>")

    cabecalho = "".join(f"<th>N = {N}</th>" for N in pivo.columns)
    return f"""
    <table class="dados">
      <thead><tr><th>(Np, Nc)</th>{cabecalho}</tr></thead>
      <tbody>{''.join(linhas)}</tbody>
    </table>
    <p class="legenda-tabela">Tempo médio de execução em segundos.
       Em destaque, a combinação de melhor desempenho.</p>
    """


def montar_tabela_escala(dados):
    if dados is None:
        return "<p class='aviso'>Rode o experimento para preencher esta tabela.</p>"

    escala_nc = dados[dados["Np"] == 1].groupby("Nc")["tempo_medio"].mean()
    escala_np = dados[dados["Nc"] == 1].groupby("Np")["tempo_medio"].mean()

    melhor_nc = escala_nc.min()
    melhor_np = escala_np.min()

    linhas = []
    for quantidade in [1, 2, 4, 8, 16]:
        tempo_nc = escala_nc.get(quantidade)
        tempo_np = escala_np.get(quantidade)
        marca_nc = " class='melhor'" if tempo_nc == melhor_nc else ""
        marca_np = " class='melhor'" if tempo_np == melhor_np else ""
        linhas.append(
            f"<tr><th>{quantidade}</th>"
            f"<td{marca_nc}>{tempo_nc:.4f}</td>"
            f"<td{marca_np}>{tempo_np:.4f}</td></tr>"
        )

    return f"""
    <table class="dados">
      <thead><tr>
        <th>Quantidade de threads</th>
        <th>Aumentando N<sub>c</sub> (com N<sub>p</sub>=1)</th>
        <th>Aumentando N<sub>p</sub> (com N<sub>c</sub>=1)</th>
      </tr></thead>
      <tbody>{''.join(linhas)}</tbody>
    </table>
    <p class="legenda-tabela">Tempo médio em segundos, calculado sobre os três
       valores de N. Em destaque, o melhor de cada coluna.</p>
    """


def numeros_do_texto(dados):
    if dados is None:
        return {
            "melhor": "—", "melhor_tempo": "—", "pior": "—", "pior_tempo": "—",
            "razao": "—", "ganho_N": "—", "custo_item": "—",
            "media_N2": "—", "media_N32": "—",
        }

    melhor = dados.loc[dados["tempo_medio"].idxmin()]
    pior = dados.loc[dados["tempo_medio"].idxmax()]
    por_N = dados.groupby("N")["tempo_medio"].mean()

    return {
        "melhor": f"N={int(melhor['N'])}, (Np,Nc)=({int(melhor['Np'])},{int(melhor['Nc'])})",
        "melhor_tempo": f"{melhor['tempo_medio']:.4f}",
        "pior": f"N={int(pior['N'])}, (Np,Nc)=({int(pior['Np'])},{int(pior['Nc'])})",
        "pior_tempo": f"{pior['tempo_medio']:.4f}",
        "razao": f"{pior['tempo_medio'] / melhor['tempo_medio']:.1f}",
        "ganho_N": f"{por_N.iloc[0] / por_N.iloc[-1]:.1f}",
        "media_N2": f"{por_N.iloc[0]:.4f}",
        "media_N32": f"{por_N.iloc[-1]:.4f}",
        "custo_item": f"{melhor['tempo_medio'] / 10_000 * 1e6:.2f}",
    }


def descrever_maquina():
    return f"{platform.system()} {platform.release()}, {os.cpu_count()} CPUs lógicas"


CSS = """
@page { size: A4; margin: 18mm 16mm; }

* { box-sizing: border-box; }

body {
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.6;
  color: #1a1a1a;
  margin: 0;
}

h1, h2, h3, h4 { line-height: 1.25; color: #0b0b0b; }
h1 { font-size: 20pt; margin: 0 0 4pt; }
h2 {
  font-size: 15pt; margin: 26pt 0 10pt;
  padding-bottom: 5pt; border-bottom: 2px solid #2a78d6;
  page-break-after: avoid;
}
h3 { font-size: 12pt; margin: 18pt 0 6pt; page-break-after: avoid; }
h4 { font-size: 10.5pt; margin: 12pt 0 4pt; color: #52514e; page-break-after: avoid; }

p { margin: 0 0 9pt; text-align: justify; }
ul, ol { margin: 0 0 9pt; padding-left: 18pt; }
li { margin-bottom: 4pt; }

code {
  font-family: "Consolas", "Courier New", monospace;
  font-size: 9pt;
  background: #f2f2ef;
  padding: 1px 4px;
  border-radius: 3px;
}

pre {
  font-family: "Consolas", "Courier New", monospace;
  font-size: 8.5pt;
  line-height: 1.45;
  background: #fbfbf9;
  border: 1px solid #e2e1dc;
  border-left: 3px solid #2a78d6;
  border-radius: 4px;
  padding: 9pt 11pt;
  overflow-x: auto;
  white-space: pre-wrap;
  page-break-inside: avoid;
  margin: 0 0 10pt;
}
pre code { background: none; padding: 0; font-size: inherit; }
pre .c { color: #6b7280; font-style: italic; }
pre .k { color: #1d4ed8; font-weight: 600; }

table { border-collapse: collapse; width: 100%; margin: 0 0 8pt; font-size: 9.5pt; }
th, td { border: 1px solid #dedcd6; padding: 5pt 8pt; text-align: left; }
thead th { background: #f2f2ef; font-weight: 600; }
table.dados td { text-align: right; font-variant-numeric: tabular-nums; }
table.dados tbody th { background: #fafaf8; font-weight: 600; }
td.melhor { background: #dff3e6; font-weight: 700; color: #12603a; }
.legenda-tabela { font-size: 8.5pt; color: #6b6a66; margin-top: -4pt; }

figure { margin: 12pt 0; page-break-inside: avoid; text-align: center; }
figure img { width: 100%; border: 1px solid #e2e1dc; border-radius: 4px; }
figcaption { font-size: 8.5pt; color: #6b6a66; margin-top: 5pt; text-align: center; }

.destaque {
  background: #f4f8fd;
  border-left: 3px solid #2a78d6;
  padding: 9pt 12pt;
  margin: 0 0 10pt;
  page-break-inside: avoid;
}
.destaque p:last-child { margin-bottom: 0; }
.destaque strong { color: #1a4f96; }

.atencao {
  background: #fdf6f0;
  border-left: 3px solid #eb6834;
  padding: 9pt 12pt;
  margin: 0 0 10pt;
  page-break-inside: avoid;
}
.atencao p:last-child { margin-bottom: 0; }

.capa {
  height: 245mm;
  display: flex; flex-direction: column; justify-content: center;
  text-align: center;
  page-break-after: always;
}
.capa .disciplina {
  font-size: 10pt; letter-spacing: 2.5px; text-transform: uppercase;
  color: #6b6a66; margin-bottom: 14pt;
}
.capa h1 { font-size: 28pt; margin-bottom: 8pt; letter-spacing: -0.5px; }
.capa .subtitulo { font-size: 13pt; color: #52514e; font-weight: 400; margin-bottom: 26pt; }
.capa .regua { width: 70pt; height: 3px; background: #2a78d6; margin: 0 auto 26pt; }
.capa .meta { font-size: 10pt; color: #52514e; line-height: 1.9; }
.capa .rodape-capa { margin-top: 34pt; font-size: 9pt; color: #8b8a85; }

.sumario { page-break-after: always; }
.sumario ol { list-style: none; padding-left: 0; counter-reset: sec; }
.sumario > ol > li {
  counter-increment: sec;
  padding: 5pt 0;
  border-bottom: 1px dotted #dedcd6;
  font-weight: 600;
}
.sumario > ol > li::before { content: counter(sec) ". "; color: #2a78d6; }

.quebra { page-break-before: always; }

.diagrama { text-align: center; margin: 14pt 0; page-break-inside: avoid; }
.diagrama svg { max-width: 100%; height: auto; }

.arquivo {
  border: 1px solid #e2e1dc; border-radius: 5px;
  padding: 9pt 12pt; margin-bottom: 9pt;
  page-break-inside: avoid;
}
.arquivo h4 {
  margin: 0 0 4pt; font-family: "Consolas", monospace;
  font-size: 10pt; color: #1a4f96;
}
.arquivo p { margin: 0; font-size: 9.5pt; }

.rodape {
  margin-top: 26pt; padding-top: 9pt;
  border-top: 1px solid #dedcd6;
  font-size: 8.5pt; color: #8b8a85; text-align: center;
}
"""


DIAGRAMA_FLUXO = """
<div class="diagrama">
<svg viewBox="0 0 640 210" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Produtores inserem no buffer protegido por semáforos; consumidores retiram">
  <defs>
    <marker id="seta" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">
      <polygon points="0 0, 9 3.5, 0 7" fill="#52514e"/>
    </marker>
  </defs>

  <rect x="8" y="30" width="112" height="34" rx="5" fill="#e8f0fb" stroke="#2a78d6"/>
  <text x="64" y="52" text-anchor="middle" font-size="12" font-family="Segoe UI"
        fill="#1a4f96">Produtor 1</text>
  <rect x="8" y="76" width="112" height="34" rx="5" fill="#e8f0fb" stroke="#2a78d6"/>
  <text x="64" y="98" text-anchor="middle" font-size="12" font-family="Segoe UI"
        fill="#1a4f96">Produtor 2</text>
  <text x="64" y="130" text-anchor="middle" font-size="11" font-family="Segoe UI"
        fill="#6b6a66">... Np threads</text>

  <line x1="124" y1="47" x2="196" y2="66" stroke="#52514e" stroke-width="1.4"
        marker-end="url(#seta)"/>
  <line x1="124" y1="93" x2="196" y2="80" stroke="#52514e" stroke-width="1.4"
        marker-end="url(#seta)"/>
  <text x="160" y="40" text-anchor="middle" font-size="10" font-family="Consolas"
        fill="#52514e">sem_wait(vagas)</text>

  <rect x="206" y="46" width="228" height="56" rx="5" fill="#fbfbf9" stroke="#52514e"
        stroke-width="1.5"/>
  <text x="320" y="34" text-anchor="middle" font-size="11" font-family="Segoe UI"
        font-weight="600" fill="#0b0b0b">Memória compartilhada (vetor de N)</text>
  <rect x="216" y="58" width="32" height="32" rx="3" fill="#dff3e6" stroke="#1baf7a"/>
  <text x="232" y="79" text-anchor="middle" font-size="11" font-family="Consolas">17</text>
  <rect x="254" y="58" width="32" height="32" rx="3" fill="#dff3e6" stroke="#1baf7a"/>
  <text x="270" y="79" text-anchor="middle" font-size="11" font-family="Consolas">42</text>
  <rect x="292" y="58" width="32" height="32" rx="3" fill="#f2f2ef" stroke="#c9c8c3"/>
  <text x="308" y="79" text-anchor="middle" font-size="11" font-family="Consolas"
        fill="#8b8a85">0</text>
  <rect x="330" y="58" width="32" height="32" rx="3" fill="#dff3e6" stroke="#1baf7a"/>
  <text x="346" y="79" text-anchor="middle" font-size="11" font-family="Consolas">91</text>
  <rect x="368" y="58" width="32" height="32" rx="3" fill="#f2f2ef" stroke="#c9c8c3"/>
  <text x="384" y="79" text-anchor="middle" font-size="11" font-family="Consolas"
        fill="#8b8a85">0</text>
  <text x="416" y="79" text-anchor="middle" font-size="12" font-family="Segoe UI"
        fill="#6b6a66">...</text>
  <text x="320" y="118" text-anchor="middle" font-size="9.5" font-family="Segoe UI"
        fill="#6b6a66">0 = posição livre &#183; protegido por mutex_memoria</text>

  <line x1="440" y1="66" x2="512" y2="47" stroke="#52514e" stroke-width="1.4"
        marker-end="url(#seta)"/>
  <line x1="440" y1="80" x2="512" y2="93" stroke="#52514e" stroke-width="1.4"
        marker-end="url(#seta)"/>
  <text x="464" y="40" text-anchor="middle" font-size="10" font-family="Consolas"
        fill="#52514e">sem_wait(itens)</text>

  <rect x="518" y="30" width="118" height="34" rx="5" fill="#fdf0e8" stroke="#eb6834"/>
  <text x="577" y="52" text-anchor="middle" font-size="12" font-family="Segoe UI"
        fill="#a8461c">Consumidor 1</text>
  <rect x="518" y="76" width="118" height="34" rx="5" fill="#fdf0e8" stroke="#eb6834"/>
  <text x="577" y="98" text-anchor="middle" font-size="12" font-family="Segoe UI"
        fill="#a8461c">Consumidor 2</text>
  <text x="577" y="130" text-anchor="middle" font-size="11" font-family="Segoe UI"
        fill="#6b6a66">... Nc threads</text>

  <text x="577" y="152" text-anchor="middle" font-size="10" font-family="Segoe UI"
        fill="#52514e">testa se é primo</text>

  <line x1="560" y1="166" x2="90" y2="166" stroke="#c9c8c3" stroke-width="1.2"
        stroke-dasharray="4 3" marker-end="url(#seta)"/>
  <text x="325" y="182" text-anchor="middle" font-size="10" font-family="Consolas"
        fill="#6b6a66">sem_post(vagas) &#8212; libera espaço para os produtores</text>
</svg>
</div>
"""

DIAGRAMA_DEADLOCK = """
<div class="diagrama">
<svg viewBox="0 0 620 128" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Ordem correta: semáforo antes do mutex. Ordem incorreta causa deadlock">
  <text x="10" y="18" font-size="11" font-family="Segoe UI" font-weight="600"
        fill="#12603a">CORRETO</text>
  <rect x="10" y="26" width="128" height="28" rx="4" fill="#dff3e6" stroke="#1baf7a"/>
  <text x="74" y="45" text-anchor="middle" font-size="10.5"
        font-family="Consolas">sem_wait(vagas)</text>
  <line x1="140" y1="40" x2="166" y2="40" stroke="#52514e" stroke-width="1.3"
        marker-end="url(#seta)"/>
  <rect x="168" y="26" width="118" height="28" rx="4" fill="#dff3e6" stroke="#1baf7a"/>
  <text x="227" y="45" text-anchor="middle" font-size="10.5"
        font-family="Consolas">lock(mutex)</text>
  <line x1="288" y1="40" x2="314" y2="40" stroke="#52514e" stroke-width="1.3"
        marker-end="url(#seta)"/>
  <rect x="316" y="26" width="128" height="28" rx="4" fill="#dff3e6" stroke="#1baf7a"/>
  <text x="380" y="45" text-anchor="middle" font-size="10.5"
        font-family="Consolas">unlock(mutex)</text>
  <line x1="446" y1="40" x2="472" y2="40" stroke="#52514e" stroke-width="1.3"
        marker-end="url(#seta)"/>
  <rect x="474" y="26" width="134" height="28" rx="4" fill="#dff3e6" stroke="#1baf7a"/>
  <text x="541" y="45" text-anchor="middle" font-size="10.5"
        font-family="Consolas">sem_post(itens)</text>

  <text x="10" y="86" font-size="11" font-family="Segoe UI" font-weight="600"
        fill="#a3261f">DEADLOCK</text>
  <rect x="10" y="94" width="118" height="28" rx="4" fill="#fdeceb" stroke="#e34948"/>
  <text x="69" y="113" text-anchor="middle" font-size="10.5"
        font-family="Consolas">lock(mutex)</text>
  <line x1="130" y1="108" x2="156" y2="108" stroke="#52514e" stroke-width="1.3"
        marker-end="url(#seta)"/>
  <rect x="158" y="94" width="128" height="28" rx="4" fill="#fdeceb" stroke="#e34948"/>
  <text x="222" y="113" text-anchor="middle" font-size="10.5"
        font-family="Consolas">sem_wait(vagas)</text>
  <text x="300" y="113" font-size="10.5" font-family="Segoe UI" fill="#a3261f">
    a thread dorme SEGURANDO o mutex &#8212; ninguém mais entra para liberá-la
  </text>
</svg>
</div>
"""


def montar_html(dados):
    num = numeros_do_texto(dados)
    grafico = imagem_embutida("grafico_desempenho.png")
    tabela = montar_tabela_resultados(dados)
    tabela_escala = montar_tabela_escala(dados)
    maquina = descrever_maquina()

    figura_grafico = (
        f'<figure><img src="{grafico}" alt="Gráfico do tempo médio de execução">'
        f'<figcaption>Tempo médio de execução por combinação de threads, '
        f'uma curva para cada valor de N.</figcaption></figure>'
        if grafico else
        "<p class='aviso'>Gráfico ainda não gerado. Rode o experimento.</p>"
    )

    modelo = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Produtor-Consumidor com Semáforos — Documentação</title>
<style>%%CSS%%</style>
</head>
<body>

<section class="capa">
  <div class="disciplina">Sistemas Operacionais &#183; Programação Concorrente</div>
  <h1>Problema Produtor-Consumidor<br>com Semáforos</h1>
  <div class="subtitulo">Implementação multithreaded em C e análise de desempenho</div>
  <div class="regua"></div>
  <div class="meta">
    Memória compartilhada limitada &#183; semáforos contadores &#183; exclusão mútua<br>
    Estudo de caso: N &#8712; {2, 8, 32} &#183; 9 combinações (N<sub>p</sub>, N<sub>c</sub>) &#183; M = 10<sup>4</sup>
  </div>
  <div class="rodape-capa">
    Medições realizadas em %%MAQUINA%%<br>
    Compilado com GCC (MinGW-w64), POSIX threads
  </div>
</section>

<section class="sumario">
  <h2 style="margin-top:0">Sumário</h2>
  <ol>
    <li>Sincronização: semáforos e exclusão mútua</li>
    <li>Estrutura do projeto</li>
    <li>Implementação em C</li>
    <li>Camada Python: experimento e gráficos</li>
    <li>Metodologia experimental</li>
    <li>Resultados</li>
    <li>Conclusão</li>
    <li>Como executar</li>
  </ol>
</section>

<h2>1. Sincronização: semáforos e exclusão mútua</h2>
<p>
A memória compartilhada é um vetor de N inteiros, onde <code>0</code> denota
posição livre. N<sub>p</sub> threads produtoras geram inteiros aleatórios entre
1 e 10<sup>7</sup> e os inserem em uma posição livre; N<sub>c</sub> threads
consumidoras retiram um número, copiam-no para memória local e testam se é
primo. O programa termina quando M números tiverem sido processados.
</p>

%%DIAGRAMA_FLUXO%%

<p>Três primitivas coordenam o acesso ao vetor:</p>
<table>
  <thead><tr><th>Primitiva</th><th>Inicia em</th><th>Responde à pergunta</th></tr></thead>
  <tbody>
    <tr><td><code>sem_vagas</code> (contador)</td><td>N</td>
        <td>Existe posição livre? Senão, o produtor dorme.</td></tr>
    <tr><td><code>sem_itens</code> (contador)</td><td>0</td>
        <td>Existe posição ocupada? Senão, o consumidor dorme.</td></tr>
    <tr><td><code>mutex_memoria</code></td><td>destravado</td>
        <td>Exclusão mútua: só uma thread mexe no vetor por vez.</td></tr>
  </tbody>
</table>
<p>
Os dois contadores são complementares: <code>sem_vagas + sem_itens</code> é
sempre igual a N.
</p>

<div class="atencao">
  <p><strong>Ordem obrigatória:</strong> semáforo contador antes do mutex,
  nunca o contrário. Invertendo, a thread dormiria segurando o mutex e
  ninguém mais conseguiria entrar na região crítica para liberá-la —
  deadlock permanente.</p>
</div>

%%DIAGRAMA_DEADLOCK%%

<h2 class="quebra">2. Estrutura do projeto</h2>
<pre><code>Produtor-Consumidor/
&#9500;&#9472; executar.py               <span class="c">ponto de entrada (menu)</span>
&#9500;&#9472; Makefile                  <span class="c">atalhos de compilação</span>
&#9500;&#9472; README.md
&#9500;&#9472; src/
&#9474;  &#9492;&#9472; produtor_consumidor.c  <span class="c">o programa do enunciado</span>
&#9500;&#9472; analise/
&#9474;  &#9500;&#9472; experimento.py         <span class="c">estudo de caso, CSV e gráfico</span>
&#9474;  &#9500;&#9472; caminhos.py            <span class="c">caminhos do projeto</span>
&#9474;  &#9500;&#9472; gerar_pdf.py           <span class="c">gera esta documentação</span>
&#9474;  &#9500;&#9472; demo_visual.py         <span class="c">animação opcional (Tkinter)</span>
&#9474;  &#9492;&#9472; simulador_python.py    <span class="c">núcleo em Python, só para a animação</span>
&#9500;&#9472; build/
&#9474;  &#9492;&#9472; produtor_consumidor     <span class="c">(.exe no Windows)</span>
&#9500;&#9472; resultados/
&#9474;  &#9500;&#9472; resultados.csv
&#9474;  &#9492;&#9472; grafico_desempenho.png
&#9492;&#9472; docs/
   &#9500;&#9472; Documentacao.pdf
   &#9492;&#9472; enunciado.jpeg</code></pre>

<div class="arquivo">
  <h4>src/produtor_consumidor.c</h4>
  <p>Toda a lógica do problema: threads, semáforos, memória compartilhada,
  teste de primalidade e cronometragem. Só depende de libc e pthreads.</p>
</div>
<div class="arquivo">
  <h4>analise/experimento.py</h4>
  <p>Compila o C se necessário, executa o binário para cada uma das 27
  configurações (10 vezes cada), lê o tempo pela saída padrão, monta o CSV
  e o gráfico. Não implementa nada do problema.</p>
</div>
<div class="arquivo">
  <h4>analise/demo_visual.py e simulador_python.py</h4>
  <p>Animação opcional em Tkinter do vetor preenchendo/esvaziando, para apoio
  visual; reimplementação em Python puro, não é a versão avaliada.</p>
</div>

<h2 class="quebra">3. Implementação em C</h2>

<h3>3.1 Estruturas de dados</h3>
<pre><code><span class="k">typedef struct</span> {
    <span class="k">int</span> *memoria;                  <span class="c">// vetor de N inteiros (0 = livre)</span>
    <span class="k">int</span>  tamanho;                  <span class="c">// N</span>

    sem_t sem_vagas;               <span class="c">// posições livres    (inicia em N)</span>
    sem_t sem_itens;               <span class="c">// posições ocupadas  (inicia em 0)</span>
    pthread_mutex_t mutex_memoria;

    <span class="k">int</span> total_itens;               <span class="c">// M</span>
    <span class="k">int</span> reservados_producao;
    <span class="k">int</span> reservados_consumo;
    pthread_mutex_t mutex_cota;

    <span class="k">long</span> primos, nao_primos;
    pthread_mutex_t mutex_estatisticas;
    <span class="k">int</span> verboso;
    pthread_mutex_t mutex_saida;
} MemoriaCompartilhada;</code></pre>

<h3>3.2 Thread produtora</h3>
<pre><code><span class="k">while</span> (reservar_item(mc, &amp;mc-&gt;reservados_producao)) {
    <span class="k">int</span> valor = gerar_numero(&amp;args-&gt;semente);

    sem_wait(&amp;mc-&gt;sem_vagas);          <span class="c">// dorme se o vetor estiver cheio</span>

    pthread_mutex_lock(&amp;mc-&gt;mutex_memoria);
    <span class="k">int</span> posicao = buscar_posicao_livre(mc);
    mc-&gt;memoria[posicao] = valor;
    pthread_mutex_unlock(&amp;mc-&gt;mutex_memoria);

    sem_post(&amp;mc-&gt;sem_itens);
}</code></pre>

<h3>3.3 Thread consumidora</h3>
<pre><code><span class="k">while</span> (reservar_item(mc, &amp;mc-&gt;reservados_consumo)) {
    sem_wait(&amp;mc-&gt;sem_itens);          <span class="c">// dorme se o vetor estiver vazio</span>

    pthread_mutex_lock(&amp;mc-&gt;mutex_memoria);
    <span class="k">int</span> posicao = buscar_posicao_ocupada(mc);
    <span class="k">int</span> valor   = mc-&gt;memoria[posicao];   <span class="c">// cópia local</span>
    mc-&gt;memoria[posicao] = POSICAO_LIVRE;
    pthread_mutex_unlock(&amp;mc-&gt;mutex_memoria);

    sem_post(&amp;mc-&gt;sem_vagas);

    <span class="k">int</span> primo = eh_primo(valor);   <span class="c">// fora da região crítica</span>
}</code></pre>

<h3>3.4 Como o programa termina</h3>
<p>
Cada thread reserva uma unidade de trabalho de uma cota compartilhada antes de
operar sobre o vetor:
</p>
<pre><code><span class="k">static int</span> reservar_item(MemoriaCompartilhada *mc, <span class="k">int</span> *contador) {
    <span class="k">int</span> obteve = 0;
    pthread_mutex_lock(&amp;mc-&gt;mutex_cota);
    <span class="k">if</span> (*contador &lt; mc-&gt;total_itens) {
        (*contador)++;
        obteve = 1;
    }
    pthread_mutex_unlock(&amp;mc-&gt;mutex_cota);
    <span class="k">return</span> obteve;
}</code></pre>
<p>
Como são reservados exatamente M itens de produção e M de consumo, nenhuma
thread fica esperando por algo que nunca chega. Verificado automaticamente em
cada uma das 270 execuções do estudo.
</p>

<h3>3.5 Decisões de projeto</h3>
<ul>
  <li><strong>RNG por thread</strong> (xorshift64* em vez de <code>rand()</code>):
      evita que o estado global do <code>rand()</code> vire um ponto de
      serialização artificial entre as threads.</li>
  <li><strong>Primalidade fora da região crítica</strong>: o valor é copiado
      para a pilha da thread antes do teste, para não prender as demais
      threads durante o cálculo.</li>
</ul>

<h2>4. Camada Python: experimento e gráficos</h2>
<p>
O C implementa o problema; o Python mede e grafica. O contrato entre os dois é
a última linha impressa pelo C:
</p>
<pre><code>RESULT &lt;tempo_em_segundos&gt; &lt;primos&gt; &lt;nao_primos&gt; &lt;consumidos&gt;</code></pre>
<p>
O tempo é cronometrado dentro do C (<code>clock_gettime(CLOCK_MONOTONIC)</code>),
em volta da criação e do <code>join</code> das threads — assim não inclui o
custo do sistema operacional criar o processo.
</p>

<h2>5. Metodologia experimental</h2>
<table>
  <thead><tr><th>Parâmetro</th><th>Valor</th></tr></thead>
  <tbody>
    <tr><td>Números processados (M)</td><td>10<sup>4</sup></td></tr>
    <tr><td>Tamanho da memória compartilhada (N)</td><td>2, 8 e 32</td></tr>
    <tr><td>Combinações (N<sub>p</sub>, N<sub>c</sub>)</td>
        <td>(1,1) (1,2) (1,4) (1,8) (1,16) (2,1) (4,1) (8,1) (16,1)</td></tr>
    <tr><td>Repetições por combinação</td><td>10</td></tr>
    <tr><td>Total de execuções</td><td>3 &#215; 9 &#215; 10 = 270</td></tr>
    <tr><td>Faixa dos números sorteados</td><td>1 a 10<sup>7</sup></td></tr>
    <tr><td>Compilação</td><td><code>%%COMPILACAO%%</code></td></tr>
    <tr><td>Máquina</td><td>%%MAQUINA%%</td></tr>
  </tbody>
</table>
<p>
As nove combinações formam dois blocos: nas cinco primeiras N<sub>p</sub>=1 e
N<sub>c</sub> cresce; nas quatro últimas N<sub>c</sub>=1 e N<sub>p</sub> cresce
— por isso o gráfico traz uma linha divisória entre os dois blocos. A
impressão no terminal fica desligada durante as medições (a E/S mascararia o
tempo real); ela só é usada no modo <code>--verbose</code>.
</p>

<h2>6. Resultados</h2>

%%FIGURA%%

<h3>6.1 Tabela completa</h3>
%%TABELA%%

<h3>6.2 Efeito de aumentar produtores x consumidores</h3>
%%TABELA_ESCALA%%

<h2>7. Conclusão</h2>
<div class="destaque">
  <p><strong>Melhor combinação: %%MELHOR%% — %%MELHOR_TEMPO%% s</strong>
  (%%RAZAO%%&#215; mais rápida que a pior, %%PIOR%%, %%PIOR_TEMPO%% s).</p>
</div>
<ul>
  <li><strong>N domina o resultado:</strong> de N=2 para N=32 o tempo médio
      cai de %%MEDIA_N2%% s para %%MEDIA_N32%% s (%%GANHO_N%%&#215;). Com N
      pequeno o vetor vive cheio ou vazio e quase toda operação encontra o
      semáforo em zero — cada bloqueio custa uma chamada ao escalonador, mais
      caro que o próprio teste de primalidade.</li>
  <li><strong>Mais threads pioraram o desempenho</strong>, dos dois lados:
      toda inserção e toda retirada passam pelo mesmo mutex, uma região
      crítica serial por construção (Lei de Amdahl). A máquina de teste tem
      %%CPUS%% CPUs lógicas.</li>
  <li><strong>Não há M que reverta o quadro.</strong> Com M cem vezes maior
      (10<sup>6</sup>, N=32) o tempo continua crescendo com mais threads:</li>
</ul>
<table>
  <thead><tr><th>(N<sub>p</sub>, N<sub>c</sub>)</th><th>Tempo com M = 10<sup>6</sup></th></tr></thead>
  <tbody>
    <tr><td>(1, 1)</td><td>1,00 s</td></tr>
    <tr><td>(1, 2)</td><td>1,05 s</td></tr>
    <tr><td>(1, 4)</td><td>1,90 s</td></tr>
    <tr><td>(1, 8)</td><td>2,91 s</td></tr>
  </tbody>
</table>
<p>
Na melhor combinação, cada número custa cerca de %%CUSTO_ITEM%% microssegundos
do início ao fim — a maior parte é sincronização, não cálculo (~94% dos
sorteios entre 1 e 10<sup>7</sup> são compostos, descartados nas primeiras
divisões). Como o trabalho útil por item é menor que o custo de sincronizar o
acesso a ele, nenhuma quantidade de threads compensa; paralelismo só valeria a
pena com um custo por item bem maior (números maiores, ou lotes por entrada na
região crítica).
</p>

<h2 class="quebra">8. Como executar</h2>
<p>
Requisitos: GCC com POSIX threads (pacote <code>gcc</code> no Linux; MinGW-w64
variante <em>posix</em> no Windows) e Python 3 com <code>pandas</code> e
<code>matplotlib</code>.
</p>
<pre><code><span class="c"># menu com todas as opções</span>
python executar.py

<span class="c"># compilar manualmente (Linux)</span>
gcc -O2 -Wall -Wextra -o build/produtor_consumidor \\
    src/produtor_consumidor.c -pthread

<span class="c"># compilar manualmente (Windows; -static evita depender de uma DLL)</span>
gcc -O2 -Wall -Wextra -static -o build/produtor_consumidor.exe \\
    src/produtor_consumidor.c -pthread

<span class="c"># demonstração: imprime cada número e se é primo</span>
build/produtor_consumidor 8 2 2 20 --verbose

<span class="c"># estudo de caso completo do enunciado</span>
python analise/experimento.py

<span class="c"># variações</span>
python analise/experimento.py --rapido
python analise/experimento.py --M 1000000 --repeticoes 3</code></pre>

<pre><code>produtor_consumidor &lt;N&gt; &lt;Np&gt; &lt;Nc&gt; &lt;M&gt; [--verbose]

  N   tamanho da memória compartilhada (vetor)
  Np  número de threads produtoras
  Nc  número de threads consumidoras
  M   quantidade de números a processar
  --verbose  imprime cada número consumido e se é primo</code></pre>

<div class="rodape">
  Documentação gerada automaticamente a partir de resultados/resultados.csv
  &#183; Medições em %%MAQUINA%%
</div>

</body>
</html>
"""

    substituicoes = {
        "%%CSS%%": CSS,
        "%%DIAGRAMA_FLUXO%%": DIAGRAMA_FLUXO,
        "%%DIAGRAMA_DEADLOCK%%": DIAGRAMA_DEADLOCK,
        "%%MAQUINA%%": maquina,
        "%%COMPILACAO%%": "gcc -O2 -Wall -Wextra -static -pthread" if os.name == "nt"
                           else "gcc -O2 -Wall -Wextra -pthread",
        "%%FIGURA%%": figura_grafico,
        "%%TABELA%%": tabela,
        "%%TABELA_ESCALA%%": tabela_escala,
        "%%CPUS%%": str(os.cpu_count()),
        "%%MELHOR%%": num["melhor"],
        "%%MELHOR_TEMPO%%": num["melhor_tempo"],
        "%%PIOR%%": num["pior"],
        "%%PIOR_TEMPO%%": num["pior_tempo"],
        "%%RAZAO%%": num["razao"],
        "%%GANHO_N%%": num["ganho_N"],
        "%%MEDIA_N2%%": num["media_N2"],
        "%%MEDIA_N32%%": num["media_N32"],
        "%%CUSTO_ITEM%%": num["custo_item"],
    }
    for marcador, valor in substituicoes.items():
        modelo = modelo.replace(marcador, valor)

    return modelo


def localizar_navegador():
    for caminho in NAVEGADORES:
        if os.path.exists(caminho):
            return caminho
    for nome in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        encontrado = shutil.which(nome)
        if encontrado:
            return encontrado
    return None


def converter_para_pdf(caminho_html, caminho_pdf):
    navegador = localizar_navegador()
    if navegador is None:
        print("Aviso: Chrome/Edge nao encontrado; o PDF nao foi gerado.")
        print(f"       O HTML continua disponivel em: {caminho_html}")
        print("       Abra-o no navegador e use Imprimir > Salvar como PDF.")
        return False

    with tempfile.TemporaryDirectory() as perfil:
        comando = [
            navegador,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir={perfil}",
            "--no-pdf-header-footer",
            f"--print-to-pdf={caminho_pdf}",
            f"file:///{caminho_html.replace(os.sep, '/')}",
        ]
        processo = subprocess.run(comando, capture_output=True, text=True, timeout=120)

    if not os.path.exists(caminho_pdf):
        print("Erro ao gerar o PDF:")
        print(processo.stderr[-800:])
        return False

    return True


def main():
    garantir_pastas()

    dados = carregar_dados()
    if dados is None:
        print("Aviso: resultados/resultados.csv nao encontrado.")
        print("       Rode primeiro: python analise/experimento.py\n")

    with open(SAIDA_HTML, "w", encoding="utf-8") as arquivo:
        arquivo.write(montar_html(dados))
    print(f"HTML gerado em : {SAIDA_HTML}")

    if converter_para_pdf(SAIDA_HTML, SAIDA_PDF):
        tamanho = os.path.getsize(SAIDA_PDF) / 1024
        print(f"PDF gerado em  : {SAIDA_PDF} ({tamanho:.0f} KB)")


if __name__ == "__main__":
    sys.exit(main())
