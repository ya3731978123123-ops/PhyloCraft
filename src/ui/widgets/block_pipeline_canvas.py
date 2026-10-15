from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QTextEdit,
    QScrollArea,
    QGroupBox,
    QSplitter,
    QDialog,
    QMessageBox,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QProgressBar,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from src.core.project_manager import STEP_KEYS, STEP_TITLES, StepRecord, PhyloProject
from src.config import OUTPUT_DIR, DATA_DIR


MODULE_METADATA = {
    "raw": {
        "step_num": "01",
        "engine": "BioPython FASTA Engine",
        "engine_full": "BioPython v1.83 序列解析與檢定核心",
        "category": "序列輸入 (Input)",
        "input_desc": "輸入: 原始定序 FASTA 檔案 (*.fasta, *.fa, *.fas)",
        "output_desc": "輸出: 結構化原始序列紀錄 (SeqRecords)",
        "alt_engines": ["NCBI GenBank Importer", "EMBL Parser", "FastQ to FASTA Converter"],
        "paper": "Cock et al. (2009) Biopython: freely available Python tools for computational molecular biology.",
    },
    "sanitize": {
        "step_num": "02",
        "engine": "PhyloCraft IUPAC Validator",
        "engine_full": "PhyloCraft 基因品質檢定與品管清洗引擎",
        "category": "品管過濾 (QC)",
        "input_desc": "輸入: 未經校驗之原始序列",
        "output_desc": "輸出: 標準化乾淨 FASTA (過濾 NCBI 特殊標頭與殘缺短序列)",
        "alt_engines": ["SeqKit Filter", "Biopython Clean", "FASTX-Toolkit"],
        "paper": "PhyloCraft Laboratory Automated QC Protocol (2026)",
    },
    "alignment": {
        "step_num": "03",
        "engine": "MAFFT v7.526",
        "engine_full": "MAFFT (Multiple Alignment using Fast Fourier Transform)",
        "category": "多重比對 (MSA)",
        "input_desc": "輸入: 標準化乾淨 FASTA 序列",
        "output_desc": "輸出: 多重序列對齊矩陣 (Aligned MSA Matrix)",
        "alt_engines": ["MUSCLE v5 (結構感知)", "Clustal Omega", "T-Coffee", "PRANK"],
        "paper": "Katoh & Standley (2013) MAFFT multiple sequence alignment software version 7.",
    },
    "trimming": {
        "step_num": "04",
        "engine": "trimAl v1.4.1",
        "engine_full": "trimAl 演化保守位點自動修剪核心",
        "category": "矩陣修剪 (Trimming)",
        "input_desc": "輸入: 多重序列比對矩陣 (MSA)",
        "output_desc": "輸出: 高信度保守位點矩陣 (Trimmed Clean Matrix)",
        "alt_engines": ["ClipKIT v2.1 (演化訊息保留)", "BMGE", "Gblocks", "直通不修剪 (Bypass)"],
        "paper": "Capella-Gutierrez et al. (2009) trimAl: a tool for automated alignment trimming.",
    },
    "modelfinder": {
        "step_num": "05",
        "engine": "ModelFinder",
        "engine_full": "ModelFinder 最佳替代模型統計評估引擎",
        "category": "模型檢定 (Model Testing)",
        "input_desc": "輸入: 修剪後多重比對矩陣",
        "output_desc": "輸出: BIC/AIC 最佳替代模型參數 (Substitution Matrix)",
        "alt_engines": ["PartitionFinder 2 (分區最佳化)", "jModelTest 2", "ProtTest 3"],
        "paper": "Kalyaanamoorthy et al. (2017) ModelFinder: fast model selection for accurate phylogenetic estimates.",
    },
    "tree": {
        "step_num": "06",
        "engine": "IQ-TREE v2.2.0 ML",
        "engine_full": "IQ-TREE 2 最大概似法系統發育拓撲推論核心",
        "category": "系統建樹 (Phylogeny)",
        "input_desc": "輸入: 比對矩陣 + 最佳替代模型設定",
        "output_desc": "輸出: 最大概似系統發育拓撲樹 (Newick Treefile)",
        "alt_engines": ["FastTree 2.1 (百萬序列極速)", "RAxML-NG", "PhyML 3.0", "MrBayes (貝氏)"],
        "paper": "Minh et al. (2020) IQ-TREE 2: New Models and Efficient Methods for Phylogenetic Inference.",
    },
    "timetree": {
        "step_num": "07",
        "engine": "LSD2 (Least-Squares Dating)",
        "engine_full": "LSD2 最小平方法快速地質分子鐘定年核心",
        "category": "分子定年 (TimeTree)",
        "input_desc": "輸入: 系統拓撲樹 + 化石/物種年代校準檔 (Date File)",
        "output_desc": "輸出: 絕對地質年代時間樹 (Chronogram TimeTree)",
        "alt_engines": ["TreeTime (ML 定年)", "BEAST 2 (Bayesian MCMC)", "MCMCTree (PAML)"],
        "paper": "To et al. (2016) Fast Dating Using Least-Squares Criteria and Algorithms.",
    },
}


class EngineInfoDialog(QDialog):
    """
    Dialog displaying module engine details, citation, and extensible alternatives.
    """

    def __init__(self, step_key: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.step_key = step_key
        meta = MODULE_METADATA.get(step_key, {})
        self.setWindowTitle(f"模塊核心引擎資訊 — {meta.get('category', step_key)}")
        self.resize(520, 360)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                color: #1E293B;
                font-size: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header Banner
        header = QLabel(f"模塊 [{meta.get('step_num', '00')}] 運算核心規格")
        header.setStyleSheet("color: #008287; font-size: 14px; font-weight: bold; border-bottom: 2px solid #008287; padding-bottom: 4px;")
        layout.addWidget(header)

        # Details Box
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #F8FAFC; border: 1px solid #BACCD9; border-radius: 2px; padding: 10px;")
        if_layout = QVBoxLayout(info_frame)
        if_layout.setSpacing(6)

        lbl_engine = QLabel(f"<b>當前使用核心:</b> {meta.get('engine_full', '標準引擎')}")
        lbl_engine.setStyleSheet("color: #0F172A; font-size: 12px;")
        if_layout.addWidget(lbl_engine)

        lbl_cat = QLabel(f"<b>所屬分析類別:</b> {meta.get('category', '生信分析')}")
        if_layout.addWidget(lbl_cat)

        lbl_paper = QLabel(f"<b>文獻出處 (Citation):</b><br><i>{meta.get('paper', 'Standard Laboratory Protocol')}</i>")
        lbl_paper.setWordWrap(True)
        lbl_paper.setStyleSheet("color: #475569; font-size: 11px;")
        if_layout.addWidget(lbl_paper)

        layout.addWidget(info_frame)

        # Alternative Engines Box
        alt_box = QGroupBox("可替換 / 擴充核心 (Interchangeable Modules):")
        alt_box.setStyleSheet("font-weight: bold; color: #008287;")
        ab_layout = QVBoxLayout(alt_box)
        ab_layout.setSpacing(6)

        alt_engines = meta.get("alt_engines", [])
        for alt in alt_engines:
            row = QLabel(f"• {alt}")
            row.setStyleSheet("color: #334155; font-size: 11px; font-weight: normal;")
            ab_layout.addWidget(row)

        note = QLabel("提示：PhyloCraft 採用模塊化標準輸入輸出介面，未來可隨時插拔或更換底層核心。")
        note.setStyleSheet("color: #64748B; font-size: 11px; font-style: italic; margin-top: 4px;")
        ab_layout.addWidget(note)

        layout.addWidget(alt_box)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("確定 (OK)")
        close_btn.setObjectName("primary_button")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


class ModuleLibraryDialog(QDialog):
    """
    Bioinformatics Tool Modules Library Dialog.
    Visualizes the entire modular assembly line architecture, loaded engines, and future extensible slots.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("生物資訊模塊庫與客製化生產線 (Bioinformatics Modules Library)")
        self.resize(780, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                color: #1E293B;
                font-size: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header Title
        title_lbl = QLabel("客製化生信模塊生產線架構 (Modular Assembly Line Architecture)")
        title_lbl.setStyleSheet("color: #008287; font-size: 15px; font-weight: bold; border-bottom: 2px solid #8B1E1E; padding-bottom: 5px;")
        layout.addWidget(title_lbl)

        desc = QLabel(
            "PhyloCraft 將 MEGA 的中央工作大白板革新為「生信模塊流水線 (Bioinformatics Pipeline Canvas)」。\n"
            "各工具依據標準化生物演化數據契約 (FASTA ➔ MSA ➔ Model ➔ Newick Tree ➔ Chronogram) 串接為自動化裝配線，\n"
            "研究者可自由勾選啟用、調整參數、旁路跳過，或於未來擴充外掛工具模塊。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #475569; font-size: 11px; background-color: #F8FAFC; border: 1px solid #BACCD9; border-radius: 2px; padding: 8px;")
        layout.addWidget(desc)

        # Table of Current & Extensible Modules
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["階段", "模塊名稱", "內建核心引擎", "輸入 / 輸出契約", "可擴充備選引擎"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        table.setRowCount(len(STEP_KEYS))
        table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #BACCD9;
                gridline-color: #E2E8F0;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #EAEFF5;
                color: #008287;
                font-weight: bold;
                border: 1px solid #BACCD9;
                padding: 4px;
            }
        """)

        for row, step_key in enumerate(STEP_KEYS):
            meta = MODULE_METADATA.get(step_key, {})
            title, _ = STEP_TITLES.get(step_key, (step_key, ""))
            io_contract = f"{meta.get('input_desc', '').replace('輸入: ', 'IN: ')} ➔ {meta.get('output_desc', '').replace('輸出: ', 'OUT: ')}"
            alts = ", ".join(meta.get("alt_engines", [])[:2])

            table.setItem(row, 0, QTableWidgetItem(f"[{meta.get('step_num', '00')}]"))
            table.setItem(row, 1, QTableWidgetItem(title.split("(")[0].strip()))
            table.setItem(row, 2, QTableWidgetItem(meta.get("engine", "標準")))
            table.setItem(row, 3, QTableWidgetItem(io_contract))
            table.setItem(row, 4, QTableWidgetItem(alts))

        layout.addWidget(table, 1)

        # Future Roadmap Box
        future_box = QGroupBox("未來可擴充模塊生態庫 (Future Extensible Modules Ecosystem):")
        future_box.setStyleSheet("color: #008287; font-weight: bold;")
        fb_layout = QHBoxLayout(future_box)
        fb_layout.setSpacing(12)

        f1 = QLabel("<b>超大規模建樹:</b><br>FastTree 2 (萬條序列)<br>RAxML-NG (高效平行)")
        f1.setStyleSheet("color: #334155; font-size: 11px; font-weight: normal;")
        fb_layout.addWidget(f1)

        f2 = QLabel("<b>結構感知比對:</b><br>MUSCLE v5 (高精準)<br>PRANK (演化感知對齊)")
        f2.setStyleSheet("color: #334155; font-size: 11px; font-weight: normal;")
        fb_layout.addWidget(f2)

        f3 = QLabel("<b>正向選汰檢定:</b><br>PAML / codeml (Ka/Ks)<br>HyPhy (分型檢定)")
        f3.setStyleSheet("color: #334155; font-size: 11px; font-weight: normal;")
        fb_layout.addWidget(f3)

        f4 = QLabel("<b>自訂外部節點:</b><br>Custom Python / Bash<br>支援研究室客製化腳本")
        f4.setStyleSheet("color: #334155; font-size: 11px; font-weight: normal;")
        fb_layout.addWidget(f4)

        layout.addWidget(future_box)

        # Footer Actions
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("關閉 (Close)")
        close_btn.setObjectName("primary_button")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


class StepBlockCard(QFrame):
    """
    Bioinformatics Visual Block Pipeline Card.
    Features:
    - Block Enable/Disable Checkbox (Bypass routing)
    - 1-Click Single Step Execution
    - Inline Parameters Drawer
    - Instant Data Inspector
    - Experiment Branching
    - Expandable Lab Notebook Memo
    - Modular Engine Information & Switching
    - Structured Biological Dataflow Specification
    """

    run_single_requested = Signal(str)   # step_key
    inspect_requested = Signal(str)      # step_key
    jump_tab_requested = Signal(str)    # step_key
    fork_requested = Signal(str)        # step_key
    note_changed = Signal(str, str)     # step_key, new_text
    enabled_changed = Signal(str, bool) # step_key, enabled
    open_preferences_requested = Signal(str) # step_key (MEGA Analysis Preferences)

    def __init__(self, step_key: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.step_key = step_key
        self.title, self.subfolder = STEP_TITLES.get(step_key, (step_key, ""))
        self.meta = MODULE_METADATA.get(step_key, {})
        self.current_record = StepRecord()
        self.notes_expanded = False
        self.params_expanded = False
        self.param_widgets = {}
        self.init_ui()

    def init_ui(self):
        self.setObjectName("step_block_card")
        self.setStyleSheet("""
            QFrame#step_block_card {
                background-color: #FFFFFF;
                border: 1px solid #BACCD9;
                border-left: 4px solid #008287;
                border-radius: 2px;
                padding: 8px;
            }
            QFrame#step_block_card:hover {
                border-color: #8BAAC6;
                border-left: 4px solid #006F73;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 1. Header Bar: Checkbox + Stage Tag + Title + Engine Tag + Run Single + Status Badge
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        self.enable_cb = QCheckBox()
        self.enable_cb.setChecked(True)
        self.enable_cb.setToolTip("啟用或跳過此積木模塊 (勾選代表在生產線中運作)")
        self.enable_cb.toggled.connect(self.on_enable_toggled)
        header_row.addWidget(self.enable_cb)

        step_num = self.meta.get("step_num", "00")
        self.stage_tag = QLabel(f"模塊 {step_num}")
        self.stage_tag.setStyleSheet("""
            background-color: #EAEFF5;
            color: #008287;
            font-size: 11px;
            font-weight: bold;
            padding: 2px 6px;
            border: 1px solid #BACCD9;
            border-radius: 2px;
        """)
        header_row.addWidget(self.stage_tag)

        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet("color: #0F172A; font-size: 13px; font-weight: bold;")
        header_row.addWidget(self.title_label)

        engine_name = self.meta.get("engine", "Core Engine")
        self.engine_tag = QLabel(f"核心: {engine_name}")
        self.engine_tag.setStyleSheet("""
            color: #475569;
            background-color: #F1F5F9;
            border: 1px solid #CBD5E1;
            padding: 2px 6px;
            border-radius: 2px;
            font-size: 11px;
        """)
        self.engine_tag.setToolTip("點選下方「更換/擴充引擎...」可檢視此模塊之詳細文獻與可替換演算法")
        header_row.addWidget(self.engine_tag)

        header_row.addStretch()

        self.run_btn = QPushButton("執行此步")
        self.run_btn.setFixedHeight(24)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #008287;
                color: #FFFFFF;
                font-weight: bold;
                border: 1px solid #00666B;
                border-radius: 2px;
                padding: 2px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #006F73;
                color: #FFFFFF;
            }
            QPushButton:disabled {
                background-color: #BACCD9;
                border-color: #94A3B8;
                color: #FFFFFF;
            }
        """)
        self.run_btn.setToolTip("單獨執行此生信模塊進行計算與驗證")
        self.run_btn.clicked.connect(lambda: self.run_single_requested.emit(self.step_key))
        header_row.addWidget(self.run_btn)

        self.status_badge = QLabel("待執行")
        self.status_badge.setStyleSheet("""
            background-color: #F1F5F9;
            color: #64748B;
            font-size: 11px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 2px;
            border: 1px solid #BACCD9;
        """)
        header_row.addWidget(self.status_badge)

        layout.addLayout(header_row)

        # 2. Biological Data Pipeline Stream Bar (Input -> Output)
        data_stream_row = QHBoxLayout()
        data_stream_row.setContentsMargins(0, 0, 0, 0)
        data_stream_row.setSpacing(4)

        in_desc = self.meta.get("input_desc", "輸入: 數據資料")
        out_desc = self.meta.get("output_desc", "輸出: 分析產物")
        self.stream_label = QLabel(f"▼ 接點 [IN] {in_desc.replace('輸入: ', '')}   ──►   [OUT] {out_desc.replace('輸出: ', '')} ▲")
        self.stream_label.setStyleSheet("""
            color: #008287;
            font-size: 11px;
            font-weight: 500;
            background-color: #F8FAFC;
            border: 1px solid #BACCD9;
            padding: 3px 8px;
            border-radius: 2px;
        """)
        self.stream_label.setWordWrap(True)
        data_stream_row.addWidget(self.stream_label, 1)
        layout.addLayout(data_stream_row)

        # 3. Summary Badge / Biological Payload chip
        self.summary_chip = QLabel("尚未執行此步驟。")
        self.summary_chip.setStyleSheet("""
            color: #475569;
            font-size: 11px;
            background-color: #FFFFFF;
            border: 1px solid #CBD5E1;
            padding: 5px 8px;
            border-radius: 2px;
        """)
        self.summary_chip.setWordWrap(True)
        layout.addWidget(self.summary_chip)

        # 4. Mini Progress Bar (shown when running)
        self.mini_progress = QProgressBar()
        self.mini_progress.setFixedHeight(4)
        self.mini_progress.setRange(0, 0)  # indeterminate pulse
        self.mini_progress.setTextVisible(False)
        self.mini_progress.setVisible(False)
        self.mini_progress.setStyleSheet("""
            QProgressBar {
                background-color: #E2E8F0;
                border-radius: 1px;
            }
            QProgressBar::chunk {
                background-color: #008287;
                border-radius: 1px;
            }
        """)
        layout.addWidget(self.mini_progress)

        # 5. Command chip (if executed)
        self.cmd_chip = QLabel("")
        self.cmd_chip.setStyleSheet("color: #008287; font-size: 11px; font-family: Consolas, monospace;")
        self.cmd_chip.setVisible(False)
        self.cmd_chip.setWordWrap(True)
        layout.addWidget(self.cmd_chip)

        # 6. Action Buttons Toolbar (2 Neat Rows)
        r1_btns = QHBoxLayout()
        r1_btns.setSpacing(6)

        self.pref_btn = QPushButton("偏好設定...")
        self.pref_btn.setFixedHeight(24)
        self.pref_btn.setStyleSheet("color: #008287; font-weight: bold;")
        self.pref_btn.setToolTip("開啟 MEGA 12 經典點後表單 (Analysis Preferences) 設定詳細參數")
        self.pref_btn.clicked.connect(lambda: self.open_preferences_requested.emit(self.step_key))
        r1_btns.addWidget(self.pref_btn)

        self.inspect_btn = QPushButton("檢視結果")
        self.inspect_btn.setFixedHeight(24)
        self.inspect_btn.setToolTip("快速檢視該模塊產出之序列、比對矩陣或演化樹檔案")
        self.inspect_btn.clicked.connect(lambda: self.inspect_requested.emit(self.step_key))
        r1_btns.addWidget(self.inspect_btn)

        self.params_btn = QPushButton("參數抽屜")
        self.params_btn.setFixedHeight(24)
        self.params_btn.setToolTip("展開此步驟之生物演化分析參數內嵌抽屜")
        self.params_btn.clicked.connect(self.toggle_params)
        r1_btns.addWidget(self.params_btn)

        self.note_toggle_btn = QPushButton("實驗筆記 (0)")
        self.note_toggle_btn.setFixedHeight(24)
        self.note_toggle_btn.setToolTip("記錄該步驟之科學觀察備忘錄")
        self.note_toggle_btn.clicked.connect(self.toggle_notes)
        r1_btns.addWidget(self.note_toggle_btn)
        layout.addLayout(r1_btns)

        r2_btns = QHBoxLayout()
        r2_btns.setSpacing(6)

        self.fork_btn = QPushButton("建立對照分支")
        self.fork_btn.setFixedHeight(24)
        self.fork_btn.setToolTip("以此模塊為起點複製一條對照實驗分支（如不同修剪標準或替代模型）")
        self.fork_btn.clicked.connect(lambda: self.fork_requested.emit(self.step_key))
        r2_btns.addWidget(self.fork_btn)

        self.jump_btn = QPushButton("前往分頁")
        self.jump_btn.setFixedHeight(24)
        self.jump_btn.setStyleSheet("color: #008287; font-weight: 500;")
        self.jump_btn.setToolTip("跳轉至此步驟之專屬進階分析分頁")
        self.jump_btn.clicked.connect(lambda: self.jump_tab_requested.emit(self.step_key))
        r2_btns.addWidget(self.jump_btn)

        self.engine_btn = QPushButton("更換/擴充引擎...")
        self.engine_btn.setFixedHeight(24)
        self.engine_btn.setToolTip("檢視此模塊核心演算法、文獻出處與可擴充之備選工具")
        self.engine_btn.clicked.connect(self.open_engine_dialog)
        r2_btns.addWidget(self.engine_btn)

        layout.addLayout(r2_btns)

        # 7. Inline Parameter Drawer (Collapsible)
        self.params_drawer = QFrame()
        self.params_drawer.setVisible(False)
        self.params_drawer.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #BACCD9;
                border-left: 3px solid #008287;
                border-radius: 2px;
                padding: 6px;
            }
        """)
        self.build_params_drawer()
        layout.addWidget(self.params_drawer)

        # 8. Student Note Drawer (Collapsible)
        self.note_drawer = QFrame()
        self.note_drawer.setVisible(False)
        self.note_drawer.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #BACCD9;
                border-left: 3px solid #B45309;
                border-radius: 2px;
                padding: 6px;
            }
        """)
        nd_layout = QVBoxLayout(self.note_drawer)
        nd_layout.setContentsMargins(6, 6, 6, 6)
        nd_layout.setSpacing(4)

        note_title = QLabel("研究生實驗觀察備忘錄 (Student Observations & Reasoning):")
        note_title.setStyleSheet("color: #B45309; font-size: 11px; font-weight: bold;")
        nd_layout.addWidget(note_title)

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText(
            "請在此記錄您的實驗思考（例如：選擇此參數之文獻理由、物種篩選備忘）。\n"
            "內容將自動永久儲存並納入論文電子實驗日誌 (ELN) 中。"
        )
        self.note_edit.setMaximumHeight(70)
        self.note_edit.setStyleSheet("font-size: 12px; color: #1E293B; background-color: #FFFFFF; border: 1px solid #BACCD9; border-radius: 2px;")
        self.note_edit.textChanged.connect(self.on_note_text_changed)
        nd_layout.addWidget(self.note_edit)

        layout.addWidget(self.note_drawer)

    def open_engine_dialog(self):
        dlg = EngineInfoDialog(self.step_key, self)
        dlg.exec()

    def build_params_drawer(self):
        pd_layout = QVBoxLayout(self.params_drawer)
        pd_layout.setContentsMargins(6, 6, 6, 6)
        pd_layout.setSpacing(6)

        p_title = QLabel(f"模塊專屬參數設定 — {self.title}")
        p_title.setStyleSheet("color: #008287; font-size: 11px; font-weight: bold;")
        pd_layout.addWidget(p_title)

        # Build controls tailored to this step
        if self.step_key == "raw":
            row = QHBoxLayout()
            row.addWidget(QLabel("輸入序列 FASTA:"))
            edit = QLineEdit()
            edit.setPlaceholderText("請選取或拖曳序列檔案...")
            row.addWidget(edit, 1)
            b_btn = QPushButton("瀏覽...")
            b_btn.clicked.connect(lambda: self.browse_raw_file(edit))
            row.addWidget(b_btn)
            sample_btn = QPushButton("載入內建範例")
            sample_btn.clicked.connect(lambda: self.load_raw_sample(edit))
            row.addWidget(sample_btn)
            pd_layout.addLayout(row)
            self.param_widgets["fasta_path"] = edit

        elif self.step_key == "sanitize":
            r1 = QHBoxLayout()
            cb_nc = QCheckBox("過濾 NCBI 特殊標頭字元（空格、斜線轉為下劃線）")
            cb_nc.setChecked(True)
            r1.addWidget(cb_nc)
            cb_len = QCheckBox("自動過濾小於 30 bp 之短殘缺序列")
            cb_len.setChecked(True)
            r1.addWidget(cb_len)
            pd_layout.addLayout(r1)
            self.param_widgets["clean_headers"] = cb_nc
            self.param_widgets["filter_short"] = cb_len

        elif self.step_key == "alignment":
            row = QHBoxLayout()
            row.addWidget(QLabel("MAFFT 比對策略:"))
            algo_combo = QComboBox()
            algo_combo.addItems([
                "auto (智慧自動判斷 - 推薦)",
                "localpair (L-INS-i 高精度局部對齊 - 論文推薦)",
                "globalpair (G-INS-i 全域對齊)",
                "fftns2 (FFT-NS-2 超快速啟發式)",
            ])
            row.addWidget(algo_combo, 2)
            row.addWidget(QLabel("執行緒:"))
            th_combo = QComboBox()
            th_combo.addItems(["AUTO", "1", "2", "4", "8"])
            row.addWidget(th_combo, 1)
            pd_layout.addLayout(row)
            self.param_widgets["strategy"] = algo_combo
            self.param_widgets["threads"] = th_combo

        elif self.step_key == "trimming":
            row = QHBoxLayout()
            row.addWidget(QLabel("trimAl 修剪演算法:"))
            algo_combo = QComboBox()
            algo_combo.addItems([
                "automated1 (期刊標準智慧啟發式 - 推薦)",
                "gappyout (移除高 Gap 空缺位點)",
                "strict (嚴格保守區過濾)",
                "strictplus (超嚴格修剪)",
            ])
            row.addWidget(algo_combo, 2)
            pd_layout.addLayout(row)
            self.param_widgets["method"] = algo_combo

        elif self.step_key == "modelfinder":
            row = QHBoxLayout()
            row.addWidget(QLabel("模型搜尋集合:"))
            scope_combo = QComboBox()
            scope_combo.addItems([
                "TESTONLY (常用標準模型 + 異質率 - 推薦)",
                "TESTNEWONLY (含 FreeRate +R 異質率)",
                "protein (常用蛋白質 22 種模式)",
            ])
            row.addWidget(scope_combo, 2)
            row.addWidget(QLabel("評選標準:"))
            crit_combo = QComboBox()
            crit_combo.addItems(["BIC (貝氏推薦)", "AIC", "AICc"])
            row.addWidget(crit_combo, 1)
            pd_layout.addLayout(row)
            self.param_widgets["scope"] = scope_combo
            self.param_widgets["criterion"] = crit_combo

        elif self.step_key == "tree":
            row = QHBoxLayout()
            row.addWidget(QLabel("替代模式:"))
            m_combo = QComboBox()
            m_combo.setEditable(True)
            m_combo.addItems(["MFP (全自動 ModelFinder 檢定)", "Q.PLANT+I+G4", "LG+G4", "GTR+I+G4", "JTT+G4"])
            row.addWidget(m_combo, 2)
            row.addWidget(QLabel("UFBoot:"))
            boot_spin = QSpinBox()
            boot_spin.setRange(100, 10000)
            boot_spin.setSingleStep(500)
            boot_spin.setValue(1000)
            row.addWidget(boot_spin, 1)
            row.addWidget(QLabel("SH-aLRT:"))
            alrt_spin = QSpinBox()
            alrt_spin.setRange(0, 10000)
            alrt_spin.setSingleStep(500)
            alrt_spin.setValue(1000)
            row.addWidget(alrt_spin, 1)
            pd_layout.addLayout(row)
            self.param_widgets["model"] = m_combo
            self.param_widgets["bootstrap"] = boot_spin
            self.param_widgets["alrt"] = alrt_spin

        elif self.step_key == "timetree":
            row = QHBoxLayout()
            row.addWidget(QLabel("定年演算法:"))
            c_combo = QComboBox()
            c_combo.addItems(["LSD2 (最小平方法時間樹)"])
            row.addWidget(c_combo)
            row.addWidget(QLabel("離群檢驗:"))
            out_spin = QDoubleSpinBox()
            out_spin.setRange(0.0, 10.0)
            out_spin.setValue(3.0)
            row.addWidget(out_spin)
            pd_layout.addLayout(row)

            row2 = QHBoxLayout()
            row2.addWidget(QLabel("定年校準檔 (Date File):"))
            df_edit = QLineEdit()
            df_edit.setPlaceholderText("選填: 物種年代/化石校準檔 (*.txt)...")
            row2.addWidget(df_edit, 1)
            b_btn = QPushButton("瀏覽...")
            b_btn.clicked.connect(lambda: self.browse_date_file(df_edit))
            row2.addWidget(b_btn)
            pd_layout.addLayout(row2)

            self.param_widgets["clock_method"] = c_combo
            self.param_widgets["outlier"] = out_spin
            self.param_widgets["date_file"] = df_edit

    def browse_date_file(self, edit: QLineEdit):
        fp, _ = QFileDialog.getOpenFileName(
            self, "選取物種年代/化石校準檔案", str(OUTPUT_DIR), "Date Files (*.txt *.tsv *.dates);;All Files (*)"
        )
        if fp:
            edit.setText(fp)

    def browse_raw_file(self, edit: QLineEdit):
        fp, _ = QFileDialog.getOpenFileName(
            self, "選取輸入序列檔案", str(OUTPUT_DIR), "FASTA Files (*.fasta *.fa *.fas *.aln);;All Files (*)"
        )
        if fp:
            edit.setText(fp)

    def load_raw_sample(self, edit: QLineEdit):
        for s in [DATA_DIR / "angiosperms_etr.fasta", DATA_DIR / "primates_cytb.fasta", Path("data/angiosperms_etr.fasta"), Path("data/primates_cytb.fasta")]:
            if s.exists():
                edit.setText(str(s.resolve()))
                return

    def get_parameters(self) -> dict:
        params = {}
        for k, w in self.param_widgets.items():
            if isinstance(w, QComboBox):
                params[k] = w.currentText().split()[0]
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                params[k] = w.value()
            elif isinstance(w, QCheckBox):
                params[k] = w.isChecked()
            elif isinstance(w, QLineEdit):
                params[k] = w.text().strip()
        return params

    def set_parameters(self, params: dict):
        for k, v in params.items():
            if k in self.param_widgets:
                w = self.param_widgets[k]
                if isinstance(w, QComboBox):
                    idx = w.findText(str(v), Qt.MatchStartsWith)
                    if idx >= 0:
                        w.setCurrentIndex(idx)
                elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                    try:
                        w.setValue(type(w.value())(v))
                    except Exception:
                        pass
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(v))
                elif isinstance(w, QLineEdit):
                    w.setText(str(v))

    def on_enable_toggled(self, checked: bool):
        self.enabled_changed.emit(self.step_key, checked)
        self.run_btn.setEnabled(checked)
        if checked:
            self.setStyleSheet("""
                QFrame#step_block_card {
                    background-color: #FFFFFF;
                    border: 1px solid #BACCD9;
                    border-left: 4px solid #008287;
                    border-radius: 2px;
                    padding: 8px;
                }
                QFrame#step_block_card:hover {
                    border-color: #8BAAC6;
                    border-left: 4px solid #006F73;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#step_block_card {
                    background-color: #F8FAFC;
                    border: 1px dashed #BACCD9;
                    border-left: 4px solid #94A3B8;
                    border-radius: 2px;
                    padding: 8px;
                }
            """)

    def set_running_state(self, running: bool):
        self.mini_progress.setVisible(running)
        self.run_btn.setEnabled(not running)
        if running:
            self.status_badge.setText("運算中...")
            self.status_badge.setStyleSheet(
                "font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 2px; "
                "background-color: #FEF3C7; color: #B45309; border: 1px solid #FDE68A;"
            )

    def set_record(self, record: StepRecord):
        self.current_record = record
        self.mini_progress.setVisible(False)
        self.run_btn.setEnabled(self.enable_cb.isChecked())

        status_styles = {
            "completed": ("已完成", "background-color: #DCFCE7; color: #15803D; border: 1px solid #86EFAC;"),
            "running": ("執行中...", "background-color: #FEF3C7; color: #B45309; border: 1px solid #FDE68A;"),
            "failed": ("失敗", "background-color: #FEE2E2; color: #B91C1C; border: 1px solid #FCA5A5;"),
            "pending": ("待執行", "background-color: #F1F5F9; color: #64748B; border: 1px solid #BACCD9;"),
        }
        text, style = status_styles.get(record.status, status_styles["pending"])
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(f"font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 2px; {style}")

        self.summary_chip.setText(record.summary or "尚未執行此步驟。")
        if record.status == "completed":
            self.summary_chip.setStyleSheet("color: #15803D; font-size: 11px; background-color: #F0FDF4; border: 1px solid #BBF7D0; padding: 5px 8px; border-radius: 2px;")
        else:
            self.summary_chip.setStyleSheet("color: #475569; font-size: 11px; background-color: #FFFFFF; border: 1px solid #CBD5E1; padding: 5px 8px; border-radius: 2px;")

        if record.command_line:
            self.cmd_chip.setText(f"執行命令: {record.command_line}")
            self.cmd_chip.setVisible(True)
        else:
            self.cmd_chip.setVisible(False)

        notes = record.student_notes or ""
        char_count = len(notes.strip())
        self.note_toggle_btn.setText(f"實驗筆記 ({char_count} 字)" if char_count > 0 else "實驗筆記 (0)")
        if self.note_edit.toPlainText() != notes:
            self.note_edit.blockSignals(True)
            self.note_edit.setPlainText(notes)
            self.note_edit.blockSignals(False)

        if record.parameters:
            self.set_parameters(record.parameters)

        self.inspect_btn.setEnabled(len(record.output_files) > 0)

    def toggle_params(self):
        self.params_expanded = not self.params_expanded
        self.params_drawer.setVisible(self.params_expanded)

    def toggle_notes(self):
        self.notes_expanded = not self.notes_expanded
        self.note_drawer.setVisible(self.notes_expanded)
        if self.notes_expanded:
            self.note_edit.setFocus()

    def on_note_text_changed(self):
        txt = self.note_edit.toPlainText()
        self.note_changed.emit(self.step_key, txt)
        char_count = len(txt.strip())
        self.note_toggle_btn.setText(f"實驗筆記 ({char_count} 字)" if char_count > 0 else "實驗筆記 (0)")


class DataFlowConnector(QWidget):
    """
    Visual flow arrow cable representing structured bioinformatics data flow between steps in the production line.
    Supports dynamic bypass label when a block is disabled.
    """

    def __init__(self, step_key: str, default_label: str = "數據流向", parent: QWidget | None = None):
        super().__init__(parent)
        self.step_key = step_key
        self.default_label = default_label
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(2)

        self.arrow_badge = QLabel(f"  ▼   {default_label}   ▼  ")
        self.arrow_badge.setStyleSheet("""
            color: #008287;
            font-size: 11px;
            font-weight: bold;
            background-color: #FFFFFF;
            border: 2px solid #008287;
            border-radius: 3px;
            padding: 3px 18px;
        """)
        layout.addWidget(self.arrow_badge)

    def set_bypassed(self, bypassed: bool):
        if bypassed:
            self.arrow_badge.setText("  ↷  已跳過此模塊 (Bypassed) ── 數據沿導線直接順流傳輸至下一站  ↷  ")
            self.arrow_badge.setStyleSheet("""
                color: #B45309;
                font-size: 11px;
                font-weight: bold;
                background-color: #FEF3C7;
                border: 2px dashed #F59E0B;
                border-radius: 3px;
                padding: 3px 18px;
            """)
        else:
            self.arrow_badge.setText(f"  ▼   {self.default_label}   ▼  ")
            self.arrow_badge.setStyleSheet("""
                color: #008287;
                font-size: 11px;
                font-weight: bold;
                background-color: #FFFFFF;
                border: 2px solid #008287;
                border-radius: 3px;
                padding: 3px 18px;
            """)


class BlockPipelineCanvas(QWidget):
    """
    Bioinformatics Visual Modular Production Line Canvas.
    Replaces MEGA's static central canvas with an interactive, extensible modular assembly line.
    Supports:
    - Block enable/disable with dynamic dataflow cable bypass routing
    - Single-step and full workflow background running
    - Inline parameter inspection
    - Step-level experiment branching
    - Tool Modules Library & Extensibility Dialog
    - Live Roadmap breadcrumbs across the 7 stages
    """

    step_jump_requested = Signal(str)      # tab route
    inspect_step_requested = Signal(str)   # inspect output of step
    run_step_requested = Signal(str)       # run single step
    fork_step_requested = Signal(str)      # fork branch
    project_note_saved = Signal(str, str)  # step_key, note
    open_preferences_requested = Signal(str) # step_key (MEGA Analysis Preferences)

    FLOW_LABELS = {
        "raw": "傳遞原始 FASTA 序列至品管過濾模塊",
        "sanitize": "傳遞標準化乾淨序列至多重比對引擎 (MAFFT)",
        "alignment": "傳遞高品質比對矩陣至位點修剪模塊 (trimAl)",
        "trimming": "傳遞修剪後無雜訊位點至最適演化模型檢定 (ModelFinder)",
        "modelfinder": "將 BIC 最優替代模型與對齊矩陣送入最大概似法建樹 (IQ-TREE)",
        "tree": "傳遞拓撲樹與分支長度至分子鐘模塊 (LSD2)",
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.cards: dict[str, StepBlockCard] = {}
        self.connectors: dict[str, DataFlowConnector] = {}
        self.roadmap_chips: dict[str, QLabel] = {}
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Top Assembly Line Banner & Roadmap Tracker
        top_banner = QFrame()
        top_banner.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #BACCD9;
                border-radius: 2px;
                padding: 6px 10px;
            }
        """)
        tb_layout = QVBoxLayout(top_banner)
        tb_layout.setContentsMargins(6, 4, 6, 4)
        tb_layout.setSpacing(4)

        # Banner Title & Library Action
        r1 = QHBoxLayout()
        r1.setContentsMargins(0, 0, 0, 0)
        banner_title = QLabel("客製化生信模塊生產線 (Bioinformatics Modular Assembly Line)")
        banner_title.setStyleSheet("color: #008287; font-size: 13px; font-weight: bold;")
        r1.addWidget(banner_title)

        banner_sub = QLabel("— 各處理模塊均為可插拔、可微調、可擴充之分析節點")
        banner_sub.setStyleSheet("color: #64748B; font-size: 11px;")
        r1.addWidget(banner_sub)

        r1.addStretch()

        lib_btn = QPushButton("模塊擴充庫 (Tool Modules Library)")
        lib_btn.setFixedHeight(24)
        lib_btn.setStyleSheet("""
            QPushButton {
                background-color: #EAEFF5;
                color: #008287;
                font-weight: bold;
                border: 1px solid #BACCD9;
                border-radius: 2px;
                padding: 2px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        lib_btn.setToolTip("檢視生信模塊庫規格、可插拔備選工具 (FastTree, MUSCLE, ClipKIT, PAML) 與擴充指南")
        lib_btn.clicked.connect(self.open_module_library)
        r1.addWidget(lib_btn)

        tb_layout.addLayout(r1)

        # Roadmap Breadcrumb Row
        roadmap_row = QHBoxLayout()
        roadmap_row.setContentsMargins(0, 2, 0, 0)
        roadmap_row.setSpacing(4)

        for i, k in enumerate(STEP_KEYS):
            meta = MODULE_METADATA.get(k, {})
            step_num = meta.get("step_num", "00")
            short_title = STEP_TITLES[k][0].split("(")[0].strip()

            chip = QLabel(f"[{step_num}] {short_title}")
            chip.setStyleSheet("""
                background-color: #F1F5F9;
                color: #475569;
                font-size: 11px;
                padding: 2px 6px;
                border: 1px solid #CBD5E1;
                border-radius: 2px;
            """)
            self.roadmap_chips[k] = chip
            roadmap_row.addWidget(chip)

            if i < len(STEP_KEYS) - 1:
                arr = QLabel("➔")
                arr.setStyleSheet("color: #BACCD9; font-size: 11px; font-weight: bold;")
                roadmap_row.addWidget(arr)

        roadmap_row.addStretch()
        tb_layout.addLayout(roadmap_row)

        main_layout.addWidget(top_banner)

        # 2. Central Scrollable Canvas (The Great White Board / 巨大純白畫布)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #FFFFFF; border: 1px solid #BACCD9; border-radius: 2px;")

        container = QWidget()
        container.setStyleSheet("background-color: #FFFFFF;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(12, 10, 12, 15)
        c_layout.setSpacing(8)

        # Build blocks sequentially
        for i, step_key in enumerate(STEP_KEYS):
            card = StepBlockCard(step_key)
            card.jump_tab_requested.connect(self.step_jump_requested.emit)
            card.inspect_requested.connect(self.inspect_step_requested.emit)
            card.run_single_requested.connect(self.run_step_requested.emit)
            card.fork_requested.connect(self.fork_step_requested.emit)
            card.note_changed.connect(self.project_note_saved.emit)
            card.enabled_changed.connect(self.on_card_enabled_changed)
            card.open_preferences_requested.connect(self.open_preferences_requested.emit)
            self.cards[step_key] = card
            c_layout.addWidget(card)

            # Add Flow connector arrow between blocks
            if i < len(STEP_KEYS) - 1:
                label = self.FLOW_LABELS.get(step_key, "傳遞中間數據")
                connector = DataFlowConnector(step_key, label)
                self.connectors[step_key] = connector
                c_layout.addWidget(connector)

        c_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

    def open_module_library(self):
        dlg = ModuleLibraryDialog(self)
        dlg.exec()

    def on_card_enabled_changed(self, step_key: str, enabled: bool):
        if step_key in self.connectors:
            self.connectors[step_key].set_bypassed(not enabled)
        self.update_roadmap()

    def update_roadmap(self):
        for k, chip in self.roadmap_chips.items():
            card = self.cards.get(k)
            if not card:
                continue
            step_num = MODULE_METADATA.get(k, {}).get("step_num", "00")
            short_title = STEP_TITLES[k][0].split("(")[0].strip()

            if not card.enable_cb.isChecked():
                chip.setText(f"[{step_num}] {short_title} (跳過)")
                chip.setStyleSheet("background-color: #F8FAFC; color: #94A3B8; font-size: 11px; padding: 2px 6px; border: 1px dashed #CBD5E1; border-radius: 2px;")
            elif card.current_record.status == "completed":
                chip.setText(f"[✓ {step_num}] {short_title}")
                chip.setStyleSheet("background-color: #DCFCE7; color: #15803D; font-size: 11px; font-weight: bold; padding: 2px 6px; border: 1px solid #86EFAC; border-radius: 2px;")
            elif card.current_record.status == "running":
                chip.setText(f"[⟳ {step_num}] {short_title}")
                chip.setStyleSheet("background-color: #FEF3C7; color: #B45309; font-size: 11px; font-weight: bold; padding: 2px 6px; border: 1px solid #FDE68A; border-radius: 2px;")
            elif card.current_record.status == "failed":
                chip.setText(f"[✕ {step_num}] {short_title}")
                chip.setStyleSheet("background-color: #FEE2E2; color: #B91C1C; font-size: 11px; font-weight: bold; padding: 2px 6px; border: 1px solid #FCA5A5; border-radius: 2px;")
            else:
                chip.setText(f"[{step_num}] {short_title}")
                chip.setStyleSheet("background-color: #F1F5F9; color: #475569; font-size: 11px; padding: 2px 6px; border: 1px solid #CBD5E1; border-radius: 2px;")

    def load_project_state(self, project: PhyloProject):
        for step_key, card in self.cards.items():
            record = project.steps.get(step_key, StepRecord())
            card.set_record(record)
        self.update_roadmap()
