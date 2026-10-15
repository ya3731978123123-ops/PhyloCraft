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
    QListWidget,
    QFileDialog,
    QComboBox,
    QCheckBox,
    QMessageBox,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
)
from PySide6.QtCore import QUrl, Signal, Qt
from PySide6.QtGui import QDesktopServices
from src.config import OUTPUT_DIR
from src.core.concatenator import concatenate_alignments, ConcatResult


class ConcatTab(QWidget):
    """
    多基因超矩陣串聯與分區模型產生分頁 (Matrix Concatenator & Partition Generator)
    提供基因覆蓋度/完整度矩陣檢視，並可一鍵直接送入 IQ-TREE 2 執行分區模型建樹。
    """

    send_to_tree_requested = Signal(str, str)  # (supermatrix_fasta, partition_file)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.file_list: list[str] = []
        self.last_result: ConcatResult | None = None
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Top Standalone Header Banner
        header_box = QFrame()
        header_box.setStyleSheet("background-color: #FFFFFF; border-radius: 6px; padding: 10px 14px; border: 1px solid #CBD5E1;")
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(0, 0, 0, 0)

        t_vbox = QVBoxLayout()
        t_vbox.setSpacing(2)

        title_row = QHBoxLayout()
        h_title = QLabel("<b>🧩 多基因超矩陣串聯與分區模型產生 (Supermatrix Concatenator)</b>")
        h_title.setStyleSheet("color: #0F172A; font-size: 14px;")
        title_row.addWidget(h_title)

        mode_badge = QLabel("🛠️ 獨立單工模式")
        mode_badge.setStyleSheet("color: #0F766E; background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 1px 8px; font-size: 10px; font-weight: bold;")
        title_row.addWidget(mode_badge)
        title_row.addStretch()
        t_vbox.addLayout(title_row)

        h_sub = QLabel("自動串聯多個基因同源比對檔、智慧補全缺漏位點 (?)、產出 IQ-TREE / NEXUS 分區模型檔與基因覆蓋度矩陣；免專案直接速算")
        h_sub.setStyleSheet("color: #64748B; font-size: 11px;")
        t_vbox.addWidget(h_sub)
        h_layout.addLayout(t_vbox, 1)

        info_btn = QLabel("💡 串聯與分區指引")
        info_btn.setStyleSheet("color: #008287; background-color: #F1F5F9; padding: 4px 10px; border-radius: 12px; font-size: 11px; border: 1px solid #CBD5E1; font-weight: 500;")
        info_btn.setToolTip(
            "演化生物學常需將多個基因（如葉綠體 matK/rbcL、粒線體 COI/Cytb、核基因 ITS）串聯為超矩陣。\n"
            "若特定物種缺乏某些基因，系統會自動補齊空缺字元（?），並同步生成 IQ-TREE 專屬分區模型檔（Partition File），\n"
            "讓 ModelFinder 能夠為每一個獨立基因分別挑選專屬的最優演化模型（Edge-proportional / Edge-unlinked）。"
        )
        h_layout.addWidget(info_btn)
        layout.addWidget(header_box)

        # 2. Middle Area: File List (Left) + Gene Occupancy Table (Right)
        mid_row = QHBoxLayout()

        # 2A. File List Box
        list_box = QGroupBox("步驟 1：待串聯之基因比對檔清單 (Gene Alignments)")
        l_layout = QVBoxLayout(list_box)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ 新增基因比對檔...")
        add_btn.clicked.connect(self.add_files)
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("移除選定")
        remove_btn.clicked.connect(self.remove_selected)
        btn_row.addWidget(remove_btn)

        clear_btn = QPushButton("清空清單")
        clear_btn.clicked.connect(self.clear_all)
        btn_row.addWidget(clear_btn)
        l_layout.addLayout(btn_row)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px; color: #1e293b;"
        )
        l_layout.addWidget(self.list_widget)
        mid_row.addWidget(list_box, 1)

        # 2B. Occupancy / Partition Table Box
        table_box = QGroupBox("步驟 1.1：基因分區與完整度分析 (Partition Occupancy)")
        t_layout = QVBoxLayout(table_box)

        self.gene_table = QTableWidget()
        self.gene_table.setColumnCount(5)
        self.gene_table.setHorizontalHeaderLabels([
            "基因 (Gene)",
            "長度 (Sites)",
            "位點區間 (Range)",
            "涵蓋物種 (Taxa)",
            "完整度 (Occupancy)",
        ])
        t_hdr = self.gene_table.horizontalHeader()
        t_hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        t_hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        t_hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        t_hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        t_hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.gene_table.verticalHeader().setVisible(False)
        self.gene_table.verticalHeader().setDefaultSectionSize(34)
        self.gene_table.setSelectionBehavior(QTableWidget.SelectRows)
        t_layout.addWidget(self.gene_table)

        self.summary_badge = QLabel("尚未執行串聯。請先加入多個基因比對檔案後點擊執行。")
        self.summary_badge.setStyleSheet("color: #006644; font-weight: bold; font-size: 12px;")
        t_layout.addWidget(self.summary_badge)

        mid_row.addWidget(table_box, 1)
        layout.addLayout(mid_row, 1)

        # 3. Partition Settings & Paths (Clean Grid Layout)
        opt_box = QGroupBox("步驟 2：分區設定與輸出位置 (Settings & Output Paths)")
        o_grid = QGridLayout(opt_box)
        o_grid.setContentsMargins(12, 14, 12, 12)
        o_grid.setHorizontalSpacing(10)
        o_grid.setVerticalSpacing(8)

        # Row 0: 分區格式與密碼子
        lbl_fmt = QLabel("分區語法格式:")
        self.part_format_combo = QComboBox()
        self.part_format_combo.setMinimumHeight(28)
        self.part_format_combo.addItems([
            "iqtree (IQ-TREE NEXUS sets block)",
            "raxml (RAxML 標準文字格式)",
            "nexus (標準 PAUP/MrBayes sets 格式)",
        ])
        self.codon_cb = QCheckBox("切分密碼子 3 個位點 (Codon 1st, 2nd, 3rd)")
        self.codon_cb.setToolTip("適用於 CDS 蛋白質編碼基因，將每個基因自動拆為 3 個獨立速率分區")

        fmt_widget = QWidget()
        fmt_layout = QHBoxLayout(fmt_widget)
        fmt_layout.setContentsMargins(0, 0, 0, 0)
        fmt_layout.setSpacing(12)
        fmt_layout.addWidget(self.part_format_combo, 1)
        fmt_layout.addWidget(self.codon_cb, 1)
        fmt_layout.addStretch()

        o_grid.addWidget(lbl_fmt, 0, 0)
        o_grid.addWidget(fmt_widget, 0, 1, 1, 2)

        # Row 1: 超矩陣 FASTA 輸出
        lbl_fa = QLabel("超矩陣 FASTA:")
        self.out_fa_edit = QLineEdit(str(OUTPUT_DIR / "supermatrix.fasta"))
        self.out_fa_edit.setMinimumHeight(28)
        out_fa_btn = QPushButton("更改位置...")
        out_fa_btn.setFixedWidth(115)
        out_fa_btn.clicked.connect(self.browse_out_fa)
        o_grid.addWidget(lbl_fa, 1, 0)
        o_grid.addWidget(self.out_fa_edit, 1, 1)
        o_grid.addWidget(out_fa_btn, 1, 2)

        # Row 2: 分區定義檔輸出
        lbl_part = QLabel("分區定義檔:")
        self.out_part_edit = QLineEdit(str(OUTPUT_DIR / "partitions.nex"))
        self.out_part_edit.setMinimumHeight(28)
        out_part_btn = QPushButton("更改位置...")
        out_part_btn.setFixedWidth(115)
        out_part_btn.clicked.connect(self.browse_out_part)
        o_grid.addWidget(lbl_part, 2, 0)
        o_grid.addWidget(self.out_part_edit, 2, 1)
        o_grid.addWidget(out_part_btn, 2, 2)

        o_grid.setColumnStretch(1, 1)
        layout.addWidget(opt_box)

        # 4. Step 3: Action Buttons
        action_box = QGroupBox("步驟 3：極速串聯與成果銜接 (Run & Next Steps)")
        ab_layout = QVBoxLayout(action_box)
        ab_layout.setContentsMargins(12, 12, 12, 12)
        ab_layout.setSpacing(8)

        btn_action_row = QHBoxLayout()
        btn_action_row.setSpacing(8)

        self.run_btn = QPushButton("▶ 執行串聯並產出分區 (Concatenate)")
        self.run_btn.setObjectName("primary_button")
        self.run_btn.setFixedHeight(34)
        self.run_btn.setToolTip("執行多基因序列串聯並自動生成 IQ-TREE 分區模型 (Concatenate & Generate)")
        self.run_btn.clicked.connect(self.run_concat)
        btn_action_row.addWidget(self.run_btn, 2)

        self.send_tree_btn = QPushButton("🌳 發送至建樹分頁 (Send to Tree) ➔")
        self.send_tree_btn.setFixedHeight(34)
        self.send_tree_btn.setEnabled(False)
        self.send_tree_btn.setToolTip("將產出之超矩陣與分區檔案自動填入建樹分頁 (Send to Partitioned Tree)")
        self.send_tree_btn.clicked.connect(self.send_to_tree)
        btn_action_row.addWidget(self.send_tree_btn, 2)

        self.open_dir_btn = QPushButton("開啟資料夾")
        self.open_dir_btn.setFixedHeight(34)
        self.open_dir_btn.clicked.connect(self.open_output_dir)
        btn_action_row.addWidget(self.open_dir_btn, 1)

        ab_layout.addLayout(btn_action_row)
        layout.addWidget(action_box)

        # 5. Result report
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setMaximumHeight(90)
        self.report_text.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; font-family: Consolas; color: #1e293b;"
        )
        layout.addWidget(self.report_text)

    def add_files(self):
        fps, _ = QFileDialog.getOpenFileNames(
            self, "選取基因比對檔案", "", "FASTA 檔案 (*.fasta *.fa *.fas *.aln);;所有檔案 (*)"
        )
        for fp in fps:
            if fp not in self.file_list:
                self.file_list.append(fp)
                self.list_widget.addItem(f"{Path(fp).name}")

    def remove_selected(self):
        selected_indexes = [item.row() for item in self.list_widget.selectedIndexes()]
        for idx in sorted(selected_indexes, reverse=True):
            self.file_list.pop(idx)
            self.list_widget.takeItem(idx)

    def clear_all(self):
        self.file_list.clear()
        self.list_widget.clear()
        self.gene_table.setRowCount(0)
        self.summary_badge.setText("尚未執行串聯。請先加入多個基因比對檔案後點擊執行。")
        self.send_tree_btn.setEnabled(False)

    def browse_out_fa(self):
        fp, _ = QFileDialog.getSaveFileName(self, "儲存超矩陣 FASTA", self.out_fa_edit.text(), "FASTA (*.fasta)")
        if fp:
            self.out_fa_edit.setText(fp)

    def browse_out_part(self):
        fp, _ = QFileDialog.getSaveFileName(
            self, "儲存分區檔案", self.out_part_edit.text(), "分區檔案 (*.nex *.txt)"
        )
        if fp:
            self.out_part_edit.setText(fp)

    def open_output_dir(self):
        out_fa = self.out_fa_edit.text().strip()
        folder = Path(out_fa).parent if out_fa else OUTPUT_DIR
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def run_concat(self):
        if len(self.file_list) < 2:
            QMessageBox.warning(self, "警告", "請至少加入 2 個單基因比對檔案進行串聯。")
            return

        out_fa = self.out_fa_edit.text().strip()
        out_part = self.out_part_edit.text().strip()
        style = self.part_format_combo.currentText().split()[0]
        codon = self.codon_cb.isChecked()

        res = concatenate_alignments(
            self.file_list,
            out_fa,
            out_part,
            partition_style=style,
            codon_partition=codon,
        )

        self.last_result = res

        if res.success:
            self.send_tree_btn.setEnabled(True)

            # Update Gene Table
            self.gene_table.setRowCount(len(res.genes))
            for row, g in enumerate(res.genes):
                self.gene_table.setItem(row, 0, QTableWidgetItem(g.gene_name))
                self.gene_table.setItem(row, 1, QTableWidgetItem(f"{g.length:,} bp"))
                self.gene_table.setItem(row, 2, QTableWidgetItem(f"{g.start} - {g.end}"))
                self.gene_table.setItem(row, 3, QTableWidgetItem(f"{g.taxa_count} / {g.total_taxa}"))

                comp_item = QTableWidgetItem(f"{g.completeness_pct:.1f}%")
                comp_item.setTextAlignment(Qt.AlignCenter)
                comp_item.setForeground(Qt.green if g.completeness_pct >= 80 else Qt.yellow)
                self.gene_table.setItem(row, 4, comp_item)

            self.summary_badge.setText(
                f"[完成] 串聯完成: 總物種數 {res.total_taxa} | 矩陣總長度 {res.total_sites:,} bp | 整體完整度 {res.overall_completeness}%"
            )

            report_lines = [
                f"[成功] {res.message}",
                f"產生物理檔案:",
                f"  • 超矩陣 FASTA: {res.output_fasta}",
                f"  • 分區模型檔: {res.output_partition}",
                f"  • 完整度矩陣 CSV: {res.output_csv}",
            ]
            if res.missing_taxa_report:
                report_lines.append("\n[提示] 部分物種缺少特定基因 (已自動補齊 ?):")
                for gene, taxa in res.missing_taxa_report.items():
                    report_lines.append(f"  - 基因 '{gene}': 缺 {len(taxa)} 個物種 ({', '.join(taxa[:4])}...)")
            self.report_text.setText("\n".join(report_lines))

            QMessageBox.information(
                self,
                "串聯成功",
                f"超矩陣串聯已完成。\n\n"
                f"• 總物種數: {res.total_taxa}\n"
                f"• 超矩陣總位點: {res.total_sites:,} bp\n"
                f"• 整體完整度: {res.overall_completeness}%\n\n"
                f"可點選下方「一鍵發送至 IQ-TREE 2 進行分區建樹」直接開始分析！",
            )
        else:
            self.send_tree_btn.setEnabled(False)
            self.report_text.setText(f"[錯誤] {res.message}")
            QMessageBox.critical(self, "串聯失敗", res.message)

    def send_to_tree(self):
        if self.last_result and self.last_result.success:
            self.send_to_tree_requested.emit(
                self.last_result.output_fasta, self.last_result.output_partition
            )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        added = 0
        for u in urls:
            fp = Path(u.toLocalFile())
            if fp.exists() and fp.suffix.lower() in (".fasta", ".fa", ".fas", ".fna", ".faa", ".aln", ".phy"):
                str_fp = str(fp)
                if str_fp not in self.file_list:
                    self.file_list.append(str_fp)
                    self.list_widget.addItem(fp.name)
                    added += 1
        if added > 0:
            self.summary_badge.setText(f"已拖曳加入 {added} 個基因比對檔，目前清單共 {len(self.file_list)} 個檔案待串聯。")
