# 🌿 PhyloCraft — Visual Evolutionary Biology Workbench

> **專為生物學家、演化學者與非程式背景學生設計的現代圖形化演化分析與建樹工作台**
> 
> *A modern, intuitive GUI workbench integrating NCBI data retrieval, MSA, alignment trimming, phylogenetic tree inference, and publication-ready tree visualization.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt-41CD52?style=flat&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Alpha%20%2F%20Active%20Development-orange.svg)]()

---

## 💡 為什麼需要打造 PhyloCraft？

在生命科學、演化生物學、農學與醫學領域中，研究人員與學生進行親緣關係與分子演化分析時，常面臨極高的「技術門檻與環境痛點」：

1. **格式相容地獄**：FASTA、PHYLIP（Strict 限制 10 字元 / Relaxed）、NEXUS 各自為政；序列名稱常因空格、冒號、垂直線或特殊符號導致建樹程式中斷閃退。
2. **工具鏈割裂**：物種基因檢索（NCBI 網頁）、多序列比對（MAFFT）、比對修剪（trimAl）、模式檢驗與建樹（IQ-TREE 2/3）、樹圖美化（FigTree）分散在十多個不同軟體，研究者需耗費大量時間手動複製貼上與格式轉換。
3. **終端機指令與環境門檻**：在 Windows 上配置 Linux 工具、WSL、MinGW 或系統環境變數（PATH）繁瑣易錯，非資訊背景學生極易遭遇挫折。
4. **科研再現性（Reproducibility）缺失**：多步驟分析中的各參數設定、軟體版本與過濾閾值難以完整被記錄追蹤。

**PhyloCraft 的核心願景**：
以 **「極致防呆、模組化、可視化、完全免配置 PATH」** 為理念，將國際頂尖命令列演化分析工具與自研視覺化介面融為一體，讓研究者只需專注在生物學科學問題本身。

---

## ✨ 核心功能特色 (Key Features)

```
🌿 PhyloCraft 系統架構
 ├── ⚡ 1. 一鍵黃金管線 (One-Click Golden Pipeline)
 ├── 🧬 2. NCBI 智慧同源基因擷取 (NCBI Ortholog & Gene Extractor)
 ├── 🧩 3. 畫布式積木工作台 (Visual Block Pipeline Canvas)
 ├── 🧹 4. 序列防呆清洗與格式轉換 (Sanitizer & Format Converter)
 ├── 🔬 5. 多序列比對與矩陣檢視 (MAFFT & MSA Visualizer)
 ├── ✂️ 6. 比對智慧修剪與報告 (trimAl Trimming & HTML Report)
 ├── 🌳 7. 系統發育推論建樹 (IQ-TREE 3/2 & FastTree 2)
 ├── 👁️ 8. 發表級演化樹檢視器 (Publication-Ready Tree Viewer, 300 DPI / SVG)
 ├── 📑 9. 電子實驗記錄簿與日誌 (Electronic Lab Notebook, ELN)
 ├── 📦 10. 多基因超矩陣串聯 (Matrix Concatenator & Partition)
 └── ⚙️ 11. 核心工具箱與自動安裝 (Tool Manager & Auto Downloader)
```

### 1. ⚡ 一鍵黃金管線 (One-Click Golden Pipeline)
* 學生只需匯入原始 FASTA 序列，點擊「🚀 開始一鍵分析」，工作台將全自動非同步執行：
  $$\text{序列防呆清洗} \longrightarrow \text{MAFFT 高精度比對} \longrightarrow \text{trimAl 智慧修剪} \longrightarrow \text{IQ-TREE 自動選模式與 ML 建樹}$$
* 分析結束後自動提示並一鍵跳轉至互動式演化樹畫布。

### 2. 🧬 NCBI 智慧同源基因擷取 (NCBI Entrez Gene Extractor)
* **告別手動繁瑣下載**：直接輸入物種階層（例如 Primates、Carnivora、Cetartiodactyla）與目標基因（如 TP53、CYTB、MB、RB1）。
* **全自動支系擴展與同源檢索**：自動透過 NCBI Entrez API 解析演化群物種，精準挑選代表性序列。
* **雙重輸出格式**：支援同時輸出高品質 RefSeq 核酸序列（Coding Sequence / mRNA）與對應蛋白質序列。
* **科研溯源記錄**：每次檢索自動生成對應的 `.provenance.csv` 與 `.provenance.md` 追蹤清單，詳細記載 NCBI Accession、物種學名、分類節點與下載時間戳記。

### 3. 🧩 畫布式積木分析工作台 (Visual Block Pipeline Canvas)
* 啟發自 Scratch 的可視化積木分析介面，支援自由拖曳、排列與連結演化分析節點。
* 節點具備即時參數配置抽屜，適合跨領域教學、工作流客製化與直觀演示。

### 4. 🧹 序列防呆清洗與多格式轉換 (Sanitizer & Converter)
* **全自動字元消洗**：智慧過濾序列 ID 中的非法字元（空格、`:`、`|`、`()`、`[]` 等）並替換為安全底線 `_`。
* **重複 ID 自動修正**：自動偵測重複序列名稱並加上編號或警告。
* **多格式無痛轉換**：支援一鍵互相轉換為 **FASTA**、**PHYLIP Relaxed**、**PHYLIP Strict (嚴格 10 字元限縮)**、**NEXUS**、**Clustal** 格式。
* **基礎序列特徵統計**：自動判斷序列型態（DNA / RNA / Protein），計算 GC 含量分佈、序列長度與 Gap 缺口佔比。

### 5. 🔬 多序列比對 (MAFFT) 與 MSA 矩陣檢視
* 支援多種經典演化比對演算法：`auto`、`L-INS-i`（高精準度結構比對）、`G-INS-i`、`E-INS-i`、`FFT-NS-2`。
* 支援自動方向校準（`--adjustdirection`），自動反轉互補方向顛倒的序列。
* 內建 MSA 彩色比對矩陣檢視元件，直觀掌握同源保守區與變異位點。

### 6. ✂️ 比對修剪過濾 (trimAl)
* 內建啟發式演算法推薦模式：`automated1`（專為 ML 建樹優化）、`gappyout`、`strict`、`strictplus`。
* 支援自訂 Gap Threshold（`-gt`）與 Similarity Threshold（`-st`）。
* 支援直接生成與預覽互動式 HTML 修剪比對報告。

### 7. 🌳 系統發育建樹 (IQ-TREE 3 / 2 & FastTree 2)
* **IQ-TREE 3 / 2**：世界頂尖最大概似法（Maximum Likelihood）推論，內建 **ModelFinder Plus (MFP)** 自動依 BIC/AIC/AICc 挑選最佳核酸/胺基酸取代模式；支援極速拔靴法（Ultrafast Bootstrap, UFBoot 1000 次）與 SH-aLRT 檢驗。
* **FastTree 2**：針對萬條以上超大規模序列提供極速 ML 建樹推論。

### 8. 👁️ 發表級互動演化樹檢視器 (Tree Viewer)
* 支援載入任何標準 Newick 樹檔（`.treefile`, `.nwk`, `.tree`）。
* **視覺自訂性高**：可自由切換分支長度（Phylogram / Cladogram）、開關 Bootstrap 支持度數值顯示與高亮條件。
* **發表級輸出**：支援暗色科技風與期刊標準白底配色切換，可直接匯出一鍵 **300 DPI 發表級圖片（PNG、向量圖 SVG、PDF）** 或複製 Newick 字串。

### 9. 📑 電子實驗記錄簿 (Electronic Lab Notebook, ELN)
* 全程紀錄每個步驟的軟體版本、命令參數、輸入輸出檔校驗碼與時間戳記。
* 自動彙整為可直接複製到論文 Supplementary Materials 的可重複性標準報告。

### 10. 📦 多基因超矩陣串聯 (Matrix Concatenator & Partition)
* 批次載入多個單基因 FASTA，自動對齊物種並將缺失基因補齊為 `?`，自動生成 Supermatrix。
* 自動輸出 IQ-TREE、RAxML 或 NEXUS 分區模型檔案（Partition File，支援密碼子 1st/2nd/3rd 位點分區）。

### 11. ⚙️ 核心工具箱與自動下載 (Tool Manager)
* **完全免手動配置環境變數**：內建官方二進位工具自動下載安裝器，點擊即可由官方來源自動下載並配置 `iqtree2/3`、`trimal`、`mafft` 與 `FastTree`。

---

## 🚀 快速啟動 (Quick Start)

### 系統需求
* **作業系統**：Windows 10 / 11（64-bit）
* **Python 環境**：Python 3.10 以上

### 安裝步驟

1. **取得專案原始碼**：
   ```bash
   git clone https://github.com/YOUR-USERNAME/PhyloCraft.git
   cd PhyloCraft
   ```

2. **安裝 Python 相依套件**：
   ```bash
   pip install -r requirements.txt
   ```

3. **啟動應用程式**：
   * **方式一（雙擊啟動）**：在專案根目錄下，直接雙擊 **`run.bat`** 即可！
   * **方式二（終端機啟動）**：
     ```bash
     python main.py
     ```

4. **下載演化分析工具**：
   * 第一次啟動後，至 **「⚙️ 核心工具」** 頁籤，點擊「一鍵自動下載安裝」，程式會自動從官方安全管道下載配置 `mafft`、`trimal`、`iqtree3` 與 `FastTree`。

---

## 📁 專案目錄結構

```text
PhyloCraft/
├── data/                      # 測試範例與標竿資料集
├── src/
│   ├── config.py              # 全域路徑設定與工具偵測
│   ├── core/                  # 核心演化邏輯與分析引擎
│   │   ├── sanitizer.py       # 序列清洗防呆與統計
│   │   ├── converter.py       # 多格式互相轉換
│   │   ├── concatenator.py    # 多基因超矩陣與分區產生器
│   │   ├── gene_extractor.py  # NCBI Entrez 同源基因自動解析引擎
│   │   ├── eln_generator.py   # 電子實驗記錄簿與科研再現性產生器
│   │   ├── tools_installer.py # 官方二進位工具自動下載解壓器
│   │   └── runners/           # 外部工具非同步行程調用器
│   │       ├── base_runner.py
│   │       ├── mafft_runner.py
│   │       ├── trimal_runner.py
│   │       ├── iqtree_runner.py
│   │       └── modelfinder_runner.py
│   └── ui/                    # PySide6 / Qt 現代桌面圖形介面
│       ├── styles.py          # 深色科技風現代 QSS 樣式表
│       ├── main_window.py     # 主視窗導航與多頁籤架構
│       ├── widgets/           # 自訂 UI 元件 (積木工作台、樹畫布、MSA檢視、日誌)
│       └── tabs/              # 11 大分析功能頁籤
├── tests/                     # 完整單元測試與防禦性稽核套件
├── scripts/                   # 論文標竿驗證與批次輔助腳本
├── main.py                    # 應用程式啟動入口
├── run.bat                    # Windows 一鍵啟動批次檔
├── requirements.txt           # Python 相依套件清單
├── LICENSE                    # MIT 開源授權協議
└── README.md                  # 專案詳細說明文件
```

---

## 🙏 學術引用與致謝 (Acknowledgements & Citations)

PhyloCraft 整合並自動化了多款國際知名的開源演化生物學計算軟體。若您在學術研究中使用了 PhyloCraft，請務必同時引用以下底層演算法之原始論文：

* **IQ-TREE 2 / 3**:
  > Minh, B. Q., Schmidt, H. A., Chernomor, O., Schrempf, D., Woodhams, M. D., von Haeseler, A., & Lanfear, R. (2020). IQ-TREE 2: New models and efficient methods for phylogenomic inference in the genomic era. *Molecular Biology and Evolution*, 37(5), 1530-1534.
* **ModelFinder**:
  > Kalyaanamoorthy, S., Minh, B. Q., Wong, T. K., von Haeseler, A., & Jermiin, L. S. (2017). ModelFinder: fast model selection for accurate phylogenetic estimates. *Nature Methods*, 14(6), 587-589.
* **MAFFT**:
  > Katoh, K., & Standley, D. M. (2013). MAFFT multiple sequence alignment software version 7: improvements in performance and usability. *Molecular Biology and Evolution*, 30(4), 772-780.
* **trimAl**:
  > Capella-Gutiérrez, S., Silla-Martínez, J. M., & Gabaldón, T. (2009). trimAl: a tool for automated alignment trimming in large-scale phylogenetic analyses. *Bioinformatics*, 25(15), 1972-1973.
* **FastTree 2**:
  > Price, M. N., Dehal, P. S., & Arkin, A. P. (2010). FastTree 2–approximately maximum-likelihood trees for large alignments. *PLoS ONE*, 5(3), e9490.

---

## 📄 開源授權 (License)

本專案基於 **[MIT License](LICENSE)** 開源授權發布，歡迎學術研究、教學與二次開發自由使用。
