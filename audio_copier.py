"""
Audio Copier — Copy audio track from one file to another
=========================================================

Takes the audio stream from File A and the video stream from File B,
and merges them into a new output file. Both streams are copied
bit-for-bit (no re-encoding = zero quality loss).

If the audio codec isn't compatible with the output container, it
automatically falls back to lossless or high-quality re-encoding.

Usage:
  python audio_copier.py

Requirements:
  - FFmpeg in system PATH
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import os
import threading


class AudioCopier:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Copier")
        self.root.geometry("640x500")
        self.root.resizable(False, False)

        self.source_file = None   # file to take AUDIO from
        self.target_file = None   # file to take VIDEO from
        self.is_converting = False

        # ── Header ──
        header = tk.Label(
            root,
            text="Audio Copier",
            font=("Helvetica", 18, "bold"),
        )
        header.pack(pady=(10, 0))

        subheader = tk.Label(
            root,
            text="Copy audio from one file into another — both streams copied losslessly",
            font=("Helvetica", 9),
            fg="gray",
        )
        subheader.pack(pady=(0, 8))

        # ── Source (Audio) ──
        src_frame = tk.LabelFrame(
            root,
            text="Audio Source  (take audio FROM this file)",
            font=("Helvetica", 10, "bold"),
        )
        src_frame.pack(fill="x", padx=15, pady=5)

        src_row = tk.Frame(src_frame)
        src_row.pack(fill="x", padx=10, pady=8)

        self.src_var = tk.StringVar(value="No file selected")
        self.src_entry = tk.Entry(
            src_row,
            textvariable=self.src_var,
            font=("Helvetica", 10),
            width=55,
            state="readonly",
            fg="gray",
        )
        self.src_entry.pack(side="left", padx=(0, 5))
        tk.Button(
            src_row,
            text="Browse",
            font=("Helvetica", 9),
            command=self.select_source,
            width=8,
        ).pack(side="left")

        # ── Target (Video) ──
        tgt_frame = tk.LabelFrame(
            root,
            text="Video Source  (take video FROM this file)",
            font=("Helvetica", 10, "bold"),
        )
        tgt_frame.pack(fill="x", padx=15, pady=5)

        tgt_row = tk.Frame(tgt_frame)
        tgt_row.pack(fill="x", padx=10, pady=8)

        self.tgt_var = tk.StringVar(value="No file selected")
        self.tgt_entry = tk.Entry(
            tgt_row,
            textvariable=self.tgt_var,
            font=("Helvetica", 10),
            width=55,
            state="readonly",
            fg="gray",
        )
        self.tgt_entry.pack(side="left", padx=(0, 5))
        tk.Button(
            tgt_row,
            text="Browse",
            font=("Helvetica", 9),
            command=self.select_target,
            width=8,
        ).pack(side="left")

        # ── Swap Button ──
        tk.Button(
            root,
            text="⇄  Swap Files",
            font=("Helvetica", 9),
            command=self.swap_files,
        ).pack(pady=3)

        # ── Options ──
        opt_frame = tk.LabelFrame(
            root,
            text="Options",
            font=("Helvetica", 10, "bold"),
        )
        opt_frame.pack(fill="x", padx=15, pady=5)

        # Duration handling
        dur_row = tk.Frame(opt_frame)
        dur_row.pack(fill="x", padx=10, pady=3)

        tk.Label(dur_row, text="Duration:", font=("Helvetica", 10)).pack(side="left")
        self.dur_var = tk.StringVar(value="shortest")
        dur_options = [
            ("shortest", "End at shorter stream"),
            ("longest", "Pad/loop shorter stream"),
            ("neither", "Keep original lengths (may desync)"),
        ]
        for val, label in dur_options:
            tk.Radiobutton(
                dur_row,
                text=label,
                variable=self.dur_var,
                value=val,
                font=("Helvetica", 9),
            ).pack(side="left", padx=8)

        # ── Output ──
        out_frame = tk.LabelFrame(
            root,
            text="Output",
            font=("Helvetica", 10, "bold"),
        )
        out_frame.pack(fill="x", padx=15, pady=5)

        out_row = tk.Frame(out_frame)
        out_row.pack(fill="x", padx=10, pady=8)

        tk.Label(out_row, text="Save as:", font=("Helvetica", 10)).pack(side="left")
        self.out_var = tk.StringVar(value="(auto)")
        self.out_entry = tk.Entry(
            out_row,
            textvariable=self.out_var,
            font=("Helvetica", 10),
            width=48,
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

        # ── Copy Button ──
        self.btn_copy = tk.Button(
            root,
            text="Copy Audio",
            font=("Helvetica", 14, "bold"),
            command=self.start_copy,
            bg="#2196F3",
            fg="white",
            state=tk.DISABLED,
            width=18,
            height=1,
        )
        self.btn_copy.pack(pady=10)

        # ── Status ──
        self.status_var = tk.StringVar()
        self.status_var.set("Select an audio source and a video source to begin.")
        self.lbl_status = tk.Label(
            root, textvariable=self.status_var, font=("Helvetica", 10), wraplength=600
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

    def select_source(self):
        f = filedialog.askopenfilename(
            title="Select Audio Source (take audio FROM this file)",
            filetypes=[
                ("Video & Audio Files", "*.mp4;*.mkv;*.avi;*.mov;*.bik;*.webm;*.mp3;*.wav;*.flac;*.aac;*.ogg;*.m4a"),
                ("Video Files", "*.mp4;*.mkv;*.avi;*.mov;*.bik;*.webm"),
                ("Audio Files", "*.mp3;*.wav;*.flac;*.aac;*.ogg;*.m4a"),
                ("All Files", "*.*"),
            ],
        )
        if f:
            self.source_file = f
            self.src_var.set(f)
            self.src_entry.config(fg="black")
            self.auto_output_name()
            self.check_ready()

    def select_target(self):
        f = filedialog.askopenfilename(
            title="Select Video Source (take video FROM this file)",
            filetypes=[
                ("Video Files", "*.mp4;*.mkv;*.avi;*.mov;*.bik;*.webm"),
                ("All Files", "*.*"),
            ],
        )
        if f:
            self.target_file = f
            self.tgt_var.set(f)
            self.tgt_entry.config(fg="black")
            self.auto_output_name()
            self.check_ready()

    def swap_files(self):
        """Swap audio source and video source."""
        self.source_file, self.target_file = self.target_file, self.source_file
        self.src_var.set(self.source_file or "No file selected")
        self.tgt_var.set(self.target_file or "No file selected")
        if self.source_file:
            self.src_entry.config(fg="black")
        else:
            self.src_entry.config(fg="gray")
        if self.target_file:
            self.tgt_entry.config(fg="black")
        else:
            self.tgt_entry.config(fg="gray")
        self.auto_output_name()
        self.check_ready()

    def browse_output(self):
        f = filedialog.asksaveasfilename(
            title="Save Output As",
            defaultextension=".mp4",
            filetypes=[
                ("MP4", "*.mp4"),
                ("MKV", "*.mkv"),
                ("MOV", "*.mov"),
                ("AVI", "*.avi"),
                ("All Files", "*.*"),
            ],
        )
        if f:
            self.out_var.set(f)
            self.out_entry.config(fg="black")

    def auto_output_name(self):
        if self.target_file:
            base = os.path.splitext(self.target_file)[0]
            self.out_var.set(base + "_newaudio.mp4")
            self.out_entry.config(fg="black")

    def check_ready(self):
        if self.source_file and self.target_file:
            self.btn_copy.config(state=tk.NORMAL)
            src_name = os.path.basename(self.source_file)
            tgt_name = os.path.basename(self.target_file)
            self.status_var.set(
                f"Audio from: {src_name}\nVideo from: {tgt_name}\nReady to copy."
            )
        else:
            self.btn_copy.config(state=tk.DISABLED)

    # ─────────────────────────────────────────────
    # Copy Logic
    # ─────────────────────────────────────────────

    def start_copy(self):
        if self.is_converting:
            return
        self.is_converting = True
        self.btn_copy.config(state=tk.DISABLED)
        threading.Thread(target=self.run_copy, daemon=True).start()

    def run_copy(self):
        output = self.out_var.get()
        if not output or output == "(auto)":
            self.auto_output_name()
            output = self.out_var.get()

        # Try stream copy first (zero re-encoding for both streams)
        self.status_var.set("Copying audio stream (no re-encoding)...")
        self.progress_var.set("Attempting direct stream copy...")

        success = self.try_copy(output)

        if not success:
            # Audio codec incompatible with output container — re-encode audio losslessly
            self.status_var.set("Audio codec incompatible. Re-encoding audio losslessly...")
            self.progress_var.set("Falling back to lossless audio re-encode...")
            success = self.try_copy_with_reencode(output)

        if not success:
            # Last resort: high-quality lossy audio
            self.status_var.set("Lossless audio not supported. Re-encoding at high quality...")
            self.progress_var.set("Falling back to AAC 320k...")
            success = self.try_copy_with_lossy_audio(output)

        if success:
            size_mb = os.path.getsize(output) / (1024 * 1024)
            self.status_var.set(f"Done! {os.path.basename(output)} ({size_mb:.1f} MB)")
            self.progress_var.set("")
            messagebox.showinfo(
                "Success",
                f"Audio copied successfully!\n\n"
                f"Output: {output}\n"
                f"Size: {size_mb:.1f} MB\n\n"
                f"Video: copied losslessly (no re-encoding)\n"
                f"Audio: copied or re-encoded as needed",
            )
        else:
            self.status_var.set("Copy failed. Check console for error details.")
            self.progress_var.set("")

        self.is_converting = False
        self.btn_copy.config(state=tk.NORMAL)

    def _get_duration_flag(self):
        if self.dur_var.get() == "shortest":
            return ["-shortest"]
        return []

    def try_copy(self, output):
        """
        Attempt 1: Copy both streams directly (zero re-encoding).
        Works when the audio codec is compatible with the output container.
        """
        command = [
            "ffmpeg",
            "-y",
            "-i", self.target_file,    # input 0: video source
            "-i", self.source_file,    # input 1: audio source
            "-map", "0:v:0",           # video from input 0
            "-map", "1:a:0",           # audio from input 1
            "-c:v", "copy",            # copy video — no re-encoding
            "-c:a", "copy",            # copy audio — no re-encoding
            *self._get_duration_flag(),
            output,
        ]

        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode == 0:
            return True

        # Clean up failed file
        if os.path.exists(output):
            os.remove(output)
        print(f"Direct copy failed:\n{result.stderr}")
        return False

    def try_copy_with_reencode(self, output):
        """
        Attempt 2: Copy video, re-encode audio as FLAC (lossless).
        Works for containers that support FLAC (MKV, some MP4).
        """
        # Pick lossless codec based on output container
        ext = os.path.splitext(output)[1].lower()
        if ext in (".mp4", ".mov", ".m4v"):
            audio_codec = "alac"      # ALAC is native to MP4/MOV
        else:
            audio_codec = "flac"      # FLAC for MKV and others

        command = [
            "ffmpeg",
            "-y",
            "-i", self.target_file,
            "-i", self.source_file,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", audio_codec,
            *self._get_duration_flag(),
            output,
        ]

        self.progress_var.set(f"Re-encoding audio as {audio_codec.upper()} (lossless)...")

        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode == 0:
            return True

        if os.path.exists(output):
            os.remove(output)
        print(f"Lossless re-encode failed:\n{result.stderr}")
        return False

    def try_copy_with_lossy_audio(self, output):
        """
        Attempt 3: Copy video, re-encode audio as AAC 320k.
        Last resort — still high quality but technically lossy.
        """
        command = [
            "ffmpeg",
            "-y",
            "-i", self.target_file,
            "-i", self.source_file,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "320k",
            *self._get_duration_flag(),
            output,
        ]

        self.progress_var.set("Re-encoding audio as AAC 320k...")

        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode == 0:
            return True

        if os.path.exists(output):
            os.remove(output)
        print(f"AAC re-encode failed:\n{result.stderr}")
        return False


if __name__ == "__main__":
    root = tk.Tk()
    app = AudioCopier(root)
    root.mainloop()
