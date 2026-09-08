# Makefile do trabalho Produtor-Consumidor com Semaforos.
#
#   make          compila o programa em C
#   make run      compila e roda uma demonstracao curta
#   make estudo   compila e roda o estudo de caso completo do enunciado
#   make doc      (re)gera a documentacao em PDF
#   make clean    remove o executavel compilado

CC      = gcc
CFLAGS  = -O2 -Wall -Wextra
LDFLAGS = -static -pthread

FONTE      = src/produtor_consumidor.c
EXECUTAVEL = build/produtor_consumidor.exe

all: $(EXECUTAVEL)

$(EXECUTAVEL): $(FONTE)
	@mkdir -p build
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

run: $(EXECUTAVEL)
	./$(EXECUTAVEL) 8 2 2 20 --verbose

estudo: $(EXECUTAVEL)
	python analise/experimento.py

doc:
	python analise/gerar_pdf.py

clean:
	rm -f $(EXECUTAVEL)

.PHONY: all run estudo doc clean
