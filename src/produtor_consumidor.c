/*
 * Produtor-Consumidor com semaforos e memoria compartilhada limitada.
 *
 * Uso: produtor_consumidor.exe <N> <Np> <Nc> <M> [--verbose]
 *   N  tamanho do vetor compartilhado (0 = posicao livre)
 *   Np threads produtoras
 *   Nc threads consumidoras
 *   M  quantidade de numeros a processar
 *
 * Ultima linha impressa (lida por analise/experimento.py):
 *   RESULT <tempo_em_segundos> <primos> <nao_primos> <consumidos>
 *
 * Compilar: gcc -O2 -Wall -Wextra -static -o build/produtor_consumidor.exe
 *           src/produtor_consumidor.c -pthread
 */

#define _POSIX_C_SOURCE 200809L

#include <pthread.h>
#include <semaphore.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef _WIN32
#include <windows.h>
#endif

#define VALOR_MAXIMO 10000000
#define POSICAO_LIVRE 0

typedef struct {
    int *memoria;
    int  tamanho;

    sem_t sem_vagas;                 /* posicoes livres   (inicia em N) */
    sem_t sem_itens;                 /* posicoes ocupadas (inicia em 0) */
    pthread_mutex_t mutex_memoria;

    int total_itens;                 /* M */
    int reservados_producao;
    int reservados_consumo;
    pthread_mutex_t mutex_cota;

    long primos;
    long nao_primos;
    pthread_mutex_t mutex_estatisticas;

    int verboso;
    pthread_mutex_t mutex_saida;
} MemoriaCompartilhada;

typedef struct {
    MemoriaCompartilhada *mc;
    int      id;
    uint64_t semente;
} ArgumentosThread;


static double agora_em_segundos(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec + (double)t.tv_nsec / 1e9;
}

/* xorshift64*, estado por thread: rand() serializaria as threads. */
static uint32_t proximo_aleatorio(uint64_t *estado)
{
    uint64_t x = *estado;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    *estado = x;
    return (uint32_t)((x * 0x2545F4914F6CDD1DULL) >> 32);
}

static int gerar_numero(uint64_t *estado)
{
    return 1 + (int)(proximo_aleatorio(estado) % VALOR_MAXIMO);
}

/* Divisao por tentativa ate raiz(valor), pulando multiplos de 2 e 3. */
static int eh_primo(int valor)
{
    if (valor <= 1) return 0;
    if (valor <= 3) return 1;
    if (valor % 2 == 0 || valor % 3 == 0) return 0;
    for (long long d = 5; d * d <= (long long)valor; d += 6) {
        if (valor % d == 0 || valor % (d + 2) == 0) return 0;
    }
    return 1;
}


/* So podem ser chamadas com mutex_memoria travado; os semaforos contadores
 * garantem que a posicao procurada sempre existe. */
static int buscar_posicao_livre(const MemoriaCompartilhada *mc)
{
    for (int i = 0; i < mc->tamanho; i++) {
        if (mc->memoria[i] == POSICAO_LIVRE) return i;
    }
    return -1;
}

static int buscar_posicao_ocupada(const MemoriaCompartilhada *mc)
{
    for (int i = 0; i < mc->tamanho; i++) {
        if (mc->memoria[i] != POSICAO_LIVRE) return i;
    }
    return -1;
}

/* Reserva uma unidade de trabalho da cota M. Garante que o programa
 * termina: nenhuma thread fica esperando por algo que nunca vai chegar. */
static int reservar_item(MemoriaCompartilhada *mc, int *contador)
{
    int obteve = 0;
    pthread_mutex_lock(&mc->mutex_cota);
    if (*contador < mc->total_itens) {
        (*contador)++;
        obteve = 1;
    }
    pthread_mutex_unlock(&mc->mutex_cota);
    return obteve;
}


static void *rotina_produtor(void *argumento)
{
    ArgumentosThread     *args = (ArgumentosThread *)argumento;
    MemoriaCompartilhada *mc   = args->mc;

    while (reservar_item(mc, &mc->reservados_producao)) {
        int valor = gerar_numero(&args->semente);

        sem_wait(&mc->sem_vagas);          /* dorme se o vetor estiver cheio */

        pthread_mutex_lock(&mc->mutex_memoria);
        int posicao = buscar_posicao_livre(mc);
        mc->memoria[posicao] = valor;
        pthread_mutex_unlock(&mc->mutex_memoria);

        if (mc->verboso) {
            pthread_mutex_lock(&mc->mutex_saida);
            printf("[Produtor %2d] produziu %8d -> posicao %d\n", args->id, valor, posicao);
            pthread_mutex_unlock(&mc->mutex_saida);
        }

        sem_post(&mc->sem_itens);
    }
    return NULL;
}

static void *rotina_consumidor(void *argumento)
{
    ArgumentosThread     *args = (ArgumentosThread *)argumento;
    MemoriaCompartilhada *mc   = args->mc;

    while (reservar_item(mc, &mc->reservados_consumo)) {
        sem_wait(&mc->sem_itens);          /* dorme se o vetor estiver vazio */

        pthread_mutex_lock(&mc->mutex_memoria);
        int posicao = buscar_posicao_ocupada(mc);
        int valor   = mc->memoria[posicao];
        mc->memoria[posicao] = POSICAO_LIVRE;
        pthread_mutex_unlock(&mc->mutex_memoria);

        sem_post(&mc->sem_vagas);

        /* Primalidade fora da regiao critica: e o trabalho caro, e nao
         * pode prender as demais threads. */
        int primo = eh_primo(valor);

        pthread_mutex_lock(&mc->mutex_estatisticas);
        if (primo) mc->primos++; else mc->nao_primos++;
        pthread_mutex_unlock(&mc->mutex_estatisticas);

        if (mc->verboso) {
            pthread_mutex_lock(&mc->mutex_saida);
            printf("[Consumidor %2d] consumiu %8d da posicao %d -> %s\n",
                   args->id, valor, posicao, primo ? "PRIMO" : "nao e primo");
            pthread_mutex_unlock(&mc->mutex_saida);
        }
    }
    return NULL;
}


static int inicializar(MemoriaCompartilhada *mc, int N, int M, int verboso)
{
    memset(mc, 0, sizeof(*mc));
    mc->tamanho = N;
    mc->total_itens = M;
    mc->verboso = verboso;

    mc->memoria = calloc((size_t)N, sizeof(int));
    if (mc->memoria == NULL) {
        perror("calloc");
        return 0;
    }

    sem_init(&mc->sem_vagas, 0, (unsigned int)N);
    sem_init(&mc->sem_itens, 0, 0);
    pthread_mutex_init(&mc->mutex_memoria, NULL);
    pthread_mutex_init(&mc->mutex_cota, NULL);
    pthread_mutex_init(&mc->mutex_estatisticas, NULL);
    pthread_mutex_init(&mc->mutex_saida, NULL);
    return 1;
}

static void finalizar(MemoriaCompartilhada *mc)
{
    sem_destroy(&mc->sem_vagas);
    sem_destroy(&mc->sem_itens);
    pthread_mutex_destroy(&mc->mutex_memoria);
    pthread_mutex_destroy(&mc->mutex_cota);
    pthread_mutex_destroy(&mc->mutex_estatisticas);
    pthread_mutex_destroy(&mc->mutex_saida);
    free(mc->memoria);
}

static void mostrar_uso(const char *programa)
{
    fprintf(stderr,
            "Uso: %s <N> <Np> <Nc> <M> [--verbose]\n"
            "  N   tamanho da memoria compartilhada (vetor)\n"
            "  Np  numero de threads produtoras\n"
            "  Nc  numero de threads consumidoras\n"
            "  M   quantidade de numeros a processar\n"
            "  --verbose  imprime cada numero consumido e se e primo\n"
            "\nExemplo: %s 8 2 4 20 --verbose\n",
            programa, programa);
}


int main(int argc, char **argv)
{
#ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
#endif

    if (argc < 5 || argc > 6) {
        mostrar_uso(argv[0]);
        return EXIT_FAILURE;
    }

    int N       = atoi(argv[1]);
    int Np      = atoi(argv[2]);
    int Nc      = atoi(argv[3]);
    int M       = atoi(argv[4]);
    int verboso = (argc == 6 && strcmp(argv[5], "--verbose") == 0);

    if (N <= 0 || Np <= 0 || Nc <= 0 || M <= 0) {
        fprintf(stderr, "Erro: N, Np, Nc e M devem ser inteiros positivos.\n");
        mostrar_uso(argv[0]);
        return EXIT_FAILURE;
    }

    MemoriaCompartilhada mc;
    if (!inicializar(&mc, N, M, verboso)) {
        return EXIT_FAILURE;
    }

    pthread_t        *produtores   = calloc((size_t)Np, sizeof(pthread_t));
    pthread_t        *consumidores = calloc((size_t)Nc, sizeof(pthread_t));
    ArgumentosThread *args_prod    = calloc((size_t)Np, sizeof(ArgumentosThread));
    ArgumentosThread *args_cons    = calloc((size_t)Nc, sizeof(ArgumentosThread));

    if (!produtores || !consumidores || !args_prod || !args_cons) {
        perror("calloc");
        free(produtores); free(consumidores); free(args_prod); free(args_cons);
        finalizar(&mc);
        return EXIT_FAILURE;
    }

    if (verboso) {
        printf("=== Produtor-Consumidor com Semaforos ===\n");
        printf("N=%d  Np=%d  Nc=%d  M=%d\n\n", N, Np, Nc, M);
    }

    uint64_t semente_base = (uint64_t)time(NULL) ^ ((uint64_t)clock() << 16);

    double inicio = agora_em_segundos();

    for (int i = 0; i < Np; i++) {
        args_prod[i].mc = &mc;
        args_prod[i].id = i + 1;
        args_prod[i].semente = semente_base + 0x9E3779B97F4A7C15ULL * (uint64_t)(i + 1);
        pthread_create(&produtores[i], NULL, rotina_produtor, &args_prod[i]);
    }
    for (int i = 0; i < Nc; i++) {
        args_cons[i].mc = &mc;
        args_cons[i].id = i + 1;
        args_cons[i].semente = semente_base + 0x9E3779B97F4A7C15ULL * (uint64_t)(Np + i + 1);
        pthread_create(&consumidores[i], NULL, rotina_consumidor, &args_cons[i]);
    }

    for (int i = 0; i < Np; i++) pthread_join(produtores[i], NULL);
    for (int i = 0; i < Nc; i++) pthread_join(consumidores[i], NULL);

    double tempo_total = agora_em_segundos() - inicio;

    if (verboso) {
        printf("\n--- Resumo ---\n");
        printf("Numeros processados : %ld\n", mc.primos + mc.nao_primos);
        printf("Primos              : %ld\n", mc.primos);
        printf("Nao primos          : %ld\n", mc.nao_primos);
        printf("Tempo de execucao   : %.6f s\n\n", tempo_total);
    }

    printf("RESULT %.9f %ld %ld %ld\n",
           tempo_total, mc.primos, mc.nao_primos, mc.primos + mc.nao_primos);

    free(produtores);
    free(consumidores);
    free(args_prod);
    free(args_cons);
    finalizar(&mc);
    return EXIT_SUCCESS;
}
