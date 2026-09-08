"""Nucleo do produtor-consumidor em Python puro, so para a animacao (demo_visual.py).
A implementacao avaliada e src/produtor_consumidor.c."""

import random
import threading
import time


def is_prime(n):
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def run_simulation(N, Np, Nc, M=10_000, on_event=None, verbose=False, delay=0.0):
    """on_event: callback por producao/consumo, usado pela animacao.
    delay: atraso artificial por operacao, so para deixar a animacao visivel."""
    buffer = [0] * N

    mutex = threading.Semaphore(1)
    empty = threading.Semaphore(N)
    full = threading.Semaphore(0)

    produce_lock = threading.Lock()
    produced_claimed = 0

    consume_lock = threading.Lock()
    consumed_claimed = 0

    stats_lock = threading.Lock()
    primes_found = 0
    non_primes_found = 0

    def claim(lock, get_count, set_count):
        with lock:
            count = get_count()
            if count >= M:
                return False
            set_count(count + 1)
            return True

    def producer(idx):
        nonlocal produced_claimed
        name = f"Produtor-{idx + 1}"
        while True:
            with produce_lock:
                if produced_claimed >= M:
                    break
                produced_claimed += 1

            val = random.randint(1, 10 ** 7)

            empty.acquire()
            with mutex:
                pos = 0
                while buffer[pos] != 0:
                    pos += 1
                buffer[pos] = val
                snapshot = list(buffer)
            full.release()

            if on_event:
                on_event({"type": "produce", "thread": name, "pos": pos,
                           "value": val, "buffer": snapshot})
            if delay:
                time.sleep(delay)

    def consumer(idx):
        nonlocal consumed_claimed, primes_found, non_primes_found
        name = f"Consumidor-{idx + 1}"
        while True:
            with consume_lock:
                if consumed_claimed >= M:
                    break
                consumed_claimed += 1

            full.acquire()
            with mutex:
                pos = 0
                while buffer[pos] == 0:
                    pos += 1
                val = buffer[pos]
                buffer[pos] = 0
                snapshot = list(buffer)
            empty.release()

            prime = is_prime(val)
            with stats_lock:
                if prime:
                    primes_found += 1
                else:
                    non_primes_found += 1

            if verbose:
                print(f"{name}: {val} {'e PRIMO' if prime else 'nao e primo'}")

            if on_event:
                on_event({"type": "consume", "thread": name, "pos": pos,
                           "value": val, "is_prime": prime, "buffer": snapshot})
            if delay:
                time.sleep(delay)

    producers = [threading.Thread(target=producer, args=(i,), daemon=True) for i in range(Np)]
    consumers = [threading.Thread(target=consumer, args=(i,), daemon=True) for i in range(Nc)]

    start_time = time.perf_counter()
    for t in producers + consumers:
        t.start()
    for t in producers + consumers:
        t.join()
    elapsed = time.perf_counter() - start_time

    return {
        "elapsed": elapsed,
        "primes": primes_found,
        "non_primes": non_primes_found,
    }
