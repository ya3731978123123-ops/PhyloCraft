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
    QMessageBox,
    QTextEdit,
    QFrame,
)
from src.config import DATA_DIR, OUTPUT_DIR
from PySide6.QtCore import Signal
from src.core.sanitizer import sanitize_fasta_file, save_sanitized_fasta, SanitizerResult
from src.core.converter import convert_alignment
from src.ui.widgets.sequence_table import SequenceTableWidget


class SanitizerTab(QWidget):
    """
    Sequence Sanitizer & Format Converter Tab
    - Detects illegal characters and duplicates
    - Displays sequence statistics
    - Converts between FASTA, PHYLIP (Strict/Relaxed), NEXUS, and Clustal
    """

    send_to_align_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.current_result: SanitizerResult | None = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Top Standalone Header Banner
        header_box = QFrame()
        header_box.setStyleSheet("background-color: #FFFFFF; border-radius: 6px; padding: 10px 14px; border: 1px solid #CBD5E1;")
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(0, 0, 0, 0)

        t_vbox = QVBoxLayout()
        t_vbox.setSpacing(2)

        title_row = QHBoxLayout()
        h_title = QLabel("<b>🧹 序列檢查與格式清洗 (Sequence Sanitizer & Format Converter)</b>")
        h_title.setStyleSheet("color: #0F172A; font-size: 14px;")
        title_row.addWidget(h_title)

        mode_badge = QLabel("🛠️ 獨立單工模式")
        mode_badge.setStyleSheet("color: #0F766E; background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 1px 8px; font-size: 10px; font-weight: bold;")
        title_row.addWidget(mode_badge)
        title_row.addStretch()
        t_vbox.addLayout(title_row)

        h_sub = QLabel("自動清洗標頭非法字元、去除重複物種名稱、修復異常序列符號，計算 GC 含量與長度分佈，並支援 PHYLIP / NEXUS 格式轉換")
        h_sub.setStyleSheet("color: #64748B; font-size: 11px;")
        t_vbox.addWidget(h_sub)
        h_layout.addLayout(t_vbox, 1)

        info_btn = QLabel("💡 格式規範說明")
        info_btn.setStyleSheet("color: #008287; background-color: #F1F5F9; padding: 4px 10px; border-radius: 12px; font-size: 11px; border: 1px solid #CBD5E1; font-weight: 500;")
        info_btn.setToolTip(
            "演化分析軟體常因序列標頭含空白鍵、冒號、括號或垂直線而報錯。\n"
            "本模組可自動清洗非法字元、保證標頭唯一性、計算 GC 含量與長度分佈，並支援多種演化格式轉換。"
        )
        h_layout.addWidget(info_btn)
        layout.addWidget(header_box)

        # Step 1: File Select (Clean Card Layout)
        file_box = QGroupBox("步驟 1：選取待檢驗檔案 (FASTA File)")
        f_grid = QGridLayout(file_box)
        f_grid.setContentsMargins(12, 14, 12, 12)
        f_grid.setHorizontalSpacing(10)
        f_grid.setVerticalSpacing(8)

        lbl_f = QLabel("FASTA 序列檔:")
        lbl_f.setStyleSheet("font-weight: 600; color: #334155;")
        self.file_edit = QLineEdit()
        self.file_edit.setMinimumHeight(30)
        self.file_edit.setPlaceholderText("請選取或拖曳 FASTA 檔案 (*.fasta, *.fa, *.fas)...")

        browse_btn = QPushButton("瀏覽 (Browse)...")
        browse_btn.setFixedHeight(30)
        browse_btn.setFixedWidth(115)
        browse_btn.clicked.connect(self.browse_file)

        sample_btn = QPushButton("💡 載入範例資料")
        sample_btn.setFixedHeight(30)
        sample_btn.setFixedWidth(120)
        sample_btn.clicked.connect(self.load_sample)

        check_btn = QPushButton("▶ 檢查與清洗")
        check_btn.setObjectName("primary_button")
        check_btn.setFixedHeight(30)
        check_btn.setFixedWidth(125)
        check_btn.clicked.connect(self.analyze_file)

        f_grid.addWidget(lbl_f, 0, 0)
        f_grid.addWidget(self.file_edit, 0, 1)
        f_grid.addWidget(browse_btn, 0, 2)
        f_grid.addWidget(sample_btn, 0, 3)
        f_grid.addWidget(check_btn, 0, 4)
        f_grid.setColumnStretch(1, 1)

        # Status / Result Banner
        self.result_banner = QFrame()
        self.result_banner.setStyleSheet("background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 6px; padding: 6px 12px;")
        rb_layout = QHBoxLayout(self.result_banner)
        rb_layout.setContentsMargins(4, 2, 4, 2)
        self.result_label = QLabel("✓ 序列檢查與清洗已完成！")
        self.result_label.setStyleSheet("color: #0F766E; font-size: 11px; font-weight: bold;")
        rb_layout.addWidget(self.result_label)
        self.result_banner.setVisible(False)
        f_grid.addWidget(self.result_banner, 1, 0, 1, 5)

        layout.addWidget(file_box)

        # Step 2: Sequence Table Display
        table_box = QGroupBox("步驟 2：序列品質與統計分析表 (Sequence Table Display)")
        tb_layout = QVBoxLayout(table_box)
        tb_layout.setContentsMargins(8, 12, 8, 8)
        self.table_widget = SequenceTableWidget()
        tb_layout.addWidget(self.table_widget)
        layout.addWidget(table_box, 1)

        # Step 3: Save Cleaned & Format Converter Box
        convert_box = QGroupBox("步驟 3：儲存清洗成果、格式轉換與前往比對 (Export & Convert)")
        c_layout = QHBoxLayout(convert_box)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setSpacing(10)

        save_clean_btn = QPushButton("💾 儲存清洗後序列")
        save_clean_btn.setFixedHeight(32)
        save_clean_btn.clicked.connect(self.save_cleaned)
        c_layout.addWidget(save_clean_btn)

        lbl_conv = QLabel("轉檔目標格式:")
        lbl_conv.setStyleSheet("font-weight: 600; color: #334155;")
        c_layout.addWidget(lbl_conv)
        self.format_combo = QComboBox()
        self.format_combo.setMinimumHeight(30)
        self.format_combo.addItems([
            "PHYLIP Relaxed (*.phy)",
            "PHYLIP Strict (10-char, *.phy)",
            "NEXUS (*.nex)",
            "Clustal (*.aln)",
        ])
        c_layout.addWidget(self.format_combo)

        convert_btn = QPushButton("轉檔 (Convert)")
        convert_btn.setFixedHeight(32)
        convert_btn.clicked.connect(self.run_conversion)
        c_layout.addWidget(convert_btn)

        c_layout.addStretch()

        self.to_align_btn = QPushButton("🧬 前往比對 (MAFFT) ➔")
        self.to_align_btn.setObjectName("primary_button")
        self.to_align_btn.setFixedHeight(32)
        self.to_align_btn.clicked.connect(self.send_to_alignment)
        c_layout.addWidget(self.to_align_btn)

        layout.addWidget(convert_box)

    def browse_file(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "選取 FASTA 序列檔案", "", "FASTA 檔案 (*.fasta *.fa *.fas *.fna);;所有檔案 (*)"
        )
        if fp:
            self.file_edit.setText(fp)
            self.analyze_file(show_dialog=True)

    def load_sample(self):
        sample = DATA_DIR / "primates_cytb.fasta"
        if sample.exists():
            self.file_edit.setText(str(sample))
            self.analyze_file(show_dialog=True)

    def analyze_file(self, show_dialog: bool = True):
        fp = self.file_edit.text().strip()
        if not fp or not Path(fp).exists():
            QMessageBox.warning(self, "提醒", "請先選取有效的 FASTA 檔案！")
            return

        res = sanitize_fasta_file(fp)
        self.current_result = res
        self.table_widget.load_data(res)

        if not res.success:
            self.result_banner.setVisible(True)
            self.result_banner.setStyleSheet("background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 6px; padding: 6px 12px;")
            self.result_label.setStyleSheet("color: #991B1B; font-size: 11px; font-weight: bold;")
            self.result_label.setText(f"✕ 序列讀取或解析失敗：{res.message}")
            if show_dialog:
                QMessageBox.critical(self, "清洗失敗", f"序列讀取或解析失敗:\n{res.message}")
            return

        seq_count = len(res.cleaned_records)
        warn_count = len(res.warnings)

        self.result_banner.setVisible(True)
        self.result_banner.setStyleSheet("background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 6px; padding: 6px 12px;")
        self.result_label.setStyleSheet("color: #0F766E; font-size: 11px; font-weight: bold;")
        if warn_count > 0:
            self.result_label.setText(f"✓ 序列檢查與清洗完成！共檢核 {seq_count} 條序列（已自動修復 {warn_count} 處異常標頭或非法字元）。")
        else:
            self.result_label.setText(f"✓ 序列檢查與清洗完成！共檢核 {seq_count} 條序列，格式完全合規，未發現異常。")

        if show_dialog:
            if warn_count > 0:
                warn_msg = "\n".join(res.warnings[:10])
                if warn_count > 10:
                    warn_msg += f"\n...以及另外 {warn_count - 10} 則提醒。"
                QMessageBox.information(
                    self,
                    "序列檢查與清洗完成",
                    f"✓ 序列檢查與清洗順利完成！\n\n"
                    f"• 共檢核序列數：{seq_count} 條\n"
                    f"• 自動修正或提醒事項（{warn_count} 項）：\n{warn_msg}\n\n"
                    f"可點選下方「儲存清洗後序列」或「前往比對 (MAFFT)」進行下一步！"
                )
            else:
                QMessageBox.information(
                    self,
                    "序列檢查與清洗完成",
                    f"✓ 序列檢查與清洗順利完成！\n\n"
                    f"• 共檢核序列數：{seq_count} 條\n"
                    f"• 格式檢驗：完全合規（無重複物種、無非法字元、標頭合乎規範）\n"
                    f"• 各序列長度與 GC 含量已更新至下方分析表。\n\n"
                    f"可點選下方「儲存清洗後序列」或「前往比對 (MAFFT)」進行下一步！"
                )

    def save_cleaned(self):
        if not self.current_result or not self.current_result.success:
            QMessageBox.warning(self, "提醒", "尚未有可儲存之分析序列。")
            return

        fp, _ = QFileDialog.getSaveFileName(
            self, "儲存清洗後的 FASTA", str(OUTPUT_DIR / "cleaned_sequences.fasta"), "FASTA (*.fasta)"
        )
        if fp:
            save_sanitized_fasta(self.current_result.cleaned_records, fp)
            QMessageBox.information(self, "儲存成功", f"清洗後 FASTA 已儲存至:\n{fp}")

    def run_conversion(self):
        fp = self.file_edit.text().strip()
        if not fp or not Path(fp).exists():
            QMessageBox.warning(self, "提醒", "請先選取有效的輸入序列檔案！")
            return

        fmt_text = self.format_combo.currentText()
        if "Relaxed" in fmt_text:
            out_fmt = "phylip-relaxed"
            ext = ".phy"
        elif "Strict" in fmt_text:
            out_fmt = "phylip-strict"
            ext = ".phy"
        elif "NEXUS" in fmt_text:
            out_fmt = "nexus"
            ext = ".nex"
        else:
            out_fmt = "clustal"
            ext = ".aln"

        default_out = str(Path(fp).with_suffix(ext))
        save_path, _ = QFileDialog.getSaveFileName(self, "儲存轉檔檔案", default_out)
        if save_path:
            ok, msg = convert_alignment(fp, save_path, in_format="fasta", out_format=out_fmt)
            if ok:
                QMessageBox.information(self, "轉檔成功", msg)
            else:
                QMessageBox.critical(self, "轉檔失敗", msg)

    def send_to_alignment(self):
        fp = self.file_edit.text().strip()
        if not fp or not Path(fp).exists():
            QMessageBox.warning(self, "警告", "請先選取或分析有效序列檔案。")
            return

        if self.current_result and self.current_result.success:
            cleaned_path = OUTPUT_DIR / f"{Path(fp).stem}_cleaned.fasta"
            save_sanitized_fasta(self.current_result.cleaned_records, cleaned_path)
            self.send_to_align_requested.emit(str(cleaned_path))
        else:
            self.send_to_align_requested.emit(fp)
