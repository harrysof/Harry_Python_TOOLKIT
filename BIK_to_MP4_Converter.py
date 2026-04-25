import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import os
import threading


class BikConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("BIK ⇄ MP4 Converter (Lossless Pipeline)")
        self.root.geometry("620x520")
        self.root.resizable(False, False)

        self.selected_files = []
        self.is_converting = False

        # ── UI Elements ──

        # Header
        header = tk.Label(
            root,
            text="BIK ⇄ MP4 Converter",
            font=("Helvetica", 16, "bold"),
        )
        header.pack(pady=(10, 0))

        subheader = tk.Label(
            root,
            text="Lossless BIK→MP4  |  Near-lossless MP4→BIK (requires RAD Video Tools)",
            font=("Helvetica", 9),
            fg="gray",
        )
        subheader.pack(pady=(0, 5))

        # ── Mode Selection ──
        mode_frame = tk.LabelFrame(root, text="Conversion Mode", font=("Helvetica", 10, "bold"))
        mode_frame.pack(fill="x", padx=15, pady=5)

        self.mode_var = tk.StringVar(value="bik_to_mp4")

        tk.Radiobutton(
            mode_frame,
            text="BIK → MP4 (Lossless — for Topaz upscaling)",
            variable=self.mode_var,
            value="bik_to_mp4",
            font=("Helvetica", 10),
            command=self.update_ui,
        ).pack(anchor="w", padx=10, pady=2)

        tk.Radiobutton(
            mode_frame,
            text="MP4 → BIK (Near-lossless — after Topaz, requires binkconv.exe)",
            variable=self.mode_var,
            value="mp4_to_bik",
            font=("Helvetica", 10),
            command=self.update_ui,
        ).pack(anchor="w", padx=10, pady=2)

        # ── File Selection ──
        file_frame = tk.LabelFrame(root, text="Files", font=("Helvetica", 10, "bold"))
        file_frame.pack(fill="both", expand=True, padx=15, pady=5)

        self.btn_select = tk.Button(
            file_frame,
            text="Select Files",
            font=("Helvetica", 11),
            command=self.select_files,
            bg="#4CAF50",
            fg="white",
        )
        self.btn_select.pack(pady=5)

        self.file_listbox = tk.Listbox(
            file_frame, width=70, height=8, font=("Consolas", 9)
        )
        self.file_listbox.pack(pady=5, padx=5)

        # ── Convert Button ──
        self.btn_convert = tk.Button(
            root,
            text="Convert",
            font=("Helvetica", 13, "bold"),
            command=self.start_conversion,
            bg="#2196F3",
            fg="white",
            state=tk.DISABLED,
            width=20,
        )
        self.btn_convert.pack(pady=8)

        # ── Status ──
        self.status_var = tk.StringVar()
        self.status_var.set("Select a conversion mode and files to begin.")
        self.lbl_status = tk.Label(
            root, textvariable=self.status_var, font=("Helvetica", 10), wraplength=580
        )
        self.lbl_status.pack(pady=5)

        # ── Progress ──
        self.progress_var = tk.StringVar()
        self.lbl_progress = tk.Label(
            root, textvariable=self.progress_var, font=("Helvetica", 9), fg="gray"
        )
        self.lbl_progress.pack(pady=(0, 5))

    # ─────────────────────────────────────────────
    # UI Helpers
    # ─────────────────────────────────────────────

    def update_ui(self):
        """Update button text and status based on selected mode."""
        if self.mode_var.get() == "bik_to_mp4":
            self.btn_select.config(text="Select BIK Files")
            self.status_var.set("Select BIK files for lossless conversion to MP4.")
        else:
            self.btn_select.config(text="Select MP4 Files")
            self.status_var.set(
                "Select upscaled MP4 files for near-lossless conversion back to BIK.\n"
                "Requires binkconv.exe (RAD Video Tools) in your system PATH."
            )
        self.file_listbox.delete(0, tk.END)
        self.selected_files = []
        self.btn_convert.config(state=tk.DISABLED)

    def select_files(self):
        mode = self.mode_var.get()
        if mode == "bik_to_mp4":
            filetypes = [("Bink Video Files", "*.bik"), ("All Files", "*.*")]
            title = "Select BIK Video Files"
        else:
            filetypes = [("MP4 Video Files", "*.mp4"), ("All Files", "*.*")]
            title = "Select Upscaled MP4 Files"

        files = filedialog.askopenfilenames(title=title, filetypes=filetypes)

        if files:
            self.selected_files = list(files)
            self.file_listbox.delete(0, tk.END)
            for f in self.selected_files:
                self.file_listbox.insert(tk.END, os.path.basename(f))
            self.btn_convert.config(state=tk.NORMAL)
            self.status_var.set(
                f"{len(self.selected_files)} file(s) selected. Ready to convert."
            )

    # ─────────────────────────────────────────────
    # Conversion Logic
    # ─────────────────────────────────────────────

    def start_conversion(self):
        if self.is_converting:
            return
        self.is_converting = True
        self.btn_convert.config(state=tk.DISABLED)
        self.btn_select.config(state=tk.DISABLED)
        threading.Thread(target=self.run_conversion, daemon=True).start()

    def run_conversion(self):
        mode = self.mode_var.get()
        if mode == "bik_to_mp4":
            self.convert_bik_to_mp4()
        else:
            self.convert_mp4_to_bik()

        self.is_converting = False
        self.btn_convert.config(state=tk.NORMAL)
        self.btn_select.config(state=tk.NORMAL)

    def convert_bik_to_mp4(self):
        """
        BIK → MP4 (Lossless H.264)

        This is the FIRST step in your upscaling pipeline.
        CRF 0 = mathematically lossless — zero quality loss from the BIK source.
        Preset 'medium' balances encoding speed and file size (at CRF 0,
        all presets produce identical visual quality; the difference is file size).

        Audio is copied without re-encoding if the codec is compatible.
        If copy fails, falls back to FLAC (lossless) or 256k AAC.
        """
        success_count = 0
        fail_count = 0
        total = len(self.selected_files)

        for i, bik_file in enumerate(self.selected_files, 1):
            base_name = os.path.splitext(bik_file)[0]
            mp4_file = base_name + "_lossless.mp4"

            self.status_var.set(f"[{i}/{total}] Converting: {os.path.basename(bik_file)}")
            self.progress_var.set("Encoding lossless H.264 — this may take a while...")

            # ── Lossless video, attempt audio copy ──
            command = [
                "ffmpeg",
                "-y",
                "-i", bik_file,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "0",
                "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                mp4_file,
            ]

            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            # If audio copy failed, retry with FLAC (lossless)
            if result.returncode != 0 and "copy" in str(result.stderr).lower():
                self.status_var.set(
                    f"[{i}/{total}] Retrying with FLAC audio: {os.path.basename(bik_file)}"
                )
                command_fallback_flac = [
                    "ffmpeg",
                    "-y",
                    "-i", bik_file,
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "0",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "flac",
                    mp4_file,
                ]
                result = subprocess.run(
                    command_fallback_flac,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

            # If FLAC also failed (MP4 container doesn't always like FLAC), try AAC 256k
            if result.returncode != 0:
                self.status_var.set(
                    f"[{i}/{total}] Retrying with AAC 256k audio: {os.path.basename(bik_file)}"
                )
                command_fallback_aac = [
                    "ffmpeg",
                    "-y",
                    "-i", bik_file,
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "0",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "256k",
                    mp4_file,
                ]
                result = subprocess.run(
                    command_fallback_aac,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

            if result.returncode == 0:
                success_count += 1
                # Show file size for awareness
                size_mb = os.path.getsize(mp4_file) / (1024 * 1024)
                self.progress_var.set(f"Output: {os.path.basename(mp4_file)} ({size_mb:.1f} MB)")
            else:
                fail_count += 1
                print(f"Error converting {bik_file}:\n{result.stderr}")

        final = f"BIK → MP4 complete! Success: {success_count}, Failed: {fail_count}"
        self.status_var.set(final)
        self.progress_var.set("")
        messagebox.showinfo("Done", final + "\n\nReady for Topaz upscaling!")

    def convert_mp4_to_bik(self):
        """
        MP4 → BIK (Near-lossless, using RAD Video Tools)

        IMPORTANT: Bink is an inherently LOSSY codec. There is no truly lossless
        BIK mode. This uses the highest possible quality setting to minimize loss.

        Requires binkconv.exe from RAD Video Tools in your system PATH.
        Download from: https://www.radgametools.com/bnkdown.htm

        binkconv.exe uses these quality flags:
          /#       = data rate in KB/sec (higher = better quality)
          /%NNNN   = percentage of original size (closer to 100 = less compression)
          /qNNNN   = quality level (1-100, use 100 for best quality)
          /cNNNN   = compress to NNNN kilobytes per second

        For maximum quality after Topaz upscaling, we use /q100 /%100
        which tells Bink to preserve as much detail as possible.
        """
        success_count = 0
        fail_count = 0
        total = len(self.selected_files)

        # Check if binkconv is available
        try:
            check = subprocess.run(
                ["binkconv", "-?"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            self.status_var.set("")
            self.progress_var.set("")
            messagebox.showerror(
                "Missing Tool",
                "binkconv.exe not found!\n\n"
                "Download RAD Video Tools from:\n"
                "https://www.radgametools.com/bnkdown.htm\n\n"
                "Install it and add binkconv.exe to your system PATH.",
            )
            self.is_converting = False
            self.btn_convert.config(state=tk.NORMAL)
            self.btn_select.config(state=tk.NORMAL)
            return
        except subprocess.TimeoutExpired:
            pass  # binkconv exists but didn't respond to -? — that's fine

        for i, mp4_file in enumerate(self.selected_files, 1):
            base_name = os.path.splitext(mp4_file)[0]
            bik_file = base_name + "_upscaled.bik"

            self.status_var.set(f"[{i}/{total}] Converting: {os.path.basename(mp4_file)}")
            self.progress_var.set("Encoding maximum quality BIK — this will be slow...")

            # ── Maximum quality Bink encode ──
            # /q100  = quality level 100 (highest possible)
            # /%100  = target 100% of original data rate (minimal compression)
            #
            # NOTE: Even at /q100 /%100, Bink IS lossy. You WILL lose some detail
            # compared to the MP4 source. This is a fundamental limitation of the
            # Bink codec — it has no lossless mode.
            #
            # If your game supports it, consider keeping the MP4 files instead
            # of converting back to BIK. Some game mods can replace cutscenes
            # with MP4/WebM if the engine allows it.
            command = [
                "binkconv",
                mp4_file,
                bik_file,
                "/q100",
                "/%100",
            ]

            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            if result.returncode == 0:
                success_count += 1
                size_mb = os.path.getsize(bik_file) / (1024 * 1024)
                self.progress_var.set(
                    f"Output: {os.path.basename(bik_file)} ({size_mb:.1f} MB)"
                )
            else:
                fail_count += 1
                error_msg = result.stderr or result.stdout or "Unknown error"
                print(f"Error converting {mp4_file}:\n{error_msg}")

        final = f"MP4 → BIK complete! Success: {success_count}, Failed: {fail_count}"
        self.status_var.set(final)
        self.progress_var.set("")
        messagebox.showinfo(
            "Done",
            final
            + "\n\nRemember: BIK is lossy — some detail from the upscaled MP4"
            + "\nwill be lost. This is unavoidable with the Bink codec.",
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = BikConverter(root)
    root.mainloop()
