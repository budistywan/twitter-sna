# 🐦 Twitter SNA Scraper

Tool untuk scraping tweet & komentar Twitter/X secara otomatis di GitHub Actions, lalu menganalisis jaringan sosialnya (Social Network Analysis).

---

## 🚀 Cara Setup (5 Menit)

### 1. Fork / Clone repo ini ke GitHub kamu

### 2. Siapkan akun Twitter (gratis)
Kamu butuh minimal **1 akun Twitter** untuk scraping. Bisa pakai akun lama atau buat baru.

### 3. Tambahkan GitHub Secrets
Pergi ke **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Isi |
|-------------|-----|
| `TW_USERNAME` | Username Twitter (tanpa @) |
| `TW_PASSWORD` | Password Twitter |
| `TW_EMAIL` | Email Twitter |

### 4. Jalankan Scraper
Pergi ke tab **Actions → 🐦 Twitter Scraper → Run workflow**

Isi:
- **Search query**: `#indonesia` atau `kata kunci` atau `@username`
- **Max tweets**: `500` (bebas)

Klik **Run workflow** → tunggu ~2-5 menit → download hasilnya di bagian **Artifacts**.

---

## 📁 Output Files

Setelah scraping selesai, kamu akan mendapat file CSV di folder `data/`:

| File | Isi |
|------|-----|
| `tweets_*.csv` | Semua tweet lengkap dengan metadata |
| `nodes_*.csv` | Daftar user (untuk SNA nodes) |
| `edges_*.csv` | Daftar interaksi (untuk SNA edges) |

### Format `nodes_*.csv`
```
id, label, followers, following, tweet_count, total_likes, total_rts
```

### Format `edges_*.csv`
```
source, target, type, weight
```
- **type**: `reply` / `retweet` / `mention`
- **weight**: jumlah interaksi antara dua user

---

## 🕸️ Analisis SNA

### Opsi 1: Jupyter Notebook (lokal)
```bash
pip install pandas networkx matplotlib pyvis python-louvain
jupyter notebook notebooks/SNA_Analysis.ipynb
```

### Opsi 2: Gephi (GUI, mudah)
1. Download [Gephi](https://gephi.org/)
2. Import `nodes_*.csv` → **Data Laboratory → Import Spreadsheet**
3. Import `edges_*.csv` → sama
4. Gunakan layout **ForceAtlas2**
5. Jalankan **Modularity** untuk deteksi komunitas

### Opsi 3: Google Colab
Upload file CSV ke Colab, jalankan notebook `SNA_Analysis.ipynb`

---

## ⚠️ Catatan Penting

- `twscrape` menggunakan akun Twitter biasa (bukan API berbayar)
- Jangan scraping terlalu agresif → akun bisa kena rate limit sementara
- Disarankan max 500-1000 tweet per run
- Data disimpan 30 hari sebagai GitHub Artifact

---

## 📊 Metric SNA yang Dihasilkan

| Metric | Artinya |
|--------|---------|
| **Degree Centrality** | Seberapa banyak koneksi langsung |
| **In-Degree** | Seberapa sering di-reply/mention/RT |
| **Betweenness** | Seberapa sering jadi "jembatan" antar kelompok |
| **PageRank** | Pengaruh keseluruhan dalam jaringan |
| **Community** | Kelompok/kluster yang terbentuk |
