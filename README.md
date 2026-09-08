# Problema Produtor-Consumidor com Semáforos

[![CI Linux](https://github.com/Kayruan/Produtor-Consumidor/actions/workflows/ci.yml/badge.svg)](https://github.com/Kayruan/Produtor-Consumidor/actions/workflows/ci.yml)

Implementação **multithreaded em C** (threads, semáforos e memória compartilhada
limitada), com a camada de **dados e gráficos em Python**.

O badge acima confirma que o projeto compila e roda em **Linux (Ubuntu)** via
GitHub Actions: compilação com `-Wall -Wextra -Werror`, casos de alta
contenção, 10 repetições para descartar deadlock esporádico, e verificação
de condição de corrida e memória com Helgrind/Memcheck (`.github/workflows/ci.yml`).

> **Documentação técnica:** [`docs/Documentacao.pdf`](docs/Documentacao.pdf) —
> sincronização, estrutura do projeto, o código em C, metodologia e resultados.

---

## Início rápido

```bash
python executar.py
```

Menu com todas as opções: execução demonstrativa, estudo de caso completo,
validação rápida, animação visual e geração do PDF.

---

## Estrutura

```
Produtor-Consumidor/
├── executar.py                    ponto de entrada (menu)
├── Makefile                       atalhos de compilação
├── README.md
├── src/
│   └── produtor_consumidor.c      O PROGRAMA DO ENUNCIADO
├── analise/
│   ├── experimento.py             estudo de caso, CSV e gráfico
│   ├── caminhos.py                caminhos do projeto
│   ├── gerar_pdf.py               gera a documentação em PDF
│   ├── demo_visual.py             animação opcional (Tkinter)
│   └── simulador_python.py        núcleo em Python, só para a animação
├── build/
│   └── produtor_consumidor.exe
├── resultados/
│   ├── resultados.csv
│   └── grafico_desempenho.png
└── docs/
    ├── Documentacao.pdf
    ├── documentacao.html
    └── enunciado.jpeg
```

**A divisão é deliberada:** o C faz o problema, o Python faz a medição. As duas
camadas se comunicam por um contrato mínimo — a última linha que o programa em
C imprime:

```
RESULT <tempo_em_segundos> <primos> <nao_primos> <consumidos>
```

O tempo é cronometrado **dentro do C**, para não incluir o custo de o sistema
operacional criar um processo.

---

## Comandos

```bash
# compilar (Linux)
gcc -O2 -Wall -Wextra -o build/produtor_consumidor src/produtor_consumidor.c -pthread

# compilar (Windows, MinGW-w64)
gcc -O2 -Wall -Wextra -static -o build/produtor_consumidor.exe \
    src/produtor_consumidor.c -pthread

# ou, se tiver o make instalado:  make
# (o experimento tambem compila sozinho, entao o make e opcional)

# demonstração: imprime cada número consumido e se é primo
build/produtor_consumidor 8 2 2 20 --verbose

# estudo de caso completo do enunciado (270 execuções)
python analise/experimento.py

# variações
python analise/experimento.py --rapido                    # validação rápida
python analise/experimento.py --M 1000000 --repeticoes 3  # M cem vezes maior
python analise/experimento.py --recompilar

# regerar a documentação em PDF
python analise/gerar_pdf.py
```

**A flag `-static` só é usada no Windows.** Sem ela o executável dependeria da
`libwinpthread-1.dll` e falharia silenciosamente fora do terminal do
compilador. No Linux ela é desnecessária (e pode falhar em sistemas sem a
libc estática instalada), por isso o Makefile e `analise/experimento.py` só a
aplicam quando detectam Windows.

### Argumentos do programa em C

```
produtor_consumidor <N> <Np> <Nc> <M> [--verbose]

  N   tamanho da memória compartilhada (vetor)
  Np  número de threads produtoras
  Nc  número de threads consumidoras
  M   quantidade de números a processar
  --verbose  imprime cada número consumido e se é primo
```

---

## Como o programa funciona

### Memória compartilhada
Um vetor de `N` inteiros. O valor **`0` significa posição livre** — por isso os
números sorteados vão de 1 a 10⁷, nunca 0.

### As três primitivas de sincronização

| Primitiva | Inicia em | Responde à pergunta |
|---|---|---|
| `sem_vagas` (contador) | `N` | Existe posição **livre**? Senão, o produtor dorme. |
| `sem_itens` (contador) | `0` | Existe posição **ocupada**? Senão, o consumidor dorme. |
| `mutex_memoria` | destravado | Posso mexer no vetor **agora**, sozinho? |

Os dois contadores são complementares: `sem_vagas + sem_itens` é sempre `N`.

### A ordem das operações (ponto mais importante)

```
sem_wait(contador) → lock(mutex) → [região crítica] → unlock(mutex) → sem_post(contador oposto)
```

Inverter isso — pegar o mutex antes do semáforo — causa **deadlock**: a thread
dormiria segurando o mutex e ninguém mais conseguiria entrar na região crítica
para liberá-la, inclusive a thread que a acordaria.

### Como o programa termina

Sem critério de parada, as threads ficariam bloqueadas para sempre nos semáforos
ao final. A solução é a **cota**: cada thread reserva uma unidade de trabalho
(`reservar_item`) antes de operar sobre o vetor, e encerra quando a cota de `M`
acaba. Como são reservados exatamente `M` itens de produção e `M` de consumo,
nenhum produtor espera por uma vaga que não vem e nenhum consumidor espera por
um item que não chega.

Isso é verificado automaticamente: cada execução confere que o número de itens
consumidos é exatamente `M`. Nas 270 execuções do estudo, passou em todas.

### Duas decisões que valem explicar

- **Gerador aleatório por thread** (`xorshift64*` em vez de `rand()`): a `rand()`
  tem estado global único e viraria um ponto de serialização artificial,
  falseando justamente o que o experimento quer medir.
- **Primalidade fora da região crítica**: o consumidor copia o número para uma
  variável local, libera a posição, e só então testa se é primo. Assim o
  trabalho caro não prende as outras threads.

---

## Resultados

Medição com M = 10⁴, 10 repetições por combinação, em uma máquina de 4 CPUs
lógicas.

**Melhor combinação: N = 32, (Np, Nc) = (1, 1)** — cerca de 10x mais rápida que
a pior.

1. **O tamanho `N` do buffer é o fator dominante.** De N=2 para N=32 o tempo cai
   cerca de 2,7x. Com N=2 produtor e consumidor ficam em *lock-step*: o vetor
   vive cheio ou vazio, quase toda operação encontra o semáforo em zero e a
   thread dorme. Cada bloqueio é uma chamada ao escalonador — muito mais cara
   que o próprio teste de primalidade.

2. **Mais threads pioraram o desempenho**, dos dois lados. Toda inserção e toda
   retirada passam pelo mesmo mutex: essa região crítica é **serial por
   construção**.

3. **Não há um `M` que reverta isso.** Verificado aumentando M em 100x
   (M = 10⁶, N = 32): o tempo continua crescendo com mais threads — 1,00 s com
   (1,1) contra 2,91 s com (1,8).

### Conclusão

O desempenho é limitado pela **região crítica**, não pelo número de threads —
o teto imposto pela **Lei de Amdahl**.

Na melhor combinação cada número custa menos de 1 microssegundo do início ao
fim, e a maior parte disso é *sincronização, não cálculo*: a esmagadora maioria
dos sorteios entre 1 e 10⁷ é um número composto, descartado já nas primeiras
divisões (só ~6% são primos e chegam a percorrer o laço até a raiz quadrada).

Como o trabalho útil por item é **menor que o custo de sincronizar o acesso a
ele**, nenhuma quantidade de threads compensa. Paralelismo só valeria a pena se
o custo por item crescesse bastante — testando números muito maiores, ou
processando um lote de números a cada entrada na região crítica.

---

## Requisitos

- **GCC com POSIX threads.** No Linux já vem com o pacote `gcc`; no Windows,
  MinGW-w64 na variante *posix*.
- **Python 3** com `pandas` e `matplotlib` (apenas para o experimento).
- **Chrome, Chromium ou Edge** (apenas para regerar o PDF). No Windows
  qualquer instalação já tem um dos dois; no Linux instale `chromium` ou
  `google-chrome` se for regerar a documentação.
