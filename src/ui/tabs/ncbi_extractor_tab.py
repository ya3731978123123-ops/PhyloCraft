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
from PySide6.QtGui import QDesktopServices, QColor, QBrush
from src.core.gene_extractor import GeneExtractor, ExtractedGeneRecord, GeneExtractionResult
from src.config import DATA_DIR, OUTPUT_DIR


NCBI_PRESETS = {
    "🌍 生命三域之樹 16S/18S rRNA (古菌、細菌、真核生物 - Carl Woese 經典系統)": {
        "gene": "SSU",
        "taxa": (
            "# 【古菌域 Archaea - 16S rRNA (真核生物親緣姊妹群)】\n"
            "NR_074218.1  # 火山嗜鹽古菌 Haloferax volcanii (1473 bp)\n"
            "NR_177349.1  # 硫化葉菌 Sulfolobus mongibelli (1498 bp)\n"
            "NR_116412.1  # 亞熱嗜熱球菌 Pyrococcus yayanosii (1424 bp)\n"
            "NR_117968.1  # 甲烷熱桿菌 Methanothermobacter crinale (1451 bp)\n\n"
            "# 【細菌域 Bacteria - 16S rRNA (天然外群)】\n"
            "NR_024570.1  # 大腸桿菌 Escherichia coli (變形菌門, 1450 bp)\n"
            "NR_102783.2  # 枯草桿菌 Bacillus subtilis (厚壁菌門, 1550 bp)\n"
            "NR_102775.2  # 海棲熱袍菌 Thermotoga maritima (熱袍菌門, 1558 bp)\n"
            "NR_074311.1  # 藍細菌 Synechocystis sp. PCC 6803 (藍菌門, 1489 bp)\n\n"
            "# 【真核域 Eukaryota - 18S rRNA】\n"
            "J01353.1     # 釀酒酵母 Saccharomyces cerevisiae (真菌界, 1798 bp)\n"
            "X16077.1     # 擬南芥 Arabidopsis thaliana (植物界, 1902 bp)\n"
            "NR_003286.4  # 智人 Homo sapiens (動物界, 1869 bp)\n"
            "X56165.1     # 四膜蟲 Tetrahymena thermophila (原生生物界, 1753 bp)"
        )
    },
    "🔬 細菌演化樹 (4株古菌打斷長枝定根 - 4古菌 + 4細菌)": {
        "gene": "16S",
        "taxa": (
            "# 【古菌外群 Archaea - 4株打破長枝吸引 LBA】\n"
            "NR_074218.1  # 火山嗜鹽古菌 Haloferax volcanii (1473 bp)\n"
            "NR_177349.1  # 硫化葉菌 Sulfolobus mongibelli (1498 bp)\n"
            "NR_116412.1  # 亞熱嗜熱球菌 Pyrococcus yayanosii (1424 bp)\n"
            "NR_117968.1  # 甲烷熱桿菌 Methanothermobacter crinale (1451 bp)\n\n"
            "# 【細菌內群 Bacteria - 4大門代表】\n"
            "NR_024570.1  # 大腸桿菌 Escherichia coli (變形菌門, 1450 bp)\n"
            "NR_102783.2  # 枯草桿菌 Bacillus subtilis (厚壁菌門, 1550 bp)\n"
            "NR_102775.2  # 海棲熱袍菌 Thermotoga maritima (熱袍菌門, 1558 bp)\n"
            "NR_074311.1  # 藍細菌 Synechocystis sp. PCC 6803 (藍菌門, 1489 bp)"
        )
    },
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
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 1. Top Compact Standalone Header Banner
        header_box = QFrame()
        header_box.setStyleSheet("background-color: #FFFFFF; border-radius: 6px; padding: 4px 10px; border: 1px solid #CBD5E1;")
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(10)

        h_title = QLabel("<b>🌐 NCBI 特定基因檢索與全透明溯源擷取</b>")
        h_title.setStyleSheet("color: #0F172A; font-size: 13px;")
        h_layout.addWidget(h_title)

        badge = QLabel("🛡️ 100% 官方可查證・杜絕黑箱序列")
        badge.setStyleSheet("color: #0F766E; background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 1px 6px; font-size: 10px; font-weight: bold;")
        h_layout.addWidget(badge)

        h_sub = QLabel("自動鎖定 CDS/rRNA 座標反向互補切片，附帶 SHA-256 與官方溯源")
        h_sub.setStyleSheet("color: #64748B; font-size: 11px;")
        h_layout.addWidget(h_sub)
        h_layout.addStretch()

        layout.addWidget(header_box)

        # 2. Main Split Area: Left (Inputs & Config) | Right (Provenance Verification Table)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        # ===== LEFT PANEL: Inputs & Config =====
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(400)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        left_box = QGroupBox("步驟 1：檢索設定與登錄號清單 (Query Configuration)")
        l_vbox = QVBoxLayout(left_box)
        l_vbox.setContentsMargins(8, 8, 8, 8)
        l_vbox.setSpacing(5)

        # 1. Target Gene Input (Primary Research Focus) - Inline compact
        gene_row = QHBoxLayout()
        gene_row.setSpacing(6)
        gene_lbl = QLabel("<b>1. 目標基因:</b>")
        gene_row.addWidget(gene_lbl)

        self.gene_combo = QComboBox()
        self.gene_combo.setEditable(True)
        self.gene_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.gene_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.gene_combo.setMinimumWidth(100)
        if self.gene_combo.lineEdit():
            self.gene_combo.lineEdit().setPlaceholderText("輸入任意基因 (如 ETR1, rbcL, SSU, 16S, TP53...)")
        self.gene_combo.addItems([
            "SSU (16S/18S rRNA 三域演化)",
            "ETR1 (乙烯受體 1, 植物)",
            "rbcL (核酮糖羧化酶, 葉綠體)",
            "matK (成熟酶 K, 條形碼)",
            "psbA (光系統 II D1 蛋白)",
            "CYTB (細胞色素 b, 粒線體)",
            "COX1 (細胞色素 c 氧化酶 I)",
            "TP53 (腫瘤抑制蛋白 P53)",
            "MB (肌紅蛋白, 肌肉儲氧)",
            "HBB (血紅蛋白 β 亞基)",
            "GAPDH (甘油醛-3-磷酸脫氫酶)",
            "ACTB (肌動蛋白, 細胞骨架)",
            "INS (胰島素, 代謝荷爾蒙)",
            "ALB (白蛋白, 滲透壓維持)",
            "HSP70 (熱休克蛋白 70)",
            "16S rRNA (細菌/古菌鑑定)",
            "18S rRNA (真核生物鑑定)",
            "ITS (內部轉錄間隔區)",
            "S (Spike 刺突蛋白, 冠狀病毒)",
            "ND1 (NADH 脫氫酶 1)",
            "ND6 (NADH 脫氫酶 6 負股)",
        ])
        self.gene_combo.currentIndexChanged.connect(
            lambda: self.gene_combo.lineEdit() and self.gene_combo.lineEdit().setCursorPosition(0)
        )
        gene_row.addWidget(self.gene_combo, 1)
        l_vbox.addLayout(gene_row)

        # 2. Accession & Species Input (Header with inline resolve button)
        taxa_hdr = QHBoxLayout()
        taxa_hdr.setSpacing(6)
        taxa_hdr.addWidget(QLabel("<b>2. 登錄號清單或物種名:</b>"))
        taxa_hdr.addStretch()

        self.btn_resolve_taxa = QPushButton("🔍 解析俗名")
        self.btn_resolve_taxa.setMinimumWidth(80)
        self.btn_resolve_taxa.setFixedHeight(22)
        self.btn_resolve_taxa.setStyleSheet("padding: 2px 6px; font-size: 11px;")
        self.btn_resolve_taxa.setToolTip("輸入植物或動物俗名（如擬南芥、水稻、人類），自動搜尋解析為 NCBI 官方 RefSeq 登錄號")
        self.btn_resolve_taxa.clicked.connect(self.resolve_vernacular_names)
        taxa_hdr.addWidget(self.btn_resolve_taxa)
        l_vbox.addLayout(taxa_hdr)

        self.taxa_edit = QTextEdit()
        self.taxa_edit.setPlaceholderText(
            "自由輸入任何格式（每行一筆，支援自訂）：\n"
            "1. NCBI 登錄號 (如 NM_105305.4, NR_024570.1, NC_000932.1)\n"
            "2. 物種俗名或學名 (如 擬南芥、水稻、Homo sapiens)\n"
            "系統將完全依據您自訂之研究數據動態至 NCBI 檢索與精準切片！"
        )
        self.taxa_edit.setFixedHeight(58)
        l_vbox.addWidget(self.taxa_edit)

        # 3. Optional Presets (Secondary Helper - 單行緊湊)
        p_row = QHBoxLayout()
        p_row.setSpacing(6)
        p_lbl = QLabel("💡 <i>示範範本 (可選):</i>")
        p_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        p_row.addWidget(p_lbl)
        self.preset_combo = QComboBox()
        self.preset_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.preset_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.preset_combo.setMinimumWidth(100)
        self.preset_combo.addItem("-- 自行輸入任意基因與物種 (不使用範本) --")
        for p_name in NCBI_PRESETS.keys():
            self.preset_combo.addItem(p_name)
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        p_row.addWidget(self.preset_combo, 1)
        l_vbox.addLayout(p_row)

        # 4. Researcher Customization Options (雙行緊湊網格)
        custom_box = QGroupBox("⚙️ 研究者進階設定 (Customization)")
        custom_layout = QGridLayout(custom_box)
        custom_layout.setContentsMargins(6, 4, 6, 4)
        custom_layout.setHorizontalSpacing(8)
        custom_layout.setVerticalSpacing(3)

        custom_layout.addWidget(QLabel("代表物種數:"), 0, 0)
        self.spin_max_taxa = QSpinBox()
        self.spin_max_taxa.setRange(2, 30)
        self.spin_max_taxa.setValue(8)
        self.spin_max_taxa.setToolTip("當輸入目/綱/門/科高階群時，透過 NCBI 伺服器依 TaxId 自動均勻抽樣之代表物種上限")
        custom_layout.addWidget(self.spin_max_taxa, 0, 1)

        custom_layout.addWidget(QLabel("導出格式:"), 0, 2)
        self.combo_seq_type = QComboBox()
        self.combo_seq_type.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo_seq_type.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.combo_seq_type.setMinimumWidth(90)
        self.combo_seq_type.addItems([
            "核酸切片 (CDS/rRNA)",
            "轉譯蛋白質 (AA)",
            "雙軌輸出 (CDS+AA)",
        ])
        self.combo_seq_type.setToolTip("選擇產出核酸 CDS 序列、由特徵表自動轉譯之蛋白質胺基酸序列，或同時雙軌輸出兩份 FASTA")
        custom_layout.addWidget(self.combo_seq_type, 0, 3)

        custom_layout.addWidget(QLabel("庫範圍:"), 1, 0)
        self.combo_db_scope = QComboBox()
        self.combo_db_scope.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo_db_scope.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.combo_db_scope.setMinimumWidth(110)
        self.combo_db_scope.addItems([
            "官方精選 RefSeq (Curated/Model)",
            "涵蓋全庫 INSDC Complete CDS",
        ])
        self.combo_db_scope.setToolTip("預設採 NCBI 官方最高品質 RefSeq 基準；非模式生物可切換至全庫完整 CDS 擴大收錄範圍")
        custom_layout.addWidget(self.combo_db_scope, 1, 1, 1, 3)
        custom_layout.setColumnStretch(3, 1)

        l_vbox.addWidget(custom_box)

        # 5. Query Transparency Inspector (單行緊湊透視)
        query_box = QGroupBox("🔍 NCBI 檢索語法即時透視 (Query Inspector)")
        q_layout = QHBoxLayout(query_box)
        q_layout.setContentsMargins(6, 4, 6, 4)
        q_layout.setSpacing(6)

        self.query_preview_edit = QLineEdit()
        self.query_preview_edit.setReadOnly(True)
        self.query_preview_edit.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.query_preview_edit.setMinimumWidth(80)
        self.query_preview_edit.setPlaceholderText("解析或檢索時，發送至 NCBI 之真實語法將即時顯示於此...")
        self.query_preview_edit.setStyleSheet("background-color: #F8FAFC; color: #0F172A; font-family: Consolas, monospace; font-size: 10px; border: 1px solid #CBD5E1; padding: 2px 4px;")
        q_layout.addWidget(self.query_preview_edit, 1)

        self.btn_open_ncbi_web = QPushButton("🌐 官網開啟")
        self.btn_open_ncbi_web.setFixedHeight(24)
        self.btn_open_ncbi_web.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_open_ncbi_web.setEnabled(False)
        self.btn_open_ncbi_web.setToolTip("點擊可直接於預設瀏覽器打開 NCBI 官方 Nuccore 搜尋結果，完全消除黑箱疑慮！")
        self.btn_open_ncbi_web.clicked.connect(self.open_ncbi_in_browser)
        q_layout.addWidget(self.btn_open_ncbi_web)

        l_vbox.addWidget(query_box)

        # 6. Output Path (單行水平緊湊)
        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        out_lbl = QLabel("<b>導出 FASTA:</b>")
        out_row.addWidget(out_lbl)

        self.out_path_edit = QLineEdit(str(DATA_DIR / "extracted_target_genes.fasta"))
        self.out_path_edit.setCursorPosition(0)
        self.out_path_edit.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.out_path_edit.setMinimumWidth(80)
        out_row.addWidget(self.out_path_edit, 1)

        browse_btn = QPushButton("瀏覽...")
        browse_btn.setFixedHeight(24)
        browse_btn.setStyleSheet("padding: 2px 10px; font-size: 11px;")
        browse_btn.clicked.connect(self.browse_output)
        out_row.addWidget(browse_btn)
        l_vbox.addLayout(out_row)

        # 7. Action Button & Progress
        act_fetch_row = QHBoxLayout()
        act_fetch_row.setSpacing(6)
        self.fetch_btn = QPushButton("🚀 開始線上擷取與座標切片")
        self.fetch_btn.setObjectName("primary_button")
        self.fetch_btn.setFixedHeight(34)
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
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("""
            QPushButton#danger_button {
                background-color: #EF4444;
                color: #FFFFFF;
                font-weight: bold;
                border: 1px solid #DC2626;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton#danger_button:disabled {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                color: #94A3B8;
                padding: 4px 12px;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_extraction)
        act_fetch_row.addWidget(self.cancel_btn)
        l_vbox.addLayout(act_fetch_row)

        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(18)
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
            "物種名稱 (Organism)",
            "NCBI 登錄號",
            "特徵座標",
            "長度",
            "蛋白質 ID",
            "SHA-256 指紋",
            "官方溯源"
        ])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(50)
        for col_idx in range(7):
            header.setSectionResizeMode(col_idx, QHeaderView.Interactive)

        self.table.setColumnWidth(0, 215)  # 物種名稱 (Organism)
        self.table.setColumnWidth(1, 95)   # NCBI 登錄號
        self.table.setColumnWidth(2, 105)  # 特徵座標 (Location)
        self.table.setColumnWidth(3, 80)   # 長度
        self.table.setColumnWidth(4, 75)   # 蛋白質 ID
        self.table.setColumnWidth(5, 95)   # SHA-256 指紋
        self.table.setColumnWidth(6, 85)   # 官方溯源
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
        main_splitter.setSizes([500, 700])

        layout.addWidget(main_splitter, 1)

    def on_preset_changed(self, text: str):
        if text in NCBI_PRESETS:
            p_data = NCBI_PRESETS[text]
            g_sym = p_data["gene"].upper()
            found = False
            for idx in range(self.gene_combo.count()):
                item_t = self.gene_combo.itemText(idx).upper()
                if (
                    item_t.startswith(g_sym)
                    or f" {g_sym} " in f" {item_t} "
                    or f"/{g_sym}" in item_t
                    or (g_sym == "SSU" and ("16S" in item_t or "18S" in item_t))
                ):
                    self.gene_combo.setCurrentIndex(idx)
                    found = True
                    break
            if not found:
                self.gene_combo.setCurrentText(p_data["gene"])
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

        # Smart Pre-flight Guard: Detect non-coding RNA Accessions vs Protein-coding Target Gene
        is_all_rna_accs = bool(targets) and all(acc.upper().startswith("NR_") for acc in targets)
        is_rna_target = any(r in target_gene.upper() for r in ("16S", "18S", "SSU", "28S", "RRNA", "ITS", "RNA"))
        if is_all_rna_accs and not is_rna_target:
            reply = QMessageBox.question(
                self,
                "⚠️ 標的基因與登錄號型態不符",
                f"偵測到您輸入的登錄號全部為【NCBI 非編碼 RNA 專用登錄號 (NR_...)】，\n"
                f"但目前設定的標的基因為【{target_gene}】(蛋白質編碼基因)。\n\n"
                f"這通常是因未切換基因選單所致，會導致特徵表中找不到 CDS 特徵而擷取失敗。\n\n"
                f"是否自動將標的基因切換為「SSU / 16S / 18S 核糖體 RNA」並繼續執行？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                target_gene = "SSU"
                for idx in range(self.gene_combo.count()):
                    item_u = self.gene_combo.itemText(idx).upper()
                    if "SSU" in item_u or ("16S" in item_u and "18S" in item_u):
                        self.gene_combo.setCurrentIndex(idx)
                        break
                else:
                    self.gene_combo.setCurrentText("SSU / 16S / 18S 核糖體 RNA")
            else:
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
            if result.qc_warnings:
                self.log_edit.append("\n⚠️ 【直系同源品管警示 (Orthology QC)】:")
                for w in result.qc_warnings:
                    self.log_edit.append(f"  • {w}")
                self.log_edit.append("  💡 演化生物學建議：可點選上方「傳送至修剪 (trimAl)」剔除非同源區段，或改以「轉譯蛋白質」模式進行建樹，以避免分支長度失真。")

            warn_note = ""
            if result.qc_warnings:
                warn_note = f"\n\n⚠️ 【直系同源長度警示】：\n偵測到 {len(result.qc_warnings)} 筆序列長度與中位數偏差 >15%！疑似混入旁系同源基因 (如 ETR1 混入 ERS1) 或未修剪前導區。\n建議檢查檢驗表或使用 trimAl 修剪。"

            QMessageBox.information(
                self,
                "擷取成功",
                f"成功從 NCBI 特徵表擷取 {result.total_extracted} 筆特定基因序列 ({result.records[0].gene_symbol})！\n\n"
                f"• FASTA 檔案：{result.output_fasta}\n"
                f"• 溯源審計表：{result.output_csv}"
                f"{warn_note}\n\n"
                f"所有序列皆已建立 NCBI 官方檢驗連結與 SHA-256 數位指紋，保證 100% 可溯源！"
            )
        else:
            QMessageBox.critical(self, "擷取失敗", f"未能成功擷取基因:\n{result.message}")

    def populate_provenance_table(self, records: list[ExtractedGeneRecord]):
        self.table.setRowCount(len(records))
        for row, r in enumerate(records):
            # 0: Organism (Scientific name + Vernacular name if available)
            org_display = r.organism or "未知物種"
            zh_name = GeneExtractor.translate_latin_to_chinese_organism(org_display)
            if zh_name and zh_name not in org_display:
                display_text = f"{org_display} ({zh_name})"
                item_org = QTableWidgetItem(display_text)
                item_org.setToolTip(f"物種學名: {org_display}\n常用中文俗名: {zh_name}\nTaxID: {r.taxid or '未標註'}")
            else:
                item_org = QTableWidgetItem(org_display)
                item_org.setToolTip(f"物種學名: {org_display}\nTaxID: {r.taxid or '未標註'}")
            font = item_org.font()
            font.setBold(True)
            item_org.setFont(font)
            item_org.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
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
            if "⚠️" in (r.qc_status or ""):
                len_str = f"⚠️ {len_str}"
            item_len = QTableWidgetItem(len_str)
            item_len.setTextAlignment(Qt.AlignCenter)
            if "⚠️" in (r.qc_status or ""):
                item_len.setToolTip(f"演化品管警示: {r.qc_status}\n序列長度與中位數偏差過大，可能為旁系同源基因 (Paralog) 或缺失/多出結構域。")
                item_len.setForeground(QColor("#B45309"))
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
            btn_link = QPushButton("🔗 NCBI")
            btn_link.setCursor(Qt.PointingHandCursor)
            btn_link.setStyleSheet("color: #008287; text-decoration: underline; background: transparent; border: none; font-size: 11px; font-weight: bold; padding: 0px;")
            url_str = r.ncbi_url
            btn_link.clicked.connect(lambda _, u=url_str: QDesktopServices.openUrl(QUrl(u)))
            self.table.setCellWidget(row, 6, btn_link)

        # Maintain balanced column 0 width (~215px) so all columns fit within viewport without horizontal scrolling
        self.table.setColumnWidth(0, 215)

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
