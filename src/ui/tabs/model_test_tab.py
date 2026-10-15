from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QMessageBox,
    QSplitter,
    QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont
from src.config import OUTPUT_DIR
from src.core.runners.modelfinder_runner import ModelFinderRunner, ModelFinderResult
from src.ui.widgets.log_viewer import LogViewer


class ModelFinderWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(ModelFinderResult)

    def __init__(self, in_p: str, out_prefix: str, scope: str, threads: str):
        super().__init__()
        self.in_p = in_p
        self.out_prefix = out_prefix
        self.scope = scope
        self.threads = threads
        self.runner = ModelFinderRunner()

    def cancel(self):
        self.runner.cancel()

    def run(self):
        res = self.runner.run_modelfinder(
            self.in_p,
            self.out_prefix,
            search_scope=self.scope,
            threads=self.threads,
            log_callback=self.log_signal.emit,
        )
        self.finished_signal.emit(res)


class ModelTestTab(QWidget):
    """
    Dedicated Molecular Substitution Model Testing Tab (ModelFinder)
    Alters between AIC/BIC criteria, candidate ranking tables, base frequencies,
    and enables 1-click model transmission to phylogenetic tree inference.
    """

    apply_model_requested = Signal(str, str)  # (model_name, input_file)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.worker: ModelFinderWorker | None = None
        self.current_result: ModelFinderResult | None = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 1. Header Banner (Modern Compact Studio Header)
        header_box = QFrame()
        header_box.setStyleSheet("background-color: #FFFFFF; border-radius: 6px; padding: 6px 12px; border: 1px solid #CBD5E1;")
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        h_title = QLabel("<b>🔬 分子演化替代模型檢定 (ModelFinder - Model Selection)</b>")
        h_title.setStyleSheet("color: #0F172A; font-size: 13px;")
        h_layout.addWidget(h_title)

        mode_badge = QLabel("🛠️ 獨立單工模式")
        mode_badge.setStyleSheet("color: #0F766E; background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 1px 8px; font-size: 10px; font-weight: bold;")
        h_layout.addWidget(mode_badge)

        h_layout.addStretch()

        info_btn = QLabel("💡 依據 BIC / AIC 自動評選最優替代模型，防範長枝吸引效應 (LBA)")
        info_btn.setStyleSheet("color: #64748B; font-size: 11px;")
        info_btn.setToolTip(
            "在構建最大概似法（ML）演化樹之前，依據統計資訊標準（BIC / AIC）客觀檢定最優替代模型，\n"
            "是國際期刊（Systematic Biology、MBE）必備之標準檢定流程，可避免長枝吸引效應（LBA）與估計偏差。"
        )
        h_layout.addWidget(info_btn)
        layout.addWidget(header_box)

        # 2. Controls & Files (Collapsible & Compact Grid Layout)
        self.ctrl_box = QGroupBox("步驟 1：檢定資料與參數設定 (Settings)")
        cb_main_layout = QVBoxLayout(self.ctrl_box)
        cb_main_layout.setContentsMargins(10, 8, 10, 8)
        cb_main_layout.setSpacing(6)

        # Top bar with collapse toggle
        cb_top_row = QHBoxLayout()
        cb_hint = QLabel("設定輸入檔案、搜尋範圍與評選標準:")
        cb_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        cb_top_row.addWidget(cb_hint)
        cb_top_row.addStretch()

        self.is_ctrl_collapsed = False
        self.btn_toggle_ctrl = QPushButton("收合參數列 ▲")
        self.btn_toggle_ctrl.setFixedHeight(22)
        self.btn_toggle_ctrl.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F766E;
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 8px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        self.btn_toggle_ctrl.clicked.connect(self.toggle_ctrl_box)
        cb_top_row.addWidget(self.btn_toggle_ctrl)
        cb_main_layout.addLayout(cb_top_row)

        self.ctrl_content = QWidget()
        c_grid = QGridLayout(self.ctrl_content)
        c_grid.setContentsMargins(0, 0, 0, 0)
        c_grid.setHorizontalSpacing(10)
        c_grid.setVerticalSpacing(6)

        # Row 0: File input
        lbl_in = QLabel("已比對之序列檔:")
        self.in_edit = QLineEdit()
        self.in_edit.setFixedHeight(26)
        self.in_edit.setPlaceholderText("請選取比對/修剪後之 FASTA 或 PHYLIP 檔案...")
        in_btn = QPushButton("瀏覽 (Browse)...")
        in_btn.setFixedHeight(26)
        in_btn.setFixedWidth(105)
        in_btn.clicked.connect(self.browse_input)

        load_iqtree_btn = QPushButton("載入既有 .iqtree 報告...")
        load_iqtree_btn.setFixedHeight(26)
        load_iqtree_btn.setFixedWidth(160)
        load_iqtree_btn.setToolTip("載入先前 ModelFinder 或 IQ-TREE 產出之 .iqtree 檢定報告並檢視所有候選模型")
        load_iqtree_btn.clicked.connect(self.browse_existing_report)

        c_grid.addWidget(lbl_in, 0, 0)
        c_grid.addWidget(self.in_edit, 0, 1)
        c_grid.addWidget(in_btn, 0, 2)
        c_grid.addWidget(load_iqtree_btn, 0, 3)
        c_grid.setColumnStretch(1, 1)

        # Row 1: Parameters Row
        param_widget = QWidget()
        param_row = QHBoxLayout(param_widget)
        param_row.setContentsMargins(0, 0, 0, 0)
        param_row.setSpacing(10)

        param_row.addWidget(QLabel("模型範圍:"))
        self.scope_combo = QComboBox()
        self.scope_combo.setFixedHeight(28)
        self.scope_combo.addItems([
            "常用標準核酸模型 (TESTONLY: 88 種模式 + 異質率)",
            "非同質異質率模型 (TESTNEWONLY: 含 FreeRate +R, 論文最新推薦)",
            "常用蛋白質模型 (TESTONLY: LG, WAG, JTT 等 22 種模式)",
            "MrBayes 貝氏相容模型集 (-mset mrbayes)",
            "BEAST 貝氏相容模型集 (-mset beast)",
        ])
        self.scope_combo.setToolTip("決定搜尋的替代模型集合")
        param_row.addWidget(self.scope_combo, 2)

        param_row.addWidget(QLabel("評選標準:"))
        self.crit_combo = QComboBox()
        self.crit_combo.setFixedHeight(28)
        self.crit_combo.addItems([
            "BIC (貝氏標準 - 推薦)",
            "AIC (赤池資訊標準)",
            "AICc (小樣本校正赤池標準)",
        ])
        param_row.addWidget(self.crit_combo, 1)

        param_row.addWidget(QLabel("CPU:"))
        self.thread_combo = QComboBox()
        self.thread_combo.setFixedHeight(28)
        self.thread_combo.addItems(["AUTO", "1", "2", "4", "8"])
        param_row.addWidget(self.thread_combo)

        c_grid.addWidget(param_widget, 1, 0, 1, 4)

        # Row 2: Action Row (Spacious & Clean)
        action_widget = QWidget()
        act_row = QHBoxLayout(action_widget)
        act_row.setContentsMargins(0, 4, 0, 0)
        act_row.setSpacing(10)

        self.run_btn = QPushButton("▶ 開始模型檢定 (Run ModelFinder)")
        self.run_btn.setObjectName("primary_button")
        self.run_btn.setFixedHeight(32)
        self.run_btn.setStyleSheet("""
            QPushButton#primary_button {
                background-color: #008287;
                color: #FFFFFF;
                font-weight: bold;
                border: 1px solid #00666B;
                border-radius: 4px;
                padding: 4px 16px;
            }
            QPushButton#primary_button:hover {
                background-color: #006F73;
            }
            QPushButton#primary_button:disabled {
                background-color: #E2E8F0;
                border: 1px solid #CBD5E1;
                color: #334155;
                font-weight: bold;
            }
        """)
        self.run_btn.clicked.connect(self.start_modelfinder)
        act_row.addWidget(self.run_btn, 3)

        self.cancel_btn = QPushButton("■ 停止 (Stop)")
        self.cancel_btn.setObjectName("danger_button")
        self.cancel_btn.setFixedHeight(32)
        self.cancel_btn.setMinimumWidth(85)
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
            QPushButton#danger_button:hover {
                background-color: #DC2626;
            }
            QPushButton#danger_button:disabled {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                color: #94A3B8;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_modelfinder)
        act_row.addWidget(self.cancel_btn, 1)

        c_grid.addWidget(action_widget, 2, 0, 1, 4)
        cb_main_layout.addWidget(self.ctrl_content)
        layout.addWidget(self.ctrl_box)

        # 3. Main Splitter: Results (Left) + Log (Right)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(6)
        main_splitter.setStyleSheet("""
            QSplitter::handle:horizontal {
                width: 6px;
                background-color: #E2E8F0;
                border-left: 1px solid #CBD5E1;
                border-right: 1px solid #CBD5E1;
                margin: 4px 0px;
                border-radius: 2px;
            }
            QSplitter::handle:horizontal:hover {
                background-color: #008287;
            }
            QSplitter::handle:vertical {
                height: 6px;
                background-color: #E2E8F0;
                border-top: 1px solid #CBD5E1;
                border-bottom: 1px solid #CBD5E1;
                margin: 0px 4px;
                border-radius: 2px;
            }
            QSplitter::handle:vertical:hover {
                background-color: #008287;
            }
        """)

        # Results Vertical Splitter (Allows flexible dragging between Best Model and Candidate Table)
        res_splitter = QSplitter(Qt.Vertical)
        res_splitter.setHandleWidth(6)

        # 3.1 Best Model Highlight Card (Sleek Compact Card)
        self.hero_frame = QFrame()
        self.hero_frame.setStyleSheet("""
            QFrame {
                background-color: #f0fdf4;
                border: 1px solid #86efac;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        hf_layout = QVBoxLayout(self.hero_frame)
        hf_layout.setContentsMargins(4, 4, 4, 4)
        hf_layout.setSpacing(4)

        top_info_row = QHBoxLayout()
        self.best_model_label = QLabel("最優替代模型: 等待檢定...")
        self.best_model_label.setStyleSheet("color: #15803d; font-size: 14px; font-weight: bold;")
        top_info_row.addWidget(self.best_model_label)
        top_info_row.addStretch()

        self.apply_btn = QPushButton("套用此最佳模型前往建樹 ➔")
        self.apply_btn.setObjectName("primary_button")
        self.apply_btn.setFixedHeight(28)
        self.apply_btn.setToolTip("套用此最優模型並切換至建樹分頁 (Apply to Tree Tab)")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self.apply_to_tree)
        top_info_row.addWidget(self.apply_btn)
        hf_layout.addLayout(top_info_row)

        sub_info_row = QHBoxLayout()
        self.stats_label = QLabel("物種數: - | 位點長度: - | 簡約訊息位點: - | BIC 分數: -")
        self.stats_label.setStyleSheet("color: #334155; font-size: 11px;")
        sub_info_row.addWidget(self.stats_label)
        sub_info_row.addStretch()

        self.freq_label = QLabel("鹼基組成: 等待分析...")
        self.freq_label.setStyleSheet("color: #006644; font-size: 11px;")
        sub_info_row.addWidget(self.freq_label)
        hf_layout.addLayout(sub_info_row)

        res_splitter.addWidget(self.hero_frame)

        # 3.2 Candidate Table
        table_box = QGroupBox("候選模型統計評比 (Candidate Models Ranking)")
        tb_layout = QVBoxLayout(table_box)
        tb_layout.setContentsMargins(6, 6, 6, 6)
        tb_layout.setSpacing(4)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setMinimumHeight(240)
        self.table.setHorizontalHeaderLabels([
            "排名", "替代模型 (Model)", "LogL",
            "BIC", "ΔBIC", "w-BIC", "AIC", "95% 信賴"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 48)
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(2, 75)
        self.table.setColumnWidth(3, 75)
        self.table.setColumnWidth(4, 60)
        self.table.setColumnWidth(5, 68)
        self.table.setColumnWidth(6, 75)
        self.table.setColumnWidth(7, 85)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                color: #1e293b;
                gridline-color: #f1f5f9;
                font-size: 11px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #006644;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #e2e8f0;
            }
        """)
        tb_layout.addWidget(self.table, 1)

        # Table Action Row
        tbl_btn_row = QHBoxLayout()
        tbl_info = QLabel("提示: 點擊表格中任意模型，可點擊右側按鈕套用該模型前往建樹。")
        tbl_info.setStyleSheet("color: #64748b; font-size: 11px;")
        tbl_btn_row.addWidget(tbl_info)
        tbl_btn_row.addStretch()

        self.apply_selected_btn = QPushButton("套用選定列模型")
        self.apply_selected_btn.setFixedHeight(24)
        self.apply_selected_btn.setEnabled(False)
        self.apply_selected_btn.clicked.connect(self.apply_selected_model_to_tree)
        tbl_btn_row.addWidget(self.apply_selected_btn)
        tb_layout.addLayout(tbl_btn_row)

        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)

        res_splitter.addWidget(table_box)
        res_splitter.setStretchFactor(0, 0)
        res_splitter.setStretchFactor(1, 1)
        res_splitter.setSizes([75, 420])

        main_splitter.addWidget(res_splitter)

        # 3.3 Log Viewer
        self.log_viewer = LogViewer("ModelFinder 即時檢定日誌 (Console)")
        main_splitter.addWidget(self.log_viewer)

        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 2)
        main_splitter.setSizes([620, 380])
        layout.addWidget(main_splitter, 1)

    def toggle_ctrl_box(self):
        self.is_ctrl_collapsed = not getattr(self, "is_ctrl_collapsed", False)
        if hasattr(self, "ctrl_content"):
            self.ctrl_content.setVisible(not self.is_ctrl_collapsed)
        if hasattr(self, "btn_toggle_ctrl"):
            self.btn_toggle_ctrl.setText("展開參數列 ▼" if self.is_ctrl_collapsed else "收合參數列 ▲")

    def set_input_file(self, file_path: str, iqtree_path: str | Path | None = None):
        self.in_edit.setText(file_path)
        if iqtree_path and Path(iqtree_path).exists():
            if self.load_existing_report(iqtree_path):
                return

        p = Path(file_path)
        base = p.stem.replace("_trimmed", "").replace("_aligned", "").replace("_cleaned", "")
        candidates = [
            p.parent / f"{p.stem}_modelfinder.iqtree",
            p.parent / f"{base}_modelfinder.iqtree",
            OUTPUT_DIR / f"{p.stem}_modelfinder.iqtree",
            OUTPUT_DIR / f"{base}_modelfinder.iqtree",
            p.parent / f"{p.stem}_tree.iqtree",
            p.parent / f"{base}_tree.iqtree",
            OUTPUT_DIR / f"{p.stem}_tree.iqtree",
            OUTPUT_DIR / f"{base}_tree.iqtree",
            p.with_suffix(".iqtree"),
        ]
        for cand in candidates:
            if cand.exists():
                if self.load_existing_report(cand):
                    break

    def browse_existing_report(self):
        fp, _ = QFileDialog.getOpenFileName(
            self,
            "選取 ModelFinder 檢定報告檔案",
            str(OUTPUT_DIR),
            "IQ-TREE Report (*.iqtree);;All Files (*.*)",
        )
        if fp:
            ok = self.load_existing_report(fp)
            if not ok:
                QMessageBox.warning(self, "載入失敗", "無法從選取的檔案中解析出 ModelFinder 檢定結果。")

    def load_existing_report(self, iqtree_path: str | Path) -> bool:
        p = Path(iqtree_path)
        if not p.exists():
            return False

        from src.core.runners.modelfinder_runner import ModelFinderRunner
        runner = ModelFinderRunner()
        log_p = p.with_suffix(".log")
        res = runner._parse_report(p, log_p)
        if res.success and (res.best_model or res.candidate_models):
            if not self.in_edit.text():
                base = p.stem.replace("_modelfinder", "").replace("_tree", "")
                for ext in [".fasta", ".fa", ".phy", ".nex"]:
                    for cand_f in [
                        p.parent / f"{base}_trimmed{ext}",
                        p.parent / f"{base}_aligned{ext}",
                        p.parent / f"{base}{ext}",
                    ]:
                        if cand_f.exists():
                            self.in_edit.setText(str(cand_f))
                            break
                    if self.in_edit.text():
                        break
            self.on_modelfinder_finished(res, show_alert=False)
            self.log_viewer.clear()
            self.log_viewer.append_log(f"[已載入既有檢定報告] 來源檔案: {p.name}")
            self.log_viewer.append_log(f"[最佳模型] {res.best_model} (BIC 統計最優解)")
            self.log_viewer.append_log(f"[候選模型總數] 共評比 {len(res.candidate_models)} 種模型")
            if log_p.exists():
                try:
                    with open(log_p, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    self.log_viewer.append_log("\n--- IQ-TREE 檢定終端日誌 (節錄) ---")
                    for line in lines[-120:]:
                        self.log_viewer.append_log(line.rstrip())
                except Exception:
                    pass
            return True
        return False

    def browse_input(self):
        fp, _ = QFileDialog.getOpenFileName(
            self,
            "選取比對序列檔案",
            str(OUTPUT_DIR),
            "Sequence Files (*.fasta *.fa *.fas *.phy *.nex);;All Files (*.*)",
        )
        if fp:
            self.set_input_file(fp)

    def start_modelfinder(self):
        in_p = self.in_edit.text().strip()
        if not in_p:
            QMessageBox.warning(self, "缺少檔案", "請先選取已對齊之 FASTA / PHYLIP 序列檔案！")
            return

        in_path = Path(in_p)
        if not in_path.exists():
            QMessageBox.warning(self, "檔案不存在", f"找不到指定檔案:\n{in_p}")
            return

        out_prefix = str(OUTPUT_DIR / f"{in_path.stem}_modelfinder")
        scope_idx = self.scope_combo.currentIndex()
        scope_map = {
            0: "TESTONLY",
            1: "TESTNEWONLY",
            2: "protein",
            3: "mrbayes",
            4: "beast",
        }
        scope = scope_map.get(scope_idx, "TESTONLY")
        threads = self.thread_combo.currentText()

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.apply_btn.setEnabled(False)
        self.apply_selected_btn.setEnabled(False)
        self.log_viewer.clear()
        self.table.setRowCount(0)
        self.best_model_label.setText("最優替代模型: 檢定計算中...")

        self.worker = ModelFinderWorker(in_p, out_prefix, scope, threads)
        self.worker.log_signal.connect(self.log_viewer.append_log)
        self.worker.finished_signal.connect(self.on_modelfinder_finished)
        self.worker.start()

    def cancel_modelfinder(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.log_viewer.append_log("[使用者已手動中止 ModelFinder 檢定]")
            self.run_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def on_modelfinder_finished(self, res: ModelFinderResult, show_alert: bool = True):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.current_result = res

        if not res.success:
            if show_alert:
                QMessageBox.critical(self, "模型檢定失敗", f"ModelFinder 檢定未成功完成:\n{res.message}")
            self.best_model_label.setText("檢定失敗")
            return

        # 1. Update Hero Card
        self.best_model_label.setText(f"最優替代模型 (BIC 最佳解): {res.best_model}")
        self.stats_label.setText(
            f"物種數: {res.taxa_count} | 序列位點長度: {res.site_count} bp | "
            f"簡約訊息位點: {res.parsimony_informative_sites} | 恆定位點: {res.constant_sites}"
        )

        # Frequencies & Rates or Model Structural Breakdown
        freq_str = ""
        if res.base_frequencies:
            freq_str = "鹼基頻率: " + " | ".join(f"f({b})={v:.3f}" for b, v in res.base_frequencies.items())
        rate_str = ""
        if res.rate_parameters:
            rate_str = "速率參數: " + " | ".join(f"{k}={v:.2f}" for k, v in list(res.rate_parameters.items())[:4])
        
        # Intelligently explain substitution model composition
        model_name = res.best_model
        explanation = []
        if "+I" in model_name:
            explanation.append("含不變位點比例 (+I: Invariable Sites)")
        if "+G" in model_name:
            explanation.append("Gamma 速率異質性 (+G: Discrete Gamma)")
        elif "+R" in model_name:
            explanation.append("FreeRate 自由異質率 (+R: FreeRate Heterogeneity)")
        if "+F" in model_name:
            explanation.append("經驗頻率 (+F: Empirical Frequencies)")

        if freq_str or rate_str:
            self.freq_label.setText(f"{freq_str}    {rate_str}".strip())
        elif explanation:
            self.freq_label.setText("模型結構特性: " + " ｜ ".join(explanation))
        else:
            self.freq_label.setText(f"最優替代模型已成功判定: {model_name}")
        self.apply_btn.setEnabled(True)
        self.apply_btn.setText(f"套用最佳模型 ({model_name}) 前往建樹")

        # 2. Populate Candidate Table
        self.table.setRowCount(len(res.candidate_models))
        for row, cand in enumerate(res.candidate_models):
            rank_item = QTableWidgetItem(f"#{cand.rank}")
            rank_item.setTextAlignment(Qt.AlignCenter)

            model_item = QTableWidgetItem(cand.model)
            model_item.setFont(QFont("Segoe UI", 9, QFont.Bold))

            logl_item = QTableWidgetItem(f"{cand.logl:.2f}")
            logl_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            bic_item = QTableWidgetItem(f"{cand.bic:.2f}")
            bic_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            delta_item = QTableWidgetItem(f"+{cand.delta_bic:.2f}" if cand.delta_bic > 0 else "0.00 (Best)")
            delta_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            wbic_item = QTableWidgetItem(f"{cand.w_bic:.4f}" if cand.w_bic > 0.0001 else "<0.0001")
            wbic_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            aic_item = QTableWidgetItem(f"{cand.aic:.2f}")
            aic_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            conf_str = "包含 (+)" if cand.in_conf_set else "排除 (-)"
            conf_item = QTableWidgetItem(conf_str)
            conf_item.setTextAlignment(Qt.AlignCenter)

            # Highlighting
            if cand.rank == 1:
                for it in [rank_item, model_item, logl_item, bic_item, delta_item, wbic_item, aic_item, conf_item]:
                    it.setBackground(QColor("#dcfce7"))
                    it.setForeground(QColor("#15803d"))
            elif cand.in_conf_set:
                for it in [rank_item, model_item, logl_item, bic_item, delta_item, wbic_item, aic_item, conf_item]:
                    it.setBackground(QColor("#f0fdf4"))
                    it.setForeground(QColor("#1e293b"))

            self.table.setItem(row, 0, rank_item)
            self.table.setItem(row, 1, model_item)
            self.table.setItem(row, 2, logl_item)
            self.table.setItem(row, 3, bic_item)
            self.table.setItem(row, 4, delta_item)
            self.table.setItem(row, 5, wbic_item)
            self.table.setItem(row, 6, aic_item)
            self.table.setItem(row, 7, conf_item)

        if show_alert:
            QMessageBox.information(
                self,
                "檢定完成",
                f"ModelFinder 已檢驗完畢！\n最佳推薦替代模型為: {res.best_model}\n共評比 {len(res.candidate_models)} 個模型組合。"
            )

    def on_table_selection_changed(self):
        sel_row = self.table.currentRow()
        if sel_row >= 0 and self.current_result and self.current_result.candidate_models and sel_row < len(self.current_result.candidate_models):
            sel_m = self.current_result.candidate_models[sel_row].model
            self.apply_btn.setText(f"套用選定模型 ({sel_m}) 前往建樹")
            self.apply_btn.setEnabled(True)
            self.apply_selected_btn.setEnabled(True)
            self.apply_selected_btn.setText(f"套用選定模型 ({sel_m})")
        else:
            best_m = self.current_result.best_model if self.current_result and self.current_result.best_model else ""
            if best_m:
                self.apply_btn.setText(f"套用最佳模型 ({best_m}) 前往建樹")
                self.apply_btn.setEnabled(True)
            else:
                self.apply_btn.setText("前往建樹 (Apply)")
                self.apply_btn.setEnabled(False)
            self.apply_selected_btn.setEnabled(False)

    def apply_to_tree(self):
        if not self.current_result or not self.current_result.best_model:
            return
        in_p = self.in_edit.text().strip()
        sel_row = self.table.currentRow()
        if sel_row >= 0 and self.current_result.candidate_models and sel_row < len(self.current_result.candidate_models):
            model_name = self.current_result.candidate_models[sel_row].model
        else:
            model_name = self.current_result.best_model
        self.apply_model_requested.emit(model_name, in_p)

    def apply_selected_model_to_tree(self):
        self.apply_to_tree()
