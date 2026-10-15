import re
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QLineEdit,
    QFrame,
    QApplication,
    QMessageBox,
    QCheckBox,
    QSpinBox,
    QScrollArea,
    QSplitter,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QDesktopServices
from PySide6.QtCore import QUrl
from Bio import SeqIO

from src.core.project_manager import StepRecord, PhyloProject, STEP_TITLES
from src.ui.widgets.msa_viewer import MSACanvas, MSAViewer


class StepInspectionDialog(QDialog):
    """
    全功能分子生物學步驟成果與實驗數據探針視窗 (Step Result & Molecular Data Inspector Dialog)
    - 採用 PhyloCraft 統一的現代科學淺色主題 (#F8FAFC, #FFFFFF, #008287)
    - 頂部 4 大分子生物學核心指標藥丸 (Taxa, Length, Data Type, Engine/Model)
    - 分頁 1: 📊 實驗參數與原生終端機指令
    - 分頁 2: 📁 成果檔案與完整物種盤點 (Full Taxa Inventory Table, 支援大檔案所有物種完整列出)
    - 分頁 3: 🧬 序列比對與突變檢驗 (內建高靈敏 MSA 矩陣、共識序列、SNPs 突顯)
    - 分頁 4: 📝 研究生實驗紀錄筆記 (同步專案與工作台徽章)
    - 底部: ↗ 前往專屬分頁檢視結果
    """

    jump_requested = Signal(str)      # step_key
    note_saved = Signal(str, str)     # step_key, new_notes

    def __init__(
        self,
        step_key: str,
        step_rec: StepRecord,
        project: PhyloProject,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.step_key = step_key
        self.step_rec = step_rec
        self.project = project
        self.seq_records = []
        self._load_sequence_records()
        self.init_ui()

    def _load_sequence_records(self):
        """Preload sequence records from output files if available."""
        if not self.step_rec.output_files:
            return
        for f in self.step_rec.output_files:
            p = Path(f)
            if p.exists() and p.suffix.lower() in (".fasta", ".fa", ".fas", ".phy", ".aln"):
                ext = p.suffix.lower()
                formats_to_try = ["phylip-relaxed", "phylip", "fasta", "nexus"] if ext in (".phy", ".phylip", ".aln") else ["fasta", "phylip-relaxed", "phylip", "nexus"]
                for fmt in formats_to_try:
                    try:
                        with open(p, "r", encoding="utf-8", errors="replace") as handle:
                            recs = list(SeqIO.parse(handle, fmt))
                        if recs:
                            self.seq_records = recs
                            break
                    except Exception:
                        continue
                if self.seq_records:
                    break

    def init_ui(self):
        title_zh = STEP_TITLES.get(self.step_key, (self.step_key.title(), ""))[0]
        self.setWindowTitle(f"🔬 步驟成果與實驗數據探針 — {title_zh}")
        self.resize(840, 680)
        self.setMinimumSize(720, 560)

        # Unified Clean Scientific Palette
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
                color: #0F172A;
            }
            QLabel {
                color: #0F172A;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Microsoft JhengHei", sans-serif;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(10)

        # 1. Top Header Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFFFFF, stop:1 #F1F5F9);
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        h_layout = QVBoxLayout(header_frame)
        h_layout.setContentsMargins(4, 4, 4, 4)
        h_layout.setSpacing(6)

        title_row = QHBoxLayout()
        step_idx_label = QLabel(f"<b>步驟模塊: {title_zh}</b>")
        step_idx_label.setStyleSheet("color: #008287; font-size: 15px; font-weight: bold;")
        title_row.addWidget(step_idx_label)

        title_row.addStretch()

        # Status badge
        is_completed = self.step_rec.status == "completed"
        badge_text = "✓ 已完成 (Completed)" if is_completed else ("⏳ 執行中 (Running)" if self.step_rec.status == "running" else "• 待執行 (Pending)")
        badge_bg = "#10B981" if is_completed else ("#0284C7" if self.step_rec.status == "running" else "#64748B")
        status_badge = QLabel(badge_text)
        status_badge.setStyleSheet(f"""
            background-color: {badge_bg};
            color: #FFFFFF;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 12px;
            border-radius: 10px;
        """)
        title_row.addWidget(status_badge)
        h_layout.addLayout(title_row)

        # Summary text
        summary_lbl = QLabel(f"<b>成果摘要:</b> {self.step_rec.summary or '尚未產出結果'}")
        summary_lbl.setStyleSheet("color: #334155; font-size: 12px;")
        summary_lbl.setWordWrap(True)
        h_layout.addWidget(summary_lbl)

        time_str = self.step_rec.timestamp or "尚無時間戳記"
        time_lbl = QLabel(f"執行時間: {time_str} ｜ 所屬專案: {self.project.name}")
        time_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        h_layout.addWidget(time_lbl)

        main_layout.addWidget(header_frame)

        # 2. Key Molecular Biology Metrics (4 Harmonious Pastel Pills)
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(8)

        params = self.step_rec.parameters or {}
        taxa_count = len(self.seq_records) if self.seq_records else params.get("taxa", params.get("taxa_count", params.get("retained_taxa", "-")))
        taxa_val = str(taxa_count)
        
        len_val = str(params.get("length", params.get("aligned_sites", params.get("retained_sites", "-"))))
        if len_val == "-" and self.seq_records:
            len_val = str(len(self.seq_records[0].seq))
        if len_val != "-":
            len_val += " bp"
            
        type_val = str(params.get("data_type", params.get("seq_type", "DNA/RNA")))
        method_val = str(params.get("best_model", params.get("algorithm", params.get("method", params.get("model", "-")))))

        pills_data = [
            ("🧬 物種數量 (Taxa)", taxa_val, "#0369A1", "#0284C7", "#F0F9FF", "#BAE6FD"),
            ("📏 矩陣長度 (Length)", len_val, "#15803D", "#059669", "#F0FDF4", "#BBF7D0"),
            ("🧪 資料型態 (Data Type)", type_val, "#7E22CE", "#9333EA", "#FAF5FF", "#E9D5FF"),
            ("⚙️ 核心模型/演算法", method_val, "#B45309", "#D97706", "#FFFBEB", "#FDE68A"),
        ]

        for p_label, p_val, p_lbl_color, p_val_color, p_bg_color, p_border_color in pills_data:
            pill = QFrame()
            pill.setStyleSheet(f"""
                QFrame {{
                    background-color: {p_bg_color};
                    border: 1px solid {p_border_color};
                    border-radius: 6px;
                    padding: 5px 8px;
                }}
            """)
            pl = QVBoxLayout(pill)
            pl.setContentsMargins(2, 2, 2, 2)
            pl.setSpacing(2)
            t_lbl = QLabel(p_label)
            t_lbl.setStyleSheet(f"color: {p_lbl_color}; font-size: 10px; font-weight: bold;")
            v_lbl = QLabel(f"<b>{p_val}</b>")
            v_lbl.setStyleSheet(f"color: {p_val_color}; font-size: 13px; font-weight: bold;")
            pl.addWidget(t_lbl)
            pl.addWidget(v_lbl)
            metrics_row.addWidget(pill, 1)

        main_layout.addLayout(metrics_row)

        # 3. Main Detailed Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #CBD5E1;
                background-color: #FFFFFF;
                border-radius: 6px;
                top: -1px;
            }
            QTabBar::tab {
                background: #F1F5F9;
                color: #475569;
                padding: 7px 16px;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid #CBD5E1;
                border-bottom: none;
                margin-right: 3px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #008287;
                font-weight: bold;
                border-top: 3px solid #008287;
                border-bottom: 1px solid #FFFFFF;
            }
            QTabBar::tab:hover:!selected {
                background: #E2E8F0;
                color: #0F766E;
            }
        """)

        # Tab 1: 📊 實驗參數與終端指令
        tab_params = QWidget()
        tp_layout = QVBoxLayout(tab_params)
        tp_layout.setContentsMargins(12, 12, 12, 12)
        tp_layout.setSpacing(8)

        lbl_p_table = QLabel("<b>實驗參數設定清單 (Parameters Table):</b>")
        lbl_p_table.setStyleSheet("color: #0F172A; font-size: 12px; font-weight: bold;")
        tp_layout.addWidget(lbl_p_table)

        self.param_table = QTableWidget()
        self.param_table.setColumnCount(2)
        self.param_table.setHorizontalHeaderLabels(["參數名稱 (Parameter)", "設定值 / 數值 (Value)"])
        self.param_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.param_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.param_table.setStyleSheet("""
            QTableWidget {
                font-size: 12px;
                background-color: #FFFFFF;
                color: #0F172A;
                gridline-color: #E2E8F0;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                selection-background-color: #E0F2F1;
                selection-color: #008287;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #334155;
                font-weight: bold;
                border: 1px solid #E2E8F0;
                padding: 6px 10px;
                font-size: 11px;
            }
        """)
        self.populate_parameters_table()
        tp_layout.addWidget(self.param_table, 1)

        # Command line
        lbl_cmd = QLabel("<b>原生生信終端指令 (Native CLI Command Line):</b>")
        lbl_cmd.setStyleSheet("color: #0F172A; font-size: 12px; font-weight: bold;")
        tp_layout.addWidget(lbl_cmd)

        cmd_box = QHBoxLayout()
        self.cmd_text = QLineEdit(self.step_rec.command_line or "（內建演算法或無原生指令）")
        self.cmd_text.setReadOnly(True)
        self.cmd_text.setStyleSheet("""
            QLineEdit {
                font-family: Consolas, monospace;
                font-size: 11px;
                background-color: #F8FAFC;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 6px 10px;
            }
        """)
        copy_cmd_btn = QPushButton("📋 複製指令")
        copy_cmd_btn.setFixedHeight(28)
        copy_cmd_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #008287;
                border: 1px solid #008287;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EBF7F7;
            }
        """)
        copy_cmd_btn.clicked.connect(self.copy_command_line)
        cmd_box.addWidget(self.cmd_text, 1)
        cmd_box.addWidget(copy_cmd_btn)
        tp_layout.addLayout(cmd_box)

        self.tabs.addTab(tab_params, "📊 實驗參數與指令")

        # Tab 2: 📁 成果檔案與完整物種盤點 (Full Taxa Inventory Table)
        tab_files = QWidget()
        tf_layout = QVBoxLayout(tab_files)
        tf_layout.setContentsMargins(12, 12, 12, 12)
        tf_layout.setSpacing(8)

        files_header = QHBoxLayout()
        lbl_out_files = QLabel("<b>產出實體成果檔案 (Output Files):</b>")
        lbl_out_files.setStyleSheet("color: #0F172A; font-size: 12px; font-weight: bold;")
        files_header.addWidget(lbl_out_files)
        files_header.addStretch()

        open_dir_btn = QPushButton("📂 開啟成果資料夾 (Open Folder)")
        open_dir_btn.setFixedHeight(28)
        open_dir_btn.setStyleSheet("""
            QPushButton {
                background-color: #008287;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #006F73;
            }
        """)
        open_dir_btn.clicked.connect(self.open_output_folder)
        files_header.addWidget(open_dir_btn)
        tf_layout.addLayout(files_header)

        self.files_summary = QLabel()
        self.files_summary.setStyleSheet("""
            color: #334155;
            font-size: 11px;
            background-color: #F8FAFC;
            padding: 8px 10px;
            border: 1px solid #E2E8F0;
            border-radius: 4px;
        """)
        if self.step_rec.output_files:
            flines = []
            for f in self.step_rec.output_files:
                p = Path(f)
                sz_str = f"({round(p.stat().st_size / 1024, 1)} KB)" if p.exists() else "(未產出)"
                flines.append(f"• <b style='color:#0F766E;'>{p.name}</b> {sz_str} — <span style='color:#64748B;'>{f}</span>")
            self.files_summary.setText("<br>".join(flines))
        else:
            self.files_summary.setText("尚未產生實體輸出檔案。")
        tf_layout.addWidget(self.files_summary)

        # Taxa Table + File Preview Vertical Splitter (Allows free vertical dragging)
        files_splitter = QSplitter(Qt.Vertical)
        files_splitter.setHandleWidth(6)
        files_splitter.setStyleSheet("""
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

        # Full Taxa Table (Ensures NO sequences are cut off or omitted)
        if self.seq_records:
            taxa_widget = QWidget()
            tw_layout = QVBoxLayout(taxa_widget)
            tw_layout.setContentsMargins(0, 0, 0, 0)
            tw_layout.setSpacing(4)

            lbl_taxa_tbl = QLabel(f"<b>物種序列完整盤點表 (全收錄共 {len(self.seq_records)} 筆物種，無任何省略):</b>")
            lbl_taxa_tbl.setStyleSheet("color: #0F172A; font-size: 12px; font-weight: bold;")
            tw_layout.addWidget(lbl_taxa_tbl)

            self.taxa_table = QTableWidget()
            self.taxa_table.setColumnCount(4)
            self.taxa_table.setHorizontalHeaderLabels(["#", "物種標頭名稱 (Taxon ID)", "長度 (bp/aa)", "序列前綴 (Preview)"])
            self.taxa_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            self.taxa_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
            self.taxa_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            self.taxa_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
            self.taxa_table.setColumnWidth(0, 45)
            self.taxa_table.setColumnWidth(1, 190)
            self.taxa_table.verticalHeader().setVisible(False)
            self.taxa_table.setStyleSheet("""
                QTableWidget {
                    font-size: 11px;
                    background-color: #FFFFFF;
                    color: #0F172A;
                    gridline-color: #E2E8F0;
                    border: 1px solid #CBD5E1;
                    border-radius: 4px;
                }
                QHeaderView::section {
                    background-color: #F8FAFC;
                    color: #334155;
                    font-weight: bold;
                    border: 1px solid #E2E8F0;
                    padding: 4px 6px;
                }
            """)
            self.taxa_table.setMinimumHeight(140)
            self.populate_taxa_table()
            tw_layout.addWidget(self.taxa_table, 1)
            files_splitter.addWidget(taxa_widget)

        # File Raw Preview (Up to 1000 lines)
        preview_widget = QWidget()
        pw_layout = QVBoxLayout(preview_widget)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        pw_layout.setSpacing(4)

        lbl_preview = QLabel("<b>原始檔案文字內容預覽 (Raw File Content Preview):</b>")
        lbl_preview.setStyleSheet("color: #0F172A; font-size: 12px; font-weight: bold;")
        pw_layout.addWidget(lbl_preview)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(90)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                color: #0F172A;
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 6px;
                line-height: 1.4;
            }
        """)
        self.load_file_preview()
        pw_layout.addWidget(self.preview_text, 1)
        files_splitter.addWidget(preview_widget)

        if self.seq_records:
            files_splitter.setStretchFactor(0, 3)
            files_splitter.setStretchFactor(1, 2)
            files_splitter.setSizes([260, 160])

        tf_layout.addWidget(files_splitter, 1)

        self.tabs.addTab(tab_files, "📁 成果檔案與物種盤點")

        # Tab 3: 🧬 序列比對與突變檢驗 (Integrated MSA & Mutation Inspector)
        if self.seq_records:
            tab_msa = QWidget()
            tm_layout = QVBoxLayout(tab_msa)
            tm_layout.setContentsMargins(10, 10, 10, 10)
            tm_layout.setSpacing(6)

            self.msa_viewer = MSAViewer()
            self.msa_viewer.load_records(self.seq_records, source_name="步驟成果序列")
            if hasattr(self.msa_viewer, "open_btn"):
                self.msa_viewer.open_btn.setVisible(False)
            # Aliases for backward compatibility
            self.msa_canvas = self.msa_viewer.canvas
            self.mut_cb = self.msa_viewer.mut_cb
            self.zoom_spin = self.msa_viewer.zoom_spin
            self.hover_pos_lbl = self.msa_viewer.hover_label

            tm_layout.addWidget(self.msa_viewer, 1)
            self.tabs.addTab(tab_msa, "🧬 序列比對與突變檢驗")

        # Tab 4: 📝 研究生實驗筆記
        tab_notes = QWidget()
        tn_layout = QVBoxLayout(tab_notes)
        tn_layout.setContentsMargins(12, 12, 12, 12)
        tn_layout.setSpacing(8)

        lbl_notes = QLabel("<b>分子演化實驗記錄筆記 (Lab Notebook & Student Notes):</b>")
        lbl_notes.setStyleSheet("color: #0F172A; font-size: 12px; font-weight: bold;")
        tn_layout.addWidget(lbl_notes)

        note_hint = QLabel("在發表期刊論文或進行實驗檢討時，記錄各步驟參數選擇理由、突變觀察心得至關重要。")
        note_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        tn_layout.addWidget(note_hint)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("請在此輸入此步驟的實驗觀察筆記、參數挑選理由或假設驗證紀錄...")
        self.notes_edit.setStyleSheet("""
            QTextEdit {
                font-size: 12px;
                color: #0F172A;
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 8px;
                line-height: 1.5;
            }
        """)
        self.notes_edit.setText(self.step_rec.student_notes or "")
        tn_layout.addWidget(self.notes_edit, 1)

        save_note_row = QHBoxLayout()
        save_note_row.addStretch()
        self.btn_save_note = QPushButton("💾 儲存筆記至專案 (Save Notes)")
        self.btn_save_note.setFixedHeight(30)
        self.btn_save_note.setStyleSheet("""
            QPushButton {
                background-color: #008287;
                color: #FFFFFF;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 4px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #006F73;
            }
        """)
        self.btn_save_note.clicked.connect(self.save_notes)
        save_note_row.addWidget(self.btn_save_note)
        tn_layout.addLayout(save_note_row)

        notes_count = len(self.step_rec.student_notes) if self.step_rec.student_notes else 0
        self.tabs.addTab(tab_notes, f"📝 實驗筆記 ({notes_count} 字)")

        main_layout.addWidget(self.tabs, 1)

        # 4. Bottom Action Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.jump_btn = QPushButton("↗ 前往專屬分頁檢視結果 (Open Dedicated Tab)")
        self.jump_btn.setFixedHeight(34)
        self.jump_btn.setStyleSheet("""
            QPushButton {
                background-color: #008287;
                color: #FFFFFF;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 6px 18px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #006F73;
            }
        """)
        self.jump_btn.clicked.connect(self.on_jump_clicked)
        bottom_bar.addWidget(self.jump_btn)

        bottom_bar.addStretch()

        close_btn = QPushButton("關閉 (Close)")
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 6px 18px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                color: #0F172A;
            }
        """)
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)

        main_layout.addLayout(bottom_bar)

    def on_msa_hover(self, text: str):
        if text:
            self.hover_pos_lbl.setText(text)
        else:
            self.hover_pos_lbl.setText("請將滑鼠移到位點上方以檢視詳細鹼基資訊")

    def populate_parameters_table(self):
        params = self.step_rec.parameters or {}
        self.param_table.setRowCount(len(params))
        for row, (k, v) in enumerate(params.items()):
            k_item = QTableWidgetItem(str(k))
            k_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            k_item.setForeground(QColor("#0F766E"))
            v_item = QTableWidgetItem(str(v))
            v_item.setForeground(QColor("#0F172A"))
            self.param_table.setItem(row, 0, k_item)
            self.param_table.setItem(row, 1, v_item)

        if not params:
            self.param_table.setRowCount(1)
            k_item = QTableWidgetItem("（無自訂參數）")
            k_item.setForeground(QColor("#64748B"))
            v_item = QTableWidgetItem("使用預設生信分析設定")
            v_item.setForeground(QColor("#64748B"))
            self.param_table.setItem(0, 0, k_item)
            self.param_table.setItem(0, 1, v_item)

    def populate_taxa_table(self):
        self.taxa_table.setRowCount(len(self.seq_records))
        for idx, rec in enumerate(self.seq_records):
            idx_item = QTableWidgetItem(str(idx + 1))
            idx_item.setTextAlignment(Qt.AlignCenter)
            
            id_item = QTableWidgetItem(rec.id)
            id_item.setFont(QFont("Consolas", 9, QFont.Bold))
            id_item.setForeground(QColor("#008287"))
            
            len_item = QTableWidgetItem(f"{len(rec.seq)} bp")
            len_item.setTextAlignment(Qt.AlignCenter)
            
            seq_snippet = str(rec.seq)[:40] + ("..." if len(rec.seq) > 40 else "")
            prev_item = QTableWidgetItem(seq_snippet)
            prev_item.setFont(QFont("Consolas", 9))
            prev_item.setForeground(QColor("#334155"))
            
            self.taxa_table.setItem(idx, 0, idx_item)
            self.taxa_table.setItem(idx, 1, id_item)
            self.taxa_table.setItem(idx, 2, len_item)
            self.taxa_table.setItem(idx, 3, prev_item)

    def load_file_preview(self):
        if not self.step_rec.output_files:
            self.preview_text.setPlainText("（此步驟尚未產生輸出檔案）")
            return

        first_file = Path(self.step_rec.output_files[0])
        if not first_file.exists():
            self.preview_text.setPlainText(f"找不到檔案: {first_file}")
            return

        try:
            with open(first_file, "r", encoding="utf-8", errors="replace") as f:
                lines = [f.readline() for _ in range(1000)]
            self.preview_text.setPlainText("".join(lines))
        except Exception as e:
            self.preview_text.setPlainText(f"無法讀取檔案預覽:\n{str(e)}")

    def copy_command_line(self):
        txt = self.cmd_text.text()
        if txt:
            QApplication.clipboard().setText(txt)
            QMessageBox.information(self, "複製完成", "原生終端指令已複製到剪貼簿！")

    def open_output_folder(self):
        if not self.project:
            return
        sub = STEP_TITLES.get(self.step_key, ("", ""))[1]
        p = Path(self.project.project_dir) / sub
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def save_notes(self):
        new_text = self.notes_edit.toPlainText().strip()
        self.step_rec.student_notes = new_text
        self.note_saved.emit(self.step_key, new_text)
        notes_idx = self.tabs.count() - 1
        self.tabs.setTabText(notes_idx, f"📝 實驗筆記 ({len(new_text)} 字)")
        QMessageBox.information(self, "筆記已儲存", "分子演化實驗記錄筆記已成功同步儲存至研究專案檔案！")

    def on_jump_clicked(self):
        self.jump_requested.emit(self.step_key)
        self.accept()
