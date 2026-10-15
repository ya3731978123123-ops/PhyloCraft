from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
)
from PySide6.QtCore import Qt
from src.core.sanitizer import SequenceInfo, SanitizerResult


class SequenceTableWidget(QWidget):
    """
    Displays sanitized sequences and diagnostic information with live search filtering.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.all_sequences: list[SequenceInfo] = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header: Summary Bar & Search Filter
        top_bar = QHBoxLayout()

        self.summary_label = QLabel("尚未載入序列。")
        self.summary_label.setStyleSheet("color: #a5adcb; font-size: 12px; font-weight: bold;")
        top_bar.addWidget(self.summary_label)

        top_bar.addStretch()

        # Real-time search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜尋物種或序列 ID...")
        self.search_edit.setFixedWidth(220)
        self.search_edit.textChanged.connect(self.filter_table)
        top_bar.addWidget(self.search_edit)

        self.match_count_label = QLabel("")
        self.match_count_label.setStyleSheet("color: #8aadf4; font-size: 11px;")
        top_bar.addWidget(self.match_count_label)

        layout.addLayout(top_bar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "#",
            "清洗後 ID (Sanitized)",
            "原始 ID (Original)",
            "長度 (bp/aa)",
            "GC 含量 (%)",
            "空缺 / 簡併位點",
            "序列預覽 (Preview)",
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 48)
        self.table.setColumnWidth(1, 165)
        self.table.setColumnWidth(2, 165)

        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self.table)

    def load_data(self, result: SanitizerResult):
        self.table.setRowCount(0)
        self.search_edit.clear()
        if not result.success:
            self.summary_label.setText("序列解析失敗。")
            self.match_count_label.setText("")
            return

        self.all_sequences = result.sequences

        summary = (
            f"總物種數: <b>{result.total_taxa}</b> | "
            f"分子類型: <b>{result.seq_type}</b> | "
            f"長度區間: <b>{result.min_length} ~ {result.max_length} bp</b> (平均: {result.avg_length}) | "
            f"是否已比對: <b>{'是 (已對齊)' if result.is_aligned else '否 (需執行多重比對)'}</b>"
        )
        self.summary_label.setText(summary)

        self.table.setRowCount(len(result.sequences))
        for row, seq in enumerate(result.sequences):
            # Index
            item_idx = QTableWidgetItem(str(row + 1))
            item_idx.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_idx)

            # Sanitized ID
            item_id = QTableWidgetItem(seq.sanitized_id)
            if seq.sanitized_id != seq.original_id:
                item_id.setForeground(Qt.cyan)
                item_id.setToolTip("此標頭已自動修正非法字元")
            self.table.setItem(row, 1, item_id)

            # Original ID
            item_orig = QTableWidgetItem(seq.original_id)
            self.table.setItem(row, 2, item_orig)

            # Length
            item_len = QTableWidgetItem(str(seq.length))
            item_len.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_len)

            # GC%
            item_gc = QTableWidgetItem(f"{seq.gc_content:.1f}%")
            item_gc.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, item_gc)

            # Gaps / Ambiguous
            item_gaps = QTableWidgetItem(f"{seq.gap_count} / {seq.ambiguous_count}")
            item_gaps.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, item_gaps)

            # Preview
            item_prev = QTableWidgetItem(seq.preview)
            self.table.setItem(row, 6, item_prev)

        self.match_count_label.setText(f"(共 {len(result.sequences)} 筆)")

    def filter_table(self, query: str):
        query = query.strip().lower()
        visible_count = 0
        total_rows = self.table.rowCount()

        for row in range(total_rows):
            if not query:
                self.table.setRowHidden(row, False)
                visible_count += 1
            else:
                id_item = self.table.item(row, 1)
                orig_item = self.table.item(row, 2)
                id_text = id_item.text().lower() if id_item else ""
                orig_text = orig_item.text().lower() if orig_item else ""

                if query in id_text or query in orig_text:
                    self.table.setRowHidden(row, False)
                    visible_count += 1
                else:
                    self.table.setRowHidden(row, True)

        if query:
            self.match_count_label.setText(f"(符合: {visible_count} / {total_rows})")
        else:
            self.match_count_label.setText(f"(共 {total_rows} 筆)")
