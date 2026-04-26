"""
random_cover_art.py  —  GUI edition
------------------------------------
Crawls a directory (recursively) for MP3 files, picks X of them at random,
extracts their embedded cover art, and saves the images to an output folder.

Requirements:
    pip install mutagen Pillow

Run:
    python random_cover_art.py
"""

import io
import random
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# ── optional deps ─────────────────────────────────────────────────────────────
try:
    from mutagen.id3 import ID3, APIC
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False


# ── core logic ────────────────────────────────────────────────────────────────

def find_mp3s(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.suffix.lower() == ".mp3" and p.is_file()]


def extract_cover(mp3_path: Path):
    """Return (bytes, mime) or None."""
    try:
        tags = ID3(mp3_path)
    except Exception:
        return None
    frames = tags.getall("APIC")
    if not frames:
        return None
    front = next((f for f in frames if f.type == 3), frames[0])
    return front.data, front.mime


def mime_to_ext(mime: str) -> str:
    return {
        "image/jpeg": ".jpg", "image/jpg": ".jpg",
        "image/png":  ".png", "image/gif": ".gif",
        "image/webp": ".webp","image/bmp": ".bmp",
    }.get(mime.lower(), ".img")


def safe_stem(path: Path) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in path.stem)[:80]


# ── palette ───────────────────────────────────────────────────────────────────
BG      = "#1a1a1a"
SURFACE = "#242424"
BORDER  = "#333333"
ACCENT  = "#c8a96e"
ACCENT2 = "#8a6a3a"
TEXT    = "#e8e0d4"
SUBTEXT = "#888880"
SUCCESS = "#6abf69"
WARN    = "#d4a44c"
ERR     = "#d46c6c"
FONT    = ("Segoe UI", 10)
FONT_SM = ("Segoe UI", 9)
FONT_H  = ("Segoe UI Semibold", 11)
MONO    = ("Consolas", 9)


# ── main app ──────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cover Art Picker")
        self.configure(bg=BG)
        self.resizable(False, False)

        self._mp3s: list[Path] = []
        self._previews: list = []   # keep ImageTk refs alive

        self._build_ui()
        self._check_deps()

    # ── dependency banner ─────────────────────────────────────────────────────

    def _check_deps(self):
        missing = []
        if not MUTAGEN_OK:
            missing.append("mutagen")
        if not PIL_OK:
            missing.append("Pillow")
        if missing:
            self._log(f"Missing packages: {', '.join(missing)}  — run: pip install {' '.join(missing)}", "warn")

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # title
        hdr = tk.Frame(self, bg=SURFACE, pady=10)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="🎵  Cover Art Picker", font=("Segoe UI Semibold", 14),
                 bg=SURFACE, fg=ACCENT).pack()
        tk.Label(hdr, text="Extract random album art from your MP3 library",
                 font=FONT_SM, bg=SURFACE, fg=SUBTEXT).pack()
        self._sep(1)

        # options
        opts = tk.Frame(self, bg=BG, padx=14, pady=10)
        opts.grid(row=2, column=0, sticky="ew")
        opts.columnconfigure(1, weight=1)

        self._make_label(opts, "Music folder", 0)
        self.var_src = tk.StringVar()
        src_row = tk.Frame(opts, bg=BG)
        src_row.grid(row=0, column=1, sticky="ew", pady=3)
        src_row.columnconfigure(0, weight=1)
        self._entry(src_row, self.var_src).grid(row=0, column=0, sticky="ew")
        self._btn(src_row, "Browse…", self._pick_src, small=True).grid(row=0, column=1, padx=(6,0))

        self._make_label(opts, "Output folder", 1)
        self.var_dst = tk.StringVar(value=str(Path.home() / "cover_arts"))
        dst_row = tk.Frame(opts, bg=BG)
        dst_row.grid(row=1, column=1, sticky="ew", pady=3)
        dst_row.columnconfigure(0, weight=1)
        self._entry(dst_row, self.var_dst).grid(row=0, column=0, sticky="ew")
        self._btn(dst_row, "Browse…", self._pick_dst, small=True).grid(row=0, column=1, padx=(6,0))

        # count / seed / normalize
        row3 = tk.Frame(opts, bg=BG)
        row3.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8,0))

        tk.Label(row3, text="How many", font=FONT_SM, bg=BG, fg=SUBTEXT).pack(side="left")
        self.var_count = tk.IntVar(value=10)
        tk.Spinbox(row3, from_=1, to=9999, textvariable=self.var_count, width=6,
                   font=FONT, bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                   buttonbackground=SURFACE, relief="flat",
                   highlightbackground=BORDER, highlightthickness=1).pack(side="left", padx=(6,20))

        self.var_use_seed = tk.BooleanVar(value=False)
        tk.Checkbutton(row3, text="Seed", variable=self.var_use_seed,
                       font=FONT_SM, bg=BG, fg=SUBTEXT, activebackground=BG,
                       selectcolor=SURFACE, command=self._toggle_seed).pack(side="left")
        self.var_seed = tk.IntVar(value=42)
        self.seed_entry = tk.Entry(row3, textvariable=self.var_seed, width=7,
                                   font=FONT, bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", highlightbackground=BORDER,
                                   highlightthickness=1, state="disabled",
                                   disabledbackground=BORDER, disabledforeground=SUBTEXT)
        self.seed_entry.pack(side="left", padx=(4,0))

        self.var_normalize = tk.BooleanVar(value=PIL_OK)
        tk.Checkbutton(row3, text="Normalize to PNG", variable=self.var_normalize,
                       font=FONT_SM, bg=BG, fg=SUBTEXT, activebackground=BG,
                       selectcolor=SURFACE).pack(side="left", padx=(20,0))

        self._sep(3)

        # action row
        act = tk.Frame(self, bg=BG, padx=14, pady=8)
        act.grid(row=4, column=0, sticky="ew")
        self.btn_scan = self._btn(act, "🔍  Scan", self._scan)
        self.btn_scan.pack(side="left")
        self.lbl_found = tk.Label(act, text="", font=FONT_SM, bg=BG, fg=SUBTEXT)
        self.lbl_found.pack(side="left", padx=12)
        self.btn_run = self._btn(act, "🎲  Extract", self._run, accent=True)
        self.btn_run.pack(side="right")
        self.btn_run.config(state="disabled")

        self._sep(5)

        # progress
        pf = tk.Frame(self, bg=BG, padx=14, pady=4)
        pf.grid(row=6, column=0, sticky="ew")
        pf.columnconfigure(0, weight=1)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Gold.Horizontal.TProgressbar",
                        troughcolor=SURFACE, background=ACCENT,
                        bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT2)
        self.progress = ttk.Progressbar(pf, style="Gold.Horizontal.TProgressbar",
                                        mode="determinate", length=460)
        self.progress.grid(row=0, column=0, sticky="ew")
        self.lbl_progress = tk.Label(pf, text="", font=FONT_SM, bg=BG, fg=SUBTEXT)
        self.lbl_progress.grid(row=1, column=0, sticky="w", pady=(2,0))

        self._sep(7)

        # log
        lf = tk.Frame(self, bg=BG, padx=14, pady=8)
        lf.grid(row=8, column=0, sticky="nsew")
        lf.columnconfigure(0, weight=1)
        tk.Label(lf, text="Log", font=FONT_H, bg=BG, fg=SUBTEXT).grid(
            row=0, column=0, sticky="w", pady=(0,4))
        self.log_box = tk.Text(lf, width=64, height=10, font=MONO,
                               bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                               relief="flat", highlightbackground=BORDER,
                               highlightthickness=1, state="disabled", wrap="word")
        self.log_box.grid(row=1, column=0, sticky="ew")
        scr = tk.Scrollbar(lf, command=self.log_box.yview, bg=SURFACE,
                           troughcolor=BG, relief="flat")
        scr.grid(row=1, column=1, sticky="ns", padx=(2,0))
        self.log_box.config(yscrollcommand=scr.set)
        self.log_box.tag_config("ok",   foreground=SUCCESS)
        self.log_box.tag_config("warn", foreground=WARN)
        self.log_box.tag_config("err",  foreground=ERR)
        self.log_box.tag_config("info", foreground=ACCENT)

        self._sep(9)

        # preview strip
        po = tk.Frame(self, bg=BG, padx=14, pady=8)
        po.grid(row=10, column=0, sticky="ew")
        tk.Label(po, text="Preview", font=FONT_H, bg=BG, fg=SUBTEXT).pack(anchor="w")
        cf = tk.Frame(po, bg=BG)
        cf.pack(fill="x")
        self.prev_canvas = tk.Canvas(cf, bg=SURFACE, height=90,
                                     highlightthickness=1, highlightbackground=BORDER)
        self.prev_canvas.pack(side="left", fill="x", expand=True)
        hscr = tk.Scrollbar(cf, orient="horizontal", command=self.prev_canvas.xview,
                            bg=SURFACE, troughcolor=BG, relief="flat")
        hscr.pack(side="bottom", fill="x")
        self.prev_canvas.configure(xscrollcommand=hscr.set)
        self.prev_inner = tk.Frame(self.prev_canvas, bg=SURFACE)
        self.prev_canvas.create_window((0,0), window=self.prev_inner, anchor="nw")
        self.prev_inner.bind("<Configure>",
            lambda e: self.prev_canvas.configure(
                scrollregion=self.prev_canvas.bbox("all")))

        # footer
        foot = tk.Frame(self, bg=BG, padx=14, pady=10)
        foot.grid(row=11, column=0, sticky="ew")
        self.btn_open = self._btn(foot, "📂  Open Output Folder", self._open_output, small=True)
        self.btn_open.pack(side="right")
        self.btn_open.config(state="disabled")

    # ── widget helpers ────────────────────────────────────────────────────────

    def _sep(self, row):
        tk.Frame(self, bg=BORDER, height=1).grid(row=row, column=0, sticky="ew")

    def _make_label(self, parent, text, row):
        tk.Label(parent, text=text, font=FONT_SM, bg=BG, fg=SUBTEXT,
                 width=14, anchor="w").grid(row=row, column=0, sticky="w", pady=3)

    def _entry(self, parent, var):
        return tk.Entry(parent, textvariable=var, font=FONT,
                        bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                        relief="flat", highlightbackground=BORDER, highlightthickness=1)

    def _btn(self, parent, text, cmd, accent=False, small=False):
        bg = ACCENT if accent else SURFACE
        fg = "#1a1200" if accent else TEXT
        b  = tk.Button(parent, text=text, command=cmd,
                       font=FONT_SM if small else FONT,
                       bg=bg, fg=fg, activebackground=ACCENT2,
                       activeforeground=TEXT, relief="flat",
                       padx=10, pady=4, cursor="hand2",
                       highlightthickness=0)
        b.bind("<Enter>", lambda e: b.config(bg=ACCENT2))
        b.bind("<Leave>", lambda e: b.config(bg=bg))
        return b

    # ── events ────────────────────────────────────────────────────────────────

    def _toggle_seed(self):
        self.seed_entry.config(state="normal" if self.var_use_seed.get() else "disabled")

    def _pick_src(self):
        d = filedialog.askdirectory(title="Select Music Folder")
        if d:
            self.var_src.set(d)
            self._mp3s.clear()
            self.lbl_found.config(text="")
            self.btn_run.config(state="disabled")

    def _pick_dst(self):
        d = filedialog.askdirectory(title="Select Output Folder")
        if d:
            self.var_dst.set(d)

    def _open_output(self):
        import os, subprocess
        path = self.var_dst.get()
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    # ── scan ──────────────────────────────────────────────────────────────────

    def _scan(self):
        src = self.var_src.get().strip()
        if not src:
            messagebox.showerror("No folder", "Please select a music folder first.")
            return
        root = Path(src)
        if not root.is_dir():
            messagebox.showerror("Invalid folder", f"Not a directory:\n{src}")
            return
        self.btn_scan.config(state="disabled", text="Scanning…")
        self._log("Scanning for MP3 files…", "info")

        def task():
            mp3s = find_mp3s(root)
            self._mp3s = mp3s
            self.after(0, lambda: self._scan_done(len(mp3s)))

        threading.Thread(target=task, daemon=True).start()

    def _scan_done(self, count):
        self.btn_scan.config(state="normal", text="🔍  Scan")
        if count == 0:
            self._log("No MP3 files found.", "warn")
            self.lbl_found.config(text="No MP3s found", fg=ERR)
            self.btn_run.config(state="disabled")
        else:
            self._log(f"Found {count} MP3 file(s).", "ok")
            self.lbl_found.config(text=f"{count} MP3s found", fg=SUCCESS)
            self.btn_run.config(state="normal")

    # ── extract ───────────────────────────────────────────────────────────────

    def _run(self):
        if not MUTAGEN_OK:
            messagebox.showerror("Missing dependency", "mutagen is not installed.\n\npip install mutagen")
            return
        if not self._mp3s:
            messagebox.showinfo("Scan first", "Please scan a folder first.")
            return

        dst       = Path(self.var_dst.get().strip())
        count     = min(self.var_count.get(), len(self._mp3s))
        seed      = self.var_seed.get() if self.var_use_seed.get() else None
        normalize = self.var_normalize.get() and PIL_OK

        chosen = random.Random(seed).sample(self._mp3s, count)
        dst.mkdir(parents=True, exist_ok=True)

        for w in self.prev_inner.winfo_children():
            w.destroy()
        self._previews.clear()

        self.progress["maximum"] = count
        self.progress["value"]   = 0
        self.btn_run.config(state="disabled")
        self.btn_open.config(state="disabled")
        self._log(f"Extracting {count} cover(s)…", "info")

        def task():
            saved, skipped = 0, 0
            thumbs = []

            for i, mp3 in enumerate(chosen, 1):
                result = extract_cover(mp3)
                if result is None:
                    self.after(0, lambda n=mp3.name: self._log(f"  ⚠  No art: {n}", "warn"))
                    skipped += 1
                else:
                    data, mime = result
                    ext  = mime_to_ext(mime)
                    stem = safe_stem(mp3)
                    out  = dst / f"{stem}{ext}"
                    ctr  = 1
                    while out.exists():
                        out = dst / f"{stem}_{ctr}{ext}"
                        ctr += 1

                    if normalize:
                        try:
                            img = Image.open(io.BytesIO(data))
                            out = out.with_suffix(".png")
                            img.save(out, "PNG")
                        except Exception:
                            out.write_bytes(data)
                    else:
                        out.write_bytes(data)

                    saved += 1
                    thumbs.append(data)
                    self.after(0, lambda n=mp3.name, o=out.name:
                               self._log(f"  ✅  {n}  →  {o}", "ok"))

                self.after(0, lambda v=i: self._set_progress(v, count))

            self.after(0, lambda: self._run_done(saved, skipped, thumbs))

        threading.Thread(target=task, daemon=True).start()

    def _set_progress(self, value, total):
        self.progress["value"] = value
        self.lbl_progress.config(text=f"{value} / {total}")

    def _run_done(self, saved, skipped, thumbs):
        self.btn_run.config(state="normal")
        self.btn_open.config(state="normal")
        self._log(f"Done — {saved} saved, {skipped} skipped.", "info")
        if PIL_OK:
            for data in thumbs:
                self._add_thumb(data)

    # ── preview ───────────────────────────────────────────────────────────────

    def _add_thumb(self, data: bytes):
        try:
            img = Image.open(io.BytesIO(data))
            img.thumbnail((80, 80))
            photo = ImageTk.PhotoImage(img)
            self._previews.append(photo)
            tk.Label(self.prev_inner, image=photo, bg=SURFACE,
                     highlightthickness=1, highlightbackground=BORDER).pack(
                     side="left", padx=3, pady=5)
        except Exception:
            pass

    # ── log ───────────────────────────────────────────────────────────────────

    def _log(self, msg: str, tag: str = ""):
        self.log_box.config(state="normal")
        self.log_box.insert("end", msg + "\n", tag)
        self.log_box.see("end")
        self.log_box.config(state="disabled")


if __name__ == "__main__":
    App().mainloop()
