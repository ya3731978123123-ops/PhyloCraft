"""
NCBI Gene Extractor & Provenance Audit Tab (🌐 NCBI 基因檢索與全透明溯源擷取頁面)
A dedicated, independent module for retrieving specific target genes from NCBI GenBank,
slicing exact CDS coordinates via Feature Tables, and producing 100% auditable provenance reports.
"""

import re
import urllib.parse
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QTextEdit,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QFrame,
    QScrollArea,
    QSplitter,
    QSizePolicy,
)
from PySide6.QtCore import QThread, Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QColor
from src.core.gene_extractor import GeneExtractor, ExtractedGeneRecord, GeneExtractionResult
from src.config import DATA_DIR, OUTPUT_DIR


NCBI_PRESETS = {
    "被子植物乙烯受體 ETR1 (Ethylene Receptors)": {
        "gene": "ETR1",
        "taxa": (
            "NM_105305.4    # 擬南芥 (Arabidopsis thaliana ETR1, 2217 bp)\n"
            "NM_001247220.2 # 番茄 (Solanum lycopersicum ETR1, 2265 bp)\n"
            "NM_001402333.1 # 水稻 (Oryza sativa ETR2, 2292 bp)\n"
            "NM_001325388.1 # 菸草 (Nicotiana tabacum ETR1, 2217 bp)\n"
            "XM_002311633.4 # 毛果楊 (Populus trichocarpa ETR2, 2289 bp)\n"
            "XM_003556299.5 # 大豆 (Glycine max ETR2, 2289 bp)"
        )
    },
    "植物中文俗名直接輸入範本 (無登錄號也能查)": {
        "gene": "ETR1",
        "taxa": (
            "擬南芥\n"
            "番茄\n"
            "水稻\n"
            "菸草\n"
            "毛果楊\n"
            "大豆\n"
            "玉米\n"
            "茶樹"
        )
    },
    "被子植物葉綠體 rbcL (光合作用核心)": {
        "gene": "RBCL",
        "taxa": (
            "NC_000932.1  # 擬南芥 (Arabidopsis thaliana, 1431 bp)\n"
            "NC_001666.2  # 玉米 (Zea mays, 1431 bp)\n"
            "NC_001320.1  # 水稻 (Oryza sativa, 1431 bp)\n"
            "NC_007898.3  # 番茄 (Solanum lycopersicum, 1431 bp)\n"
            "NC_020019.1  # 茶樹 (Camellia sinensis, 1431 bp)\n"
            "NC_007942.1  # 大豆 (Glycine max, 1431 bp)\n"
            "NC_016986.1  # 銀杏 (Ginkgo biloba 裸子植物外群, 1431 bp)"
        )
    },
    "全球熊科全物種 Cytb (Krause 2008 BMC Evol Biol)": {
        "gene": "CYTB",
        "taxa": (
            "NC_009492.1  # 大貓熊 (Ailuropoda melanoleuca, 1140 bp)\n"
            "NC_009969.1  # 眼鏡熊 (Tremarctos ornatus, 1140 bp)\n"
            "NC_009970.1  # 懶熊 (Melursus ursinus, 1140 bp)\n"
            "NC_009968.1  # 馬來熊 (Helarctos malayanus, 1140 bp)\n"
            "NC_009971.1  # 亞洲黑熊 (Ursus thibetanus, 1140 bp)\n"
            "NC_003426.1  # 美洲黑熊 (Ursus americanus, 1140 bp)\n"
            "NC_003427.1  # 棕熊 (Ursus arctos, 1140 bp)\n"
            "NC_003428.1  # 北極熊 (Ursus maritimus, 1140 bp)\n"
            "NC_001325.1  # 港海豹 (Phoca vitulina 外群, 1140 bp)\n"
            "NC_002008.4  # 家犬 (Canis lupus familiaris 外群, 1140 bp)"
        )
    },
    "鯨偶蹄目演化革命 Cytb (Montgelard 1997 MBE)": {
        "gene": "CYTB",
        "taxa": (
            "NC_000889.1  # 河馬 (Hippopotamus amphibius, 1140 bp)\n"
            "NC_001321.1  # 長鬚鯨 (Balaenoptera physalus, 1140 bp)\n"
            "NC_006853.1  # 牛 (Bos taurus, 1140 bp)\n"
            "NC_000845.1  # 豬 (Sus scrofa, 1140 bp)\n"
            "NC_001640.1  # 馬 (Equus caballus 奇蹄目外群, 1140 bp)"
        )
    },
    "靈長類粒線體 Cytb (Hayasaka 1988 MBE)": {
        "gene": "CYTB",
        "taxa": (
            "NC_012920.1  # 智人 (Homo sapiens, 1140 bp)\n"
            "NC_001643.1  # 黑猩猩 (Pan troglodytes, 1140 bp)\n"
            "NC_001645.1  # 大猩猩 (Gorilla gorilla, 1140 bp)\n"
            "NC_002083.1  # 蘇門答臘紅毛猩猩 (Pongo abelii, 1140 bp)\n"
            "NC_005943.1  # 恆河猴 (Macaca mulatta, 1141 bp)\n"
            "NC_004025.1  # 環尾狐猴 (Lemur catta 原猴外群, 1140 bp)"
        )
    },
    "冠狀病毒 Spike 刺突蛋白 (Zhou 2020 Nature)": {
        "gene": "S",
        "taxa": (
            "NC_045512.2  # 新型冠狀病毒 (SARS-CoV-2 Wuhan-Hu-1, 3822 bp)\n"
            "MN996532.2   # 菊頭蝠冠狀病毒 (Bat CoV RaTG13, 3810 bp)\n"
            "NC_004718.3  # 2003 SARS 病毒 (SARS-CoV Tor2, 3768 bp)\n"
            "MG772933.1   # 舟山蝙蝠冠狀病毒 (Bat SARS-like ZC45, 3741 bp)\n"
            "NC_019843.3  # 中東呼吸症候群 (MERS-CoV 外群, 4062 bp)"
        )
    },
    "哺乳動物肌紅蛋白演化 (MB / Myoglobin 諾貝爾經典)": {
        "gene": "MB",
        "taxa": (
            "NM_005368.3    # 人類 (Homo sapiens, 465 bp)\n"
            "XM_007111818.1 # 抹香鯨 (Physeter macrocephalus 潛水哺乳, 465 bp)\n"
            "NM_001081829.1 # 馬 (Equus caballus 結構生物經典, 465 bp)\n"
            "NM_001003194.1 # 家犬 (Canis lupus familiaris, 465 bp)\n"
            "NM_013593.3    # 小鼠 (Mus musculus 模式動物, 465 bp)"
        )
    },
    "脊椎動物胰島素演化 (INS / Insulin 跨度 4 億年)": {
        "gene": "INS",
        "taxa": (
            "NM_000207.3    # 人類 (Homo sapiens, 333 bp)\n"
            "XM_016919751.2 # 黑猩猩 (Pan troglodytes, 333 bp)\n"
            "NM_001434734.1 # 馬 (Equus caballus, 333 bp)\n"
            "NM_001109772.1 # 豬 (Sus scrofa, 333 bp)\n"
            "NM_001185126.1 # 牛 (Bos taurus, 333 bp)\n"
            "NM_008387.5    # 小鼠 (Mus musculus, 333 bp)\n"
            "NM_205222.1    # 雞 (Gallus gallus 鳥類外群, 324 bp)\n"
            "NM_131056.1    # 斑馬魚 (Danio rerio 硬骨魚外群, 339 bp)"
        )
    },
    "靈長類 TP53 抑癌基因演化 (Primates TP53 / P53 8 物種展開)": {
        "gene": "TP53",
        "taxa": "靈長目"
    }
}


class TabExtractionWorker(QThread):
    progress_signal = Signal(int, int, str)
    log_signal = Signal(str)
    query_signal = Signal(str)
    finished_signal = Signal(object)

    def __init__(
        self,
        targets: list[str],
        target_gene: str,
        out_file: Path,
        sequence_type: str = "cds",
        max_taxa_per_clade: int = 8,
        refseq_only: bool = True,
    ):
        super().__init__()
        self.targets = targets
        self.target_gene = target_gene
        self.out_file = out_file
        self.sequence_type = sequence_type
        self.max_taxa_per_clade = max_taxa_per_clade
        self.refseq_only = refseq_only
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        extractor = GeneExtractor()

        def on_prog(curr, total, msg):
            self.progress_signal.emit(curr, total, msg)
            self.log_signal.emit(f"[{curr}/{total}] {msg}")

        result = extractor.extract_target_genes(
            targets=self.targets,
            target_gene=self.target_gene,
            output_fasta=self.out_file,
            sequence_type=self.sequence_type,
            max_taxa_per_clade=self.max_taxa_per_clade,
            refseq_only=self.refseq_only,
            progress_callback=on_prog,
            cancel_check=lambda: self._is_cancelled,
            query_reporter=lambda q: self.query_signal.emit(q),
        )
        self.finished_signal.emit(result)


class NCBIGeneTab(QWidget):
    """
    Dedicated Tab for NCBI Target Gene Extraction and Provenance Auditing.
    Allows researchers to extract verified target genes and inspect coordinates,
    direct URLs, and cryptographic checksums to prevent 'untraceable black-box' sequences.
    """

    send_to_sanitizer_requested = Signal(str)
    send_to_align_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_result: GeneExtractionResult | None = None
        self.worker: TabExtractionWorker | None = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # 1. Top Standalone Header Banner
        header_box = QFrame()
        header_box.setStyleSheet("background-color: #FFFFFF; border-radius: 6px; padding: 10px 14px; border: 1px solid #CBD5E1;")
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(0, 0, 0, 0)

        t_vbox = QVBoxLayout()
        t_vbox.setSpacing(2)

        title_row = QHBoxLayout()
        h_title = QLabel("<b>🌐 NCBI 特定基因檢索與全透明溯源擷取 (NCBI Gene Extractor & Provenance Audit)</b>")
        h_title.setStyleSheet("color: #0F172A; font-size: 14px;")
        title_row.addWidget(h_title)

        badge = QLabel("🛡️ 100% 官方可查證・杜絕黑箱序列")
        badge.setStyleSheet("color: #0F766E; background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 1px 8px; font-size: 10px; font-weight: bold;")
        title_row.addWidget(badge)
        title_row.addStretch()
        t_vbox.addLayout(title_row)

        h_sub = QLabel(
            "由全基因組或粒線體組之特徵註解表 (Feature Table) 自動鎖定 CDS/rRNA 座標，處理正負股反向互補並精準切片，"
            "同時產出附帶 NCBI 官方連結與 SHA-256 數位指紋之溯源報告書。"
        )
        h_sub.setStyleSheet("color: #64748B; font-size: 11px;")
        t_vbox.addWidget(h_sub)
        h_layout.addLayout(t_vbox, 1)

        layout.addWidget(header_box)

        # 2. Main Split Area: Left (Inputs & Config) | Right (Provenance Verification Table)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        # ===== LEFT PANEL: Inputs & Config =====
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(430)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        left_box = QGroupBox("步驟 1：檢索設定與登錄號清單 (Query Configuration)")
        l_vbox = QVBoxLayout(left_box)
        l_vbox.setContentsMargins(10, 12, 14, 12)
        l_vbox.setSpacing(8)

        # Preset Row
        l_vbox.addWidget(QLabel("<b>經典研究與論文範例 (Presets):</b>"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("-- 請選擇經典範本或手動填寫 --")
        for p_name in NCBI_PRESETS.keys():
            self.preset_combo.addItem(p_name)
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        l_vbox.addWidget(self.preset_combo)

        # Gene Selection Row
        l_vbox.addWidget(QLabel("<b>目標基因代號或中文蛋白名 (Target Gene):</b>"))
        self.gene_combo = QComboBox()
        self.gene_combo.setEditable(True)
        self.gene_combo.addItems([
            "ETR1 / 乙烯受體 1 (植物荷爾蒙感知, ~2200 bp)",
            "rbcL / 核酮糖二磷酸羧化酶大亞基 (植物光合作用核心, ~1430 bp)",
            "matK / 成熟酶 K (植物葉綠體DNA條形碼, ~1530 bp)",
            "psbA / 光系統 II D1 蛋白 (~1060 bp)",
            "CYTB / 細胞色素 b (粒線體演化經典, ~1140 bp)",
            "COX1 / 細胞色素 c 氧化酶 I (動物條形碼)",
            "TP53 / P53 / 腫瘤抑制蛋白 P53 (細胞週期與抑癌基因, ~1182 bp)",
            "MB / 肌紅蛋白 (動物肌肉儲氧蛋白, ~465 bp)",
            "HBB / 血紅蛋白 β 亞基 (脊椎動物氧氣運輸)",
            "GAPDH / 甘油醛-3-磷酸脫氫酶 (通用管家蛋白)",
            "ACTB / 肌動蛋白 (微絲細胞骨架)",
            "INS / 胰島素 (代謝荷爾蒙)",
            "ALB / 白蛋白 (血清滲透壓維持)",
            "HSP70 / 熱休克蛋白 70 (抗逆熱震蛋白)",
            "16S / 16S 核糖體 RNA (菌種鑑定)",
            "18S / 18S 核糖體 RNA (真核核糖體)",
            "ITS / 內部轉錄間隔區 (植物真菌條形碼)",
            "S / Spike 刺突蛋白 (冠狀病毒, ~3800 bp)",
            "ND1 (NADH 脫氫酶 1)",
            "ND6 (NADH 脫氫酶 6 負股)",
        ])
        l_vbox.addWidget(self.gene_combo)

        # Accession Editor
        l_vbox.addWidget(QLabel("<b>NCBI 登錄號清單或物種中文俗名:</b>"))
        self.taxa_edit = QTextEdit()
        self.taxa_edit.setPlaceholderText(
            "支援輸入格式：\n"
            "1. NCBI 登錄號 (如 NM_105305.4)\n"
            "2. 植物或物種中文俗名 (如 擬南芥、水稻、番茄、玉米、大豆、茶樹、蘋果)\n"
            "3. 物種學名 (如 Arabidopsis thaliana)\n"
            "後方亦可加上 # 物種備註。系統自動支援中文俗名智能解析！"
        )
        self.taxa_edit.setFixedHeight(95)
        l_vbox.addWidget(self.taxa_edit)

        # Taxa Resolve Action Button
        self.btn_resolve_taxa = QPushButton("🔍 解析物種俗名 ➔ 官方登錄號")
        self.btn_resolve_taxa.setFixedHeight(28)
        self.btn_resolve_taxa.setToolTip("輸入植物中文俗名（如擬南芥、番茄、水稻、玉米、茶樹），一鍵自動搜尋並解析為 NCBI 官方 RefSeq 登錄號")
        self.btn_resolve_taxa.clicked.connect(self.resolve_vernacular_names)
        l_vbox.addWidget(self.btn_resolve_taxa)

        # Researcher Customization Options (研究者進階客製選項)
        custom_box = QGroupBox("⚙️ 研究者進階設定 (Customization)")
        custom_layout = QGridLayout(custom_box)
        custom_layout.setContentsMargins(8, 8, 8, 8)
        custom_layout.setSpacing(6)

        custom_layout.addWidget(QLabel("演化群代表物種數:"), 0, 0)
        self.spin_max_taxa = QSpinBox()
        self.spin_max_taxa.setRange(2, 30)
        self.spin_max_taxa.setValue(8)
        self.spin_max_taxa.setToolTip("當輸入目/綱/門/科高階群時，透過 NCBI 伺服器依 TaxId 自動均勻抽樣之代表物種上限 (2~30 種)")
        custom_layout.addWidget(self.spin_max_taxa, 0, 1)

        custom_layout.addWidget(QLabel("序列導出格式:"), 1, 0)
        self.combo_seq_type = QComboBox()
        self.combo_seq_type.addItems([
            "核酸特徵切片 (CDS/rRNA)",
            "轉譯蛋白質 (Amino Acids)",
            "雙軌輸出 (CDS + 蛋白質)",
        ])
        self.combo_seq_type.setToolTip("選擇產出核酸 CDS 序列、由特徵表自動轉譯之蛋白質胺基酸序列，或同時雙軌輸出兩份 FASTA")
        custom_layout.addWidget(self.combo_seq_type, 1, 1)

        custom_layout.addWidget(QLabel("資料庫範圍:"), 2, 0)
        self.combo_db_scope = QComboBox()
        self.combo_db_scope.addItems([
            "官方精選 RefSeq (Curated/Model)",
            "涵蓋全庫 INSDC Complete CDS",
        ])
        self.combo_db_scope.setToolTip("預設採 NCBI 官方最高品質 RefSeq 基準；非模式生物可切換至全庫完整 CDS 擴大收錄範圍")
        custom_layout.addWidget(self.combo_db_scope, 2, 1)
        custom_layout.setColumnStretch(1, 1)

        l_vbox.addWidget(custom_box)

        # Query Transparency Inspector (NCBI 檢索語法即時透視)
        query_box = QGroupBox("🔍 NCBI 檢索語法即時透視 (Query Inspector)")
        q_vbox = QVBoxLayout(query_box)
        q_vbox.setContentsMargins(8, 8, 8, 8)
        q_vbox.setSpacing(4)

        self.query_preview_edit = QLineEdit()
        self.query_preview_edit.setReadOnly(True)
        self.query_preview_edit.setPlaceholderText("解析或檢索時，系統發送至 NCBI 之真實語法將即時顯示於此...")
        self.query_preview_edit.setStyleSheet("background-color: #F8FAFC; color: #0F172A; font-family: Consolas, monospace; font-size: 10px; border: 1px solid #CBD5E1; padding: 2px 4px;")
        q_vbox.addWidget(self.query_preview_edit)

        self.btn_open_ncbi_web = QPushButton("🌐 在 NCBI 官網開啟此檢索語法")
        self.btn_open_ncbi_web.setFixedHeight(24)
        self.btn_open_ncbi_web.setEnabled(False)
        self.btn_open_ncbi_web.setToolTip("點擊可直接於預設瀏覽器打開 NCBI 官方 Nuccore 搜尋結果，完全消除黑箱疑慮！")
        self.btn_open_ncbi_web.clicked.connect(self.open_ncbi_in_browser)
        q_vbox.addWidget(self.btn_open_ncbi_web)

        l_vbox.addWidget(query_box)

        # Output Path
        l_vbox.addWidget(QLabel("<b>導出 FASTA 路徑:</b>"))
        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self.out_path_edit = QLineEdit(str(DATA_DIR / "extracted_target_genes.fasta"))
        self.out_path_edit.setCursorPosition(0)
        out_row.addWidget(self.out_path_edit, 1)
        browse_btn = QPushButton("瀏覽...")
        browse_btn.setFixedWidth(75)
        browse_btn.clicked.connect(self.browse_output)
        out_row.addWidget(browse_btn)
        l_vbox.addLayout(out_row)

        # Action Button & Progress
        act_fetch_row = QHBoxLayout()
        act_fetch_row.setSpacing(6)
        self.fetch_btn = QPushButton("🚀 開始線上擷取與座標切片")
        self.fetch_btn.setObjectName("primary_button")
        self.fetch_btn.setFixedHeight(36)
        self.fetch_btn.setStyleSheet("""
            QPushButton#primary_button {
                background-color: #008287;
                color: #FFFFFF;
                font-weight: bold;
                border: 1px solid #00666B;
                border-radius: 4px;
            }
            QPushButton#primary_button:disabled {
                background-color: #E2E8F0;
                border: 1px solid #CBD5E1;
                color: #334155;
                font-weight: bold;
            }
        """)
        self.fetch_btn.clicked.connect(self.start_extraction)
        act_fetch_row.addWidget(self.fetch_btn, 1)

        self.cancel_btn = QPushButton("⏹ 停止")
        self.cancel_btn.setObjectName("danger_button")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setFixedWidth(75)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("""
            QPushButton#danger_button {
                background-color: #EF4444;
                color: #FFFFFF;
                font-weight: bold;
                border: 1px solid #DC2626;
                border-radius: 4px;
            }
            QPushButton#danger_button:disabled {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                color: #94A3B8;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_extraction)
        act_fetch_row.addWidget(self.cancel_btn)
        l_vbox.addLayout(act_fetch_row)

        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(24)
        self.prog_bar.setValue(0)
        self.prog_bar.setFormat("工具就緒")
        l_vbox.addWidget(self.prog_bar)

        left_scroll.setWidget(left_box)

        # ===== RIGHT PANEL: Provenance Table & Audit Trail =====
        right_box = QGroupBox("步驟 2：全透明特徵溯源檢驗表 (Traceability & Provenance Verification)")
        r_vbox = QVBoxLayout(right_box)
        r_vbox.setSpacing(8)

        # Traceability Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "物種學名 (Organism)",
            "NCBI 登錄號",
            "特徵座標 (Location)",
            "長度",
            "蛋白質 ID",
            "SHA-256 數位指紋",
            "官方溯源連結"
        ])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        header.setSectionResizeMode(6, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 125)
        self.table.setColumnWidth(2, 115)
        self.table.setColumnWidth(3, 115)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 135)
        self.table.setAlternatingRowColors(True)
        r_vbox.addWidget(self.table)

        # Log & Status Box
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(85)
        self.log_edit.setPlaceholderText("擷取執行即時通訊日誌...")
        r_vbox.addWidget(self.log_edit)

        # Bottom Action Bar
        act_row = QHBoxLayout()
        self.btn_export_report = QPushButton("📊 導出溯源審計報告 (CSV/MD)")
        self.btn_export_report.setFixedHeight(32)
        self.btn_export_report.setEnabled(False)
        self.btn_export_report.clicked.connect(self.export_report)
        act_row.addWidget(self.btn_export_report)

        act_row.addStretch()

        self.btn_send_sanitizer = QPushButton("🧹 一鍵送至序列清洗 ➔")
        self.btn_send_sanitizer.setFixedHeight(32)
        self.btn_send_sanitizer.setEnabled(False)
        self.btn_send_sanitizer.clicked.connect(self.send_to_sanitizer)
        act_row.addWidget(self.btn_send_sanitizer)

        self.btn_send_align = QPushButton("🧬 一鍵送至 MAFFT 比對 ➔")
        self.btn_send_align.setFixedHeight(32)
        self.btn_send_align.setEnabled(False)
        self.btn_send_align.clicked.connect(self.send_to_align)
        act_row.addWidget(self.btn_send_align)

        r_vbox.addLayout(act_row)

        main_splitter.addWidget(left_scroll)
        main_splitter.addWidget(right_box)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([450, 750])

        layout.addWidget(main_splitter, 1)

    def on_preset_changed(self, text: str):
        if text in NCBI_PRESETS:
            p_data = NCBI_PRESETS[text]
            g_sym = p_data["gene"].upper()
            for idx in range(self.gene_combo.count()):
                item_t = self.gene_combo.itemText(idx).upper()
                if item_t.startswith(g_sym) or f" {g_sym} " in f" {item_t} " or f"/{g_sym}" in item_t:
                    self.gene_combo.setCurrentIndex(idx)
                    break
            if self.gene_combo.lineEdit():
                self.gene_combo.lineEdit().setCursorPosition(0)
            self.taxa_edit.setPlainText(p_data["taxa"])

    def browse_output(self):
        f, _ = QFileDialog.getSaveFileName(self, "選取 FASTA 儲存路徑", str(DATA_DIR), "FASTA Files (*.fasta *.fa)")
        if f:
            self.out_path_edit.setText(f)

    def resolve_vernacular_names(self):
        raw_text = self.taxa_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "輸入為空", "請先輸入植物或動物物種中文俗名（如 擬南芥、人類、小鼠、茶樹）或學名！")
            return

        combo_txt = self.gene_combo.currentText().strip()
        raw_gene = combo_txt.split()[0].split("/")[0].strip()
        target_gene = GeneExtractor.canonicalize_gene_symbol(raw_gene) or raw_gene
        if re.search(r"[\u4e00-\u9fff]", target_gene):
            zh_matches = re.findall(r"[\u4e00-\u9fff]+", combo_txt)
            for zm in zh_matches:
                found = GeneExtractor.canonicalize_gene_symbol(zm)
                if found and not re.search(r"[\u4e00-\u9fff]", found):
                    target_gene = found
                    break

        if re.search(r"[\u4e00-\u9fff]", target_gene):
            QMessageBox.warning(
                self,
                "未識別之中文蛋白名稱",
                f"未能將輸入的中文蛋白名「{target_gene}」轉換為國際標準基因代號。\n\n"
                "NCBI 官方資料庫僅支援標準英文基因符號（如 MB、HBB、ACTB、ETR1 等）。\n"
                "請在「目標基因代號」欄位手動輸入其英文代號（如 MB）後再試。"
            )
            return

        self.btn_resolve_taxa.setEnabled(False)
        self.log_edit.append(f"🔍 正在解析物種俗名並檢索 NCBI 官方登錄號 (標的基因: {target_gene})...")
        self.prog_bar.setValue(20)
        self.prog_bar.setFormat("正在檢索 NCBI 登錄號...")
        QApplication.processEvents()

        max_taxa = self.spin_max_taxa.value()
        refseq_only = (self.combo_db_scope.currentIndex() == 0)

        resolved_tuples = GeneExtractor.resolve_taxa_to_accessions(
            raw_text,
            target_gene,
            max_taxa_per_clade=max_taxa,
            refseq_only=refseq_only,
            query_reporter=self.on_query_updated,
        )
        self.btn_resolve_taxa.setEnabled(True)
        self.prog_bar.setValue(100)
        self.prog_bar.setFormat("物種登錄號解析完畢")

        new_lines = [line_fmt for _, _, line_fmt in resolved_tuples]
        self.taxa_edit.setPlainText("\n".join(new_lines))
        resolved_count = sum(1 for acc, _, _ in resolved_tuples if acc)
        orig_count = len([l for l in raw_text.splitlines() if l.strip()])
        if resolved_count > orig_count:
            self.log_edit.append(f"🎉 解析完成！偵測到高階分類階元（門/綱/目/科/屬），已智慧跨物種採樣展開 {resolved_count} 筆代表性物種官方 RefSeq 登錄號！")
        else:
            self.log_edit.append(f"🎉 解析完成！已成功為 {resolved_count} 筆物種對應官方 NCBI RefSeq 登錄號。")

    def on_query_updated(self, query: str):
        self.last_ncbi_query = query
        self.query_preview_edit.setText(query)
        self.query_preview_edit.setCursorPosition(0)
        self.btn_open_ncbi_web.setEnabled(True)

    def open_ncbi_in_browser(self):
        if hasattr(self, "last_ncbi_query") and self.last_ncbi_query:
            url_str = f"https://www.ncbi.nlm.nih.gov/nuccore/?term={urllib.parse.quote(self.last_ncbi_query)}"
            QDesktopServices.openUrl(QUrl(url_str))

    def start_extraction(self):
        raw_text = self.taxa_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "輸入為空", "請輸入至少一個 NCBI 登錄號或物種中文俗名！")
            return

        combo_txt = self.gene_combo.currentText().strip()
        raw_gene = combo_txt.split()[0].split("/")[0].strip()
        target_gene = GeneExtractor.canonicalize_gene_symbol(raw_gene) or raw_gene
        if re.search(r"[\u4e00-\u9fff]", target_gene):
            zh_matches = re.findall(r"[\u4e00-\u9fff]+", combo_txt)
            for zm in zh_matches:
                found = GeneExtractor.canonicalize_gene_symbol(zm)
                if found and not re.search(r"[\u4e00-\u9fff]", found):
                    target_gene = found
                    break

        if re.search(r"[\u4e00-\u9fff]", target_gene):
            QMessageBox.warning(
                self,
                "未識別之中文蛋白名稱",
                f"未能將輸入的中文蛋白名「{target_gene}」轉換為國際標準基因代號。\n\n"
                "NCBI 官方資料庫僅支援標準英文基因符號（如 MB、HBB、ACTB、ETR1 等）。\n"
                "請在「目標基因代號」欄位手動輸入其英文代號（如 MB）後再試。"
            )
            return

        max_taxa = self.spin_max_taxa.value()
        refseq_only = (self.combo_db_scope.currentIndex() == 0)
        seq_idx = self.combo_seq_type.currentIndex()
        seq_type = "cds"
        if seq_idx == 1:
            seq_type = "protein"
        elif seq_idx == 2:
            seq_type = "both"

        # 1. Check if direct accessions exist
        targets = GeneExtractor.parse_accessions(raw_text)

        # 2. If no direct accessions parsed, auto-resolve Chinese or Latin organism names!
        if not targets:
            self.log_edit.append(f"🔍 偵測到物種中文俗名，正在自動檢索 NCBI 官方登錄號 (標的: {target_gene})...")
            self.prog_bar.setValue(15)
            self.prog_bar.setFormat("解析物種登錄號中...")
            QApplication.processEvents()

            resolved_tuples = GeneExtractor.resolve_taxa_to_accessions(
                raw_text,
                target_gene,
                max_taxa_per_clade=max_taxa,
                refseq_only=refseq_only,
                query_reporter=self.on_query_updated,
            )
            targets = [acc for acc, _, _ in resolved_tuples if acc]
            if targets:
                new_lines = [line_fmt for _, _, line_fmt in resolved_tuples]
                self.taxa_edit.setPlainText("\n".join(new_lines))
                self.log_edit.append(f"🎉 自動解析成功：已取得 {len(targets)} 筆 NCBI 登錄號！")

        if not targets:
            QMessageBox.warning(self, "輸入無效", "未解析到有效登錄號或已知物種名稱！請檢查輸入內容。")
            return

        out_path = Path(self.out_path_edit.text().strip())
        self.fetch_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.table.setRowCount(0)
        self.log_edit.clear()
        self.prog_bar.setValue(10)
        self.prog_bar.setFormat("正在連線 NCBI E-Utilities 擷取特徵註解表...")

        self.worker = TabExtractionWorker(
            targets=targets,
            target_gene=target_gene,
            out_file=out_path,
            sequence_type=seq_type,
            max_taxa_per_clade=max_taxa,
            refseq_only=refseq_only,
        )
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.log_signal.connect(self.log_edit.append)
        self.worker.query_signal.connect(self.on_query_updated)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def cancel_extraction(self):
        if self.worker and self.worker.isRunning():
            self.cancel_btn.setEnabled(False)
            self.prog_bar.setFormat("正在中止中...")
            self.log_edit.append("⚠️ 使用者觸發中斷，正在安全停止工作緒...")
            self.worker.cancel()

    def on_progress(self, curr: int, total: int, msg: str):
        pct = int(curr / total * 90) + 10
        self.prog_bar.setValue(pct)
        self.prog_bar.setFormat(f"擷取中: {curr}/{total}")

    def on_finished(self, result: GeneExtractionResult):
        self.fetch_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.prog_bar.setValue(100)
        self.prog_bar.setFormat("擷取與座標切片完畢")
        self.current_result = result

        if result.success:
            self.btn_export_report.setEnabled(True)
            self.btn_send_sanitizer.setEnabled(True)
            self.btn_send_align.setEnabled(True)
            self.populate_provenance_table(result.records)
            self.log_edit.append(f"\n🎉 成功！已建立全透明可溯源 FASTA: {result.output_fasta}")
            QMessageBox.information(
                self,
                "擷取成功",
                f"成功從 NCBI 特徵表擷取 {result.total_extracted} 筆特定基因序列 ({result.records[0].gene_symbol})！\n\n"
                f"• FASTA 檔案：{result.output_fasta}\n"
                f"• 溯源審計表：{result.output_csv}\n\n"
                f"所有序列皆已建立 NCBI 官方檢驗連結與 SHA-256 數位指紋，保證 100% 可溯源！"
            )
        else:
            QMessageBox.critical(self, "擷取失敗", f"未能成功擷取基因:\n{result.message}")

    def populate_provenance_table(self, records: list[ExtractedGeneRecord]):
        self.table.setRowCount(len(records))
        for row, r in enumerate(records):
            # 0: Organism
            item_org = QTableWidgetItem(r.organism)
            self.table.setItem(row, 0, item_org)

            # 1: Accession
            item_acc = QTableWidgetItem(r.accession)
            item_acc.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, item_acc)

            # 2: Location
            item_loc = QTableWidgetItem(r.coordinates_str)
            item_loc.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, item_loc)

            # 3: Length
            if r.protein_length > 0:
                len_str = f"{r.seq_length} bp ({r.protein_length} aa)"
            else:
                len_str = f"{r.seq_length} bp"
            item_len = QTableWidgetItem(len_str)
            item_len.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_len)

            # 4: Protein ID
            item_prot = QTableWidgetItem(r.protein_id or "N/A")
            item_prot.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, item_prot)

            # 5: SHA-256
            item_sha = QTableWidgetItem(f"{r.sha256_hash[:10]}...")
            item_sha.setTextAlignment(Qt.AlignCenter)
            item_sha.setToolTip(f"完整 SHA-256 數位指紋:\n{r.sha256_hash}")
            self.table.setItem(row, 5, item_sha)

            # 6: Clickable URL Action
            btn_link = QPushButton("🔗 NCBI 官方直達")
            btn_link.setCursor(Qt.PointingHandCursor)
            btn_link.setStyleSheet("color: #008287; text-decoration: underline; background: transparent; border: none; font-size: 11px; font-weight: bold;")
            url_str = r.ncbi_url
            btn_link.clicked.connect(lambda _, u=url_str: QDesktopServices.openUrl(QUrl(u)))
            self.table.setCellWidget(row, 6, btn_link)

    def export_report(self):
        if not self.current_result or not self.current_result.output_csv:
            return
        p_csv = Path(self.current_result.output_csv)
        QMessageBox.information(
            self,
            "溯源審計檔案路徑",
            f"溯源審計清單已自動生成並儲存於：\n\n"
            f"1. CSV 格式：\n{p_csv.resolve()}\n\n"
            f"2. Markdown 格式：\n{p_csv.with_suffix('.md').resolve()}\n\n"
            f"此檔案可直接附於學術論文 Supplementary Materials 中供審稿人查驗！"
        )

    def send_to_sanitizer(self):
        if self.current_result and self.current_result.output_fasta:
            self.send_to_sanitizer_requested.emit(self.current_result.output_fasta)

    def send_to_align(self):
        if self.current_result and self.current_result.output_fasta:
            self.send_to_align_requested.emit(self.current_result.output_fasta)
