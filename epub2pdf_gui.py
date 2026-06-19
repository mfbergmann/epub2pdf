#!/usr/bin/env python3
"""Desktop GUI for epub2pdf — drag-and-drop EPUB to print-paginated PDF."""
import os
import platform
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from epub2pdf import convert, NoPageListError

PAGE_SIZES = ["6x9 (book)", "Letter", "A4"]
PAGE_SIZE_MAP = {"6x9 (book)": "6x9", "Letter": "letter", "A4": "a4"}


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("epub2pdf")
        self.root.resizable(False, False)
        self.epub_path = None
        self.last_output = None
        self._build_ui()
        self.root.update_idletasks()
        self._center_window()

    def _center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 3
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=24)
        frame.grid(sticky="nsew")

        ttk.Label(frame, text="epub2pdf", font=("Helvetica", 20, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 2))
        ttk.Label(frame, text="Convert EPUBs to citation-ready PDFs",
                  font=("Helvetica", 11)).grid(
            row=1, column=0, columnspan=3, pady=(0, 16))

        ttk.Label(frame, text="EPUB file:").grid(row=2, column=0, sticky="w")
        self.file_var = tk.StringVar(value="No file selected")
        ttk.Label(frame, textvariable=self.file_var, width=40,
                  foreground="gray").grid(row=2, column=1, padx=8, sticky="w")
        ttk.Button(frame, text="Browse…", command=self._browse).grid(
            row=2, column=2)

        opts = ttk.LabelFrame(frame, text="Options", padding=12)
        opts.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        ttk.Label(opts, text="Page size:").grid(row=0, column=0, sticky="w")
        self.size_var = tk.StringVar(value=PAGE_SIZES[0])
        ttk.Combobox(opts, textvariable=self.size_var, values=PAGE_SIZES,
                     state="readonly", width=14).grid(row=0, column=1, padx=8, sticky="w")

        self.compact_var = tk.BooleanVar()
        ttk.Checkbutton(opts, text="Compact mode (shorter PDF, inline markers)",
                        variable=self.compact_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.convert_btn = ttk.Button(frame, text="Convert to PDF",
                                      command=self._start_convert)
        self.convert_btn.grid(row=4, column=0, columnspan=3, pady=(16, 0),
                              sticky="ew")
        self.convert_btn.state(["disabled"])

        self.status_var = tk.StringVar(value="Select an EPUB file to get started.")
        ttk.Label(frame, textvariable=self.status_var, wraplength=380,
                  foreground="gray").grid(
            row=5, column=0, columnspan=3, pady=(10, 0), sticky="w")

        self.open_btn = ttk.Button(frame, text="Show output file",
                                   command=self._show_output)
        self.open_btn.grid(row=6, column=0, columnspan=3, pady=(8, 0), sticky="ew")
        self.open_btn.grid_remove()

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.progress.grid_remove()

    def _browse(self):
        path = filedialog.askopenfilename(
            filetypes=[("EPUB files", "*.epub"), ("All files", "*.*")])
        if path:
            self.epub_path = path
            self.file_var.set(os.path.basename(path))
            self.convert_btn.state(["!disabled"])
            self.open_btn.grid_remove()
            self.status_var.set("Ready to convert.")

    def _start_convert(self):
        self.convert_btn.state(["disabled"])
        self.open_btn.grid_remove()
        self.status_var.set("Converting… this may take a minute.")
        self.progress.grid()
        self.progress.start(15)
        threading.Thread(target=self._do_convert, daemon=True).start()

    def _do_convert(self):
        page_size = PAGE_SIZE_MAP.get(self.size_var.get(), "6x9")
        compact = self.compact_var.get()
        try:
            out, n, title, author = convert(
                self.epub_path, page_size=page_size, compact=compact)
            self.last_output = out
            label = title or os.path.basename(self.epub_path)
            self.root.after(0, self._on_success,
                            f"Done! {n} print pages converted.\n"
                            f"“{label}” → {os.path.basename(out)}")
        except NoPageListError:
            self.root.after(0, self._on_no_pagelist)
        except Exception as e:
            self.root.after(0, self._on_error, str(e))

    def _on_success(self, msg):
        self.progress.stop()
        self.progress.grid_remove()
        self.status_var.set(msg)
        self.open_btn.grid()
        self.convert_btn.state(["!disabled"])

    def _on_no_pagelist(self):
        self.progress.stop()
        self.progress.grid_remove()
        if messagebox.askyesno(
                "No print page list",
                "This EPUB doesn't contain print page numbers.\n\n"
                "Convert anyway? The PDF will have page numbers, "
                "but they won't match the print edition."):
            self.status_var.set("Converting without print pagination…")
            self.progress.grid()
            self.progress.start(15)
            threading.Thread(target=self._do_force_convert, daemon=True).start()
        else:
            self.status_var.set("Conversion cancelled.")
            self.convert_btn.state(["!disabled"])

    def _do_force_convert(self):
        page_size = PAGE_SIZE_MAP.get(self.size_var.get(), "6x9")
        compact = self.compact_var.get()
        try:
            out, n, title, author = convert(
                self.epub_path, page_size=page_size, compact=compact, force=True)
            self.last_output = out
            label = title or os.path.basename(self.epub_path)
            self.root.after(0, self._on_success,
                            f"Done (no print pagination).\n"
                            f"“{label}” → {os.path.basename(out)}")
        except Exception as e:
            self.root.after(0, self._on_error, str(e))

    def _on_error(self, msg):
        self.progress.stop()
        self.progress.grid_remove()
        messagebox.showerror("Conversion failed", msg)
        self.status_var.set("Conversion failed. Try another file?")
        self.convert_btn.state(["!disabled"])

    def _show_output(self):
        if not self.last_output or not os.path.exists(self.last_output):
            return
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", "-R", self.last_output])
        elif system == "Windows":
            subprocess.Popen(["explorer", "/select,", self.last_output])
        else:
            folder = os.path.dirname(self.last_output)
            subprocess.Popen(["xdg-open", folder])


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
