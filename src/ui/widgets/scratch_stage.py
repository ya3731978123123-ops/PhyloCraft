"""
Scratch Stage Widget (成果展示舞台)
Inspired by Scratch's upper-right interactive stage & sprites library:
- Green Flag [▶] (Run All / Start Pipeline)
- Red Octagon [■] (Stop / Cancel Workflow)
- Real-time live result display: Interactive Evolutionary Tree, MSA Matrix, or Log
- Middle Attributes Bar (matching Scratch's Sprite Info: Taxa, Sites, Model, Bootstrap)
- Bottom Artifacts Library (matching Scratch's Sprites Gallery: Tree, MSA, Trimming, Model, TimeTree)
- Export actions: High-Res Publication Image, ELN Report
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QFrame,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from src.ui.widgets.tree_canvas import TreeCanvasWidget
from src.ui.widgets.msa_viewer import MSACanvas
from src.config import OUTPUT_DIR


class ScratchStageWidget(QWidget):
    """
    Scratch-style live outcome stage with Green Flag (Run), Red Octagon (Stop),
    Attributes Inspector Bar, and Artifacts Assets Library.
    """

    run_pipeline_requested = Signal()
    stop_pipeline_requested = Signal()
    open_tree_explorer_requested = Signal()
    open_msa_explorer_requested = Signal()
    open_eln_requested = Signal()
    artifact_selected = Signal(str)  # step_key
    popout_requested = Signal()
    dock_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.is_popped_out = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # 1. Stage Header: Green Flag + Red Stop + Status Pill
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #BACCD9;
                border-radius: 4px;
                padding: 4px 6px;
            }
        """)
        hf_layout = QVBoxLayout(header_frame)
        hf_layout.setContentsMargins(6, 4, 6, 4)
        hf_layout.setSpacing(4)

        # Row 1: Green Flag + Red Stop + Status Text + Popout Window Button
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(6)

        # Green Flag Button (Scratch Run)
        self.flag_btn = QPushButton("▶")
        self.flag_btn.setFixedSize(28, 28)
        self.flag_btn.setToolTip("點擊綠旗：依據畫布上的積木堆疊順序，全自動執行生信流水線！")
        self.flag_btn.setCursor(Qt.PointingHandCursor)
        self.flag_btn.setStyleSheet("""
            QPushButton {
                background-color: #45D33A;
                color: #FFFFFF;
                font-family: 'Segoe UI Symbol', sans-serif;
                font-size: 13px;
                font-weight: bold;
                border: 2px solid #33AA2A;
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: #38BD2E;
            }
            QPushButton:disabled {
                background-color: #BACCD9;
                border-color: #94A3B8;
            }
        """)
        self.flag_btn.clicked.connect(self.run_pipeline_requested.emit)
        row1.addWidget(self.flag_btn)

        # Red Stop Button (Scratch Stop)
        self.stop_btn = QPushButton("■")
        self.stop_btn.setFixedSize(28, 28)
        self.stop_btn.setToolTip("點擊紅燈：立即中斷當前運算")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #EC5959;
                color: #FFFFFF;
                font-family: 'Segoe UI Symbol', sans-serif;
                font-size: 12px;
                font-weight: bold;
                border: 2px solid #C73B3B;
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: #D94444;
            }
            QPushButton:disabled {
                background-color: #BACCD9;
                border-color: #94A3B8;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_pipeline_requested.emit)
        row1.addWidget(self.stop_btn)

        # Status text
        self.status_label = QLabel("舞台就緒 (Stage Ready)")
        self.status_label.setStyleSheet("color: #008287; font-size: 11px; font-weight: bold;")
        row1.addWidget(self.status_label)

        row1.addStretch()

        # Pop-out / Floating window toggle button (MEGA style)
        self.popout_btn = QPushButton("🗗 獨立視窗")
        self.popout_btn.setFixedHeight(22)
        self.popout_btn.setToolTip("彈出獨立全功能成果舞台視窗 (MEGA 風格多視窗模式)")
        self.popout_btn.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F766E;
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        self.popout_btn.clicked.connect(self.on_popout_clicked)
        row1.addWidget(self.popout_btn)

        hf_layout.addLayout(row1)

        # Row 2: View Mode Switchers evenly distributed
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(4)

        view_btn_style = """
            QPushButton {
                background-color: #F8FAFC;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                font-size: 10px;
                font-weight: 600;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #008287;
            }
            QPushButton:checked {
                background-color: #008287;
                color: #FFFFFF;
                border-color: #006F73;
            }
        """

        self.view_tree_btn = QPushButton("演化樹 (Tree)")
        self.view_tree_btn.setFixedHeight(22)
        self.view_tree_btn.setCheckable(True)
        self.view_tree_btn.setChecked(True)
        self.view_tree_btn.setStyleSheet(view_btn_style)
        self.view_tree_btn.setToolTip("即時視覺化檢視系統發育演化樹成果")
        self.view_tree_btn.clicked.connect(lambda: self.switch_stage_view(0))
        row2.addWidget(self.view_tree_btn, 1)

        self.view_msa_btn = QPushButton("比對矩陣 (MSA)")
        self.view_msa_btn.setFixedHeight(22)
        self.view_msa_btn.setCheckable(True)
        self.view_msa_btn.setStyleSheet(view_btn_style)
        self.view_msa_btn.setToolTip("即時視覺化檢視多重序列對齊矩陣與突變位點")
        self.view_msa_btn.clicked.connect(lambda: self.switch_stage_view(1))
        row2.addWidget(self.view_msa_btn, 1)

        self.view_log_btn = QPushButton("終端日誌 (Log)")
        self.view_log_btn.setFixedHeight(22)
        self.view_log_btn.setCheckable(True)
        self.view_log_btn.setStyleSheet(view_btn_style)
        self.view_log_btn.setToolTip("即時查看底層生信工具終端機標準輸出日誌")
        self.view_log_btn.clicked.connect(lambda: self.switch_stage_view(2))
        row2.addWidget(self.view_log_btn, 1)

        hf_layout.addLayout(row2)

        layout.addWidget(header_frame)

        # 2. Stage Screen (White rounded canvas with border)
        stage_screen = QFrame()
        stage_screen.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 2px solid #BACCD9;
                border-radius: 6px;
            }
        """)
        ss_layout = QVBoxLayout(stage_screen)
        ss_layout.setContentsMargins(2, 2, 2, 2)

        self.stack = QStackedWidget()

        # Page 0: Tree Viewer Canvas
        self.tree_canvas = TreeCanvasWidget(compact_mode=True)
        self.stack.addWidget(self.tree_canvas)

        # Page 1: MSA Alignment Viewer Canvas
        self.msa_canvas = MSACanvas()
        self.stack.addWidget(self.msa_canvas)

        # Page 2: Live Log Terminal
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #0F172A; color: #38BDF8; font-family: Consolas, monospace; font-size: 11px;")
        self.log_text.setPlaceholderText(
            "[系統就緒]\n\n"
            "點擊綠旗 (▶) 或在積木畫布執行管線，\n"
            "MAFFT / trimAl / IQ-TREE 等底層生信工具原生標準輸出 (stdout / stderr) 將即時串流於此..."
        )
        self.stack.addWidget(self.log_text)

        ss_layout.addWidget(self.stack)
        layout.addWidget(stage_screen, 1)

        # 3. Middle Attributes Bar (matching Scratch's Sprite Info Bar)
        attr_bar = QFrame()
        attr_bar.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 2px 4px;
            }
        """)
        ab_layout = QGridLayout(attr_bar)
        ab_layout.setContentsMargins(4, 2, 4, 2)
        ab_layout.setHorizontalSpacing(4)
        ab_layout.setVerticalSpacing(2)

        self.pill_taxa = QLabel("物種 (Taxa): -")
        self.pill_taxa.setStyleSheet("background-color: #FFFFFF; border: 1px solid #BACCD9; border-radius: 3px; padding: 1px 4px; font-size: 10px; font-weight: bold; color: #0284C7;")
        ab_layout.addWidget(self.pill_taxa, 0, 0)

        self.pill_sites = QLabel("位點 (Sites): -")
        self.pill_sites.setStyleSheet("background-color: #FFFFFF; border: 1px solid #BACCD9; border-radius: 3px; padding: 1px 4px; font-size: 10px; font-weight: bold; color: #008287;")
        ab_layout.addWidget(self.pill_sites, 0, 1)

        self.pill_model = QLabel("最適模型 (Model): -")
        self.pill_model.setStyleSheet("background-color: #FFFFFF; border: 1px solid #BACCD9; border-radius: 3px; padding: 1px 4px; font-size: 10px; font-weight: bold; color: #7C3AED;")
        ab_layout.addWidget(self.pill_model, 1, 0)

        self.pill_boot = QLabel("拔靴檢驗 (Boot): -")
        self.pill_boot.setStyleSheet("background-color: #FFFFFF; border: 1px solid #BACCD9; border-radius: 3px; padding: 1px 4px; font-size: 10px; font-weight: bold; color: #059669;")
        ab_layout.addWidget(self.pill_boot, 1, 1)

        layout.addWidget(attr_bar)

        # 4. Bottom Artifacts / Assets Library (Collapsible to preserve ample Stage Screen space)
        self.lib_box = QFrame()
        self.lib_box.setVisible(False)
        self.lib_box.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
            }
        """)
        lb_vbox = QVBoxLayout(self.lib_box)
        lb_vbox.setContentsMargins(6, 4, 6, 4)
        lb_vbox.setSpacing(4)

        lb_title = QLabel("<b>分析成果捷徑庫 (Artifacts Gallery):</b>")
        lb_title.setStyleSheet("color: #475569; font-size: 10px;")
        lb_vbox.addWidget(lb_title)

        grid_artifacts = QGridLayout()
        grid_artifacts.setContentsMargins(0, 0, 0, 0)
        grid_artifacts.setHorizontalSpacing(4)
        grid_artifacts.setVerticalSpacing(4)

        self.art_buttons: dict[str, QPushButton] = {}
        artifacts = [
            ("raw", "原始序列", "#0284C7"),
            ("alignment", "多重比對", "#008287"),
            ("trimming", "修剪矩陣", "#D97706"),
            ("modelfinder", "模型報告", "#7C3AED"),
            ("tree", "系統發育樹", "#059669"),
            ("timetree", "分子時間樹", "#DC2626"),
        ]
        for i, (key, name, color) in enumerate(artifacts):
            r = i // 3
            c = i % 3
            btn = QPushButton(name)
            btn.setFixedHeight(22)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #F8FAFC;
                    color: {color};
                    border: 1px solid #CBD5E1;
                    border-radius: 3px;
                    padding: 1px 4px;
                    font-size: 10px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {color};
                    color: #FFFFFF;
                }}
            """)
            btn.clicked.connect(lambda checked=False, k=key: self.artifact_selected.emit(k))
            self.art_buttons[key] = btn
            grid_artifacts.addWidget(btn, r, c)

        lb_vbox.addLayout(grid_artifacts)
        layout.addWidget(self.lib_box)

        # 5. Stage Bottom Actions
        bot_layout = QGridLayout()
        bot_layout.setContentsMargins(0, 0, 0, 0)
        bot_layout.setHorizontalSpacing(4)
        bot_layout.setVerticalSpacing(3)

        export_img_btn = QPushButton("導出插圖 (300 DPI)...")
        export_img_btn.setFixedHeight(25)
        export_img_btn.setToolTip("導出當前演化樹或矩陣為高解析度論文發表級插圖 (PNG/PDF)")
        export_img_btn.clicked.connect(self.export_stage_image)
        bot_layout.addWidget(export_img_btn, 0, 0)

        open_explorer_btn = QPushButton("全功能檢視器 ↗")
        open_explorer_btn.setFixedHeight(25)
        open_explorer_btn.setToolTip("切換至對應分頁使用完整的樹編輯與比對編輯器")
        open_explorer_btn.clicked.connect(self.open_explorer_dispatch)
        bot_layout.addWidget(open_explorer_btn, 0, 1)

        self.btn_toggle_lib = QPushButton("📦 成果捷徑庫 (6) ▾")
        self.btn_toggle_lib.setFixedHeight(23)
        self.btn_toggle_lib.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F766E;
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        self.btn_toggle_lib.setToolTip("展開或收合成畫成果捷徑按鈕")
        self.btn_toggle_lib.clicked.connect(self.toggle_lib_box)
        bot_layout.addWidget(self.btn_toggle_lib, 1, 0)

        eln_btn = QPushButton("導出 ELN 紀錄")
        eln_btn.setFixedHeight(23)
        eln_btn.setStyleSheet("color: #008287; font-weight: bold; font-size: 10px;")
        eln_btn.setToolTip("編譯論文 Supplementary Material 電子實驗紀錄簿")
        eln_btn.clicked.connect(self.open_eln_requested.emit)
        bot_layout.addWidget(eln_btn, 1, 1)

        layout.addLayout(bot_layout)

    def update_attributes(self, taxa: int | str = "-", sites: int | str = "-", model: str = "-", boot: int | str = "-"):
        self.pill_taxa.setText(f"物種 (Taxa): {taxa}")
        self.pill_sites.setText(f"位點 (Sites): {sites}" + (" bp" if str(sites).isdigit() else ""))
        self.pill_model.setText(f"最適模型 (Model): {model}")
        self.pill_boot.setText(f"拔靴檢驗 (Boot): {boot}")

    def switch_stage_view(self, index: int):
        self.stack.setCurrentIndex(index)
        self.view_tree_btn.setChecked(index == 0)
        self.view_msa_btn.setChecked(index == 1)
        self.view_log_btn.setChecked(index == 2)

    def toggle_lib_box(self):
        vis = self.lib_box.isVisible()
        self.lib_box.setVisible(not vis)
        self.btn_toggle_lib.setText("📦 成果捷徑庫 (6) ▾" if vis else "📦 成果捷徑庫 (6) ▴")

    def open_explorer_dispatch(self):
        curr = self.stack.currentIndex()
        if curr == 0:
            self.open_tree_explorer_requested.emit()
        elif curr == 1:
            self.open_msa_explorer_requested.emit()
        else:
            self.open_tree_explorer_requested.emit()

    def set_running_state(self, running: bool, status_text: str = ""):
        self.flag_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        if running:
            self.status_label.setText(status_text or "積木流水線運算中...")
            self.status_label.setStyleSheet("color: #B45309; font-size: 12px; font-weight: bold;")
            self.switch_stage_view(2)  # Automatically show live log during run
        else:
            self.status_label.setText(status_text or "分析完成！成果已呈現在舞台。")
            self.status_label.setStyleSheet("color: #15803D; font-size: 12px; font-weight: bold;")
            self.switch_stage_view(0)  # Show tree upon completion

    def load_tree_file(self, tree_path: str | Path):
        p = Path(tree_path)
        if p.exists():
            try:
                self.tree_canvas.load_tree_file(p, show_alert=False)
                self.switch_stage_view(0)
            except Exception:
                pass

    def load_msa_file(self, msa_path: str | Path):
        p = Path(msa_path)
        if p.exists():
            try:
                from Bio import SeqIO
                records = list(SeqIO.parse(str(p), "fasta"))
                if records:
                    self.msa_canvas.load_records(records)
                    self.switch_stage_view(1)
            except Exception:
                pass

    def append_log(self, text: str):
        self.log_text.append(text)

    def export_stage_image(self):
        fp, _ = QFileDialog.getSaveFileName(
            self, "導出舞台成果圖片", str(OUTPUT_DIR / "publication_result.png"), "PNG Image (*.png);;PDF Document (*.pdf)"
        )
        if fp:
            if self.stack.currentIndex() == 0 and self.tree_canvas.tree:
                self.tree_canvas.export_image(fp, dpi=300, show_alert=False)
                QMessageBox.information(self, "導出成功", f"演化樹圖片已順利儲存至:\n{fp}")
            elif self.stack.currentIndex() == 1 and self.msa_canvas.taxa:
                pix = self.msa_canvas.grab()
                pix.save(fp)
                QMessageBox.information(self, "導出成功", f"比對矩陣圖片已順利儲存至:\n{fp}")
            else:
                QMessageBox.information(self, "提示", "目前舞台尚未有可導出之演化樹或比對矩陣成果。")

    def on_popout_clicked(self):
        if self.is_popped_out:
            self.dock_requested.emit()
        else:
            self.popout_requested.emit()

    def set_popped_out_state(self, popped: bool):
        self.is_popped_out = popped
        if popped:
            self.popout_btn.setText("🗖 嵌入主視窗")
            self.popout_btn.setToolTip("將獨立舞台視窗重新嵌入回主工作台")
        else:
            self.popout_btn.setText("🗗 獨立視窗")
            self.popout_btn.setToolTip("彈出獨立全功能成果舞台視窗 (MEGA 風格多視窗模式)")
