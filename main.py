"""
Image Compressor & Converter
Aplikasi desktop (Windows) untuk kompres ukuran file gambar, atur/pertahankan
resolusi, dan konversi format antar JPG, PNG, WEBP, BMP. Mendukung proses
banyak file sekaligus (bulk/batch).
"""

import os
import io
import threading
import queue
import traceback
from dataclasses import dataclass, field

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image

SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

FORMAT_CHOICES = ["Sama seperti asli", "JPG", "PNG", "WEBP", "BMP"]
FORMAT_TO_PIL = {"JPG": "JPEG", "PNG": "PNG", "WEBP": "WEBP", "BMP": "BMP"}
FORMAT_TO_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp"}


def set_state(widget, enabled):
    """Portable enable/disable for ttk widgets (ttk.Scale doesn't accept
    state via .config() on some Tk builds, but the .state() API always works)."""
    widget.state(["!disabled"] if enabled else ["disabled"])


def human_size(num_bytes):
    if num_bytes is None:
        return "-"
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < step:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} TB"


@dataclass
class ImageItem:
    path: str
    orig_size: int = 0
    orig_w: int = 0
    orig_h: int = 0
    status: str = "Menunggu"
    out_size: int = None
    error: str = ""

    def __post_init__(self):
        try:
            self.orig_size = os.path.getsize(self.path)
            with Image.open(self.path) as im:
                self.orig_w, self.orig_h = im.size
        except Exception as exc:  # noqa: BLE001
            self.status = "Error"
            self.error = str(exc)


def source_pil_format(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG",
        ".webp": "WEBP", ".bmp": "BMP",
    }.get(ext)


def compute_target_size(orig_w, orig_h, mode, custom_w, custom_h, keep_aspect, percent):
    if mode == "keep":
        return orig_w, orig_h
    if mode == "percent":
        scale = max(percent, 1) / 100.0
        return max(1, round(orig_w * scale)), max(1, round(orig_h * scale))
    if mode == "custom":
        tw, th = custom_w, custom_h
        if keep_aspect:
            if tw and th:
                ratio = min(tw / orig_w, th / orig_h)
                return max(1, round(orig_w * ratio)), max(1, round(orig_h * ratio))
            if tw:
                ratio = tw / orig_w
                return tw, max(1, round(orig_h * ratio))
            if th:
                ratio = th / orig_h
                return max(1, round(orig_w * ratio)), th
            return orig_w, orig_h
        return tw or orig_w, th or orig_h
    return orig_w, orig_h


def prep_for_format(img, pil_format):
    """Flatten alpha / palette for formats that don't support transparency."""
    if pil_format in ("JPEG", "BMP"):
        if img.mode in ("RGBA", "LA", "P"):
            base = img.convert("RGBA") if img.mode != "RGBA" else img
            bg = Image.new("RGB", base.size, (255, 255, 255))
            bg.paste(base, mask=base.split()[-1] if base.mode == "RGBA" else None)
            return bg
        if img.mode != "RGB":
            return img.convert("RGB")
        return img
    if pil_format == "WEBP":
        return img
    if pil_format == "PNG":
        return img
    return img


def encode(img, pil_format, quality):
    buf = io.BytesIO()
    if pil_format == "JPEG":
        img.save(buf, format="JPEG", quality=quality, optimize=True)
    elif pil_format == "WEBP":
        img.save(buf, format="WEBP", quality=quality, method=6)
    elif pil_format == "PNG":
        compress_level = max(0, min(9, round(9 - (quality / 100) * 9)))
        img.save(buf, format="PNG", optimize=True, compress_level=compress_level)
    elif pil_format == "BMP":
        img.save(buf, format="BMP")
    return buf.getvalue()


def quantize_png(img, colors):
    return img.convert("P", palette=Image.ADAPTIVE, colors=colors)


def save_with_quality(img, pil_format, quality):
    return encode(img, pil_format, quality)


def save_with_target_size(img, pil_format, target_kb, min_quality, max_quality):
    """Try to get as close as possible to target_kb (<=) via quality search,
    PNG palette quantization, and finally progressive downscaling."""
    target_bytes = target_kb * 1024
    working = img

    def best_for_current_size():
        if pil_format in ("JPEG", "WEBP"):
            lo, hi = min_quality, max_quality
            best_data = None
            while lo <= hi:
                mid = (lo + hi) // 2
                data = encode(working, pil_format, mid)
                if len(data) <= target_bytes:
                    best_data = data
                    lo = mid + 1
                else:
                    hi = mid - 1
            if best_data is None:
                best_data = encode(working, pil_format, min_quality)
            return best_data
        if pil_format == "PNG":
            data = encode(working, "PNG", 100)
            if len(data) <= target_bytes:
                return data
            for colors in (256, 128, 64, 32, 16, 8):
                quant = quantize_png(working, colors)
                data = encode(quant, "PNG", 100)
                if len(data) <= target_bytes:
                    return data
            return data
        # BMP: no quality knob, size is fixed by resolution/depth
        return encode(working, "BMP", 100)

    data = best_for_current_size()
    attempts = 0
    while len(data) > target_bytes and attempts < 12:
        w, h = working.size
        if min(w, h) <= 32:
            break
        working = working.resize((max(1, round(w * 0.85)), max(1, round(h * 0.85))), Image.LANCZOS)
        data = best_for_current_size()
        attempts += 1

    return data


class CompressorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Compressor & Converter")
        self.root.geometry("980x680")
        self.root.minsize(860, 600)

        self.items = []  # list[ImageItem]
        self.msg_queue = queue.Queue()
        self.worker_thread = None
        self.stop_requested = False

        self._build_ui()
        self.root.after(100, self._poll_queue)

    # ---------------------------------------------------------------- UI --
    def _build_ui(self):
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        # --- Top toolbar: file list controls (bulk add/remove) ---
        toolbar = ttk.Frame(root, padding=(10, 10, 10, 0))
        toolbar.grid(row=0, column=0, sticky="ew")
        ttk.Button(toolbar, text="Tambah File...", command=self.add_files).pack(side="left")
        ttk.Button(toolbar, text="Tambah Folder (Bulk)...", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Hapus Terpilih", command=self.remove_selected).pack(side="left")
        ttk.Button(toolbar, text="Kosongkan Daftar", command=self.clear_list).pack(side="left", padx=6)
        self.count_label = ttk.Label(toolbar, text="0 file")
        self.count_label.pack(side="right")

        # --- File list (Treeview) ---
        list_frame = ttk.Frame(root, padding=(10, 8))
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        columns = ("name", "resolution", "size", "status", "result")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("name", text="File")
        self.tree.heading("resolution", text="Resolusi")
        self.tree.heading("size", text="Ukuran Asli")
        self.tree.heading("status", text="Status")
        self.tree.heading("result", text="Hasil")
        self.tree.column("name", width=320, anchor="w")
        self.tree.column("resolution", width=110, anchor="center")
        self.tree.column("size", width=100, anchor="center")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("result", width=160, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        # --- Settings panel ---
        settings = ttk.Frame(root, padding=(10, 0, 10, 8))
        settings.grid(row=2, column=0, sticky="ew")
        for c in range(3):
            settings.columnconfigure(c, weight=1)

        # Format
        fmt_frame = ttk.LabelFrame(settings, text="Format Output", padding=10)
        fmt_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.format_var = tk.StringVar(value=FORMAT_CHOICES[0])
        self.format_combo = ttk.Combobox(fmt_frame, textvariable=self.format_var,
                                          values=FORMAT_CHOICES, state="readonly")
        self.format_combo.pack(fill="x")
        self.format_combo.bind("<<ComboboxSelected>>", self._on_format_change)

        # Compression / quality
        comp_frame = ttk.LabelFrame(settings, text="Kompresi & Kualitas", padding=10)
        comp_frame.grid(row=0, column=1, sticky="nsew", padx=6)

        self.comp_mode = tk.StringVar(value="quality")
        ttk.Radiobutton(comp_frame, text="Atur kualitas", variable=self.comp_mode,
                         value="quality", command=self._on_comp_mode_change).grid(row=0, column=0, sticky="w")
        self.quality_var = tk.IntVar(value=85)
        self.quality_scale = ttk.Scale(comp_frame, from_=1, to=100, orient="horizontal",
                                        variable=self.quality_var, command=self._on_quality_slide)
        self.quality_scale.grid(row=0, column=1, sticky="ew", padx=6)
        self.quality_label = ttk.Label(comp_frame, text="85")
        self.quality_label.grid(row=0, column=2, sticky="w")
        comp_frame.columnconfigure(1, weight=1)

        ttk.Radiobutton(comp_frame, text="Target ukuran file (KB)", variable=self.comp_mode,
                         value="target", command=self._on_comp_mode_change).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.target_kb_var = tk.StringVar(value="200")
        self.target_kb_entry = ttk.Entry(comp_frame, textvariable=self.target_kb_var, width=10, state="disabled")
        self.target_kb_entry.grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(comp_frame, text="KB per file").grid(row=1, column=2, sticky="w", pady=(6, 0))

        self.quality_note = ttk.Label(comp_frame, text="", foreground="#888")
        self.quality_note.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # Resolution
        res_frame = ttk.LabelFrame(settings, text="Resolusi", padding=10)
        res_frame.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        self.res_mode = tk.StringVar(value="keep")
        ttk.Radiobutton(res_frame, text="Pertahankan resolusi asli", variable=self.res_mode,
                         value="keep", command=self._on_res_mode_change).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(res_frame, text="Atur resolusi (px)", variable=self.res_mode,
                         value="custom", command=self._on_res_mode_change).grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 0))

        self.width_var = tk.StringVar()
        self.height_var = tk.StringVar()
        self.width_entry = ttk.Entry(res_frame, textvariable=self.width_var, width=7, state="disabled")
        self.width_entry.grid(row=2, column=0, sticky="w", padx=(18, 2))
        ttk.Label(res_frame, text="x").grid(row=2, column=1)
        self.height_entry = ttk.Entry(res_frame, textvariable=self.height_var, width=7, state="disabled")
        self.height_entry.grid(row=2, column=2, sticky="w", padx=(2, 6))

        self.keep_aspect_var = tk.BooleanVar(value=True)
        self.keep_aspect_check = ttk.Checkbutton(res_frame, text="Kunci rasio aspek", variable=self.keep_aspect_var,
                                                  state="disabled")
        self.keep_aspect_check.grid(row=3, column=0, columnspan=4, sticky="w", padx=(18, 0))

        ttk.Radiobutton(res_frame, text="Skala persen (%)", variable=self.res_mode,
                         value="percent", command=self._on_res_mode_change).grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.percent_var = tk.StringVar(value="100")
        self.percent_entry = ttk.Entry(res_frame, textvariable=self.percent_var, width=7, state="disabled")
        self.percent_entry.grid(row=5, column=0, sticky="w", padx=(18, 0))

        # --- Output folder ---
        out_frame = ttk.Frame(root, padding=(10, 0, 10, 8))
        out_frame.grid(row=3, column=0, sticky="ew")
        out_frame.columnconfigure(1, weight=1)
        ttk.Label(out_frame, text="Folder Output:").grid(row=0, column=0, sticky="w")
        self.out_dir_var = tk.StringVar(value="")
        ttk.Entry(out_frame, textvariable=self.out_dir_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(out_frame, text="Pilih...", command=self.choose_out_dir).grid(row=0, column=2)
        ttk.Checkbutton(out_frame, text="Timpa file jika sudah ada",
                         variable=tk.BooleanVar(value=False)).grid(row=1, column=1, sticky="w", pady=(4, 0))

        # --- Bottom: process bulk + progress + log ---
        bottom = ttk.Frame(root, padding=(10, 0, 10, 10))
        bottom.grid(row=4, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self.process_btn = ttk.Button(bottom, text="Proses Semua (Bulk)", command=self.start_processing)
        self.process_btn.grid(row=0, column=0, sticky="w")
        self.cancel_btn = ttk.Button(bottom, text="Batalkan", command=self.cancel_processing, state="disabled")
        self.cancel_btn.grid(row=0, column=1, padx=6)

        self.progress = ttk.Progressbar(bottom, orient="horizontal", mode="determinate")
        self.progress.grid(row=0, column=2, sticky="ew", padx=6)
        bottom.columnconfigure(2, weight=1)

        self.summary_label = ttk.Label(bottom, text="")
        self.summary_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self._on_comp_mode_change()
        self._on_res_mode_change()

    # ---------------------------------------------------------- UI events --
    def _on_format_change(self, *_):
        fmt = self.format_var.get()
        if fmt == "BMP":
            self.quality_note.config(text="BMP tidak mendukung pengaturan kualitas (format tanpa kompresi).")
        else:
            self.quality_note.config(text="")

    def _on_comp_mode_change(self):
        mode = self.comp_mode.get()
        if mode == "quality":
            set_state(self.quality_scale, True)
            set_state(self.target_kb_entry, False)
        else:
            set_state(self.quality_scale, False)
            set_state(self.target_kb_entry, True)

    def _on_quality_slide(self, val):
        self.quality_label.config(text=str(round(float(val))))

    def _on_res_mode_change(self):
        mode = self.res_mode.get()
        set_state(self.width_entry, mode == "custom")
        set_state(self.height_entry, mode == "custom")
        set_state(self.keep_aspect_check, mode == "custom")
        set_state(self.percent_entry, mode == "percent")

    # ------------------------------------------------------- file list ops --
    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Pilih gambar (bisa pilih banyak sekaligus)",
            filetypes=[("Gambar", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Semua file", "*.*")],
        )
        if paths:
            self._add_paths(paths)

    def add_folder(self):
        folder = filedialog.askdirectory(title="Pilih folder (semua gambar di dalamnya akan ditambahkan)")
        if not folder:
            return
        found = []
        for dirpath, _dirs, filenames in os.walk(folder):
            for fn in filenames:
                if fn.lower().endswith(SUPPORTED_EXTS):
                    found.append(os.path.join(dirpath, fn))
        if not found:
            messagebox.showinfo("Tidak ada gambar", "Tidak ditemukan file gambar yang didukung di folder ini.")
            return
        self._add_paths(found)

    def _add_paths(self, paths):
        existing = {it.path for it in self.items}
        added = 0
        for p in paths:
            if p in existing:
                continue
            item = ImageItem(path=p)
            self.items.append(item)
            self._insert_row(item)
            added += 1
        self._update_count()

    def _insert_row(self, item):
        res = f"{item.orig_w}x{item.orig_h}" if item.orig_w else "-"
        self.tree.insert("", "end", iid=item.path, values=(
            os.path.basename(item.path), res, human_size(item.orig_size), item.status, "-"
        ))

    def remove_selected(self):
        sel = self.tree.selection()
        for iid in sel:
            self.tree.delete(iid)
            self.items = [it for it in self.items if it.path != iid]
        self._update_count()

    def clear_list(self):
        self.tree.delete(*self.tree.get_children())
        self.items = []
        self._update_count()

    def _update_count(self):
        self.count_label.config(text=f"{len(self.items)} file")

    def choose_out_dir(self):
        folder = filedialog.askdirectory(title="Pilih folder output")
        if folder:
            self.out_dir_var.set(folder)

    # -------------------------------------------------------- processing --
    def _read_settings(self):
        fmt_choice = self.format_var.get()
        comp_mode = self.comp_mode.get()
        quality = int(round(self.quality_var.get()))
        try:
            target_kb = float(self.target_kb_var.get())
        except ValueError:
            target_kb = None

        res_mode = self.res_mode.get()
        try:
            width = int(self.width_var.get()) if self.width_var.get().strip() else None
        except ValueError:
            width = None
        try:
            height = int(self.height_var.get()) if self.height_var.get().strip() else None
        except ValueError:
            height = None
        try:
            percent = float(self.percent_var.get())
        except ValueError:
            percent = 100.0
        keep_aspect = self.keep_aspect_var.get()

        out_dir = self.out_dir_var.get().strip()
        return dict(fmt_choice=fmt_choice, comp_mode=comp_mode, quality=quality,
                    target_kb=target_kb, res_mode=res_mode, width=width, height=height,
                    percent=percent, keep_aspect=keep_aspect, out_dir=out_dir)

    def start_processing(self):
        if not self.items:
            messagebox.showwarning("Daftar kosong", "Tambahkan minimal satu file gambar terlebih dahulu.")
            return
        settings = self._read_settings()
        if settings["comp_mode"] == "target" and not settings["target_kb"]:
            messagebox.showerror("Input tidak valid", "Isi target ukuran file (KB) dengan angka yang valid.")
            return
        if not settings["out_dir"]:
            if not messagebox.askyesno(
                "Folder output belum dipilih",
                "Belum ada folder output dipilih. Simpan hasil di subfolder 'compressed' "
                "di sebelah masing-masing file asli?"):
                return

        set_state(self.process_btn, False)
        set_state(self.cancel_btn, True)
        self.progress.config(maximum=len(self.items), value=0)
        self.stop_requested = False

        self.worker_thread = threading.Thread(target=self._worker, args=(settings,), daemon=True)
        self.worker_thread.start()

    def cancel_processing(self):
        self.stop_requested = True
        set_state(self.cancel_btn, False)

    def _worker(self, settings):
        total_orig = 0
        total_out = 0
        ok_count = 0
        err_count = 0

        for item in self.items:
            if self.stop_requested:
                self.msg_queue.put(("status", item.path, "Dibatalkan"))
                continue
            try:
                out_path, out_size = self._process_one(item, settings)
                total_orig += item.orig_size
                total_out += out_size
                ok_count += 1
                self.msg_queue.put(("done", item.path, human_size(out_size)))
            except Exception as exc:  # noqa: BLE001
                err_count += 1
                self.msg_queue.put(("error", item.path, str(exc)))
                traceback.print_exc()
            self.msg_queue.put(("progress", None, None))

        self.msg_queue.put(("finished", None, (ok_count, err_count, total_orig, total_out)))

    def _process_one(self, item, settings):
        with Image.open(item.path) as im:
            im.load()
            src_fmt = source_pil_format(item.path)
            fmt_choice = settings["fmt_choice"]
            pil_format = src_fmt if fmt_choice == "Sama seperti asli" else FORMAT_TO_PIL[fmt_choice]

            new_w, new_h = compute_target_size(
                im.width, im.height, settings["res_mode"],
                settings["width"], settings["height"],
                settings["keep_aspect"], settings["percent"],
            )
            work_img = im.resize((new_w, new_h), Image.LANCZOS) if (new_w, new_h) != im.size else im.copy()
            work_img = prep_for_format(work_img, pil_format)

            if settings["comp_mode"] == "target" and pil_format != "BMP":
                data = save_with_target_size(work_img, pil_format, settings["target_kb"], 5, 95)
            elif settings["comp_mode"] == "target" and pil_format == "BMP":
                data = encode(work_img, "BMP", 100)
            else:
                data = save_with_quality(work_img, pil_format, settings["quality"])

        out_dir = settings["out_dir"]
        base = os.path.splitext(os.path.basename(item.path))[0]
        ext = FORMAT_TO_EXT[pil_format]
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, base + ext)
        else:
            local_dir = os.path.join(os.path.dirname(item.path), "compressed")
            os.makedirs(local_dir, exist_ok=True)
            out_path = os.path.join(local_dir, base + ext)

        out_path = self._unique_path(out_path)
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path, len(data)

    @staticmethod
    def _unique_path(path):
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        n = 1
        while os.path.exists(f"{base} ({n}){ext}"):
            n += 1
        return f"{base} ({n}){ext}"

    def _poll_queue(self):
        try:
            while True:
                kind, path, payload = self.msg_queue.get_nowait()
                if kind == "progress":
                    self.progress.step(1)
                elif kind == "done":
                    if self.tree.exists(path):
                        self.tree.set(path, "status", "Selesai")
                        self.tree.set(path, "result", payload)
                elif kind == "error":
                    if self.tree.exists(path):
                        self.tree.set(path, "status", "Error")
                        self.tree.set(path, "result", payload[:40])
                elif kind == "status":
                    if self.tree.exists(path):
                        self.tree.set(path, "status", payload)
                elif kind == "finished":
                    ok_count, err_count, total_orig, total_out = payload
                    saved = total_orig - total_out
                    pct = (saved / total_orig * 100) if total_orig else 0
                    self.summary_label.config(
                        text=(f"Selesai: {ok_count} berhasil, {err_count} gagal. "
                              f"Ukuran total: {human_size(total_orig)} -> {human_size(total_out)} "
                              f"(hemat {pct:.1f}%).")
                    )
                    set_state(self.process_btn, True)
                    set_state(self.cancel_btn, False)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:  # noqa: BLE001
        pass
    app = CompressorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
