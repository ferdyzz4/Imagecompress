# Image Compressor & Converter

Aplikasi desktop Windows untuk:
- **Kompres ukuran file gambar** — atur kualitas manual, atau tentukan **target ukuran file (KB)** dan aplikasi otomatis mencari kualitas terbaik yang muat di batas itu.
- **Atur resolusi atau pertahankan resolusi asli** — bisa custom width x height (dengan kunci rasio aspek), atau skala persen (%).
- **Konversi format**: JPG, PNG, WEBP, BMP (bebas convert antar format apa saja).
- **Bulk / batch processing** — tambahkan banyak file sekaligus atau seluruh isi folder, lalu proses semuanya dalam satu klik. Progress bar dan status per-file ditampilkan di tabel.

Source code: [main.py](main.py) (Python + Tkinter + Pillow, ±600 baris, sudah diuji logikanya).

---

## Catatan penting

Kode ini dibuat & diuji dari macOS, sehingga **file `.exe` tidak bisa dihasilkan langsung di sini** (Windows `.exe` harus di-build di mesin Windows atau lewat CI Windows — tidak bisa cross-compile dari macOS). Pilih salah satu cara di bawah untuk mendapatkan `ImageCompressor.exe`.

## Cara 1 — Build otomatis lewat GitHub Actions (tanpa perlu komputer Windows)

1. Push folder ini ke repo GitHub Anda (butuh akun GitHub, gratis).
2. Workflow [.github/workflows/build.yml](.github/workflows/build.yml) sudah disiapkan — otomatis jalan tiap push ke branch `main`, atau bisa dipicu manual lewat tab **Actions → Build Windows EXE → Run workflow**.
3. Setelah selesai (~2 menit), buka run tersebut → bagian **Artifacts** → unduh `ImageCompressor-windows.zip`, di dalamnya ada `ImageCompressor.exe`.

```bash
cd ImageCompressor
git init
git add .
git commit -m "Image Compressor app"
git branch -M main
git remote add origin <URL_REPO_GITHUB_ANDA>
git push -u origin main
```

## Cara 2 — Build manual di komputer Windows

1. Install [Python 3.10+](https://www.python.org/downloads/) — saat instalasi centang **"Add python.exe to PATH"**.
2. Salin folder `ImageCompressor` ini ke komputer Windows.
3. Double-click [build_exe.bat](build_exe.bat) — script ini otomatis membuat virtual environment, install `Pillow` & `PyInstaller`, lalu build.
4. Hasil ada di `dist\ImageCompressor.exe` — file ini portable, tinggal disalin/dijalankan di komputer Windows lain tanpa perlu install Python.

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
