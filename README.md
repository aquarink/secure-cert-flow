# Automated Certificate & Attendance Management System 📜⚡

Aplikasi berbasis web untuk memfasilitasi panitia acara (konferensi internasional, seminar nasional, webinar, dan lokakarya) dalam membuat, mengelola presensi kehadiran terverifikasi, serta menerbitkan dan mendistribusikan sertifikat secara massal dengan tata letak dinamis dan validasi anti-pemalsuan (*fraud-proof*).

---

## 🌟 Sorotan Fitur Utama

### 1. 📅 Kelola Acara
Pusat kendali untuk membuat dan mengatur detail konferensi atau webinar Anda sebelum mulai membuka presensi dan menerbitkan sertifikat.
* **Manajemen Terpusat**: Buat acara baru dengan detail lengkap (Nama Acara, Tanggal, Lokasi Aula/Daring, dan Deskripsi).
* **Keamanan Data**: Dilengkapi dengan fitur hapus acara yang ketat. Untuk mencegah ketidaksengajaan, pengguna diwajibkan melewati konfirmasi keamanan dengan mengetik kata **`HAPUS`** secara manual, mengingat tindakan ini akan menghapus seluruh data peserta, presensi, dan sertifikat yang terkait dengan acara tersebut.

---

### 2. 🎨 Template & Koordinat (*Visual Placement*)
Sistem kustomisasi sertifikat yang sangat interaktif dan fleksibel.
* **Upload Fleksibel**: Pengguna cukup mengunggah file gambar template sertifikat kosong (*naked certificate*) dan tanda tangan transparan (*PNG*).
* **Penempatan Dinamis**: Tidak ada posisi yang statis. Pengguna dapat menambahkan banyak titik area (teks, tanda tangan, atau QR Code) lalu mengatur koordinat X & Y secara presisi di atas gambar template.
* **Atur Parameter**: Setelah posisi dirasa pas, pengguna cukup klik tombol **"Tambah / Bubuhkan"**, lalu sebuah pop-up modal akan muncul untuk menamai parameter tersebut (misalnya `nama_peserta`, `judul_paper`, `institusi`, `peran`—tanpa menggunakan spasi).

---

### 3. 📑 Katalog Judul Paper (*Submissions*)
Sistem manajemen artikel ilmiah dan presentasi khusus untuk konferensi akademik.
* **Pencatatan Paper Terstruktur**: Mengelola kode paper, judul lengkap artikel, nama-nama penulis (*authors*), dan nama presenter utama.
* **Integrasi Otomatis**: Katalog judul paper ini terhubung langsung ke formulir presensi publik sehingga presenter dan author dapat mencari dan memilih paper mereka secara instan.

---

### 4. 📸 Presensi & Kehadiran Terverifikasi (*Attendance Management*)
Sistem manajemen kehadiran terpadu untuk memastikan sertifikat hanya diterbitkan bagi partisipan yang benar-benar hadir dan valid.
* **Generator Link & QR Code Unik**: Setiap acara secara otomatis memiliki tautan publik unik dan QR Code untuk ditampilkan di layar proyektor atau dicetak di lokasi acara.
* **Verifikasi Izin Perangkat (*Browser Permissions*)**: Formulir presensi publik secara otomatis memvalidasi izin akses Kamera dan Lokasi GPS (*Geotag*). Tombol submit akan terkunci jika izin belum diberikan.
* **Pengambilan Foto Kamera Langsung (*Live Photo Capture*)**: Peserta mengambil foto langsung melalui kamera browser (*live webcam / selfie*) saat check-in untuk mencegah manipulasi unggah file galeri.
* **Pencatatan Otomatis Geotagging & IP**: Sistem otomatis merekam titik koordinat GPS (Latitude & Longitude), alamat IP perangkat, dan *timestamp* presensi.
* **Penerbitan Sertifikat Satu Klik**: Panitia dapat langsung menerbitkan sertifikat resmi secara massal dari daftar hadir yang telah terverifikasi.

---

### 5. 📊 Import Data Partisipan (Excel Bulk)
Proses cepat untuk memasukkan ratusan hingga ribuan data partisipan tanpa ribet.
* **Upload Dokumen**: Panitia cukup mengunggah daftar partisipan berupa file spreadsheet (`.xlsx` atau `.csv`).
* **Pencocokan Otomatis**: Sistem secara otomatis mencocokkan header kolom pada file spreadsheet dengan nama parameter (seperti `nama_peserta`, `judul_paper`, `peran`) yang telah dibubuhkan pada menu Template.
* **Live Progress Bar**: Antarmuka dilengkapi bilah kemajuan pemrosesan yang memperbarui jumlah data selesai secara *real-time*.

---

### 6. 🛡️ Validasi & Klaim Sertifikat Anti-Pemalsuan
* **Keamanan Ekstra**: Setiap lembar sertifikat dilengkapi QR Code dan kode klaim unik alfanumerik (8 karakter) serta *checksum* integritas digital.
* **Portal Publik Peserta**: Peserta dapat memasukkan kode unik mereka di halaman klaim publik untuk mempratinjau gambar sertifikat beresolusi tinggi dan mengunduh sertifikat resmi mereka.
* **Pemeriksaan Keaslian Publik**: Siapa pun dapat memindai QR Code untuk memeriksa keaslian sertifikat secara langsung.

---

## 🖥️ Panduan Akses Antarmuka Web

| Menu / Halaman | Tautan Akses |
| :--- | :--- |
| **Halaman Utama** | `https://sertifikat.uinjakarta.id/` |
| **Dashboard Panitia** | `https://sertifikat.uinjakarta.id/dashboard` |
| **Login Panitia** | `https://sertifikat.uinjakarta.id/login` |
| **Form Presensi Publik** | `https://sertifikat.uinjakarta.id/attendance/{event_id}` |
| **Portal Klaim Publik (8-Char)** | `https://sertifikat.uinjakarta.id/claim` |
| **Verifikasi QR Anti-Pemalsuan** | `https://sertifikat.uinjakarta.id/verify/{claim_code}` |
| **Health Status Check** | `https://sertifikat.uinjakarta.id/health` |

---
*Dikembangkan untuk efisiensi, akurasi, dan integritas penerbitan sertifikat digital.*
