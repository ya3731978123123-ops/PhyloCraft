from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
)
from src.ui.widgets.tree_canvas import TreeCanvasWidget


class TreeViewerTab(QWidget):
    """
    Interactive Tree Explorer & Publication Visualizer Tab
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # File Setup Bar (Compact single line)
        f_layout = QHBoxLayout()
        f_layout.setContentsMargins(0, 0, 0, 0)
        f_layout.setSpacing(8)

        lbl = QLabel("演化樹檔案:")
        lbl.setStyleSheet("font-weight: bold; color: #006644;")
        f_layout.addWidget(lbl)

        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("請選取或拖曳 .treefile, .nwk, 或 .tree 檔案至此...")
        self.file_edit.setFixedHeight(30)
        f_layout.addWidget(self.file_edit, 1)

        browse_btn = QPushButton("瀏覽 (Browse)...")
        browse_btn.setFixedHeight(30)
        browse_btn.clicked.connect(self.browse_tree_file)
        f_layout.addWidget(browse_btn)

        reload_btn = QPushButton("重新載入")
        reload_btn.setFixedHeight(30)
        reload_btn.clicked.connect(self.reload_current)
        f_layout.addWidget(reload_btn)

        layout.addLayout(f_layout)

        # Tree Canvas
        self.canvas_widget = TreeCanvasWidget()
        layout.addWidget(self.canvas_widget, 1)

    def browse_tree_file(self):
        fp, _ = QFileDialog.getOpenFileName(
            self,
            "Select Newick Tree File",
            "",
            "Tree Files (*.treefile *.nwk *.tree *.newick);;All Files (*)",
        )
        if fp:
            self.load_tree(fp)

    def load_tree(self, tree_path: str | Path):
        p = Path(tree_path)
        if p.exists():
            self.file_edit.setText(str(p))
            self.canvas_widget.load_tree_file(p)

    def reload_current(self):
        fp = self.file_edit.text().strip()
        if fp:
            self.load_tree(fp)
