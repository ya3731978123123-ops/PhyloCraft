"""
Scratch Puzzle Blocks Component (卡榫式生信積木模塊)
Authentic Scratch-style interlocking jigsaw blocks for bioinformatics workflows:
- Puzzle notch on top, puzzle tab on bottom for physical interlocking
- Hat block shape for 'When Green Flag Clicked' (事件旗子積木)
- Distinct Scratch category colors
- Inline capsule dropdowns, inputs, and toggle controls
- Active running glow effect (#FFE66D)
- 100% compatible with existing test suite and ProjectManager
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QFrame,
    QTextEdit,
    QFileDialog,
    QProgressBar,
    QScrollArea,
    QAbstractScrollArea,
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import (
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QBrush,
    QFont,
)

from src.core.project_manager import STEP_KEYS, STEP_TITLES, StepRecord
from src.config import OUTPUT_DIR, DATA_DIR


# Authentic Scratch Category Colors
BLOCK_THEMES = {
    "event": {
        "bg": QColor("#FFAB19"),       # Scratch Event Yellow-Amber
        "border": QColor("#CF8B17"),
        "text": "#FFFFFF",
        "category": "事件 (Events)",
    },
    "raw": {
        "bg": QColor("#4C97FF"),       # Scratch Blue
        "border": QColor("#3373CC"),
        "text": "#FFFFFF",
        "category": "序列輸入 (Input)",
    },
    "sanitize": {
        "bg": QColor("#5973E8"),       # Scratch Indigo
        "border": QColor("#4158BA"),
        "text": "#FFFFFF",
        "category": "品質管理 (QC)",
    },
    "alignment": {
        "bg": QColor("#0FBD8C"),       # Scratch Teal
        "border": QColor("#0B8E69"),
        "text": "#FFFFFF",
        "category": "多重比對 (Align)",
    },
    "trimming": {
        "bg": QColor("#FF8C1A"),       # Scratch Orange
        "border": QColor("#DB6E00"),
        "text": "#FFFFFF",
        "category": "位點修剪 (Trim)",
    },
    "modelfinder": {
        "bg": QColor("#9966FF"),       # Scratch Purple
        "border": QColor("#774DCB"),
        "text": "#FFFFFF",
        "category": "演化模型 (Model)",
    },
    "tree": {
        "bg": QColor("#59C059"),       # Scratch Green
        "border": QColor("#389438"),
        "text": "#FFFFFF",
        "category": "系統建樹 (Tree)",
    },
    "tree_fasttree": {
        "bg": QColor("#10B981"),       # Scratch Emerald Green
        "border": QColor("#047857"),
        "text": "#FFFFFF",
        "category": "極速建樹 (FastTree)",
    },
    "alignment_muscle": {
        "bg": QColor("#0284C7"),       # Scratch Cyan/Sky
        "border": QColor("#0369A1"),
        "text": "#FFFFFF",
        "category": "結構比對 (MUSCLE)",
    },
    "timetree": {
        "bg": QColor("#FF6680"),       # Scratch Strawberry Red
        "border": QColor("#D9405C"),
        "text": "#FFFFFF",
        "category": "分子定年 (Clock)",
    },
    "stage": {
        "bg": QColor("#4CBFE6"),       # Scratch Cyan
        "border": QColor("#2B92B5"),
        "text": "#FFFFFF",
        "category": "舞台輸出 (Stage)",
    },
}

STEP_TITLES_EXTENDED = {
    **STEP_TITLES,
    "tree_fasttree": ("FastTree 2 (超極速系統建樹)", "06_fasttree"),
    "alignment_muscle": ("MUSCLE (結構感知多重序列比對)", "03_alignment_muscle"),
}


class ScratchHatBlock(QWidget):
    """
    Scratch Event Hat Block: '當 點擊綠旗 (When Green Flag Clicked)'.
    Features smooth curved hat top and puzzle tab on bottom.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self.setFixedHeight(46)
        self.setMinimumWidth(320)
        self.theme = BLOCK_THEMES["event"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 12, 6)
        layout.setSpacing(8)

        # Flag icon
        flag_lbl = QLabel("▶")
        flag_lbl.setStyleSheet("background: transparent; color: #45D33A; font-size: 16px; font-weight: bold;")
        layout.addWidget(flag_lbl)

        title_lbl = QLabel("當 點擊綠旗 ▶ 時 依序執行生信工作流")
        title_lbl.setStyleSheet("background: transparent; color: #FFFFFF; font-size: 12px; font-weight: bold; letter-spacing: 0.5px;")
        layout.addWidget(title_lbl)

        layout.addStretch()

        self.downstream_block = None
        self.upstream_block = None
        self.canvas = None
        self.is_dragging = False
        self.drag_start_pos = None
        self.block_start_pos = None
        self.has_moved = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint()
            self.block_start_pos = self.pos()
            self.is_dragging = True
            self.has_moved = False
            self.raise_()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            delta = event.globalPosition().toPoint() - self.drag_start_pos
            if delta.manhattanLength() > 3:
                self.has_moved = True
            new_pos = self.block_start_pos + delta
            if self.parentWidget():
                new_x = max(10, min(self.parentWidget().width() - self.width() - 10, new_pos.x()))
                new_y = max(10, min(self.parentWidget().height() - self.height() - 10, new_pos.y()))
            else:
                new_x = max(10, new_pos.x())
                new_y = max(10, new_pos.y())
            dx = new_x - self.x()
            dy = new_y - self.y()
            self.move(new_x, new_y)
            curr = self.downstream_block
            visited = {id(self)}
            while curr and id(curr) not in visited:
                visited.add(id(curr))
                curr.raise_()
                curr.move(curr.x() + dx, curr.y() + dy)
                curr = getattr(curr, "downstream_block", None)
            if self.canvas and hasattr(self.canvas, "update_container_bounds"):
                self.canvas.update_container_bounds()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_dragging and event.button() == Qt.LeftButton:
            self.is_dragging = False
            if not self.has_moved:
                self.clicked.emit()
            elif self.canvas and hasattr(self.canvas, "check_block_snap"):
                self.canvas.check_block_snap(self)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width() - 2)
        h = float(self.height() - 6)

        path = QPainterPath()
        # Hat arc top
        path.moveTo(2, 14)
        path.quadTo(35, -4, 75, 2)
        path.lineTo(w - 4, 2)
        path.quadTo(w, 2, w, 6)
        # Right edge
        path.lineTo(w, h - 4)
        path.quadTo(w, h, w - 4, h)
        # Bottom edge with tab
        path.lineTo(38, h)
        path.lineTo(34, h + 5)
        path.lineTo(20, h + 5)
        path.lineTo(16, h)
        path.lineTo(6, h)
        path.quadTo(2, h, 2, h - 4)
        path.closeSubpath()

        # Fill & Border
        painter.setBrush(QBrush(self.theme["bg"]))
        painter.setPen(QPen(self.theme["border"], 2))
        painter.drawPath(path)


class ScratchPuzzleBlock(QWidget):
    """
    Scratch Interlocking Command Block.
    Physical puzzle notch on top, puzzle tab on bottom.
    Embeds capsule inputs, enable checkbox, and run button.
    Maintains 100% API compatibility with previous StepBlockCard.
    """

    run_single_requested = Signal(str)   # step_key
    inspect_requested = Signal(str)      # step_key
    jump_tab_requested = Signal(str)    # step_key
    fork_requested = Signal(str)        # step_key
    note_changed = Signal(str, str)     # step_key, new_text
    enabled_changed = Signal(str, bool) # step_key, enabled
    open_preferences_requested = Signal(str) # step_key
    delete_requested = Signal(object)   # self

    def __init__(
        self,
        step_key: str,
        parent: QWidget | None = None,
        instance_id: str | None = None,
        custom_title: str | None = None,
    ):
        super().__init__(parent)
        self.step_key = step_key
        self.instance_id = instance_id or step_key
        title_info = STEP_TITLES_EXTENDED.get(step_key, STEP_TITLES.get(step_key, (step_key, "")))
        self.title, self.subfolder = title_info
        if custom_title:
            self.title = custom_title
        self.theme = BLOCK_THEMES.get(step_key, BLOCK_THEMES.get(step_key.split("_")[0], BLOCK_THEMES["raw"]))
        self.current_record = StepRecord()
        self.notes_expanded = False
        self.params_expanded = False
        self.is_running = False
        self.upstream_block = None
        self.downstream_block = None
        self.downstream_blocks = []  # For parallel branching
        self.canvas = None
        self.is_dragging = False
        self.param_widgets = {}

        self.setMinimumWidth(500)
        self.init_ui()

    def init_ui(self):
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 8, 14, 10)
        main_layout.setSpacing(5)

        # 1. Block Header Row (Checkbox + Module ID + Title + Run + Prefs + Status + Delete)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        # Enable checkbox
        self.enable_cb = QCheckBox()
        self.enable_cb.setChecked(True)
        self.enable_cb.setToolTip("啟用或跳過此積木模塊")
        self.enable_cb.setStyleSheet("""
            QCheckBox {
                background: transparent;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                background-color: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.3);
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #008287;
                image: none;
            }
        """)
        self.enable_cb.toggled.connect(self.on_enable_toggled)
        header_row.addWidget(self.enable_cb)

        # Module Tag (e.g. 模塊 01)
        step_num_map = {
            "raw": "01",
            "sanitize": "02",
            "alignment": "03",
            "alignment_muscle": "03B",
            "trimming": "04",
            "modelfinder": "05",
            "tree": "06",
            "tree_fasttree": "06B",
            "timetree": "07",
        }
        tag_text = step_num_map.get(self.step_key, self.instance_id[:4].upper())
        self.stage_pill = QLabel(f"模塊 {tag_text}")
        self.stage_pill.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.25);
            color: #FFFFFF;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
        """)
        header_row.addWidget(self.stage_pill)

        # Title Label
        short_title = self.title.split("(")[0].strip()
        self.title_label = QLabel(short_title)
        self.title_label.setStyleSheet("background: transparent; color: #FFFFFF; font-size: 12px; font-weight: bold;")
        header_row.addWidget(self.title_label)

        header_row.addStretch()

        # Run Single Step Button
        self.run_btn = QPushButton("▶ 執行此步")
        self.run_btn.setFixedHeight(24)
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #1E293B;
                border: 1px solid rgba(0, 0, 0, 0.25);
                border-radius: 12px;
                padding: 1px 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                color: #008287;
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.4);
                color: #64748B;
            }
        """)
        self.run_btn.setToolTip("獨立執行此積木模塊")
        self.run_btn.clicked.connect(lambda: self.run_single_requested.emit(self.step_key))
        header_row.addWidget(self.run_btn)

        # Settings Gear / MEGA Preferences Button
        self.pref_btn = QPushButton("偏好設定...")
        self.pref_btn.setFixedHeight(24)
        self.pref_btn.setCursor(Qt.PointingHandCursor)
        self.pref_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.22);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.45);
                border-radius: 12px;
                padding: 1px 9px;
                font-size: 10px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #FFFFFF;
                color: #1E293B;
            }
        """)
        self.pref_btn.setToolTip("開啟 MEGA 12 經典點後表單 (Analysis Preferences)")
        self.pref_btn.clicked.connect(lambda: self.open_preferences_requested.emit(self.step_key))
        header_row.addWidget(self.pref_btn)

        # Status Badge Pill
        self.status_badge = QLabel("待執行")
        self.status_badge.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.25);
            color: #FFFFFF;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 7px;
            border-radius: 9px;
        """)
        header_row.addWidget(self.status_badge)

        # Delete Block Button (✕)
        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedSize(20, 20)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setToolTip("自工作流畫布中移除此積木模塊")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.22);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.35);
                border-radius: 10px;
                font-size: 11px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #EF4444;
                border-color: #DC2626;
                color: #FFFFFF;
            }
        """)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        header_row.addWidget(self.delete_btn)

        main_layout.addLayout(header_row)

        # 2. Inline Capsule Inputs Row (On its own dedicated row - ample space, never squished!)
        capsule_row = QHBoxLayout()
        capsule_row.setContentsMargins(0, 2, 0, 2)
        capsule_row.setSpacing(6)
        self.build_capsule_controls(capsule_row)
        capsule_row.addStretch()
        main_layout.addLayout(capsule_row)

        # 3. Result Summary Strip (Interactive & Clickable to Inspect)
        self.summary_chip = QLabel("尚未執行此步驟 ── 點此檢視詳情")
        self.summary_chip.setObjectName("summary_chip")
        self.summary_chip.setCursor(Qt.PointingHandCursor)
        self.summary_chip.setToolTip("點擊以在下方數據探針中檢視此步驟之產出資料與矩陣")
        self.summary_chip.setStyleSheet("""
            QLabel#summary_chip {
                color: #FFFFFF;
                font-size: 11px;
                background-color: rgba(0, 0, 0, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 4px;
                padding: 4px 8px;
                margin-top: 1px;
            }
            QLabel#summary_chip:hover {
                background-color: rgba(0, 0, 0, 0.35);
                border-color: rgba(255, 255, 255, 0.5);
            }
        """)
        self.summary_chip.setWordWrap(True)
        main_layout.addWidget(self.summary_chip)

        # Hidden but test-compatible widgets
        self.cmd_chip = QLabel("")
        self.cmd_chip.setVisible(False)
        main_layout.addWidget(self.cmd_chip)

        self.mini_progress = QProgressBar()
        self.mini_progress.setFixedHeight(3)
        self.mini_progress.setTextVisible(False)
        self.mini_progress.setVisible(False)
        main_layout.addWidget(self.mini_progress)

        # 4. Quick Action Buttons Row (Clear 24px buttons with hand cursor)
        sub_row = QHBoxLayout()
        sub_row.setContentsMargins(0, 2, 0, 0)
        sub_row.setSpacing(5)

        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.22);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.38);
                border-radius: 4px;
                font-size: 10px;
                font-weight: 500;
                padding: 2px 7px;
            }
            QPushButton:hover {
                background-color: #FFFFFF;
                color: #0F172A;
            }
        """

        self.inspect_btn = QPushButton("🔍 成果探針")
        self.inspect_btn.setFixedHeight(24)
        self.inspect_btn.setCursor(Qt.PointingHandCursor)
        self.inspect_btn.setToolTip("在下方數據探針中即時預覽此步驟之產出資料與矩陣")
        self.inspect_btn.setStyleSheet(btn_style)
        self.inspect_btn.clicked.connect(lambda: self.inspect_requested.emit(self.step_key))
        sub_row.addWidget(self.inspect_btn)

        self.params_btn = QPushButton("⚙️ 參數抽屜")
        self.params_btn.setFixedHeight(24)
        self.params_btn.setCursor(Qt.PointingHandCursor)
        self.params_btn.setToolTip("展開或收合此模塊的詳細參數設定抽屜")
        self.params_btn.setStyleSheet(btn_style)
        self.params_btn.clicked.connect(self.toggle_params)
        sub_row.addWidget(self.params_btn)

        self.note_toggle_btn = QPushButton("📝 筆記 (0)")
        self.note_toggle_btn.setFixedHeight(24)
        self.note_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.note_toggle_btn.setToolTip("展開此步驟專屬之實驗筆記備忘錄，撰寫觀察心得與假設")
        self.note_toggle_btn.setStyleSheet(btn_style)
        self.note_toggle_btn.clicked.connect(self.toggle_notes)
        sub_row.addWidget(self.note_toggle_btn)

        self.fork_btn = QPushButton("🌿 分支實驗")
        self.fork_btn.setFixedHeight(24)
        self.fork_btn.setCursor(Qt.PointingHandCursor)
        self.fork_btn.setToolTip("以此步驟成果為起點，建立新的平行對照研究專案")
        self.fork_btn.setStyleSheet(btn_style)
        self.fork_btn.clicked.connect(lambda: self.fork_requested.emit(self.step_key))
        sub_row.addWidget(self.fork_btn)

        self.jump_btn = QPushButton("↗ 專屬分頁")
        self.jump_btn.setFixedHeight(24)
        self.jump_btn.setCursor(Qt.PointingHandCursor)
        self.jump_btn.setToolTip("跳轉至此分析步驟對應之全功能獨立視圖分頁")
        self.jump_btn.setStyleSheet(btn_style)
        self.jump_btn.clicked.connect(lambda: self.jump_tab_requested.emit(self.step_key))
        sub_row.addWidget(self.jump_btn)

        sub_row.addStretch()
        main_layout.addLayout(sub_row)

        # Inline Parameter Drawer (Collapsible)
        self.params_drawer = QFrame()
        self.params_drawer.setVisible(False)
        self.params_drawer.setStyleSheet("background-color: #FFFFFF; border: 1px solid #BACCD9; border-radius: 4px; padding: 6px;")
        self.build_params_drawer()
        main_layout.addWidget(self.params_drawer)

        # Student Note Drawer (Collapsible)
        self.note_drawer = QFrame()
        self.note_drawer.setVisible(False)
        self.note_drawer.setStyleSheet("background-color: #FFFFFF; border: 1px solid #BACCD9; border-radius: 4px; padding: 4px;")
        nd_layout = QVBoxLayout(self.note_drawer)
        nd_layout.setContentsMargins(4, 4, 4, 4)
        nd_layout.setSpacing(2)
        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("請在此輸入此步驟的實驗觀察心得、參數選擇理由或論文筆記...")
        self.note_edit.setMaximumHeight(60)
        self.note_edit.setStyleSheet("font-size: 11px; color: #1E293B; background-color: #F8FAFC;")
        self.note_edit.textChanged.connect(self.on_note_text_changed)
        nd_layout.addWidget(self.note_edit)
        main_layout.addWidget(self.note_drawer)

    def build_capsule_controls(self, layout: QHBoxLayout):
        capsule_combo_style = """
            QComboBox {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid rgba(0, 0, 0, 0.25);
                border-radius: 11px;
                padding: 2px 22px 2px 8px;
                font-size: 11px;
                font-weight: 500;
                min-height: 22px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border-left: none;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #475569;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #0F172A;
                selection-background-color: #008287;
                selection-color: #FFFFFF;
                border: 1px solid #CBD5E1;
            }
        """

        capsule_spin_style = """
            QSpinBox, QDoubleSpinBox {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid rgba(0, 0, 0, 0.25);
                border-radius: 11px;
                padding: 2px 18px 2px 8px;
                font-size: 11px;
                font-weight: 500;
                min-height: 22px;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #E2E8F0;
                border-top-right-radius: 11px;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid #E2E8F0;
                border-bottom-right-radius: 11px;
            }
        """

        def inline_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("background: transparent; color: #FFFFFF; font-size: 11px; font-weight: bold; border: none; padding: 0;")
            return lbl

        if self.step_key == "raw":
            layout.addWidget(inline_label("序列檔案:"))
            btn = QPushButton("選取 FASTA 序列檔案...")
            btn.setFixedHeight(24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #0284C7;
                    border: 1px solid rgba(0,0,0,0.25);
                    border-radius: 12px;
                    padding: 2px 12px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #F0F9FF;
                }
            """)
            btn.setToolTip("選取原始定序 FASTA 檔案 (*.fasta, *.fa, *.fas)")
            btn.clicked.connect(self.browse_raw)
            layout.addWidget(btn)

        elif self.step_key == "sanitize":
            layout.addWidget(inline_label("品管規則:"))
            qc_badge = QLabel("IUPAC 規格防呆驗證")
            qc_badge.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.25);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.45);
                border-radius: 11px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            """)
            qc_badge.setToolTip("自動清洗 NCBI 標頭特殊字元、過短殘缺序列並保障 Taxon 命名唯一性")
            layout.addWidget(qc_badge)

        elif self.step_key == "alignment":
            layout.addWidget(inline_label("演算法:"))
            algo = QComboBox()
            algo.setStyleSheet(capsule_combo_style)
            algo.addItems(["auto (智慧推薦)", "localpair (高精度 L-INS-i)", "globalpair (全域 G-INS-i)", "fftns2 (極速 FFT-NS-2)"])
            algo.setToolTip("MAFFT 多重序列對齊演算法")
            layout.addWidget(algo)
            self.param_widgets["strategy"] = algo

        elif self.step_key == "trimming":
            layout.addWidget(inline_label("修剪策略:"))
            method = QComboBox()
            method.setStyleSheet(capsule_combo_style)
            method.addItems(["automated1 (智慧啟發式)", "gappyout (保守移除空位)", "strict (高嚴格度過濾)"])
            method.setToolTip("trimAl 系統發育位點保守修剪策略")
            layout.addWidget(method)
            self.param_widgets["method"] = method

        elif self.step_key == "modelfinder":
            layout.addWidget(inline_label("評選標準:"))
            crit = QComboBox()
            crit.setStyleSheet(capsule_combo_style)
            crit.addItems(["BIC (貝氏推薦最佳)", "AIC (赤池標準)", "AICc (小樣本校正)"])
            crit.setToolTip("ModelFinder 替代演化模型評選統計準則")
            layout.addWidget(crit)
            self.param_widgets["criterion"] = crit

        elif self.step_key == "tree":
            layout.addWidget(inline_label("替代模型:"))
            m_combo = QComboBox()
            m_combo.setStyleSheet(capsule_combo_style)
            m_combo.addItems(["MFP (自動模型最佳化)", "GTR+I+G4", "LG+G4", "Q.PLANT+I+G4"])
            m_combo.setToolTip("IQ-TREE 2 系統發育演化模型")
            layout.addWidget(m_combo)
            self.param_widgets["model"] = m_combo

            layout.addWidget(inline_label("拔靴自展:"))
            boot_spin = QSpinBox()
            boot_spin.setStyleSheet(capsule_spin_style)
            boot_spin.setRange(100, 10000)
            boot_spin.setValue(1000)
            boot_spin.setSuffix(" 次")
            boot_spin.setToolTip("UFBoot 超快速拔靴分支支撐率檢驗次數")
            layout.addWidget(boot_spin)
            self.param_widgets["bootstrap"] = boot_spin

        elif self.step_key == "tree_fasttree":
            layout.addWidget(inline_label("模型:"))
            ft_m = QComboBox()
            ft_m.setStyleSheet(capsule_combo_style)
            ft_m.addItems(["-nt (核酸自動 GTR+CAT)", "-gtr -nt (GTR 全參模式)", "Jukes-Cantor (極速)", "LG (蛋白質標準)", "WAG (蛋白質)"])
            ft_m.setToolTip("FastTree 2 近似最大似然演化模型")
            layout.addWidget(ft_m)
            self.param_widgets["model"] = ft_m

            layout.addWidget(inline_label("加速:"))
            speed = QComboBox()
            speed.setStyleSheet(capsule_combo_style)
            speed.addItems(["標準 (Standard)", "極速 (-fastest)"])
            layout.addWidget(speed)
            self.param_widgets["speed"] = speed

        elif self.step_key == "alignment_muscle":
            layout.addWidget(inline_label("模式:"))
            m_mode = QComboBox()
            m_mode.setStyleSheet(capsule_combo_style)
            m_mode.addItems(["Super5 (超高精準結構感知)", "PPP (漸進式高速比對)"])
            layout.addWidget(m_mode)
            self.param_widgets["mode"] = m_mode

        elif self.step_key == "timetree":
            layout.addWidget(inline_label("校準檔:"))
            btn_calib = QPushButton("選取年代校準檔...")
            btn_calib.setFixedHeight(24)
            btn_calib.setCursor(Qt.PointingHandCursor)
            btn_calib.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #D9405C;
                    border: 1px solid rgba(0, 0, 0, 0.25);
                    border-radius: 12px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #FFF1F2;
                }
            """)
            btn_calib.clicked.connect(self.browse_date_file)
            layout.addWidget(btn_calib)

            layout.addWidget(inline_label("離群標準差:"))
            out_spin = QDoubleSpinBox()
            out_spin.setStyleSheet(capsule_spin_style)
            out_spin.setRange(0.0, 10.0)
            out_spin.setValue(3.0)
            out_spin.setSuffix(" σ")
            out_spin.setToolTip("LSD2 最小平方法分子鐘離群檢驗標準差")
            layout.addWidget(out_spin)
            self.param_widgets["outlier"] = out_spin

    def browse_raw(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "選取輸入序列檔案 (FASTA 格式)", str(OUTPUT_DIR), "FASTA 序列檔案 (*.fasta *.fa *.fas *.fna);;所有檔案 (*)"
        )
        if fp:
            if "fasta_path" in self.param_widgets:
                self.param_widgets["fasta_path"].setText(fp)
            self.summary_chip.setText(f"已指定序列檔案: {Path(fp).name}")

    def browse_date_file(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "選取年代校準標籤檔案", str(OUTPUT_DIR), "校準日期檔 (*.txt *.date);;所有檔案 (*)"
        )
        if fp:
            if "date_file" in self.param_widgets:
                self.param_widgets["date_file"].setText(fp)
            self.summary_chip.setText(f"已指定年代校準檔: {Path(fp).name}")

    def build_params_drawer(self):
        pd_layout = QVBoxLayout(self.params_drawer)
        pd_layout.setContentsMargins(8, 8, 8, 8)
        pd_layout.setSpacing(6)

        header_lbl = QLabel(f"<b>{self.title} — 詳細設定抽屜:</b>")
        header_lbl.setStyleSheet("color: #008287; font-size: 11px;")
        pd_layout.addWidget(header_lbl)

        if self.step_key == "raw":
            pd_layout.addWidget(QLabel("原始序列輸入路徑 (FASTA 格式):"))
            f_row = QHBoxLayout()
            edit = QLineEdit()
            edit.setPlaceholderText("請選取或輸入 FASTA 序列檔案完整路徑 (*.fasta, *.fa)...")
            edit.setStyleSheet("font-size: 11px; background-color: #F8FAFC;")
            self.param_widgets["fasta_path"] = edit
            f_row.addWidget(edit, 1)

            btn_browse = QPushButton("瀏覽檔案...")
            btn_browse.setFixedHeight(24)
            btn_browse.setStyleSheet("padding: 2px 8px; font-size: 11px;")
            btn_browse.clicked.connect(self.browse_raw)
            f_row.addWidget(btn_browse)
            pd_layout.addLayout(f_row)

        elif self.step_key == "sanitize":
            cb_nc = QCheckBox("過濾 NCBI 標頭特殊字元 (將空白、管線號、斜線等轉換為標準底線)")
            cb_nc.setChecked(True)
            cb_len = QCheckBox("排除過短殘缺序列 (過濾長度小於 30 bp 之短片段)")
            cb_len.setChecked(True)
            cb_uniq = QCheckBox("嚴格保障 Taxon 命名唯一性 (防止同名序列衝突)")
            cb_uniq.setChecked(True)
            pd_layout.addWidget(cb_nc)
            pd_layout.addWidget(cb_len)
            pd_layout.addWidget(cb_uniq)
            self.param_widgets["clean_headers"] = cb_nc
            self.param_widgets["filter_short"] = cb_len
            self.param_widgets["unique_names"] = cb_uniq

        elif self.step_key == "alignment":
            row_th = QHBoxLayout()
            row_th.addWidget(QLabel("平行運算 CPU 核心數 (Threads):"))
            th_combo = QComboBox()
            th_combo.addItems(["AUTO (自動偵測最佳線程)", "1 (單核心)", "2", "4", "8", "16"])
            self.param_widgets["threads"] = th_combo
            row_th.addWidget(th_combo)
            pd_layout.addLayout(row_th)

            row_gap = QHBoxLayout()
            row_gap.addWidget(QLabel("間隙開啟罰分 (Gap Opening Penalty):"))
            gap_spin = QDoubleSpinBox()
            gap_spin.setRange(0.0, 5.0)
            gap_spin.setValue(1.53)
            gap_spin.setSingleStep(0.1)
            self.param_widgets["op"] = gap_spin
            row_gap.addWidget(gap_spin)
            pd_layout.addLayout(row_gap)

        elif self.step_key == "trimming":
            row_gt = QHBoxLayout()
            row_gt.addWidget(QLabel("位點保留最低覆蓋率 (Gap Threshold -gt):"))
            gt_spin = QDoubleSpinBox()
            gt_spin.setRange(0.0, 1.0)
            gt_spin.setValue(0.80)
            gt_spin.setSingleStep(0.05)
            self.param_widgets["gt"] = gt_spin
            row_gt.addWidget(gt_spin)
            pd_layout.addLayout(row_gt)

            row_st = QHBoxLayout()
            row_st.addWidget(QLabel("同源保守相似度閾值 (Similarity Threshold -st):"))
            st_spin = QDoubleSpinBox()
            st_spin.setRange(0.0, 1.0)
            st_spin.setValue(0.001)
            st_spin.setDecimals(4)
            st_spin.setSingleStep(0.001)
            self.param_widgets["st"] = st_spin
            row_st.addWidget(st_spin)
            pd_layout.addLayout(row_st)

        elif self.step_key == "modelfinder":
            row_sc = QHBoxLayout()
            row_sc.addWidget(QLabel("搜尋模型池範疇 (Search Scope):"))
            scope_combo = QComboBox()
            scope_combo.addItems(["TESTONLY (評比 88+ 種常見核心模型)", "STANDARD (標準全模型庫)", "EXTENDED (擴展頻率與交換率)"])
            self.param_widgets["scope"] = scope_combo
            row_sc.addWidget(scope_combo)
            pd_layout.addLayout(row_sc)

            cb_r = QCheckBox("包含 FreeRate 自由率異質性模型 (+R1 ~ +R10)")
            cb_r.setChecked(True)
            self.param_widgets["freerate"] = cb_r
            pd_layout.addWidget(cb_r)

        elif self.step_key == "tree":
            row_alrt = QHBoxLayout()
            row_alrt.addWidget(QLabel("SH-aLRT 分支支撐率檢定次數 (SH-like Test):"))
            alrt_spin = QSpinBox()
            alrt_spin.setRange(0, 10000)
            alrt_spin.setValue(1000)
            alrt_spin.setSingleStep(100)
            self.param_widgets["alrt"] = alrt_spin
            row_alrt.addWidget(alrt_spin)
            pd_layout.addLayout(row_alrt)

            pd_layout.addWidget(QLabel("外群生根設定 (Outgroup): 系統自動檢定最遠分化枝"))

        elif self.step_key == "timetree":
            pd_layout.addWidget(QLabel("地質/化石/採樣年代校準標籤檔 (Date Calibration File):"))
            d_row = QHBoxLayout()
            df_edit = QLineEdit()
            df_edit.setPlaceholderText("選取包含分類群年代標註之文字檔 (*.txt)...")
            df_edit.setStyleSheet("font-size: 11px; background-color: #F8FAFC;")
            self.param_widgets["date_file"] = df_edit
            d_row.addWidget(df_edit, 1)

            btn_browse_d = QPushButton("瀏覽校準檔...")
            btn_browse_d.setFixedHeight(24)
            btn_browse_d.setStyleSheet("padding: 2px 8px; font-size: 11px;")
            btn_browse_d.clicked.connect(self.browse_date_file)
            d_row.addWidget(btn_browse_d)
            pd_layout.addLayout(d_row)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width() - 2)
        h = float(self.height() - 6)

        path = QPainterPath()
        # Top notch
        path.moveTo(2, 4)
        path.quadTo(2, 0, 6, 0)
        path.lineTo(16, 0)
        path.lineTo(20, 5)
        path.lineTo(34, 5)
        path.lineTo(38, 0)
        path.lineTo(w - 4, 0)
        path.quadTo(w, 0, w, 4)
        # Right edge
        path.lineTo(w, h - 4)
        path.quadTo(w, h, w - 4, h)
        # Bottom tab
        path.lineTo(38, h)
        path.lineTo(34, h + 5)
        path.lineTo(20, h + 5)
        path.lineTo(16, h)
        path.lineTo(6, h)
        path.quadTo(2, h, 2, h - 4)
        path.closeSubpath()

        # Check running state glow
        if self.is_running:
            painter.setPen(QPen(QColor("#FFE66D"), 4))
        else:
            painter.setPen(QPen(self.theme["border"], 2))

        bg_col = self.theme["bg"]
        if not self.enable_cb.isChecked():
            bg_col = QColor("#94A3B8")  # Grayed out when bypassed

        painter.setBrush(QBrush(bg_col))
        painter.drawPath(path)

    def on_enable_toggled(self, checked: bool):
        self.enabled_changed.emit(self.step_key, checked)
        self.run_btn.setEnabled(checked)
        self.update()

    def set_running_state(self, running: bool):
        self.is_running = running
        self.run_btn.setEnabled(not running)
        if running:
            self.status_badge.setText("運算中...")
            self.status_badge.setStyleSheet("background-color: #FEF3C7; color: #B45309; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 9px;")
        self.update()

    def set_record(self, record: StepRecord):
        self.current_record = record
        self.is_running = False
        self.run_btn.setEnabled(self.enable_cb.isChecked())

        status_map = {
            "completed": ("已完成 ✓", "background-color: #DCFCE7; color: #15803D; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 9px;"),
            "running": ("執行中...", "background-color: #FEF3C7; color: #B45309; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 9px;"),
            "failed": ("失敗 ✕", "background-color: #FEE2E2; color: #B91C1C; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 9px;"),
            "pending": ("待執行", "background-color: rgba(0,0,0,0.2); color: #FFFFFF; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 9px;"),
        }
        text, style = status_map.get(record.status, status_map["pending"])
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(style)

        if record.summary:
            self.summary_chip.setText(record.summary)

        if record.command_line:
            self.cmd_chip.setText(f"Cmd: {record.command_line}")

        notes = record.student_notes or ""
        char_count = len(notes.strip())
        self.note_toggle_btn.setText(f"📝 筆記 ({char_count} 字)" if char_count > 0 else "📝 筆記 (0)")
        if self.note_edit.toPlainText() != notes:
            self.note_edit.blockSignals(True)
            self.note_edit.setPlainText(notes)
            self.note_edit.blockSignals(False)

        if record.parameters:
            self.set_parameters(record.parameters)

        self.inspect_btn.setEnabled(True)
        self.update()

    def get_parameters(self) -> dict:
        params = {}
        for k, w in self.param_widgets.items():
            if isinstance(w, QComboBox):
                params[k] = w.currentText().split()[0]
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                params[k] = w.value()
            elif isinstance(w, QCheckBox):
                params[k] = w.isChecked()
            elif isinstance(w, QLineEdit):
                params[k] = w.text().strip()
        return params

    def set_parameters(self, params: dict):
        for k, v in params.items():
            if k in self.param_widgets:
                w = self.param_widgets[k]
                if isinstance(w, QComboBox):
                    idx = w.findText(str(v), Qt.MatchStartsWith)
                    if idx >= 0:
                        w.setCurrentIndex(idx)
                elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                    try:
                        w.setValue(type(w.value())(v))
                    except Exception:
                        pass
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(v))
                elif isinstance(w, QLineEdit):
                    w.setText(str(v))

    def mousePressEvent(self, event):
        child = self.childAt(event.pos())
        # Check if click was inside an interactive control or drawer
        w = child
        while w and w is not self:
            if w is self.summary_chip:
                self.inspect_requested.emit(self.step_key)
                event.accept()
                return
            if isinstance(w, (QPushButton, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QTextEdit, QScrollArea)):
                super().mousePressEvent(event)
                return
            if w is self.note_drawer or w is self.params_drawer:
                super().mousePressEvent(event)
                return
            w = w.parentWidget()

        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint()
            self.block_start_pos = self.pos()
            self.is_dragging = True
            self.raise_()
            # Detach from upstream block when picked up
            if self.upstream_block:
                self.upstream_block.downstream_block = None
                self.upstream_block = None
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            delta = event.globalPosition().toPoint() - self.drag_start_pos
            new_pos = self.block_start_pos + delta
            if self.parentWidget():
                new_x = max(10, min(self.parentWidget().width() - self.width() - 10, new_pos.x()))
                new_y = max(10, min(self.parentWidget().height() - self.height() - 10, new_pos.y()))
            else:
                new_x = max(10, new_pos.x())
                new_y = max(10, new_pos.y())
            dx = new_x - self.x()
            dy = new_y - self.y()
            self.move(new_x, new_y)
            # Move attached downstream blocks together
            curr = self.downstream_block
            visited = {id(self)}
            while curr and id(curr) not in visited:
                visited.add(id(curr))
                curr.raise_()
                curr.move(curr.x() + dx, curr.y() + dy)
                curr = getattr(curr, "downstream_block", None)
            if self.canvas and hasattr(self.canvas, "update_container_bounds"):
                self.canvas.update_container_bounds()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_dragging and event.button() == Qt.LeftButton:
            self.is_dragging = False
            if self.canvas and hasattr(self.canvas, "check_block_snap"):
                self.canvas.check_block_snap(self)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def toggle_params(self):
        prev_h = self.sizeHint().height() if self.isVisible() else self.height()
        self.params_expanded = not self.params_expanded
        self.params_drawer.setVisible(self.params_expanded)
        self.adjustSize()
        delta_h = (self.sizeHint().height() if self.isVisible() else self.height()) - prev_h
        if delta_h != 0:
            self._shift_downstream(delta_h)

    def toggle_notes(self):
        prev_h = self.sizeHint().height() if self.isVisible() else self.height()
        self.notes_expanded = not self.notes_expanded
        self.note_drawer.setVisible(self.notes_expanded)
        if self.notes_expanded:
            self.note_edit.setFocus()
        self.adjustSize()
        delta_h = (self.sizeHint().height() if self.isVisible() else self.height()) - prev_h
        if delta_h != 0:
            self._shift_downstream(delta_h)

    def _shift_downstream(self, delta_h: int):
        curr = self.downstream_block
        visited = {id(self)}
        while curr and id(curr) not in visited:
            visited.add(id(curr))
            curr.move(curr.x(), curr.y() + delta_h)
            curr = getattr(curr, "downstream_block", None)
        if self.canvas and hasattr(self.canvas, "update_container_bounds"):
            self.canvas.update_container_bounds()

    def on_note_text_changed(self):
        txt = self.note_edit.toPlainText()
        self.note_changed.emit(self.step_key, txt)
        char_count = len(txt.strip())
        self.note_toggle_btn.setText(f"📝 筆記 ({char_count} 字)" if char_count > 0 else "📝 筆記 (0)")
