"""Animacao Tkinter do buffer: slots do vetor, estatisticas ao vivo e log de eventos.
A simulacao roda em background (simulador_python.run_simulation); a janela so
consome eventos de uma fila thread-safe."""

import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

from simulador_python import run_simulation

SLOT_EMPTY = "#3a3f4b"
SLOT_FILLED = "#4C6EF5"
FLASH_PRODUCE = "#2F9E44"
FLASH_CONSUME_PRIME = "#F76707"
FLASH_CONSUME_COMPOSITE = "#868E96"
BG = "#1e1f26"
FG = "#e9ecef"


class DemoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Produtor-Consumidor - Demo Visual")
        self.root.configure(bg=BG)

        self.event_queue = queue.Queue()
        self.worker = None
        self.running = False
        self.start_time = None

        self.produced = 0
        self.consumed = 0
        self.primes = 0
        self.non_primes = 0

        self._build_controls()
        self._build_canvas()
        self._build_dashboard()
        self._build_log()

        self.root.after(30, self._poll_events)

    # ---------- UI construction ----------

    def _build_controls(self):
        frame = tk.Frame(self.root, bg=BG, padx=10, pady=10)
        frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.n_var = tk.IntVar(value=16)
        self.np_var = tk.IntVar(value=2)
        self.nc_var = tk.IntVar(value=2)
        self.m_var = tk.IntVar(value=300)
        self.speed_var = tk.DoubleVar(value=0.15)

        def labeled_spin(label, var, frm, to):
            tk.Label(frame, text=label, bg=BG, fg=FG).pack(side="left", padx=(0, 4))
            spin = tk.Spinbox(frame, from_=frm, to=to, textvariable=var, width=5)
            spin.pack(side="left", padx=(0, 12))
            return spin

        labeled_spin("N (buffer)", self.n_var, 2, 64)
        labeled_spin("Np", self.np_var, 1, 16)
        labeled_spin("Nc", self.nc_var, 1, 16)
        labeled_spin("M (itens)", self.m_var, 10, 5000)

        tk.Label(frame, text="Velocidade (delay/op)", bg=BG, fg=FG).pack(side="left", padx=(0, 4))
        tk.Scale(frame, from_=0.0, to=0.5, resolution=0.01, orient="horizontal",
                  variable=self.speed_var, length=120, bg=BG, fg=FG,
                  troughcolor="#2b2d36", highlightthickness=0).pack(side="left", padx=(0, 12))

        self.start_btn = tk.Button(frame, text="Iniciar", command=self.start, bg="#4C6EF5", fg="white")
        self.start_btn.pack(side="left", padx=4)

        self.status_lbl = tk.Label(frame, text="Pronto", bg=BG, fg=FG)
        self.status_lbl.pack(side="left", padx=12)

    def _build_canvas(self):
        self.canvas_frame = tk.Frame(self.root, bg=BG, padx=10)
        self.canvas_frame.grid(row=1, column=0, sticky="nsew")
        self.canvas = tk.Canvas(self.canvas_frame, width=560, height=320, bg=BG, highlightthickness=0)
        self.canvas.pack()
        self.slot_rects = []
        self.slot_texts = []

    def _draw_slots(self, n):
        self.canvas.delete("all")
        self.slot_rects = []
        self.slot_texts = []
        cols = min(8, n)
        rows = (n + cols - 1) // cols
        size = min(60, 540 // cols)
        pad = 6
        for i in range(n):
            r, c = divmod(i, cols)
            x0 = pad + c * (size + pad)
            y0 = pad + r * (size + pad)
            rect = self.canvas.create_rectangle(x0, y0, x0 + size, y0 + size,
                                                  fill=SLOT_EMPTY, outline="#555", width=1)
            text = self.canvas.create_text(x0 + size / 2, y0 + size / 2, text="", fill=FG, font=("Consolas", 8))
            self.slot_rects.append(rect)
            self.slot_texts.append(text)
        self.canvas.config(height=pad + rows * (size + pad))

    def _build_dashboard(self):
        frame = tk.Frame(self.root, bg=BG, padx=10, pady=10)
        frame.grid(row=1, column=1, sticky="n")

        self.stat_vars = {
            "produced": tk.StringVar(value="Produzidos: 0"),
            "consumed": tk.StringVar(value="Consumidos: 0"),
            "primes": tk.StringVar(value="Primos: 0"),
            "non_primes": tk.StringVar(value="Nao-primos: 0"),
            "elapsed": tk.StringVar(value="Tempo: 0.00s"),
            "rate": tk.StringVar(value="Vazao: 0.0 itens/s"),
        }
        tk.Label(frame, text="Estatisticas", bg=BG, fg=FG, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        for key in self.stat_vars:
            tk.Label(frame, textvariable=self.stat_vars[key], bg=BG, fg=FG,
                     font=("Consolas", 10)).pack(anchor="w", pady=2)

        self.progress = ttk.Progressbar(frame, length=220, mode="determinate")
        self.progress.pack(pady=(8, 0))

    def _build_log(self):
        frame = tk.Frame(self.root, bg=BG, padx=10)
        frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        tk.Label(frame, text="Log", bg=BG, fg=FG).pack(anchor="w")
        self.log_text = tk.Text(frame, height=8, width=90, bg="#111319", fg=FG,
                                  font=("Consolas", 9), state="disabled")
        self.log_text.pack()

    # ---------- simulation control ----------

    def start(self):
        if self.running:
            return
        N, Np, Nc, M = self.n_var.get(), self.np_var.get(), self.nc_var.get(), self.m_var.get()
        delay = self.speed_var.get()

        self._draw_slots(N)
        self.produced = self.consumed = self.primes = self.non_primes = 0
        self.progress.config(maximum=M, value=0)
        self._log_clear()
        self.status_lbl.config(text=f"Rodando N={N} Np={Np} Nc={Nc} M={M}...")
        self.start_btn.config(state="disabled")
        self.running = True
        self.start_time = time.perf_counter()

        def on_event(ev):
            self.event_queue.put(ev)

        def worker():
            result = run_simulation(N=N, Np=Np, Nc=Nc, M=M, on_event=on_event, delay=delay)
            self.event_queue.put({"type": "done", "elapsed": result["elapsed"],
                                    "primes": result["primes"], "non_primes": result["non_primes"]})

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    # ---------- event polling (runs on the Tk main thread) ----------

    def _poll_events(self):
        try:
            while True:
                ev = self.event_queue.get_nowait()
                self._handle_event(ev)
        except queue.Empty:
            pass
        if self.running and self.start_time is not None:
            elapsed = time.perf_counter() - self.start_time
            rate = self.consumed / elapsed if elapsed > 0 else 0.0
            self.stat_vars["elapsed"].set(f"Tempo: {elapsed:.2f}s")
            self.stat_vars["rate"].set(f"Vazao: {rate:.1f} itens/s")
        self.root.after(30, self._poll_events)

    def _handle_event(self, ev):
        if ev["type"] == "produce":
            self.produced += 1
            self._flash(ev["pos"], FLASH_PRODUCE, str(ev["value"])[-4:])
            self.stat_vars["produced"].set(f"Produzidos: {self.produced}")
            self._log(f"{ev['thread']} escreveu {ev['value']} na posicao {ev['pos']}")
        elif ev["type"] == "consume":
            self.consumed += 1
            if ev["is_prime"]:
                self.primes += 1
            else:
                self.non_primes += 1
            color = FLASH_CONSUME_PRIME if ev["is_prime"] else FLASH_CONSUME_COMPOSITE
            self._flash(ev["pos"], color, "")
            self.stat_vars["consumed"].set(f"Consumidos: {self.consumed}")
            self.stat_vars["primes"].set(f"Primos: {self.primes}")
            self.stat_vars["non_primes"].set(f"Nao-primos: {self.non_primes}")
            self.progress.config(value=self.consumed)
            tag = "PRIMO" if ev["is_prime"] else "nao-primo"
            self._log(f"{ev['thread']} leu {ev['value']} ({tag}) da posicao {ev['pos']}")
        elif ev["type"] == "done":
            self.running = False
            self.start_btn.config(state="normal")
            self.status_lbl.config(text=f"Concluido em {ev['elapsed']:.2f}s")
            self._log(f"--- Simulacao concluida em {ev['elapsed']:.2f}s "
                       f"({ev['primes']} primos, {ev['non_primes']} nao-primos) ---")

    def _flash(self, pos, color, label):
        rect = self.slot_rects[pos]
        text = self.slot_texts[pos]
        self.canvas.itemconfig(rect, fill=color)
        self.canvas.itemconfig(text, text=label)

        def revert():
            still_filled = label != ""
            self.canvas.itemconfig(rect, fill=SLOT_FILLED if still_filled else SLOT_EMPTY)
            if not still_filled:
                self.canvas.itemconfig(text, text="")
        self.root.after(180, revert)

    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _log_clear(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")


def main():
    root = tk.Tk()
    app = DemoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
