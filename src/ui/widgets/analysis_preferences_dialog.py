"""
MEGA 12 Analysis Preferences Dialog (點後表單).
Replicates MEGA 12's iconic analysis options modal property sheet:
- Two-column Property Grid layout (Option → Setting)
- Categorized section dividers (Teal bold uppercase: ANALYSIS, SUBSTITUTION MODEL, etc.)
- Crisp academic widgets (#F7F8F8 canvas, #BACCD9 borders, #008287 primary action)
- Bottom action buttons: Help, Cancel, Save Settings, Compute
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QCheckBox,
    QFileDialog,
    QScrollArea,
    QFrame,
    QTabWidget,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor


class AnalysisPreferencesDialog(QDialog):
    """
    Iconic MEGA 12 Analysis Preferences Dialog.
    """

    def __init__(self, analysis_type: str, initial_params: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.analysis_type = analysis_type
        self.params = dict(initial_params or {})
        self.should_compute = False
        self.controls = {}

        self.setup_ui()

    def setup_ui(self):
        titles = {
            "raw": ("分析偏好設定: 原始序列檔案與分子型態", "Raw Sequence Input & Molecular Data"),
            "tree": ("分析偏好設定: 最大概似法系統發育建樹 (IQ-TREE 2)", "Maximum Likelihood Tree Inference"),
            "modelfinder": ("分析偏好設定: 尋找最佳演化替代模型 (ModelFinder)", "Find Best DNA/Protein Models (ML)"),
            "alignment": ("分析偏好設定: 多重序列比對 (MAFFT)", "Multiple Sequence Alignment (MAFFT)"),
            "trimming": ("分析偏好設定: 比對序列修剪 (trimAl)", "Trimming & Filtering (trimAl)"),
            "timetree": ("分析偏好設定: 分子鐘分歧時間定年 (LSD2 / RelTime)", "Estimate Divergence Times (ML)"),
            "sanitize": ("分析偏好設定: 序列品管防呆與格式化", "Sequence Sanitizer & Quality Control"),
            "concat": ("分析偏好設定: 多基因超矩陣串接與分區", "Multi-Gene Supermatrix Concatenation"),
        }
        title_zh, title_en = titles.get(self.analysis_type, ("分析偏好設定 (Analysis Preferences)", "Analysis Preferences"))
        self.setWindowTitle(f"Analysis Preferences: {title_en}")
        self.resize(580, 560)
        self.setMinimumSize(540, 500)

        # MEGA Palette
        self.setStyleSheet("""
            QDialog {
                background-color: #F7F8F8;
            }
            QLabel {
                font-family: "Segoe UI", "Proxima Nova", Arial, sans-serif;
                color: #222222;
            }
            QTabWidget::pane {
                border: 1px solid #BACCD9;
                background-color: #F7F8F8;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #E2E8F0;
                color: #334155;
                border: 1px solid #BACCD9;
                border-bottom: none;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 500;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #F7F8F8;
                color: #008287;
                font-weight: bold;
                border-bottom: 1px solid #F7F8F8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Tab Widget (MEGA tab header)
        tabs = QTabWidget()
        tab_main = QWidget()
        tab_main_layout = QVBoxLayout(tab_main)
        tab_main_layout.setContentsMargins(0, 0, 0, 0)
        tab_main_layout.setSpacing(0)

        # Property grid scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background-color: #F7F8F8;")

        grid_container = QWidget()
        grid_container.setStyleSheet("background-color: #F7F8F8;")
        self.grid_layout = QVBoxLayout(grid_container)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(1)

        # 1. Header Bar: Option | Setting
        header_bar = QWidget()
        header_bar.setFixedHeight(28)
        header_bar.setStyleSheet("background-color: #8F9CA8; border: 1px solid #788998;")
        h_layout = QHBoxLayout(header_bar)
        h_layout.setContentsMargins(12, 0, 12, 0)

        opt_lbl = QLabel("Option")
        opt_lbl.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 12px;")
        opt_lbl.setFixedWidth(200)

        set_lbl = QLabel("Setting")
        set_lbl.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 12px;")

        h_layout.addWidget(opt_lbl)
        h_layout.addWidget(set_lbl)
        self.grid_layout.addWidget(header_bar)

        # 2. Build rows based on analysis type
        if self.analysis_type == "raw":
            self.build_raw_options()
        elif self.analysis_type == "tree":
            self.build_tree_options()
        elif self.analysis_type == "modelfinder":
            self.build_modelfinder_options()
        elif self.analysis_type == "alignment":
            self.build_alignment_options()
        elif self.analysis_type == "trimming":
            self.build_trimming_options()
        elif self.analysis_type == "timetree":
            self.build_timetree_options()
        elif self.analysis_type == "sanitize":
            self.build_sanitize_options()
        else:
            self.build_generic_options()

        self.grid_layout.addStretch()
        scroll.setWidget(grid_container)
        tab_main_layout.addWidget(scroll)

        tabs.addTab(tab_main, f"{title_en}")

        # Secondary tab: Information / Citations
        tab_info = QWidget()
        info_layout = QVBoxLayout(tab_info)
        info_layout.setContentsMargins(16, 16, 16, 16)
        info_desc = QLabel(
            f"<b>{title_zh}</b><br><br>"
            f"本分析表單完全參照 MEGA 12 經典「點後表單」(Analysis Preferences) 規範設計。<br>"
            f"在點選「計算 (Compute)」後，系統將自動驗證所有輸入參數，並在背景以多執行緒執行高通量演化計算。<br><br>"
            f"<b>計算引擎:</b> IQ-TREE 2 / ModelFinder / MAFFT / trimAl / LSD2<br>"
            f"<b>資料流狀態:</b> 參數自動與專案工作站及實驗紀錄簿同步存檔。"
        )
        info_desc.setWordWrap(True)
        info_desc.setStyleSheet("color: #334155; font-size: 12px; line-height: 1.5;")
        info_layout.addWidget(info_desc)
        info_layout.addStretch()
        tabs.addTab(tab_info, "說明與文獻 (Information)")

        layout.addWidget(tabs, 1)

        # 3. Action Buttons Footer
        footer = QWidget()
        footer.setFixedHeight(42)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(4, 4, 4, 4)
        f_layout.setSpacing(10)

        help_btn = QPushButton("? 說明 (Help)")
        help_btn.setFixedHeight(28)
        help_btn.setMinimumWidth(85)
        help_btn.setStyleSheet(self._button_style_secondary())
        help_btn.clicked.connect(self.show_help_dialog)
        f_layout.addWidget(help_btn)

        f_layout.addStretch()

        cancel_btn = QPushButton("取消 (Cancel)")
        cancel_btn.setFixedHeight(28)
        cancel_btn.setMinimumWidth(80)
        cancel_btn.setStyleSheet(self._button_style_secondary())
        cancel_btn.clicked.connect(self.reject)
        f_layout.addWidget(cancel_btn)

        self.save_btn = QPushButton("儲存設定 (Save Settings)")
        self.save_btn.setFixedHeight(28)
        self.save_btn.setMinimumWidth(155)
        self.save_btn.setToolTip("保存目前偏好設定並返回視窗")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #008287;
                border: 1px solid #008287;
                border-radius: 2px;
                padding: 2px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EBF7F7;
            }
        """)
        self.save_btn.clicked.connect(self.on_save_clicked)
        f_layout.addWidget(self.save_btn)

        self.compute_btn = QPushButton("執行計算 (Compute)")
        self.compute_btn.setFixedHeight(28)
        self.compute_btn.setMinimumWidth(125)
        self.compute_btn.setToolTip("驗證並保存設定，立即開始分析計算")
        self.compute_btn.setStyleSheet("""
            QPushButton {
                background-color: #008287;
                color: #FFFFFF;
                border: 1px solid #006C70;
                border-radius: 2px;
                padding: 2px 18px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #006C70;
            }
        """)
        self.compute_btn.clicked.connect(self.on_compute_clicked)
        f_layout.addWidget(self.compute_btn)

        layout.addWidget(footer)

    def _button_style_secondary(self) -> str:
        return """
            QPushButton {
                background-color: #FFFFFF;
                color: #222222;
                border: 1px solid #BACCD9;
                border-radius: 2px;
                padding: 2px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #F0F4F8;
                border-color: #9AAAB8;
            }
        """

    def _control_style(self) -> str:
        return """
            background-color: #FFFFFF;
            border: 1px solid #BACCD9;
            border-radius: 1px;
            padding: 2px 6px;
            font-size: 11px;
            color: #222222;
            height: 22px;
        """

    def add_section_header(self, text: str):
        sec = QWidget()
        sec.setFixedHeight(24)
        sec.setStyleSheet("background-color: #EBF1F5; border: 1px solid #D6E2EB; margin-top: 3px;")
        l = QHBoxLayout(sec)
        l.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(text.upper())
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #00828A; font-weight: bold; font-size: 11px; letter-spacing: 0.5px;")
        l.addWidget(lbl)
        self.grid_layout.addWidget(sec)

    def add_row(self, option_name: str, widget: QWidget, is_static: bool = False):
        row = QWidget()
        row.setFixedHeight(30)
        row.setStyleSheet("background-color: transparent;")
        l = QHBoxLayout(row)
        l.setContentsMargins(6, 2, 6, 2)
        l.setSpacing(10)

        lbl = QLabel(f"{option_name}  →")
        lbl.setFixedWidth(200)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl.setStyleSheet("color: #334155; font-size: 11px; font-weight: 500;")
        l.addWidget(lbl)

        if is_static:
            widget.setStyleSheet("color: #64748b; font-style: italic; font-size: 11px;")
        else:
            widget.setStyleSheet(self._control_style())

        l.addWidget(widget, 1)
        self.grid_layout.addWidget(row)

    # ================= Specialized Option Builders =================

    def build_tree_options(self):
        # 1. ANALYSIS
        self.add_section_header("Analysis")
        cb_scope = QComboBox()
        cb_scope.addItems(["Nucleotide", "Amino Acid"])
        cb_scope.setCurrentText("Nucleotide" if self.params.get("seq_type", "DNA") == "DNA" else "Amino Acid")
        self.controls["seq_type"] = cb_scope
        self.add_row("Substitutions Type", cb_scope)

        lbl_engine = QLabel("IQ-TREE 2 (Maximum Likelihood)")
        self.add_row("Statistical Method", lbl_engine, is_static=True)

        # 2. TEST OF PHYLOGENY
        self.add_section_header("Test of Phylogeny")
        cb_test = QComboBox()
        cb_test.addItems(["Ultrafast Bootstrap (UFBoot)", "SH-aLRT + UFBoot", "Standard Non-parametric Bootstrap", "None"])
        self.controls["test_method"] = cb_test
        self.add_row("Test of Phylogeny", cb_test)

        sb_boot = QSpinBox()
        sb_boot.setRange(100, 10000)
        sb_boot.setSingleStep(100)
        sb_boot.setValue(int(self.params.get("bootstrap", 1000)))
        self.controls["bootstrap"] = sb_boot
        self.add_row("No. of Bootstrap Replications", sb_boot)

        # 3. SUBSTITUTION MODEL
        self.add_section_header("Substitution Model")
        cb_model = QComboBox()
        cb_model.setEditable(True)
        cb_model.addItems([
            "Auto (ModelFinder)",
            "GTR+G+I",
            "GTR+F+R4",
            "HKY+G",
            "JC",
            "K80",
            "SYM",
            "WAG+G+F",
            "LG+G+F",
            "Q.pfam+R4",
        ])
        curr_m = self.params.get("model", "Auto (ModelFinder)")
        if curr_m:
            cb_model.setCurrentText(curr_m)
        self.controls["model"] = cb_model
        self.add_row("Model / Method", cb_model)

        # 4. RATES AND PATTERNS
        self.add_section_header("Rates and Patterns")
        cb_rates = QComboBox()
        cb_rates.addItems(["Gamma Distributed (+G)", "FreeRate (+R)", "Uniform Rates", "Invariable Sites (+I)", "Gamma + Invariable (+G+I)"])
        self.controls["rates"] = cb_rates
        self.add_row("Rates among Sites", cb_rates)

        sb_cat = QSpinBox()
        sb_cat.setRange(2, 16)
        sb_cat.setValue(4)
        self.controls["gamma_cats"] = sb_cat
        self.add_row("No of Discrete Gamma Categories", sb_cat)

        # 5. DATA SUBSET TO USE
        self.add_section_header("Data Subset to Use")
        cb_gaps = QComboBox()
        cb_gaps.addItems(["Use all sites", "Complete deletion (Trimming)", "Pairwise deletion"])
        self.controls["gaps"] = cb_gaps
        self.add_row("Gaps / Missing Data Treatment", cb_gaps)

        # 6. SYSTEM RESOURCE USAGE
        self.add_section_header("System Resource Usage")
        cb_threads = QComboBox()
        cb_threads.addItems(["AUTO (Detect optimal cores)", "2", "4", "8", "16", "32"])
        curr_th = str(self.params.get("threads", "AUTO"))
        idx = cb_threads.findText(curr_th)
        if idx >= 0:
            cb_threads.setCurrentIndex(idx)
        self.controls["threads"] = cb_threads
        self.add_row("Number of Threads", cb_threads)

    def build_modelfinder_options(self):
        # 1. SCOPE
        self.add_section_header("Scope")
        cb_scope = QComboBox()
        cb_scope.addItems(["Nucleotide (DNA / RNA)", "Protein (Amino Acid)"])
        self.controls["seq_type"] = cb_scope
        self.add_row("Substitutions Type", cb_scope)

        # 2. MODEL SELECTION CRITERION
        self.add_section_header("Model Selection Criterion")
        cb_crit = QComboBox()
        cb_crit.addItems(["BIC (Bayesian Information Criterion - Recommended)", "AIC (Akaike Information Criterion)", "AICc (Corrected AIC)"])
        self.controls["criterion"] = cb_crit
        self.add_row("Optimal Model Criterion", cb_crit)

        # 3. SEARCH SCOPE
        self.add_section_header("Search Scope")
        cb_scope_models = QComboBox()
        cb_scope_models.addItems([
            "Standard Models (-m TEST)",
            "Extended FreeRate Heterogeneity (-m TESTNEW)",
            "Only Fast Standard Models (-m TESTONLY)",
            "Protein Extended Matrices (-m TESTNEW)",
        ])
        self.controls["search_scope"] = cb_scope_models
        self.add_row("Model Candidates Set", cb_scope_models)

        # 4. SYSTEM RESOURCE USAGE
        self.add_section_header("System Resource Usage")
        cb_threads = QComboBox()
        cb_threads.addItems(["AUTO", "2", "4", "8", "16"])
        self.controls["threads"] = cb_threads
        self.add_row("Number of Threads", cb_threads)

    def build_alignment_options(self):
        # 1. ALIGNMENT ALGORITHM
        self.add_section_header("Alignment Algorithm")
        cb_strat = QComboBox()
        cb_strat.addItems([
            "auto (Automatically select strategy)",
            "linsi (L-INS-i: High accuracy, local alignment)",
            "ginsi (G-INS-i: High accuracy, global alignment)",
            "fftns2 (FFT-NS-2: Fast progressive alignment)",
        ])
        curr_strat = self.params.get("strategy", "auto")
        for i in range(cb_strat.count()):
            if curr_strat in cb_strat.itemText(i):
                cb_strat.setCurrentIndex(i)
                break
        self.controls["strategy"] = cb_strat
        self.add_row("Alignment Strategy", cb_strat)

        # 2. GAP PENALTIES
        self.add_section_header("Gap Penalties")
        dsb_gap = QDoubleSpinBox()
        dsb_gap.setRange(0.1, 10.0)
        dsb_gap.setSingleStep(0.1)
        dsb_gap.setValue(1.53)
        self.controls["gap_open"] = dsb_gap
        self.add_row("Gap Opening Penalty (op)", dsb_gap)

        dsb_offset = QDoubleSpinBox()
        dsb_offset.setRange(0.0, 1.0)
        dsb_offset.setSingleStep(0.01)
        dsb_offset.setValue(0.123)
        self.controls["offset"] = dsb_offset
        self.add_row("Gap Extension Penalty (ep)", dsb_offset)

        # 3. SEQUENCE DIRECTION
        self.add_section_header("Sequence Direction")
        cb_dir = QComboBox()
        cb_dir.addItems(["Adjust direction automatically (--adjustdirection)", "Keep original sequence direction"])
        self.controls["direction"] = cb_dir
        self.add_row("Direction Adjustment", cb_dir)

        # 4. SYSTEM RESOURCE USAGE
        self.add_section_header("System Resource Usage")
        cb_threads = QComboBox()
        cb_threads.addItems(["AUTO", "2", "4", "8"])
        self.controls["threads"] = cb_threads
        self.add_row("Number of Threads", cb_threads)

    def build_trimming_options(self):
        # 1. TRIMMING STRATEGY
        self.add_section_header("Trimming Strategy")
        cb_mode = QComboBox()
        cb_mode.addItems([
            "automated1 (Optimized heuristic for ML phylogeny)",
            "gappyout (Conserve positions with lower gap ratio)",
            "strict (Conservative trimming for divergence)",
            "strictplus (Most stringent trimming)",
        ])
        curr_m = self.params.get("mode", "automated1")
        for i in range(cb_mode.count()):
            if curr_m in cb_mode.itemText(i):
                cb_mode.setCurrentIndex(i)
                break
        self.controls["mode"] = cb_mode
        self.add_row("Trimming Method", cb_mode)

        # 2. CUTOFF THRESHOLDS
        self.add_section_header("Cutoff Thresholds")
        dsb_gt = QDoubleSpinBox()
        dsb_gt.setRange(0.0, 1.0)
        dsb_gt.setSingleStep(0.05)
        dsb_gt.setValue(0.8)
        self.controls["gap_threshold"] = dsb_gt
        self.add_row("Gap Threshold (-gt)", dsb_gt)

        dsb_st = QDoubleSpinBox()
        dsb_st.setRange(0.0, 1.0)
        dsb_st.setSingleStep(0.01)
        dsb_st.setValue(0.001)
        self.controls["sim_threshold"] = dsb_st
        self.add_row("Similarity Threshold (-st)", dsb_st)

        sb_cons = QSpinBox()
        sb_cons.setRange(0, 100)
        sb_cons.setValue(60)
        self.controls["cons_pct"] = sb_cons
        self.add_row("Minimum Block Length (%)", sb_cons)

    def build_timetree_options(self):
        # 1. ANALYSIS & METHOD
        self.add_section_header("Analysis")
        lbl_m = QLabel("LSD2 (Least-Squares Dating) / RelTime")
        self.add_row("Dating Method", lbl_m, is_static=True)

        # 2. CLOCK SETTINGS
        self.add_section_header("Clock Settings")
        cb_clock = QComboBox()
        cb_clock.addItems(["Strict Molecular Clock", "Relaxed Clock (Outlier Removal)"])
        self.controls["clock_type"] = cb_clock
        self.add_row("Clock Type", cb_clock)

        dsb_z = QDoubleSpinBox()
        dsb_z.setRange(1.0, 10.0)
        dsb_z.setValue(3.0)
        self.controls["z_score"] = dsb_z
        self.add_row("Outlier Z-score Threshold", dsb_z)

        # 3. CALIBRATION & PRIORS
        self.add_section_header("Calibration and Priors")
        le_cal = QLineEdit()
        le_cal.setPlaceholderText("選取校準檔案 (*.date / *.txt / *.tsv)...")
        if self.params.get("date_file"):
            le_cal.setText(str(self.params["date_file"]))
        self.controls["date_file"] = le_cal

        cal_row_w = QWidget()
        cl = QHBoxLayout(cal_row_w)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)
        cl.addWidget(le_cal, 1)
        browse_b = QPushButton("瀏覽...")
        browse_b.setFixedWidth(60)
        browse_b.setStyleSheet(self._button_style_secondary())
        browse_b.clicked.connect(lambda: self._browse_file(le_cal, "校準時間檔 (*.date *.txt *.tsv)"))
        cl.addWidget(browse_b)
        self.add_row("Date Calibration File", cal_row_w)

        # 4. VARIANCE ESTIMATION
        self.add_section_header("Variance Estimation")
        cb_var = QComboBox()
        cb_var.addItems(["Analytical Method", "Parametric Bootstrap (100 replicates)", "None"])
        self.controls["variance"] = cb_var
        self.add_row("Variance Estimation Method", cb_var)

    def build_sanitize_options(self):
        self.add_section_header("Sanitization Scope")
        cb_space = QCheckBox("將標頭空格與非法字元替換為底線 (_)")
        cb_space.setChecked(True)
        self.controls["clean_spaces"] = cb_space
        self.add_row("Header Standardization", cb_space)

        cb_dup = QCheckBox("自動重命名重複物種標頭 (加入遞增序號)")
        cb_dup.setChecked(True)
        self.controls["fix_duplicates"] = cb_dup
        self.add_row("Duplicate Taxa Handling", cb_dup)

        self.add_section_header("Alphabet Validation")
        cb_alpha = QComboBox()
        cb_alpha.addItems(["Auto-Detect (DNA / Protein)", "Enforce DNA Alphabet (ACGTN-)", "Enforce Protein Alphabet"])
        self.controls["alphabet"] = cb_alpha
        self.add_row("Alphabet Check", cb_alpha)

    def build_raw_options(self):
        # Section 1: DATA SOURCE & FORMAT
        self.add_section_header("DATA SOURCE & FILE FORMAT")

        # Input FASTA Path
        raw_f_row = QWidget()
        rf_l = QHBoxLayout(raw_f_row)
        rf_l.setContentsMargins(0, 0, 0, 0)
        rf_l.setSpacing(4)
        raw_edit = QLineEdit(str(self.params.get("fasta_path", "")))
        btn_raw_b = QPushButton("瀏覽...")
        btn_raw_b.clicked.connect(lambda: self._browse_file(raw_edit, "FASTA 序列檔案 (*.fasta *.fa *.fas *.fna);;所有檔案 (*)"))
        rf_l.addWidget(raw_edit, 1)
        rf_l.addWidget(btn_raw_b)
        self.controls["fasta_path"] = raw_edit
        self.add_row("Input Sequence File", raw_f_row)

        # Molecular Data Type
        dtype_combo = QComboBox()
        dtype_combo.addItems(["Nucleotide (DNA/RNA)", "Amino Acid (Protein)", "Auto-detect (自動判斷)"])
        curr_dtype = self.params.get("data_type", "Nucleotide (DNA/RNA)")
        idx = dtype_combo.findText(curr_dtype, Qt.MatchStartsWith)
        if idx >= 0:
            dtype_combo.setCurrentIndex(idx)
        self.controls["data_type"] = dtype_combo
        self.add_row("Molecular Data Type", dtype_combo)

        # Genetic Code Table (for codon translations)
        code_combo = QComboBox()
        code_combo.addItems([
            "1. Standard (通用標準遺傳密碼)",
            "2. Vertebrate Mitochondrial (脊椎動物粒線體)",
            "3. Yeast Mitochondrial (酵母菌粒線體)",
            "4. Mold/Protozoan Mitochondrial",
            "5. Invertebrate Mitochondrial (無脊椎動物粒線體)",
            "11. Bacterial/Archaeal/Plastid (細菌與質體)",
        ])
        curr_code = str(self.params.get("genetic_code", "1. Standard"))
        c_idx = code_combo.findText(curr_code, Qt.MatchStartsWith)
        if c_idx >= 0:
            code_combo.setCurrentIndex(c_idx)
        self.controls["genetic_code"] = code_combo
        self.add_row("Genetic Code Table", code_combo)

        # Section 2: PRE-VALIDATION & CHECKS
        self.add_section_header("PRE-VALIDATION & SANITY CHECKS")

        # Auto Check Taxon Name Duplicates
        dup_cb = QCheckBox("啟用同名物種自動去重防呆 (Auto-resolve Duplicate Taxa)")
        dup_cb.setChecked(self.params.get("resolve_duplicates", True))
        self.controls["resolve_duplicates"] = dup_cb
        self.add_row("Taxon Name Collision Check", dup_cb)

        # Check IUPAC Non-standard Bases
        iupac_cb = QCheckBox("檢查並預警非法非 IUPAC 字符 (Check Illegal Characters)")
        iupac_cb.setChecked(self.params.get("check_iupac", True))
        self.controls["check_iupac"] = iupac_cb
        self.add_row("Illegal Base Warning", iupac_cb)

    def build_generic_options(self):
        self.add_section_header("General Options")
        for k, v in self.params.items():
            le = QLineEdit(str(v))
            self.controls[k] = le
            self.add_row(k.replace("_", " ").title(), le)

    def _browse_file(self, line_edit: QLineEdit, filter_str: str):
        path, _ = QFileDialog.getOpenFileName(self, "選取檔案", "", filter_str)
        if path:
            line_edit.setText(path)

    # ================= Actions =================

    def get_settings(self) -> dict:
        result = dict(self.params)
        for k, w in self.controls.items():
            if isinstance(w, QComboBox):
                text = w.currentText()
                if " (" in text:
                    code = text.split(" (")[0].strip()
                    result[k] = code
                else:
                    result[k] = text
            elif isinstance(w, QSpinBox) or isinstance(w, QDoubleSpinBox):
                result[k] = w.value()
            elif isinstance(w, QLineEdit):
                result[k] = w.text().strip()
            elif isinstance(w, QCheckBox):
                result[k] = w.isChecked()
        return result

    def on_save_clicked(self):
        self.should_compute = False
        self.accept()

    def on_compute_clicked(self):
        self.should_compute = True
        self.accept()

    def show_help_dialog(self):
        QMessageBox.information(
            self,
            "MEGA 12 Analysis Preferences Help",
            f"=== {self.windowTitle()} ===\n\n"
            "此對話框為演化基因體學分析偏好設定表單。\n"
            "每一列皆對應至專業二進位分析程式庫 (IQ-TREE 2 / MAFFT / trimAl / LSD2) 之核心參數。\n\n"
            "• Option: 參數名稱與分析維度\n"
            "• Setting: 參數設定值 (白色方框中可自由調整)\n"
            "• 計算 (Compute): 驗證設定並立即啟動分析\n"
            "• 儲存設定 (Save Settings): 保存設定並返回視窗",
        )
