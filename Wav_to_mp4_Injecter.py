"""
WAV Audio Injector for MP4
==========================

Replaces the audio track of an MP4 with a WAV file — video stream is
copied bit-for-bit (no re-encoding), so video quality is preserved 100%.

Audio handling:
  - WAV is uncompressed PCM (already lossless)
  - Script tries 3 audio codecs in order:
      1. PCM copy  — zero re-encoding (not all players support PCM in MP4)
      2. ALAC      — lossless compression, widely supported in MP4/MOV
      3. FLAC      — lossless compression, good open-source support

Usage:
  python wav_inject_mp4.py

Requirements:
  - FFmpeg in system PATH
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import os
import threading


class WavInjector:
    def __init__(self, root):
        self.root = root
        self.root.title("WAV → MP4 Audio Injector (Lossless)")
        self.root.geometry("620x480")
        self.root.resizable(False, False)

        self.mp4_file = None
        self.wav_file = None
        self.is_converting = False

        # ── Header ──
        header = tk.Label(
            root,
            text="WAV Audio Injector",
            font=("Helvetica", 16, "bold"),
        )
        header.pack(pady=(10, 0))

        subheader = tk.Label(
            root,
            text="Replace MP4 audio with WAV — video stream copied losslessly",
            font=("Helvetica", 9),
            fg="gray",
        )
        subheader.pack(pady=(0, 8))

        # ── File Selection ──
        files_frame = tk.LabelFrame(
            root, text="Files", font=("Helvetica", 10, "bold")
        )
        files_frame.pack(fill="x", padx=15, pady=5)

        # MP4 row
        mp4_row = tk.Frame(files_frame)
        mp4_row.pack(fill="x", padx=10, pady=5)

        tk.Label(mp4_row, text="MP4 (video):", font=("Helvetica", 10)).pack(
            side="left"
        )
        self.mp4_var = tk.StringVar(value="(none)")
        self.mp4_entry = tk.Entry(
            mp4_row,
            textvariable=self.mp4_var,
            font=("Helvetica", 10),
            width=45,
            state="readonly",
            fg="gray",
        )
        self.mp4_entry.pack(side="left", padx=5)
        tk.Button(
            mp4_row,
            text="Browse",
            font=("Helvetica", 9),
            command=self.select_mp4,
        ).pack(side="left")

        # WAV row
        wav_row = tk.Frame(files_frame)
        wav_row.pack(fill="x", padx=10, pady=5)

        tk.Label(wav_row, text="WAV (audio):", font=("Helvetica", 10)).pack(
            side="left"
        )
        self.wav_var = tk.StringVar(value="(none)")
        self.wav_entry = tk.Entry(
            wav_row,
            textvariable=self.wav_var,
            font=("Helvetica", 10),
            width=45,
            state="readonly",
            fg="gray",
        )
        self.wav_entry.pack(side="left", padx=5)
        tk.Button(
            wav_row,
            text="Browse",
            font=("Helvetica", 9),
            command=self.select_wav,
        ).pack(side="left")

        # ── Audio Codec Choice ──
        codec_frame = tk.LabelFrame(
            root, text="Audio Codec", font=("Helvetica", 10, "bold")
        )
        codec_frame.pack(fill="x", padx=15, pady=5)

        self.codec_var = tk.StringVar(value="auto")

        codec_options = [
            (
                "auto",
                "Auto (try PCM copy → ALAC → FLAC — best compatibility)",
            ),
            (
                "pcm",
                "PCM (s32le) — zero re-encoding, largest file, some players won't play it",
            ),
            (
                "alac",
                "ALAC — lossless compression, good MP4/MOV/Apple compatibility",
            ),
            (
                "flac",
                "FLAC — lossless compression, good open-source/player compatibility",
            ),
        ]

        for val, label in codec_options:
            tk.Radiobutton(
                codec_frame,
                text=label,
                variable=self.codec_var,
                value=val,
                font=("Helvetica", 9),
                anchor="w",
            ).pack(fill="x", padx=10, pady=1)

        # ── Output ──
        out_frame = tk.LabelFrame(
            root, text="Output", font=("Helvetica", 10, "bold")
        )
        out_frame.pack(fill="x", padx=15, pady=5)

        out_row = tk.Frame(out_frame)
        out_row.pack(fill="x", padx=10, pady=5)

        tk.Label(out_row, text="Save as:", font=("Helvetica", 10)).pack(
            side="left"
        )
        self.out_var = tk.StringVar(value="(auto)")
        self.out_entry = tk.Entry(
            out_row,
            textvariable=self.out_var,
            font=("Helvetica", 10),
            width=42,
            state="readonly",
            fg="gray",
        )
        self.out_entry.pack(side="left", padx=5)
        tk.Button(
            out_row,
            text="Browse",
            font=("Helvetica", 9),
            command=self.browse_output,
        ).pack(side="left")

        # ── Inject Button ──
        self.btn_inject = tk.Button(
            root,
            text="Inject Audio",
            font=("Helvetica", 13, "bold"),
            command=self.start_inject,
            bg="#2196F3",
            fg="white",
            state=tk.DISABLED,
            width=20,
        )
        self.btn_inject.pack(pady=10)

        # ── Status ──
        self.status_var = tk.StringVar()
        self.status_var.set("Select an MP4 and a WAV file to begin.")
        self.lbl_status = tk.Label(
            root, textvariable=self.status_var, font=("Helvetica", 10), wraplength=580
        )
        self.lbl_status.pack(pady=2)

        self.progress_var = tk.StringVar()
        self.lbl_progress = tk.Label(
            root, textvariable=self.progress_var, font=("Helvetica", 9), fg="gray"
        )
        self.lbl_progress.pack(pady=(0, 5))

    # ─────────────────────────────────────────────
    # File Selection
    # ─────────────────────────────────────────────

    def select_mp4(self):
        f = filedialog.askopenfilename(
            title="Select MP4 Video File",
            filetypes=[("MP4 Video Files", "*.mp4"), ("All Files", "*.*")],
        )
        if f:
            self.mp4_file = f
            self.mp4_var.set(f)
            self.mp4_entry.config(fg="black")
            self.auto_output_name()
            self.check_ready()

    def select_wav(self):
        f = filedialog.askopenfilename(
            title="Select WAV Audio File",
            filetypes=[
                ("WAV Audio Files", "*.wav"),
                ("All Audio Files", "*.wav;*.flac;*.mp3;*.ogg;*.aac"),
                ("All Files", "*.*"),
            ],
        )
        if f:
            self.wav_file = f
            self.wav_var.set(f)
            self.wav_entry.config(fg="black")
            self.check_ready()

    def browse_output(self):
        f = filedialog.asksaveasfilename(
            title="Save Output As",
            defaultextension=".mp4",
            filetypes=[("MP4 Video Files", "*.mp4"), ("All Files", "*.*")],
        )
        if f:
            self.out_var.set(f)
            self.out_entry.config(fg="black")

    def auto_output_name(self):
        if self.mp4_file:
            base = os.path.splitext(self.mp4_file)[0]
            self.out_var.set(base + "_newaudio.mp4")
            self.out_entry.config(fg="black")

    def check_ready(self):
        if self.mp4_file and self.wav_file:
            self.btn_inject.config(state=tk.NORMAL)
            self.status_var.set("Ready. Click 'Inject Audio' to combine.")
        else:
            self.btn_inject.config(state=tk.DISABLED)

    # ─────────────────────────────────────────────
    # Injection Logic
    # ─────────────────────────────────────────────

    def start_inject(self):
        if self.is_converting:
            return
        self.is_converting = True
        self.btn_inject.config(state=tk.DISABLED)
        threading.Thread(target=self.run_inject, daemon=True).start()

    def run_inject(self):
        output = self.out_var.get()
        if not output or output == "(auto)":
            self.auto_output_name()
            output = self.out_var.get()

        codec_choice = self.codec_var.get()

        if codec_choice == "auto":
            success = self.try_auto_inject(output)
        else:
            success = self.inject_with_codec(output, codec_choice)

        if success:
            size_mb = os.path.getsize(output) / (1024 * 1024)
            self.status_var.set(f"Done! Output: {os.path.basename(output)} ({size_mb:.1f} MB)")
            self.progress_var.set("")
            messagebox.showinfo(
                "Success",
                f"Audio injected successfully!\n\n"
                f"Output: {output}\n"
                f"Size: {size_mb:.1f} MB\n\n"
                f"Video stream: copied losslessly (zero re-encoding)\n"
                f"Audio stream: encoded losslessly",
            )
        else:
            self.status_var.set("Injection failed. Check console for details.")
            self.progress_var.set("")

        self.is_converting = False
        self.btn_inject.config(state=tk.NORMAL)

    def try_auto_inject(self, output):
        """
        Try audio codecs in order: PCM → ALAC → FLAC
        Returns True on first success.
        """
        codecs = ["pcm", "alac", "flac"]

        for codec in codecs:
            self.status_var.set(f"Trying {codec.upper()} audio codec...")
            if self.inject_with_codec(output, codec):
                return True

        return False

    def inject_with_codec(self, output, codec):
        """
        Build and run the FFmpeg command.

        Key flags:
          -c:v copy     — video stream is copied bit-for-bit, NO re-encoding
          -map 0:v:0    — take video from input 0 (the MP4)
          -map 1:a:0    — take audio from input 1 (the WAV)
          -shortest     — stop at the end of the shorter stream

        This guarantees the video track is 100% identical to the source.
        """
        # Build audio codec args
        if codec == "pcm":
            audio_args = ["-c:a", "pcm_s32le"]
        elif codec == "alac":
            audio_args = ["-c:a", "alac"]
        elif codec == "flac":
            audio_args = ["-c:a", "flac"]
        else:
            return False

        command = [
            "ffmpeg",
            "-y",
            "-i", self.mp4_file,       # input 0: MP4 (video + old audio)
            "-i", self.wav_file,       # input 1: WAV (new audio)
            "-map", "0:v:0",           # use video from MP4
            "-map", "1:a:0",           # use audio from WAV
            "-c:v", "copy",            # copy video — NO re-encoding
            *audio_args,               # encode audio losslessly
            "-shortest",               # match duration to shorter stream
            output,
        ]

        self.progress_var.set(
            f"Injecting {codec.upper()} audio — video copied losslessly..."
        )

        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode == 0:
            return True
        else:
            print(f"FFmpeg error ({codec}):\n{result.stderr}")
            # Clean up failed output file
            if os.path.exists(output):
                os.remove(output)
            return False


if __name__ == "__main__":
    root = tk.Tk()
    app = WavInjector(root)
    root.mainloop()
