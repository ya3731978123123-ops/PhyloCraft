from datetime import datetime
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QCheckBox,
)
from PySide6.QtGui import QTextCursor, QColor
from PySide6.QtCore import Qt


class LogViewer(QWidget):
    """
    Real-time scrolling log console with syntax coloring, clear, and copy functions.
    """

    def __init__(self, title: str = "Execution Log", parent: QWidget | None = None):
        super().__init__(parent)
        self.init_ui(title)

    def init_ui(self, title: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(2, 0, 2, 0)
        header_layout.setSpacing(6)
        self.title_label = QLabel(f"<b>{title}</b>")
        self.title_label.setStyleSheet("color: #008287; font-size: 11px;")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(True)
        header_layout.addWidget(self.auto_scroll_cb)

        btn_style = """
            QPushButton {
                background-color: #F8FAFC;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 500;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #0F766E;
            }
        """

        self.copy_btn = QPushButton("複製 (Copy)")
        self.copy_btn.setMinimumWidth(85)
        self.copy_btn.setFixedHeight(26)
        self.copy_btn.setStyleSheet(btn_style)
        self.copy_btn.clicked.connect(self.copy_log)
        header_layout.addWidget(self.copy_btn)

        self.clear_btn = QPushButton("清除 (Clear)")
        self.clear_btn.setMinimumWidth(85)
        self.clear_btn.setFixedHeight(26)
        self.clear_btn.setStyleSheet(btn_style)
        self.clear_btn.clicked.connect(self.clear_log)
        header_layout.addWidget(self.clear_btn)

        self.is_collapsed = False
        self.toggle_btn = QPushButton("收合日誌 ▲")
        self.toggle_btn.setMinimumWidth(95)
        self.toggle_btn.setFixedHeight(26)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F766E;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        self.toggle_btn.setToolTip("點擊以收合終端日誌並騰出更多操作空間，亦可再次展開")
        self.toggle_btn.clicked.connect(self.toggle_collapse)
        header_layout.addWidget(self.toggle_btn)

        layout.addLayout(header_layout)

        # Log Text Box
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMinimumHeight(100)
        self.text_edit.setPlaceholderText(
            "[終端就緒] 點擊執行按鈕後，原生生信工具指令輸出與即時運算進度將即時串流於此..."
        )
        self.text_edit.setStyleSheet(
            """
            QTextEdit {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                color: #1e293b;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.4;
            }
            """
        )
        layout.addWidget(self.text_edit)

    def toggle_collapse(self):
        self.set_collapsed(not self.is_collapsed)

    def set_collapsed(self, collapsed: bool):
        self.is_collapsed = collapsed
        self.text_edit.setVisible(not collapsed)
        self.toggle_btn.setText("展開日誌 ▼" if collapsed else "收合日誌 ▲")
        self.toggle_btn.setToolTip("點擊以展開終端日誌" if collapsed else "點擊以收合終端日誌並騰出更多操作空間")
        if collapsed:
            self.setFixedHeight(32)
        else:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(120)

    def append_log(self, text: str, custom_color: str | None = None):
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Color-coded rules
        color = custom_color or "#1e293b"
        if not custom_color:
            if "[Command]" in text:
                color = "#0284c7"
            elif "[Success]" in text:
                color = "#16a34a"
            elif "[Error]" in text or "[Exception]" in text or "ERROR" in text:
                color = "#dc2626"
            elif "[Warning]" in text or "WARNING" in text:
                color = "#d97706"
            elif "[Step" in text or "Stage" in text:
                color = "#7c3aed"

        formatted = f'<span style="color: #94a3b8;">[{timestamp}]</span> <span style="color: {color};">{text}</span>'
        self.text_edit.append(formatted)

        if self.is_collapsed:
            self.toggle_btn.setText("展開日誌 (新輸出 •) ▼")

        if self.auto_scroll_cb.isChecked():
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.text_edit.setTextCursor(cursor)

    def clear_log(self):
        self.text_edit.clear()

    def clear(self):
        self.clear_log()

    def copy_log(self):
        self.text_edit.selectAll()
        self.text_edit.copy()
        cursor = self.text_edit.textCursor()
        cursor.clearSelection()
        self.text_edit.setTextCursor(cursor)
