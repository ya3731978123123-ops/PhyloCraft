"""
Module Toolbox Widget (生信模塊工具箱)
Inspired by visual block programming (Scratch / App Inventor / Blockly)
and professional bioinformatics workflow platforms (MEGA, Galaxy, KNIME).
Allows researchers to search, filter, and add modular tools from the palette onto the central canvas.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QLineEdit,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor


TOOLBOX_CATEGORIES = [
    {
        "id": "input_qc",
        "category": "1. 序列輸入與品管",
        "short_cat": "輸入品管",
        "color": "#0284C7",  # Sky Blue
        "items": [
            ("raw", "FASTA 序列輸入", "BioPython FASTA 讀取與規格檢驗，支援單一及批次載入", "原始檔"),
            ("sanitize", "IUPAC 品管清洗", "過濾 NCBI 特殊標頭、空白、特殊符號與過短殘缺序列", "品管清洗"),
        ],
    },
    {
        "id": "alignment",
        "category": "2. 多重序列比對",
        "short_cat": "多重比對",
        "color": "#008287",  # MEGA Teal
        "items": [
            ("alignment", "MAFFT 多重比對", "高速 FFT-NS-2 / L-INS-i 高精度演算法，精確處理長同源位點", "核心比對"),
            ("alignment_muscle", "MUSCLE v5 (備選)", "高精確度結構感知比對引擎，適合蛋白質與二級結構檢定", "備選比對"),
        ],
    },
    {
        "id": "trimming",
        "category": "3. 保守位點修剪",
        "short_cat": "位點修剪",
        "color": "#D97706",  # Amber
        "items": [
            ("trimming", "trimAl 智慧修剪", "automated1 保守區與 Gap 自動過濾，移除對齊低信噪位點", "核心修剪"),
            ("trimming_clipkit", "ClipKIT (備選)", "精準保留系統發育資訊位點 (PI Sites)，避免過度修剪", "位點保留"),
        ],
    },
    {
        "id": "modelfinder",
        "category": "4. 替代演化模型",
        "short_cat": "演化模型",
        "color": "#7C3AED",  # Purple
        "items": [
            ("modelfinder", "ModelFinder 模型評選", "BIC / AIC 統計檢定最優替代模型，評選 88+ 種核酸/胺基酸矩陣", "最佳模型"),
            ("modelfinder_part", "PartitionFinder (備選)", "多基因串聯超矩陣分區模型最佳化，支援基因間獨立演化率", "分區模型"),
        ],
    },
    {
        "id": "tree",
        "category": "5. 系統發育建樹",
        "short_cat": "系統建樹",
        "color": "#059669",  # Emerald
        "items": [
            ("tree", "IQ-TREE 最大概似建樹", "ML 拓撲推論 + 1000 次 UFBoot 與 SH-aLRT 超快速分支支撐檢定", "ML建樹"),
            ("tree_fasttree", "FastTree 2 (極速備選)", "百萬級序列近似最大似然極速推論，適合初步拓撲快速篩查", "極速建樹"),
        ],
    },
    {
        "id": "timetree",
        "category": "6. 分子定年時間樹",
        "short_cat": "分子定年",
        "color": "#DC2626",  # Red
        "items": [
            ("timetree", "LSD2 最小平方法定年", "結合化石/物種年代標註快速推算 tMRCA 與分子鐘突變速率", "分子定年"),
            ("timetree_treetime", "TreeTime (ML 備選)", "最大概似連續時間分子鐘模型，適用於病毒及演化速率變異", "連續時間"),
        ],
    },
    {
        "id": "viewer",
        "category": "7. 成果探針與報告",
        "short_cat": "視覺探針",
        "color": "#475569",  # Slate
        "items": [
            ("viewer_tree", "Tree Explorer 樹檢視器", "演化樹製圖工作室：圓形樹/矩形樹/放射樹、外群自定義與高解析輸出", "樹圖檢視"),
            ("viewer_msa", "Align Explorer 比對檢視器", "核酸與胺基酸智慧著色、SNPs 突變位點即時定位與變異度統計", "比對檢視"),
            ("viewer_eln", "論文電子實驗日誌 (ELN)", "自動編譯 Supplementary Material 報告 (Markdown/PDF/ZIP 封裝)", "論文ELN"),
        ],
    },
]


class ToolboxCardWidget(QFrame):
    """
    A non-glitching, responsive card representing a modular bioinformatics tool.
    Clean typography, colored category indicator, and direct action button.
    """

    card_clicked = Signal(str)

    def __init__(self, key: str, name: str, desc: str, badge: str, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.key = key
        self.color = color
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet(f"""
            ToolboxCardWidget {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-left: 3px solid {color};
                border-radius: 4px;
            }}
            ToolboxCardWidget:hover {{
                background-color: #F8FAFC;
                border-color: #BACCD9;
                border-left: 3px solid {color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Row 1: Name and Category badge
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(4)

        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #1E293B;")
        row1.addWidget(lbl_name)
        row1.addStretch()

        lbl_badge = QLabel(badge)
        lbl_badge.setStyleSheet(f"""
            font-size: 9px;
            font-weight: 500;
            color: {color};
            background-color: #F1F5F9;
            border: 1px solid #E2E8F0;
            border-radius: 3px;
            padding: 1px 4px;
        """)
        row1.addWidget(lbl_badge)
        layout.addLayout(row1)

        # Row 2: Wrapped Description
        lbl_desc = QLabel(desc)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #64748B; font-size: 10px; line-height: 1.15;")
        layout.addWidget(lbl_desc)

        # Row 3: Balanced action row with subtle hint and button
        row3 = QHBoxLayout()
        row3.setContentsMargins(0, 1, 0, 0)

        lbl_hint = QLabel("點擊卡片快速加入 ➔")
        lbl_hint.setStyleSheet("color: #94A3B8; font-size: 9px;")
        row3.addWidget(lbl_hint)
        row3.addStretch()

        btn_add = QPushButton("➕ 加入")
        btn_add.setFixedHeight(18)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: #F8FAFC;
                color: {color};
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                padding: 1px 8px;
                font-size: 9px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: #FFFFFF;
            }}
        """)
        btn_add.clicked.connect(lambda: self.card_clicked.emit(self.key))
        row3.addWidget(btn_add)
        layout.addLayout(row3)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.card_clicked.emit(self.key)
            event.accept()
        else:
            super().mousePressEvent(event)


class ModuleToolboxWidget(QWidget):
    """
    Side palette of modular bioinformatics blocks.
    Users can search tools, filter by category, or click tools to focus/add them to the canvas.
    """

    tool_clicked = Signal(str)        # step_key or action_key
    preset_selected = Signal(int)     # 0: standard, 1: fast, 2: timetree
    toggle_toolbox_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumWidth(230)
        self.cards_by_key = {}
        self.cat_frames = []
        self.current_filter_cat = "all"
        self.init_ui()

    def init_ui(self):
        self.setMinimumWidth(230)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 1. Header Bar
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        title = QLabel("生信模塊工具箱")
        title.setStyleSheet("color: #008287; font-size: 13px; font-weight: bold;")
        header_row.addWidget(title)

        sub = QLabel("Toolbox")
        sub.setStyleSheet("color: #64748B; font-size: 11px;")
        header_row.addWidget(sub)

        header_row.addStretch()

        self.btn_collapse = QPushButton("◀ 收合")
        self.btn_collapse.setFixedHeight(22)
        self.btn_collapse.setStyleSheet("""
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
        self.btn_collapse.setToolTip("收合生信模塊工具箱，為中央畫布騰出更多空間")
        self.btn_collapse.clicked.connect(self.toggle_toolbox_requested.emit)
        header_row.addWidget(self.btn_collapse)
        layout.addLayout(header_row)

        # 2. Search Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜尋模塊 (MAFFT, IQ-TREE...)")
        self.search_edit.setFixedHeight(24)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #BACCD9;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                color: #1E293B;
            }
            QLineEdit:focus {
                border-color: #008287;
            }
        """)
        self.search_edit.textChanged.connect(self.filter_modules)
        layout.addWidget(self.search_edit)

        # 3. Category Filter Chips (Compact 2-Row Flow Grid)
        filter_grid = QGridLayout()
        filter_grid.setContentsMargins(0, 0, 0, 0)
        filter_grid.setSpacing(3)

        self.filter_btns = {}
        quick_cats = [
            ("all", "全部"),
            ("input_qc", "輸入"),
            ("alignment", "比對"),
            ("trimming", "修剪"),
            ("modelfinder", "模型"),
            ("tree", "建樹"),
            ("timetree", "定年"),
            ("viewer", "探針"),
        ]
        for idx, (cid, cname) in enumerate(quick_cats):
            fbtn = QPushButton(cname)
            fbtn.setFixedHeight(21)
            fbtn.setCheckable(True)
            if cid == "all":
                fbtn.setChecked(True)
            fbtn.setStyleSheet("""
                QPushButton {
                    background-color: #F1F5F9;
                    color: #475569;
                    border: 1px solid #CBD5E1;
                    border-radius: 3px;
                    font-size: 10px;
                    padding: 1px 3px;
                }
                QPushButton:checked {
                    background-color: #008287;
                    color: #FFFFFF;
                    border-color: #008287;
                    font-weight: bold;
                }
                QPushButton:hover:!checked {
                    background-color: #E2E8F0;
                }
            """)
            fbtn.clicked.connect(lambda checked=False, c=cid: self.set_category_filter(c))
            self.filter_btns[cid] = fbtn
            row = idx // 4
            col = idx % 4
            filter_grid.addWidget(fbtn, row, col)

        layout.addLayout(filter_grid)

        # 4. Scroll Area with Categorized Modules (Strictly No Horizontal Scrollbar & Dedicated Vertical Channel)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #F8FAFC;
                border: 1px solid #BACCD9;
                border-radius: 4px;
            }
            QScrollBar:vertical {
                border: none;
                background: #F1F5F9;
                width: 8px;
                margin: 2px 2px 2px 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #008287;
            }
        """)

        cat_container = QWidget()
        cat_container.setStyleSheet("background-color: #F8FAFC;")
        cc_layout = QVBoxLayout(cat_container)
        cc_layout.setContentsMargins(6, 4, 14, 4)
        cc_layout.setSpacing(6)

        for cat in TOOLBOX_CATEGORIES:
            cat_frame = QWidget()
            cf_layout = QVBoxLayout(cat_frame)
            cf_layout.setContentsMargins(0, 0, 0, 0)
            cf_layout.setSpacing(4)

            # Category section header with colored accent pill and count indicator
            cat_hdr = QWidget()
            ch_layout = QHBoxLayout(cat_hdr)
            ch_layout.setContentsMargins(2, 4, 4, 0)
            ch_layout.setSpacing(5)

            pill = QFrame()
            pill.setFixedSize(3, 12)
            pill.setStyleSheet(f"background-color: {cat['color']}; border-radius: 1px;")
            ch_layout.addWidget(pill)

            cat_title = QLabel(cat["category"])
            cat_title.setStyleSheet(f"color: {cat['color']}; font-size: 11px; font-weight: bold;")
            ch_layout.addWidget(cat_title)
            ch_layout.addStretch()

            cnt = QLabel(f"{len(cat['items'])} 項")
            cnt.setStyleSheet("color: #94A3B8; font-size: 9px;")
            ch_layout.addWidget(cnt)

            cf_layout.addWidget(cat_hdr)

            for key, name, desc, badge in cat["items"]:
                card = ToolboxCardWidget(key, name, desc, badge, cat["color"])
                card.card_clicked.connect(self.tool_clicked.emit)
                cf_layout.addWidget(card)
                self.cards_by_key[key] = (card, cat["id"], name.lower() + " " + desc.lower())

            cc_layout.addWidget(cat_frame)
            self.cat_frames.append((cat_frame, cat["id"]))

        cc_layout.addStretch()
        scroll.setWidget(cat_container)
        layout.addWidget(scroll, 1)

    def set_category_filter(self, cat_id: str):
        self.current_filter_cat = cat_id
        for cid, btn in self.filter_btns.items():
            btn.setChecked(cid == cat_id)
        self.filter_modules()

    def filter_modules(self):
        query = self.search_edit.text().strip().lower()
        cat_filter = self.current_filter_cat

        for cat_frame, cat_id in self.cat_frames:
            cat_has_visible_cards = False
            # Check cards under this category
            for card, cid, text_corpus in self.cards_by_key.values():
                if cid == cat_id:
                    matches_cat = (cat_filter == "all" or cat_filter == cid)
                    matches_query = (not query or query in text_corpus)
                    visible = matches_cat and matches_query
                    card.setVisible(visible)
                    if visible:
                        cat_has_visible_cards = True
            cat_frame.setVisible(cat_has_visible_cards)
