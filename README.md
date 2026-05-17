# Multiple Gmail Account Storage 🦊🛡️

A secure, isolated browser launcher for managing multiple Gmail/Google accounts using [Camoufox](https://camoufox.com/python). 
Designed to bypass strict fingerprinting, prevent cross-contamination between accounts, and ensure privacy.

## ✨ Fitur Utama
- **Isolasi Penuh:** Setiap akun (grup) berjalan di profil browser (user data dir) yang benar-benar terpisah. Cookies, cache, dan sesi tidak akan pernah bocor antar akun.
- **Bypass Fingerprinting:** Menggunakan konfigurasi Camoufox untuk menghindari deteksi *bot/fraud* dari sistem keamanan Google.
- **Penyesuaian Resolusi (Anti-Clipping):** Memaksa resolusi *viewport* (1200x700) agar sesuai dengan tampilan monitor Windows, mencegah terdeteksinya ukuran layar yang tidak wajar.
- **Log Aktivitas Lengkap:** Melacak semua error, navigasi, dan informasi teknis browser secara *real-time* ke folder `logs/` (dengan sistem filter otomatis untuk URL sensitif).
- **Keamanan Path Traversal:** Validasi input ketat saat membuka profil, mencegah akses folder di luar sistem (Path Traversal Protection).

## 🚀 Cara Penggunaan

1. Pastikan Anda sudah menginstal Python (disarankan versi 3.10+).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Jalankan melalui script **Batch** (Sangat disarankan):
   - Klik ganda pada `Buka_Grup.bat`
   - Masukkan nama grup (Contoh: `Grup_1`, `akun_kerja`, dll)
   - Browser Camoufox akan terbuka dan sesi Anda akan tersimpan otomatis.

*Atau via terminal:*
```bash
python jalankan_grup.py <nama_grup>
```

## 📂 Struktur Log
Log disimpan di folder `/logs` dengan format penamaan per hari:
`YYYY-MM-DD_<nama_grup>.log`
Log akan memfilter otomatis URL sensitif (seperti `accounts.google.com`) demi privasi, namun tetap mencatat aktivitas navigasi lain dan info teknis browser.

## 🛡️ Catatan Keamanan
Repositori ini sudah dilengkapi dengan `.gitignore` ketat. **JANGAN PERNAH** menghapus atau mengubah aturan di `.gitignore` untuk mencegah data profil, *cookies*, dan histori penelusuran Anda (folder `Grup_*`) bocor ke publik jika Anda melakukan *push* ke repositori eksternal.

## 📄 Lisensi
Distributed under the MIT License. See `LICENSE` for more information.
