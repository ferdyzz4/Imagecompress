# Image Compressor & Converter

Aplikasi desktop Windows & macOS untuk:
- **Kompres ukuran file gambar** — atur kualitas manual, atau tentukan **target ukuran file (KB)** dan aplikasi otomatis mencari kualitas terbaik yang muat di batas itu.
- **Atur resolusi atau pertahankan resolusi asli** — bisa custom width x height (dengan kunci rasio aspek), atau skala persen (%).
- **Konversi format**: JPG, PNG, WEBP, BMP (bebas convert antar format apa saja).
- **Bulk / batch processing** — tambahkan banyak file sekaligus atau seluruh isi folder, lalu proses semuanya dalam satu klik. Progress bar dan status per-file ditampilkan di tabel.

Source code: [main.py](main.py) (Python + Tkinter/ttkbootstrap + Pillow, tampilan modern flat-UI, sudah diuji logikanya).

---

## Download langsung

Rilis terbaru (file siap pakai untuk Windows & macOS) ada di halaman **[Releases](https://github.com/ferdyzz4/Imagecompress/releases)**.

- **Windows**: unduh `ImageCompressor.exe`, langsung double-click untuk jalankan (tidak perlu install apa pun).
- **macOS**: unduh `ImageCompressor-macOS.zip`, extract, lalu buka `ImageCompressor.app`. Karena aplikasi ini belum ditandatangani dengan sertifikat Apple Developer (belum di-notarize), saat pertama kali dibuka macOS akan menampilkan peringatan "tidak bisa dibuka / developer tidak dikenal". Caranya: **klik kanan pada ImageCompressor.app → pilih "Open" → klik "Open" lagi** pada dialog konfirmasi (hanya perlu dilakukan sekali).

Setiap push ke branch `main`, GitHub Actions ([.github/workflows/build.yml](.github/workflows/build.yml)) otomatis build ulang untuk kedua platform ini — hasilnya bisa diunduh dari tab **Actions** (artifact) atau dibuatkan Release baru secara manual.

## Build manual — Windows

1. Install [Python 3.10+](https://www.python.org/downloads/) — saat instalasi centang **"Add python.exe to PATH"**.
2. Salin folder `ImageCompressor` ini ke komputer Windows.
3. Double-click [build_exe.bat](build_exe.bat) — script ini otomatis membuat virtual environment, install `Pillow` & `PyInstaller`, lalu build.
4. Hasil ada di `dist\ImageCompressor.exe` — file ini portable, tinggal disalin/dijalankan di komputer Windows lain tanpa perlu install Python.

## Build manual — macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt pyinstaller
pyinstaller --windowed --name ImageCompressor --collect-all ttkbootstrap main.py
```

Hasilnya ada di `dist/ImageCompressor.app`.

## Menjalankan langsung tanpa build (mode developer, Windows/Mac/Linux)

```bash
pip install -r requirements.txt
python main.py
```

---

## Cara pakai aplikasi

1. **Tambah File...** untuk pilih beberapa gambar, atau **Tambah Folder (Bulk)...** untuk memasukkan semua gambar dalam folder (termasuk subfolder) sekaligus.
2. Atur **Format Output** — pilih "Sama seperti asli" untuk sekadar kompres tanpa ganti format, atau pilih JPG/PNG/WEBP/BMP untuk konversi.
3. Atur **Kompresi & Kualitas**:
   - **Atur kualitas** — geser slider 1–100 (semakin tinggi, semakin bagus kualitas & semakin besar file).
   - **Target ukuran file (KB)** — isi angka KB yang diinginkan, aplikasi otomatis mencari kualitas terbaik yang mendekati target tersebut (dan akan mengecilkan resolusi sedikit jika target sangat kecil dan tidak tercapai lewat kualitas saja).
4. Atur **Resolusi**:
   - **Pertahankan resolusi asli** — tidak diubah.
   - **Atur resolusi (px)** — isi lebar/tinggi target, centang "Kunci rasio aspek" agar tidak gepeng.
   - **Skala persen (%)** — misal 50 untuk setengah ukuran asli.
5. Pilih **Folder Output** (opsional — jika kosong, hasil disimpan di subfolder `compressed` di sebelah tiap file asli).
6. Klik **Proses Semua (Bulk)** — semua file di daftar diproses berurutan, status & ukuran hasil tiap file muncul di tabel, dan ringkasan total penghematan ukuran ditampilkan di bawah.

## Format yang didukung

| Format | Kompresi kualitas | Transparansi | Catatan |
|---|---|---|---|
| JPG | Ya | Tidak (latar diputihkan) | Paling kecil untuk foto |
| PNG | Ya (via palet warna) | Ya | Lossless, cocok untuk gambar dengan teks/garis tegas |
| WEBP | Ya | Ya | Umumnya paling efisien ukurannya |
| BMP | Tidak (uncompressed) | Tidak | Ukuran besar, hanya bisa dikecilkan lewat resolusi |
