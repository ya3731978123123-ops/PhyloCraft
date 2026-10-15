from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QFileDialog,
    QFrame,
)
from src.ui.widgets.msa_viewer import MSAViewer


class MSATab(QWidget):
    """
    Interactive MSA Alignment Viewer Tab
    Color-coded nucleotide and protein matrix with consensus and SNP highlights.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 1. Header Box (Sleek single-line)
        header_box = QFrame()
        header_box.setStyleSheet("background-color: #f8fafc; border-radius: 8px; padding: 10px 14px; border: 1px solid #e2e8f0;")
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(0, 0, 0, 0)

        t_vbox = QVBoxLayout()
        t_vbox.setSpacing(2)
        h_title = QLabel("<b>多重序列比對檢視器 (MSA Alignment Explorer)</b>")
        h_title.setStyleSheet("color: #0f172a; font-size: 14px;")
        t_vbox.addWidget(h_title)
        h_sub = QLabel("標準色彩編碼比對檢視器，具備共識序列 (Consensus) 與單核苷酸突變 (SNPs) 篩選功能")
        h_sub.setStyleSheet("color: #64748b; font-size: 11px;")
        t_vbox.addWidget(h_sub)
        h_layout.addLayout(t_vbox, 1)

        info_btn = QLabel("操作指引")
        info_btn.setStyleSheet("color: #006644; background-color: #f1f5f9; padding: 4px 10px; border-radius: 12px; font-size: 11px; border: 1px solid #cbd5e1;")
        info_btn.setToolTip(
            "以四色高亮（A=綠、T=紅、C=藍、G=橘）呈現核酸位點，提供頂部刻度尺標與底部共識序列（Consensus）。\n"
            "操作快速鍵：\n"
            "• 滑鼠滾輪：上下捲動物種\n"
            "• Shift + 滾輪：水平平移序列位點\n"
            "• Ctrl + 滾輪：自由縮放位點與文字大小\n"
            "• 勾選「僅突顯突變」：自動將保留位點淡化為點，凸顯物種間特徵變異 SNPs。"
        )
        h_layout.addWidget(info_btn)
        layout.addWidget(header_box)

        # MSA Viewer Component
        self.msa_viewer = MSAViewer()
        layout.addWidget(self.msa_viewer, 1)

    def load_alignment(self, file_path: str | Path):
        self.msa_viewer.load_alignment_file(file_path)
