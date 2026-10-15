"""
NCBI Target Gene Extractor Dialog (特定基因自動檢索與攫取視窗)
Provides an interactive GUI for researchers to extract specific target genes
(e.g., Cytb, COX1/COI, 16S, rbcL, matK, Spike) from NCBI GenBank via Feature Table parsing.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QPushButton,
    QProgressBar,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import QThread, Signal, Qt
from src.core.gene_extractor import GeneExtractor, GeneExtractionResult
from src.config import DATA_DIR, OUTPUT_DIR


PRESETS = {
    "全球熊科全物種 Cytb (Krause 2008)": {
        "gene": "CYTB",
        "taxa": (
            "NC_009492.1  # 大貓熊 (Ailuropoda melanoleuca)\n"
            "NC_009969.1  # 眼鏡熊 (Tremarctos ornatus)\n"
            "NC_009970.1  # 懶熊 (Melursus ursinus)\n"
            "NC_009968.1  # 馬來熊 (Helarctos malayanus)\n"
            "NC_009971.1  # 亞洲黑熊 (Ursus thibetanus)\n"
            "NC_003426.1  # 美洲黑熊 (Ursus americanus)\n"
            "NC_003427.1  # 棕熊 (Ursus arctos)\n"
            "NC_003428.1  # 北極熊 (Ursus maritimus)\n"
            "NC_001325.1  # 港海豹 (Phoca vitulina 外群)\n"
            "NC_002008.4  # 家犬 (Canis lupus familiaris 外群)"
        )
    },
    "鯨偶蹄目演化 Cytb (Montgelard 1997)": {
        "gene": "CYTB",
        "taxa": (
            "NC_000889.1  # 河馬 (Hippopotamus amphibius)\n"
            "NC_001321.1  # 長鬚鯨 (Balaenoptera physalus)\n"
            "NC_006853.1  # 牛 (Bos taurus)\n"
            "NC_000845.1  # 豬 (Sus scrofa)\n"
            "NC_001640.1  # 馬 (Equus caballus 外群)"
        )
    },
    "靈長類經典演化 Cytb (Hayasaka 1988)": {
        "gene": "CYTB",
        "taxa": (
            "NC_012920.1  # 智人 (Homo sapiens)\n"
            "NC_001643.1  # 黑猩猩 (Pan troglodytes)\n"
            "NC_001645.1  # 大猩猩 (Gorilla gorilla)\n"
            "NC_002083.1  # 紅毛猩猩 (Pongo abelii)\n"
            "NC_005943.1  # 恆河猴 (Macaca mulatta)\n"
            "NC_004025.1  # 環尾狐猴 (Lemur catta 外群)"
        )
    },
    "冠狀病毒 Spike 刺突蛋白 (Zhou 2020)": {
        "gene": "S",
        "taxa": (
            "NC_045512.2  # SARS-CoV-2 (Wuhan-Hu-1)\n"
            "MN996532.2   # 蝙蝠冠狀病毒 (Bat CoV RaTG13)\n"
            "NC_004718.3  # 2003 SARS 病毒 (SARS-CoV Tor2)\n"
            "MG772933.1   # 蝙蝠 SARS 樣病毒 (Bat SARS-like ZC45)\n"
            "NC_019843.3  # MERS 冠狀病毒 (MERS-CoV 外群)"
        )
    }
}


class ExtractionWorker(QThread):
    progress_signal = Signal(int, int, str)
    log_signal = Signal(str)
    finished_signal = Signal(object)  # GeneExtractionResult

    def __init__(self, targets: list[str], target_gene: str, out_file: Path):
        super().__init__()
        self.targets = targets
        self.target_gene = target_gene
        self.out_file = out_file

    def run(self):
        extractor = GeneExtractor()

        def on_prog(curr, total, msg):
            self.progress_signal.emit(curr, total, msg)
            self.log_signal.emit(f"[{curr}/{total}] {msg}")

        result = extractor.extract_target_genes(
            targets=self.targets,
            target_gene=self.target_gene,
            output_fasta=self.out_file,
            progress_callback=on_prog,
        )
        self.finished_signal.emit(result)


class GeneExtractorDialog(QDialog):
    """
    Dialog allowing researchers to fetch and extract specific genes (CDS/rRNA)
    directly from NCBI GenBank by accession number or species presets.
    """

    gene_extracted_signal = Signal(str)  # Emits output FASTA path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NCBI 特定基因精準攫取器 (NCBI Target Gene Extractor)")
        self.resize(720, 560)
        self.extracted_fasta_path = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header Info
        header = QLabel(
            "<b>🧬 特定基因自動檢索與座標精準攫取器 (Target Gene Extractor)</b><br>"
            "<span style='color: #64748B; font-size: 11px;'>"
            "由全基因組或粒線體組之註解特徵表 (Feature Table) 自動鎖定 CDS/rRNA 座標，"
            "處理正負股反向互補並裁切出精準長度之編碼序列，直接導出乾淨 FASTA。"
            "</span>"
        )
        layout.addWidget(header)

        # Config Box
        cfg_box = QGroupBox("1. 設定目標基因與經典範例")
        cfg_grid = QGridLayout(cfg_box)

        cfg_grid.addWidget(QLabel("目標基因代號:"), 0, 0)
        self.gene_combo = QComboBox()
        self.gene_combo.setEditable(True)
        self.gene_combo.addItems([
            "CYTB (粒線體細胞色素 b, ~1140 bp)",
            "COX1 / COI (細胞色素 c 氧化酶 I, DNA 條形碼)",
            "16S (16S 核糖體 RNA)",
            "12S (12S 核糖體 RNA)",
            "rbcL (植物葉綠體二磷酸核酮糖羧化酶)",
            "matK (植物葉綠體成熟酶 K)",
            "S / Spike (冠狀病毒刺突醣蛋白, ~3800 bp)",
            "ND1 (NADH 脫氫酶 1)",
            "ND2 (NADH 脫氫酶 2)"
        ])
        cfg_grid.addWidget(self.gene_combo, 0, 1)

        cfg_grid.addWidget(QLabel("載入經典文獻範例:"), 0, 2)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("-- 請選擇論文範例或手動輸入 --")
        for p_name in PRESETS.keys():
            self.preset_combo.addItem(p_name)
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        cfg_grid.addWidget(self.preset_combo, 0, 3)

        layout.addWidget(cfg_box)

        # Input Box
        input_box = QGroupBox("2. 輸入 NCBI 登錄號 (Accession List) 或本機 GenBank 檔路徑")
        in_layout = QVBoxLayout(input_box)
        self.taxa_edit = QTextEdit()
        self.taxa_edit.setPlaceholderText(
            "請每行輸入一個 NCBI 登錄號 (例如 NC_003428.1)，可於後方加上 '#' 附註物種名稱..."
        )
        in_layout.addWidget(self.taxa_edit)
        layout.addWidget(input_box)

        # Output Box
        out_box = QGroupBox("3. 導出設定與執行進度")
        out_layout = QVBoxLayout(out_box)

        f_row = QHBoxLayout()
        f_row.addWidget(QLabel("儲存 FASTA 路徑:"))
        self.out_path_edit = QLineEdit(str(DATA_DIR / "extracted_target_genes.fasta"))
        f_row.addWidget(self.out_path_edit)
        browse_btn = QPushButton("瀏覽...")
        browse_btn.clicked.connect(self.browse_output)
        f_row.addWidget(browse_btn)
        out_layout.addLayout(f_row)

        self.prog_bar = QProgressBar()
        self.prog_bar.setValue(0)
        self.prog_bar.setFormat("準備就緒")
        out_layout.addWidget(self.prog_bar)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(100)
        out_layout.addWidget(self.log_edit)

        layout.addWidget(out_box)

        # Button Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.fetch_btn = QPushButton("🚀 開始自 NCBI 擷取基因")
        self.fetch_btn.setFixedHeight(34)
        self.fetch_btn.setObjectName("primary_button")
        self.fetch_btn.clicked.connect(self.start_extraction)
        btn_row.addWidget(self.fetch_btn)

        self.cancel_btn = QPushButton("關閉")
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)

    def on_preset_changed(self, text: str):
        if text in PRESETS:
            p_data = PRESETS[text]
            # Set gene
            g_sym = p_data["gene"]
            for idx in range(self.gene_combo.count()):
                if self.gene_combo.itemText(idx).startswith(g_sym):
                    self.gene_combo.setCurrentIndex(idx)
                    break
            self.taxa_edit.setPlainText(p_data["taxa"])

    def browse_output(self):
        f, _ = QFileDialog.getSaveFileName(self, "選取 FASTA 儲存路徑", str(DATA_DIR), "FASTA Files (*.fasta *.fa)")
        if f:
            self.out_path_edit.setText(f)

    def start_extraction(self):
        raw_text = self.taxa_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "輸入為空", "請輸入至少一個 NCBI 登錄號！")
            return

        # Parse target gene
        combo_txt = self.gene_combo.currentText().strip()
        target_gene = combo_txt.split()[0].split("/")[0].strip()

        # Parse accessions (ignore comments after #)
        targets = []
        for line in raw_text.splitlines():
            line_clean = line.split("#")[0].strip()
            if line_clean:
                targets.append(line_clean)

        if not targets:
            QMessageBox.warning(self, "輸入無效", "未解析到有效登錄號！")
            return

        out_path = Path(self.out_path_edit.text().strip())
        self.fetch_btn.setEnabled(False)
        self.log_edit.clear()
        self.prog_bar.setValue(10)
        self.prog_bar.setFormat("正在連線 NCBI E-Utilities 擷取特徵表...")

        self.worker = ExtractionWorker(targets, target_gene, out_path)
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.log_signal.connect(self.log_edit.append)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, curr: int, total: int, msg: str):
        pct = int(curr / total * 90) + 10
        self.prog_bar.setValue(pct)
        self.prog_bar.setFormat(f"進度: {curr}/{total}")

    def on_finished(self, result: GeneExtractionResult):
        self.fetch_btn.setEnabled(True)
        self.prog_bar.setValue(100)
        self.prog_bar.setFormat("擷取完畢")

        if result.success:
            self.extracted_fasta_path = result.output_fasta
            self.log_edit.append(f"\n🎉 成功！已導出乾淨 FASTA: {result.output_fasta}")
            QMessageBox.information(
                self,
                "擷取成功",
                f"成功擷取 {result.total_extracted} 筆 {result.records[0].gene_symbol} 基因序列！\n"
                f"檔案已儲存至:\n{result.output_fasta}\n\n已自動載入至序列檢查清洗頁面。"
            )
            self.gene_extracted_signal.emit(result.output_fasta)
            self.accept()
        else:
            QMessageBox.critical(self, "擷取失敗", f"未能擷取到特定基因:\n{result.message}")
