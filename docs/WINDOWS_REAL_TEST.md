# NVRA — Manual Test Guide (Windows 10 / 11)

Panduan ini untuk **QA / pengguna** yang memverifikasi **NVRAFX** pada mesin Windows nyata.  
Tidak menggantikan CI GitHub Actions; melengkapi validasi hardware, GUI, Task Scheduler, dan recovery.

| Item | Nilai |
|------|--------|
| Produk | **NVRAFX.exe** (bukan NVRA.exe / NUNG.exe) |
| LIVE default | **DISABLED** / fail-closed |
| Password di argv | **Dilarang** — gunakan prompt tersembunyi / token file |
| Environment | Windows 10 atau 11 x64 |

---

## 0. Prasyarat mesin

- [ ] Windows 10/11 x64, akun dengan hak membuat Scheduled Task (user biasa cukup untuk task *current user*).
- [ ] PowerShell 5.1+ atau PowerShell 7.
- [ ] Tidak menjalankan antivirus yang memblokir PyInstaller one-file tanpa pengecualian (jika di-quarantine, whitelist folder `C:\NVRA\`).
- [ ] Koneksi internet hanya jika menguji unduhan artifact dari GitHub (boleh offline setelah file lokal siap).

---

## 1. Persiapan — unduh & verifikasi artifact

### 1.1 Unduh dari GitHub Actions

1. Buka repositori: https://github.com/whatman42/nvra  
2. Tab **Actions** → workflow **Windows Build** (atau **NVRA CI and Windows Build**).  
3. Pilih run **terakhir yang SUCCESS** pada branch `main`.  
4. Di bagian **Artifacts**, unduh:
   - `nvrafx-windows-release` **atau**
   - `NVRAFX-Windows`
5. Ekstrak ZIP. Pastikan ada minimal:
   - `NVRAFX.exe`
   - `SHA256SUMS.txt` (jika tersedia di paket)

### 1.2 Verifikasi SHA-256

Di PowerShell (sesuaikan path unduhan):

```powershell
cd $HOME\Downloads\nvrafx-windows-release   # atau folder ekstraksi Anda
Get-FileHash .\NVRAFX.exe -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

- [ ] Hash `NVRAFX.exe` **sama** dengan baris di `SHA256SUMS.txt`.  
- [ ] Jika tidak cocok → **STOP**. Jangan jalankan binary. Ulangi unduhan dari run SUCCESS yang benar.

### 1.3 Letakkan di `C:\NVRA\`

```powershell
New-Item -ItemType Directory -Force -Path C:\NVRA | Out-Null
Copy-Item -Force .\NVRAFX.exe C:\NVRA\NVRAFX.exe
# Opsional: salin SHA256SUMS.txt dan manifest ke C:\NVRA\
Get-Item C:\NVRA\NVRAFX.exe | Format-List FullName, Length, LastWriteTime
```

- [ ] `C:\NVRA\NVRAFX.exe` ada dan ukuran masuk akal (ratusan MB untuk onefile ML build).

---

## 2. First-Run Enrollment

### 2.1 Jalankan aplikasi

```powershell
Start-Process -FilePath C:\NVRA\NVRAFX.exe
```

Atau double-click `C:\NVRA\NVRAFX.exe` di Explorer.

### 2.2 Enrollment akun baru

| Cek | Kriteria PASS |
|-----|----------------|
| Prefill username | Field username **kosong** (tidak ada default admin/demo) |
| Password | Input **tersembunyi** (mask), tidak terlihat di UI sebagai plain text |
| Password di process list | Tidak memasukkan password lewat argument baris perintah |
| Enrollment selesai | Akun terdaftar; aplikasi meminta / memungkinkan **login** |
| Setelah login | Sesi masuk tanpa error fatal; tidak ada dialog credential mentah di log layar |

- [ ] Enrollment PASS  
- [ ] Login PASS  

**Jangan** menyimpan password di file teks, screenshot, atau tiket bug.  
Jika gagal: catat **pesan error UI** saja (tanpa secret).

### 2.3 CLI opsional (tanpa GUI)

Jika menguji jalur CLI (dari sumber repo, bukan wajib untuk artifact onefile):

```powershell
# Password tidak boleh di argv — gunakan prompt interaktif getpass
# Contoh konsep: register / login via subcommand aplikasi
```

Untuk binary produksi, fokus pada **GUI enrollment** di atas.

---

## 3. Startup & GUI — state machine

Setelah login, amati **header / status bar** (atau panel status) selama startup.

Urutan yang diharapkan (nama label bisa sedikit berbeda, urutan konsep harus sama):

1. **LICENSE CHECK** (atau setara)  
2. **LOADING STATE** / LOAD_STATE  
3. **BROKER CONNECT**  
4. **RECONCILIATION**  
5. **RISK / GOVERNOR**  
6. **READY**  
7. **RUNNING**

| Cek | PASS jika |
|-----|-----------|
| Urutan | Tidak melompat ke RUNNING tanpa tahap sebelumnya (kecuali mode yang memang paper-only tanpa broker) |
| Error | Tidak ada crash / dialog fatal; error transient boleh retry |
| LIVE | Mode default **bukan** LIVE capital aktif; LIVE tetap gated |
| GUI | Window utama responsif setelah READY/RUNNING |

**Catat** di tabel pelaporan:

- Label yang terlihat di header  
- Waktu kasar sampai READY  
- Pesan error (jika ada), **tanpa** token/password/API key  

- [ ] Startup sequence PASS  
- [ ] GUI stabil PASS  

---

## 4. Auto-Start (Task Scheduler)

Skrip resmi ada di repositori sumber:

- `scripts\windows\register_autostart.ps1`  
- `scripts\windows\unregister_autostart.ps1`  

Clone atau unduh skrip tersebut ke mesin uji (artifact EXE saja tidak selalu menyertakan skrip).

### 4.1 Daftar task

Buka PowerShell **di folder repo** (atau path tempat skrip disalin):

```powershell
cd <path-ke-repo-nvra>
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows\register_autostart.ps1 -ExecutablePath "C:\NVRA\NVRAFX.exe"
```

### 4.2 Verifikasi task

```powershell
Get-ScheduledTask -TaskName "NVRA-AutoStart" | Format-List TaskName, State, TaskPath
(Get-ScheduledTask -TaskName "NVRA-AutoStart").Actions | Format-List
```

| Cek | PASS jika |
|-----|-----------|
| Nama task | `NVRA-AutoStart` |
| Action | Menunjuk ke `C:\NVRA\NVRAFX.exe` |
| Trigger | At logon (user saat ini) |
| Restart policy | Restart Count = **5**, interval ≈ **1 menit** (sesuai skrip) |

### 4.3 Restart PC

1. Simpan pekerjaan lain.  
2. **Restart** Windows.  
3. Login dengan user yang sama.  
4. Setelah desktop siap, cek:

```powershell
Get-Process -Name NVRAFX -ErrorAction SilentlyContinue
Get-ScheduledTask -TaskName "NVRA-AutoStart" | Select-Object State, LastRunTime, LastTaskResult
```

- [ ] `NVRAFX` berjalan otomatis setelah logon → PASS  
- [ ] Jika tidak: catat `LastTaskResult`, Event Viewer → Task Scheduler logs  

---

## 5. Crash Recovery

Dengan task `NVRA-AutoStart` masih terdaftar dan aplikasi sedang berjalan:

1. Buka **Task Manager** (`Ctrl+Shift+Esc`).  
2. Tab **Details** / **Proses** → pilih **NVRAFX.exe** → **End task**.  
3. **Tunggu ± 1 menit** (sesuai `RestartInterval` skrip).  
4. Cek apakah proses muncul kembali:

```powershell
Get-Process -Name NVRAFX -ErrorAction SilentlyContinue
Get-ScheduledTaskInfo -TaskName "NVRA-AutoStart" | Format-List *
```

| Cek | PASS jika |
|-----|-----------|
| Restart otomatis | Proses `NVRAFX` muncul lagi dalam ~1–2 menit |
| Batas restart | Policy maksimal **5** kali restart (jangan harapkan infinite restart) |
| Setelah 5 gagal beruntun | Task bisa berhenti me-restart — itu **sesuai desain**, bukan bug |

Ulangi kill **sekali** saja untuk tes normal; jangan sengaja menghabiskan 5 restart kecuali menguji batas.

- [ ] Recovery setelah 1 kill → PASS / FAIL  

---

## 6. Unregister Auto-Start

```powershell
cd <path-ke-repo-nvra>
.\scripts\windows\unregister_autostart.ps1 -ExecutablePath "C:\NVRA\NVRAFX.exe"
Get-ScheduledTask -TaskName "NVRA-AutoStart" -ErrorAction SilentlyContinue
```

| Cek | PASS jika |
|-----|-----------|
| Task hilang | `Get-ScheduledTask` tidak menemukan `NVRA-AutoStart` (atau skrip mencetak *not registered*) |
| Proses | Aplikasi yang sedang jalan **tidak** wajib mati; hanya task yang dihapus |

Opsional: restart sekali lagi dan pastikan **tidak** auto-start.

- [ ] Unregister PASS  

---

## 7. Pelaporan hasil

Isi tabel berikut. Lampirkan screenshot **hanya** untuk FAIL (blur data sensitif).

| # | Skenario | Hasil (PASS/FAIL) | Catatan / bukti |
|---|----------|-------------------|-----------------|
| 1 | SHA-256 cocok | | Hash (boleh partial: 8 karakter awal + akhir) |
| 2 | First-run enrollment | | Prefill? Mask password? |
| 3 | Login setelah enrollment | | |
| 4 | Startup state sequence | | Label yang terlihat |
| 5 | GUI READY/RUNNING stabil | | |
| 6 | Register `NVRA-AutoStart` | | |
| 7 | Auto-start setelah reboot | | LastTaskResult |
| 8 | Crash recovery (1× kill) | | |
| 9 | Unregister task | | |
| 10 | Tidak ada secret di log/screenshot | | |

### Jika FAIL

Lampirkan:

1. Screenshot UI error (sensor password/token).  
2. Cuplikan log aplikasi **jika** ada file log di folder data user — **hapus** baris yang berisi token, password, API key.  
3. Output:

```powershell
Get-ScheduledTask -TaskName "NVRA-AutoStart" -ErrorAction SilentlyContinue | Format-List *
Get-FileHash C:\NVRA\NVRAFX.exe -Algorithm SHA256
```

4. Versi Windows: `winver` atau:

```powershell
[System.Environment]::OSVersion.VersionString
```

**Jangan** lampirkan: password, session token, API key broker, isi Credential Manager.

---

## 8. Batasan & peringatan

- **LIVE** dapat menghasilkan transaksi nyata jika di-ARM dan capital di-unlock di masa depan. Default distribusi: **fail-closed**, capital blocked.  
- Tes ini **tidak** mensyaratkan order LIVE ke broker.  
- Artifact **unsigned** (Authenticode belum wajib di pipeline saat panduan ini ditulis): andalkan SHA-256 dari Actions yang Anda percayai.  
- Onefile PyInstaller kadang memicu false positive antivirus — dokumentasikan produk/vendor jika di-quarantine.

---

## 9. Referensi cepat

| Sumber | Lokasi |
|--------|--------|
| Auto-start register | `scripts/windows/register_autostart.ps1` |
| Auto-start unregister | `scripts/windows/unregister_autostart.ps1` |
| Docs auto-start | `docs/AUTOSTART.md` |
| LIVE validation (dev) | `LIVE_VALIDATION.md` |
| Actions (artifact) | https://github.com/whatman42/nvra/actions |

---

*Dokumen QA manual — tidak mengubah perilaku runtime aplikasi.*
