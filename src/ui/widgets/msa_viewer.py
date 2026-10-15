from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollBar,
    QLabel,
    QCheckBox,
    QSpinBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QLineEdit,
)
from PySide6.QtGui import QPainter, QFont, QColor, QBrush, QPen, QWheelEvent, QMouseEvent
from PySide6.QtCore import Qt, QRect, Signal
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord


class MSACanvas(QWidget):
    """
    High-performance virtual scrolling canvas for visualizing alignments.
    Supports mouse gestures (Wheel, Shift+Wheel, Ctrl+Wheel) and position tracking.
    """

    position_hovered = Signal(str)
    scroll_changed = Signal(int, int)

    COLOR_MAP = {
        "A": (QColor("#dcfce7"), QColor("#15803d")),
        "C": (QColor("#e0f2fe"), QColor("#0369a1")),
        "G": (QColor("#fef3c7"), QColor("#b45309")),
        "T": (QColor("#fee2e2"), QColor("#b91c1c")),
        "U": (QColor("#fee2e2"), QColor("#b91c1c")),
        "-": (QColor("#f8fafc"), QColor("#94a3b8")),
        ".": (QColor("#f8fafc"), QColor("#94a3b8")),
        "?": (QColor("#f8fafc"), QColor("#94a3b8")),
    }
    DEFAULT_COLOR = (QColor("#f8fafc"), QColor("#334155"))

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.taxa: list[str] = []
        self.sequences: list[str] = []
        self.consensus: str = ""
        self.total_taxa = 0
        self.alignment_length = 0

        self.char_w = 14
        self.char_h = 22
        self.header_w = 170
        self.ruler_h = 24
        self.consensus_h = 24

        self.scroll_x = 0
        self.scroll_y = 0

        self.mutation_only_mode = False
        self.font = QFont("Consolas, Courier New, monospace", 10, QFont.Bold)
        self.setMouseTracking(True)

    def load_records(self, records: list[SeqRecord]):
        self.taxa = [r.id for r in records]
        raw_seqs = [str(r.seq).upper() for r in records]
        self.total_taxa = len(raw_seqs)
        max_len = max((len(s) for s in raw_seqs), default=0)
        self.alignment_length = max_len
        # Pad any shorter sequence to max_len to safely handle unaligned inputs
        self.sequences = [s.ljust(max_len, "-") for s in raw_seqs]

        # Compute consensus
        if self.total_taxa > 0 and self.alignment_length > 0:
            consensus_chars = []
            for col in range(self.alignment_length):
                bases = [self.sequences[row][col] for row in range(self.total_taxa)]
                counts = {}
                for b in bases:
                    counts[b] = counts.get(b, 0) + 1
                top = max(counts, key=counts.get)
                consensus_chars.append(top)
            self.consensus = "".join(consensus_chars)
        else:
            self.consensus = ""

        self.update()

    def set_zoom(self, font_size: int):
        self.font.setPointSize(font_size)
        self.char_w = int(font_size * 1.35)
        self.char_h = int(font_size * 2.0)
        self.update()

    def set_mutation_mode(self, enabled: bool):
        self.mutation_only_mode = enabled
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        """
        Handle direct mouse wheel interactions on the canvas:
        - Regular Wheel: Vertical scroll across taxa
        - Shift + Wheel (or horizontal tilt): Horizontal scroll across alignment positions
        - Ctrl + Wheel: Zoom in / Zoom out
        """
        modifiers = event.modifiers()
        delta = event.angleDelta().y()

        if modifiers == Qt.ControlModifier:
            curr = self.font.pointSize()
            new_size = max(8, min(22, curr + (1 if delta > 0 else -1)))
            self.set_zoom(new_size)
            event.accept()
        elif modifiers == Qt.ShiftModifier or event.angleDelta().x() != 0:
            h_delta = event.angleDelta().x() if event.angleDelta().x() != 0 else delta
            step = 3 if h_delta < 0 else -3
            max_x = max(0, self.alignment_length - 5)
            self.scroll_x = max(0, min(max_x, self.scroll_x + step))
            self.scroll_changed.emit(self.scroll_x, self.scroll_y)
            self.update()
            event.accept()
        else:
            step = 2 if delta < 0 else -2
            max_y = max(0, self.total_taxa - 3)
            self.scroll_y = max(0, min(max_y, self.scroll_y + step))
            self.scroll_changed.emit(self.scroll_x, self.scroll_y)
            self.update()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        x = event.position().x()
        y = event.position().y()

        if x > self.header_w and self.ruler_h < y < (self.height() - self.consensus_h):
            col_idx = self.scroll_x + int((x - self.header_w) // self.char_w)
            row_idx = self.scroll_y + int((y - self.ruler_h) // self.char_h)

            if 0 <= col_idx < self.alignment_length and 0 <= row_idx < self.total_taxa:
                taxon = self.taxa[row_idx]
                base = self.sequences[row_idx][col_idx]
                self.position_hovered.emit(f"物種: <b>{taxon}</b> | 位點: <b>第 {col_idx + 1} bp</b> | 鹼基: <b>{base}</b>")
                return

        self.position_hovered.emit("")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font)

        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        if self.total_taxa == 0 or self.alignment_length == 0:
            painter.setPen(QColor("#64748b"))
            padded_rect = self.rect().adjusted(16, 16, -16, -16)
            painter.drawText(
                padded_rect,
                Qt.AlignCenter | Qt.TextWordWrap,
                "尚未載入比對檔案。\n\n可直接將 .fasta 比對檔拖曳至此處，\n或於「一鍵黃金管線」完成後檢視。",
            )
            return

        avail_w = max(10, w - self.header_w)
        avail_h = max(10, h - self.ruler_h - self.consensus_h)

        visible_cols = avail_w // self.char_w + 2
        visible_rows = avail_h // self.char_h + 2

        start_col = max(0, self.scroll_x)
        end_col = min(self.alignment_length, start_col + visible_cols)

        start_row = max(0, self.scroll_y)
        end_row = min(self.total_taxa, start_row + visible_rows)

        # 1. Ruler Background
        painter.fillRect(0, 0, w, self.ruler_h, QColor("#f8fafc"))
        painter.setPen(QColor("#e2e8f0"))
        painter.drawLine(0, self.ruler_h, w, self.ruler_h)

        # 2. Taxa Column Background
        painter.fillRect(0, 0, self.header_w, h, QColor("#f8fafc"))
        painter.setPen(QColor("#e2e8f0"))
        painter.drawLine(self.header_w, 0, self.header_w, h)

        # 3. Ruler Ticks & Numbers
        painter.setPen(QColor("#006644"))
        for col in range(start_col, end_col):
            x = self.header_w + (col - start_col) * self.char_w
            pos = col + 1
            if pos == 1 or pos % 10 == 0:
                painter.drawText(x, self.ruler_h - 6, str(pos))
                painter.drawLine(x, self.ruler_h - 4, x, self.ruler_h)
            elif pos % 5 == 0:
                painter.drawLine(x, self.ruler_h - 2, x, self.ruler_h)

        # 4. Taxa Labels & Sequence Matrix
        ref_seq = self.sequences[0] if self.sequences else ""

        for row in range(start_row, end_row):
            y = self.ruler_h + (row - start_row) * self.char_h
            taxon_name = self.taxa[row]
            seq = self.sequences[row]

            # Taxon Name
            painter.setPen(QColor("#1e293b"))
            text_rect = QRect(8, y, self.header_w - 16, self.char_h)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, taxon_name)

            # Base Cells
            for col in range(start_col, end_col):
                x = self.header_w + (col - start_col) * self.char_w
                char = seq[col] if col < len(seq) else "-"
                ref_char = ref_seq[col] if col < len(ref_seq) else "-"

                is_diff = (row == 0) or (char != ref_char)
                bg_color, fg_color = self.COLOR_MAP.get(char, self.DEFAULT_COLOR)

                if self.mutation_only_mode and not is_diff:
                    painter.fillRect(x + 1, y + 1, self.char_w - 2, self.char_h - 2, QColor("#ffffff"))
                    painter.setPen(QColor("#94a3b8"))
                    painter.drawText(QRect(x, y, self.char_w, self.char_h), Qt.AlignCenter, "·")
                else:
                    painter.fillRect(x + 1, y + 1, self.char_w - 2, self.char_h - 2, bg_color)
                    painter.setPen(fg_color)
                    painter.drawText(QRect(x, y, self.char_w, self.char_h), Qt.AlignCenter, char)

        # 5. Consensus Bar at Bottom
        consensus_y = h - self.consensus_h
        painter.fillRect(0, consensus_y, w, self.consensus_h, QColor("#f1f5f9"))
        painter.setPen(QColor("#e2e8f0"))
        painter.drawLine(0, consensus_y, w, consensus_y)

        painter.setPen(QColor("#008287"))
        painter.drawText(QRect(8, consensus_y, self.header_w - 16, self.consensus_h), Qt.AlignVCenter, "共識序列 (Consensus)")

        for col in range(start_col, end_col):
            x = self.header_w + (col - start_col) * self.char_w
            c_char = self.consensus[col] if col < len(self.consensus) else ""
            painter.drawText(QRect(x, consensus_y, self.char_w, self.consensus_h), Qt.AlignCenter, c_char)


class MSAViewer(QWidget):
    """
    Scrollable wrapper widget with mouse wheel gestures, position jump, and zoom controls.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Toolbar Row 1: File Info & Controls
        tb_layout1 = QHBoxLayout()

        self.info_label = QLabel("尚未載入比對檔案。")
        self.info_label.setStyleSheet("color: #006644; font-weight: bold; font-size: 13px;")
        tb_layout1.addWidget(self.info_label)

        tb_layout1.addStretch()

        self.mut_cb = QCheckBox("僅突顯突變 (Highlight SNPs)")
        self.mut_cb.setToolTip("將與第 1 條參考序列相同的位點縮為淡點 ·，讓物種特有突變一目了然")
        self.mut_cb.stateChanged.connect(self.toggle_mut_mode)
        tb_layout1.addWidget(self.mut_cb)

        tb_layout1.addWidget(QLabel("縮放:"))
        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(8, 22)
        self.zoom_spin.setValue(11)
        self.zoom_spin.setToolTip("字體大小 (支援 Ctrl + 滑鼠滾輪即時縮放)")
        self.zoom_spin.valueChanged.connect(self.on_zoom_changed)
        tb_layout1.addWidget(self.zoom_spin)

        self.open_btn = QPushButton("開啟比對檔...")
        self.open_btn.clicked.connect(self.browse_alignment)
        tb_layout1.addWidget(self.open_btn)

        main_layout.addLayout(tb_layout1)

        # Toolbar Row 2: Jump to Position & Mouse Help
        tb_layout2 = QHBoxLayout()

        tb_layout2.addWidget(QLabel("前往位點 (Jump to bp):"))
        self.jump_edit = QLineEdit()
        self.jump_edit.setPlaceholderText("例如: 500")
        self.jump_edit.setFixedWidth(80)
        self.jump_edit.returnPressed.connect(self.jump_to_position)
        tb_layout2.addWidget(self.jump_edit)

        jump_btn = QPushButton("前往 (Go)")
        jump_btn.clicked.connect(self.jump_to_position)
        tb_layout2.addWidget(jump_btn)

        tb_layout2.addSpacing(15)

        self.hover_label = QLabel("")
        self.hover_label.setStyleSheet("color: #a6da95; font-size: 12px;")
        tb_layout2.addWidget(self.hover_label)

        tb_layout2.addStretch()

        hint_label = QLabel("滾輪: 上下捲動 | <b>Shift + 滾輪</b>: 水平橫移 | <b>Ctrl + 滾輪</b>: 縮放")
        hint_label.setStyleSheet("color: #6e738d; font-size: 11px;")
        tb_layout2.addWidget(hint_label)

        main_layout.addLayout(tb_layout2)

        # Canvas with Scrollbars
        grid_container = QWidget()
        grid_container.setStyleSheet("background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 4px;")
        g_layout = QVBoxLayout(grid_container)
        g_layout.setContentsMargins(0, 0, 0, 0)
        g_layout.setSpacing(0)

        middle_row = QHBoxLayout()
        middle_row.setContentsMargins(0, 0, 0, 0)
        middle_row.setSpacing(0)

        self.canvas = MSACanvas()
        self.canvas.position_hovered.connect(self.hover_label.setText)
        self.canvas.scroll_changed.connect(self.on_canvas_scrolled)
        middle_row.addWidget(self.canvas, 1)

        scroll_style = """
            QScrollBar:vertical {
                border: none;
                background-color: #F1F5F9;
                width: 14px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #CBD5E1;
                min-height: 28px;
                border-radius: 4px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #008287;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background-color: #F1F5F9;
                height: 14px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #CBD5E1;
                min-width: 28px;
                border-radius: 4px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #008287;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """

        self.v_scroll = QScrollBar(Qt.Vertical)
        self.v_scroll.setStyleSheet(scroll_style)
        self.v_scroll.valueChanged.connect(self.on_v_scroll)
        middle_row.addWidget(self.v_scroll)

        g_layout.addLayout(middle_row, 1)

        self.h_scroll = QScrollBar(Qt.Horizontal)
        self.h_scroll.setStyleSheet(scroll_style)
        self.h_scroll.valueChanged.connect(self.on_h_scroll)
        g_layout.addWidget(self.h_scroll)

        main_layout.addWidget(grid_container, 1)

    def on_canvas_scrolled(self, sx: int, sy: int):
        self.h_scroll.blockSignals(True)
        self.v_scroll.blockSignals(True)
        self.h_scroll.setValue(sx)
        self.v_scroll.setValue(sy)
        self.h_scroll.blockSignals(False)
        self.v_scroll.blockSignals(False)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_scrollbars()

    def wheelEvent(self, event: QWheelEvent):
        """
        Forward wheel events to canvas so scrollbars and display synchronize smoothly.
        """
        self.canvas.wheelEvent(event)

    def jump_to_position(self):
        txt = self.jump_edit.text().strip()
        if not txt.isdigit():
            return
        pos = int(txt)
        if pos < 1 or pos > self.canvas.alignment_length:
            QMessageBox.warning(
                self, "無效位點", f"請輸入介於 1 至 {self.canvas.alignment_length} 之間的位點編號。"
            )
            return

        # Center target position
        target_scroll = max(0, min(self.h_scroll.maximum(), pos - 10))
        self.h_scroll.setValue(target_scroll)

    def load_records(self, records: list[SeqRecord], source_name: str = ""):
        if not records:
            return
        lengths = {len(r.seq) for r in records}
        max_len = max(lengths)
        is_unaligned = len(lengths) > 1

        self.canvas.load_records(records)
        name_str = f"<b>{source_name}</b> ｜ " if source_name else ""
        if is_unaligned:
            self.info_label.setText(
                f"{name_str}<span style='color:#B45309;'>([提示] 序列長度不一致/尚未對齊，已自動補齊顯示)</span> ｜ 物種數: <b>{len(records)}</b> ｜ 最大長度: <b>{max_len} bp</b>"
            )
        else:
            self.info_label.setText(
                f"{name_str}物種數: <b>{len(records)}</b> ｜ 比對總長度: <b>{max_len} bp</b>"
            )
        self.update_scrollbars()

    def load_alignment_file(self, file_path: str | Path):
        p = Path(file_path)
        if not p.exists():
            return

        records = []
        last_error = ""

        ext = p.suffix.lower()
        if ext in (".phy", ".phylip"):
            formats_to_try = ["phylip-relaxed", "phylip", "fasta", "nexus"]
        elif ext in (".nex", ".nexus"):
            formats_to_try = ["nexus", "fasta", "phylip-relaxed"]
        else:
            formats_to_try = ["fasta", "phylip-relaxed", "phylip", "nexus"]

        for fmt in formats_to_try:
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as handle:
                    recs = list(SeqIO.parse(handle, fmt))
                if recs:
                    records = recs
                    break
            except Exception as e:
                last_error = str(e)
                continue

        if not records:
            QMessageBox.warning(self, "警告", f"無法解析比對檔案 (支援 FASTA, PHYLIP, NEXUS)。\n{last_error}")
            return

        self.load_records(records, source_name=p.name)

    def update_scrollbars(self):
        w = self.canvas.width()
        h = self.canvas.height()

        avail_w = max(10, w - self.canvas.header_w)
        avail_h = max(10, h - self.canvas.ruler_h - self.canvas.consensus_h)

        visible_cols = max(1, avail_w // self.canvas.char_w)
        visible_rows = max(1, avail_h // self.canvas.char_h)

        max_x = max(0, self.canvas.alignment_length - visible_cols)
        max_y = max(0, self.canvas.total_taxa - visible_rows)

        self.h_scroll.setRange(0, max_x)
        self.h_scroll.setPageStep(max(1, visible_cols))

        self.v_scroll.setRange(0, max_y)
        self.v_scroll.setPageStep(max(1, visible_rows))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scrollbars()

    def on_h_scroll(self, value: int):
        self.canvas.scroll_x = value
        self.canvas.update()

    def on_v_scroll(self, value: int):
        self.canvas.scroll_y = value
        self.canvas.update()

    def on_zoom_changed(self, size: int):
        self.canvas.set_zoom(size)
        self.update_scrollbars()

    def toggle_mut_mode(self):
        self.canvas.set_mutation_mode(self.mut_cb.isChecked())

    def browse_alignment(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "選取比對檔案", "", "比對檔案 (*.fasta *.fa *.fas *.phy);;所有檔案 (*)"
        )
        if fp:
            self.load_alignment_file(fp)
