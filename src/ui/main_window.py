from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QLabel,
    QStatusBar,
    QMessageBox,
    QPushButton,
    QFrame,
)
from PySide6.QtGui import QIcon, QFont, QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt

from src.ui.styles import MODERN_STYLE
from src.ui.tabs.workstation_tab import WorkstationTab
from src.ui.tabs.pipeline_tab import PipelineTab
from src.ui.tabs.sanitizer_tab import SanitizerTab
from src.ui.tabs.alignment_tab import AlignmentTab
from src.ui.tabs.trimming_tab import TrimmingTab
from src.ui.tabs.msa_tab import MSATab
from src.ui.tabs.model_test_tab import ModelTestTab
from src.ui.tabs.tree_tab import TreeTab
from src.ui.tabs.tree_viewer_tab import TreeViewerTab
from src.ui.tabs.concat_tab import ConcatTab
from src.ui.tabs.tools_tab import ToolsTab
from src.ui.tabs.ncbi_extractor_tab import NCBIGeneTab
from src.config import get_tool_status


class MainWindow(QMainWindow):
    """
    Main Application Window for PhyloCraft.
    Features:
    - Sidebar Navigation
    - Drag & Drop file handling
    - One-click cross-tab workflows
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhyloCraft — Evolutionary Genomics Workbench")
        self.resize(1280, 820)
        self.setMinimumSize(1024, 680)
        self.setStyleSheet(MODERN_STYLE)

        # Enable global Drag-and-Drop
        self.setAcceptDrops(True)

        self.init_ui()
        self.update_status_bar()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Modern Studio Header Container
        ribbon_container = QWidget()
        ribbon_container.setObjectName("studio_header_container")
        ribbon_container.setStyleSheet("""
            QWidget#studio_header_container {
                background-color: #FFFFFF;
                border-bottom: 1px solid #CBD5E1;
            }
        """)
        rc_layout = QHBoxLayout(ribbon_container)
        rc_layout.setContentsMargins(12, 6, 12, 6)
        rc_layout.setSpacing(10)

        # 1A. Left Brand & Project Status
        brand_layout = QHBoxLayout()
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(8)

        logo_icon = QLabel("🌿")
        logo_icon.setStyleSheet("font-size: 16px;")
        brand_layout.addWidget(logo_icon)

        title_lbl = QLabel("PhyloCraft Studio")
        title_lbl.setStyleSheet("color: #008287; font-size: 14px; font-weight: bold; letter-spacing: 0.5px;")
        brand_layout.addWidget(title_lbl)

        ver_badge = QLabel("v2.0")
        ver_badge.setStyleSheet("color: #64748B; background-color: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 4px; padding: 1px 6px; font-size: 10px; font-weight: bold;")
        brand_layout.addWidget(ver_badge)

        self.project_badge = QLabel("📁 專案: My_Evolution_Project")
        self.project_badge.setMaximumWidth(240)
        self.project_badge.setToolTip("當前專案: My_Evolution_Project")
        self.project_badge.setStyleSheet("""
            color: #0F766E;
            background-color: #F0FDF4;
            border: 1px solid #BBF7D0;
            border-radius: 4px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 600;
        """)
        brand_layout.addWidget(self.project_badge)
        rc_layout.addLayout(brand_layout)

        rc_layout.addStretch()

        # 1B. Center Mode Switcher (Sleek Segmented Switcher Pills)
        center_nav_layout = QHBoxLayout()
        center_nav_layout.setContentsMargins(0, 0, 0, 0)
        center_nav_layout.setSpacing(4)

        self.last_standalone_tool_idx = 3  # Default to MAFFT Alignment
        self.ribbon_buttons: dict[int, QPushButton] = {}

        core_tabs_defs = [
            (0, "🎨 積木流程", "積木流程工作台 (Workflow Studio)\n生物演化積木流程、多管線工作台與對照實驗"),
            (11, "🌐 NCBI 溯源", "NCBI 基因線上檢索與特徵溯源擷取 (NCBI Gene Extractor)\n在線精確檢索目標基因 CDS、官方直達溯源與 SHA-256 指紋"),
            (-1, "🛠️ 獨立工具", "獨立單工工具箱 (Quick Tools Hub)\n無需建立專案或拖拉積木，載入單檔即刻極速比對、修剪、評選或建樹"),
            (8, "🌲 演化樹", "演化樹製圖工坊 (Tree Studio)\n發表級演化樹美化、定根、縮放與高解析度匯出"),
            (5, "🧬 比對檢視", "多重序列比對檢視器 (MSA Viewer)\n多序列比對矩陣、核酸顏色、共識序列與 SNPs 突變篩選"),
            (1, "⚡ 批次流程", "自動化批次流程 (Automated Pipeline)\n一鍵式自動化批次執行流程"),
            (10, "⚙️ 系統環境", "核心工具庫管理 (Core Tools Manager)\n演化分析核心工具程式庫偵測與一鍵自動下載"),
        ]

        def create_nav_btn(idx, title, tip):
            btn = QPushButton(title)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #F8FAFC;
                    color: #334155;
                    border: 1px solid #CBD5E1;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 600;
                    min-width: 70px;
                }
                QPushButton:hover {
                    background-color: #E2E8F0;
                    color: #008287;
                }
                QPushButton:checked {
                    background-color: #008287;
                    border: 1px solid #005457;
                    color: #FFFFFF;
                    font-weight: bold;
                }
            """)
            if idx == -1:
                btn.clicked.connect(lambda: self.nav_list.setCurrentRow(self.last_standalone_tool_idx))
            else:
                btn.clicked.connect(lambda _, target=idx: self.nav_list.setCurrentRow(target))
            return btn

        for idx, title, tip in core_tabs_defs:
            btn = create_nav_btn(idx, title, tip)
            if idx == -1:
                self.btn_tools_hub = btn
            self.ribbon_buttons[idx] = btn
            center_nav_layout.addWidget(btn)

        # For backward test compatibility, create dummy buttons for indices not in core_tabs_defs
        for idx in range(12):
            if idx not in self.ribbon_buttons:
                dummy_btn = QPushButton()
                dummy_btn.setCheckable(True)
                dummy_btn.setVisible(False)
                self.ribbon_buttons[idx] = dummy_btn

        rc_layout.addLayout(center_nav_layout)
        rc_layout.addStretch()

        # 1C. Right Quick Actions (Cleaned: no redundant global pipeline run/stop buttons)
        right_actions_layout = QHBoxLayout()
        right_actions_layout.setContentsMargins(0, 0, 0, 0)
        right_actions_layout.setSpacing(6)

        # Retain references for backward compatibility without rendering in global ribbon
        self.btn_run = QPushButton("▶ 執行")
        self.btn_run.clicked.connect(lambda: self.workstation_tab.run_entire_flow())
        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.clicked.connect(lambda: self.workstation_tab.cancel_workflow())

        btn_eln = QPushButton("📄 論文 ELN")
        btn_eln.setFixedHeight(28)
        btn_eln.setCursor(Qt.PointingHandCursor)
        btn_eln.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #008287;
                border: 1px solid #008287;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #F0FDF4;
            }
        """)
        btn_eln.setToolTip("即時生成電子實驗紀錄簿 (ELN) 與論文 Supplementary Material 封裝包")
        btn_eln.clicked.connect(lambda: self.workstation_tab.open_eln_dialog())
        right_actions_layout.addWidget(btn_eln)

        btn_demo = QPushButton("💡 範例資料")
        btn_demo.setFixedHeight(28)
        btn_demo.setCursor(Qt.PointingHandCursor)
        btn_demo.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                color: #0F172A;
            }
        """)
        btn_demo.setToolTip("載入標準靈長類 Cytb 科研範例資料集")
        btn_demo.clicked.connect(lambda: self.workstation_tab.load_demo_project(show_alert=True))
        right_actions_layout.addWidget(btn_demo)

        rc_layout.addLayout(right_actions_layout)
        main_layout.addWidget(ribbon_container)

        # 1D. Standalone Quick Tools Hub Sub-Navigation Bar
        self.standalone_hub_bar = QWidget()
        self.standalone_hub_bar.setObjectName("standalone_hub_bar")
        self.standalone_hub_bar.setStyleSheet("""
            QWidget#standalone_hub_bar {
                background-color: #F8FAFC;
                border-bottom: 2px solid #008287;
            }
        """)
        sh_layout = QHBoxLayout(self.standalone_hub_bar)
        sh_layout.setContentsMargins(14, 5, 14, 5)
        sh_layout.setSpacing(6)

        hub_title = QLabel("🛠️ 獨立單工工具箱 ｜ 快速切換：")
        hub_title.setStyleSheet("color: #0F172A; font-size: 11px; font-weight: bold;")
        sh_layout.addWidget(hub_title)

        self.standalone_tool_buttons: dict[int, QPushButton] = {}
        standalone_defs = [
            (11, "🌐 NCBI 擷取", "NCBI 基因檢索 (NCBI Extractor)：在線下載、特徵註解精確座標切片與溯源"),
            (2, "🧹 序列清洗", "序列清洗 (Sanitizer)：標頭清洗、格式轉換與品質過濾"),
            (3, "🧬 MAFFT 比對", "MAFFT 比對 (Alignment)：高速高品質多重序列比對與反向校正"),
            (4, "✂️ trimAl 修剪", "trimAl 修剪 (Trimming)：保守演化位點修剪與長空缺過濾"),
            (6, "🔬 模型評選", "模型評選 (ModelFinder)：88+ 種替代模型統計評選 (BIC/AIC)"),
            (7, "🌳 系統建樹", "系統建樹 (IQ-TREE)：最大概似法推論與超快拔靴值檢驗"),
            (9, "🧩 超矩陣串聯", "超矩陣串聯 (Concatenate)：多基因串聯、缺失數據補齊與分區模型"),
        ]

        def create_standalone_btn(s_idx, s_title, s_tip):
            btn = QPushButton(s_title)
            btn.setCheckable(True)
            btn.setToolTip(s_tip)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #334155;
                    border: 1px solid #CBD5E1;
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 500;
                    min-width: 68px;
                }
                QPushButton:hover {
                    background-color: #F1F5F9;
                    color: #008287;
                    border-color: #008287;
                }
                QPushButton:checked {
                    background-color: #008287;
                    border: 1px solid #005457;
                    color: #FFFFFF;
                    font-weight: bold;
                }
            """)
            btn.clicked.connect(lambda _, target=s_idx: self.nav_list.setCurrentRow(target))
            return btn

        for s_idx, s_title, s_tip in standalone_defs:
            s_btn = create_standalone_btn(s_idx, s_title, s_tip)
            self.standalone_tool_buttons[s_idx] = s_btn
            sh_layout.addWidget(s_btn)

        sh_layout.addStretch()

        hub_badge = QLabel("⚡ 獨立單工模式：免建專案・載入即跑・直接輸出成果")
        hub_badge.setStyleSheet("color: #0F766E; font-size: 11px; background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 3px; padding: 2px 8px; font-weight: 500;")
        sh_layout.addWidget(hub_badge)

        btn_back_studio = QPushButton("🎨 返回積木工作台 ➔")
        btn_back_studio.setFixedHeight(26)
        btn_back_studio.setCursor(Qt.PointingHandCursor)
        btn_back_studio.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #0F766E;
                border: 1px solid #0F766E;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0F766E;
                color: #FFFFFF;
            }
        """)
        btn_back_studio.clicked.connect(lambda: self.nav_list.setCurrentRow(0))
        sh_layout.addWidget(btn_back_studio)

        self.standalone_hub_bar.setVisible(False)
        main_layout.addWidget(self.standalone_hub_bar)

        # 2. Hidden Navigation List (Maintains 100% API & Test Compatibility)
        self.nav_list = QListWidget()
        self.nav_list.setVisible(False)
        nav_items = [
            ("專案工作台", "Research Workstation"),
            ("自動化流程", "Automated Pipeline"),
            ("序列檢驗清洗", "Sanitizer & Converter"),
            ("多重序列比對", "MAFFT Alignment"),
            ("比對位點修剪", "trimAl Trimming"),
            ("比對矩陣檢視器", "MSA Alignment Viewer"),
            ("替代模型檢定", "ModelFinder Selection"),
            ("系統發育建樹", "IQ-TREE Inference"),
            ("演化樹檢視器", "Interactive Tree Viewer"),
            ("多基因超矩陣", "Matrix Concatenator"),
            ("系統工具與環境", "Tools Manager"),
            ("NCBI 基因檢索", "NCBI Gene Extractor"),
        ]
        for title_text, _ in nav_items:
            self.nav_list.addItem(QListWidgetItem(title_text))

        # 3. Full-Width Central Workspace Area (QStackedWidget)
        self.stack = QStackedWidget()
        self.stack.setObjectName("content_area")

        # Instantiate tabs
        self.workstation_tab = WorkstationTab()
        self.pipeline_tab = PipelineTab()
        self.sanitizer_tab = SanitizerTab()
        self.alignment_tab = AlignmentTab()
        self.trimming_tab = TrimmingTab()
        self.msa_tab = MSATab()
        self.model_test_tab = ModelTestTab()
        self.tree_tab = TreeTab()
        self.tree_viewer_tab = TreeViewerTab()
        self.concat_tab = ConcatTab()
        self.tools_tab = ToolsTab()
        self.ncbi_gene_tab = NCBIGeneTab()

        self.stack.addWidget(self.workstation_tab)    # 0
        self.stack.addWidget(self.pipeline_tab)       # 1
        self.stack.addWidget(self.sanitizer_tab)      # 2
        self.stack.addWidget(self.alignment_tab)      # 3
        self.stack.addWidget(self.trimming_tab)       # 4
        self.stack.addWidget(self.msa_tab)            # 5
        self.stack.addWidget(self.model_test_tab)     # 6
        self.stack.addWidget(self.tree_tab)           # 7
        self.stack.addWidget(self.tree_viewer_tab)    # 8
        self.stack.addWidget(self.concat_tab)         # 9
        self.stack.addWidget(self.tools_tab)          # 10
        self.stack.addWidget(self.ncbi_gene_tab)      # 11

        main_layout.addWidget(self.stack, 1)

        # Connect Navigation synchronization
        self.nav_list.currentRowChanged.connect(self.on_nav_row_changed)
        self.nav_list.setCurrentRow(0)

        # Connect cross-tab signals
        self.workstation_tab.jump_to_tab_requested.connect(self.nav_list.setCurrentRow)
        self.workstation_tab.view_tree_requested.connect(self.switch_to_tree_viewer)
        self.workstation_tab.view_msa_requested.connect(self.switch_to_msa_viewer)
        self.workstation_tab.view_model_test_requested.connect(self.switch_to_model_test_report)
        self.workstation_tab.step_jump_with_data_requested.connect(self.handle_step_jump_with_data)
        self.pipeline_tab.pipeline_finished_with_details.connect(self.sync_pipeline_to_workstation)
        self.pipeline_tab.view_tree_requested.connect(self.switch_to_tree_viewer)
        self.pipeline_tab.view_msa_requested.connect(self.switch_to_msa_viewer)
        self.pipeline_tab.test_model_requested.connect(self.switch_to_model_test)
        self.sanitizer_tab.send_to_align_requested.connect(self.switch_to_alignment)
        self.alignment_tab.view_msa_requested.connect(self.switch_to_msa_viewer)
        self.alignment_tab.trim_requested.connect(self.switch_to_trimming)
        self.trimming_tab.view_msa_requested.connect(self.switch_to_msa_viewer)
        self.trimming_tab.test_model_requested.connect(self.switch_to_model_test)
        self.trimming_tab.send_to_tree_requested.connect(self.switch_to_tree_from_trimming)
        self.model_test_tab.apply_model_requested.connect(self.switch_to_tree_tab)
        self.tree_tab.view_tree_requested.connect(self.switch_to_tree_viewer)
        self.concat_tab.send_to_tree_requested.connect(self.switch_to_tree_from_concat)
        self.ncbi_gene_tab.send_to_sanitizer_requested.connect(self.switch_to_sanitizer)
        self.ncbi_gene_tab.send_to_align_requested.connect(self.switch_to_alignment)

        # Modern Studio Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("background-color: #FFFFFF; color: #475569; border-top: 1px solid #E2E8F0; font-size: 11px;")
        self.setStatusBar(self.status_bar)

        # 4. Classic Academic Menu Bar (MEGA Desktop Style)
        self.create_menu_bar()

    def create_menu_bar(self):
        menubar = self.menuBar()

        # 1. 檔案 (File)
        file_menu = menubar.addMenu("檔案 (File)")
        act_open_proj = file_menu.addAction("開啟專案... (Open Project...)")
        act_open_proj.triggered.connect(self.workstation_tab.open_project_dialog)
        act_new_proj = file_menu.addAction("新建專案... (New Project...)")
        act_new_proj.triggered.connect(self.workstation_tab.new_project_dialog)
        file_menu.addSeparator()
        act_eln = file_menu.addAction("導出電子實驗紀錄簿 (Export ELN Report)...")
        act_eln.triggered.connect(self.workstation_tab.open_eln_dialog)
        file_menu.addSeparator()
        act_exit = file_menu.addAction("結束 (Exit)")
        act_exit.triggered.connect(self.close)

        # 2. 分析 (Analysis) - Direct access to MEGA Analysis Preferences dialogs
        analysis_menu = menubar.addMenu("分析 (Analysis)")
        act_align = analysis_menu.addAction("多重序列比對偏好 (Align Sequences - MAFFT)...")
        act_align.triggered.connect(lambda: self.open_analysis_preferences("alignment"))
        act_trim = analysis_menu.addAction("比對位點修剪偏好 (Trim Alignment - trimAl)...")
        act_trim.triggered.connect(lambda: self.open_analysis_preferences("trimming"))
        act_model = analysis_menu.addAction("替代模型檢定偏好 (Find Best Models - ModelFinder)...")
        act_model.triggered.connect(lambda: self.open_analysis_preferences("modelfinder"))
        act_tree = analysis_menu.addAction("推論最大概似樹偏好 (Construct ML Tree - IQ-TREE 2)...")
        act_tree.triggered.connect(lambda: self.open_analysis_preferences("tree"))
        act_timetree = analysis_menu.addAction("分子鐘時間樹定年偏好 (Estimate TimeTree - LSD2)...")
        act_timetree.triggered.connect(lambda: self.open_analysis_preferences("timetree"))
        act_sanitize = analysis_menu.addAction("序列檢驗清洗偏好 (Sanitize Sequences)...")
        act_sanitize.triggered.connect(lambda: self.open_analysis_preferences("sanitize"))
        act_ncbi = analysis_menu.addAction("NCBI 基因線上檢索與溯源 (Retrieve from NCBI)...")
        act_ncbi.triggered.connect(lambda: self.nav_list.setCurrentRow(11))
        analysis_menu.addSeparator()
        act_pipeline = analysis_menu.addAction("執行全自動分析流程 (Automated Pipeline)...")
        act_pipeline.triggered.connect(lambda: self.nav_list.setCurrentRow(1))

        # 3. 檢視 (View)
        view_menu = menubar.addMenu("檢視 (View)")
        act_v_workstation = view_menu.addAction("專案工作台 (Project Workstation)")
        act_v_workstation.triggered.connect(lambda: self.nav_list.setCurrentRow(0))
        act_v_pipe = view_menu.addAction("自動化流程 (Automated Pipeline)")
        act_v_pipe.triggered.connect(lambda: self.nav_list.setCurrentRow(1))
        act_v_ncbi = view_menu.addAction("NCBI 基因檢索與溯源 (NCBI Extractor)")
        act_v_ncbi.triggered.connect(lambda: self.nav_list.setCurrentRow(11))
        act_v_tree = view_menu.addAction("演化樹製圖檢視器 (Tree Explorer)")
        act_v_tree.triggered.connect(lambda: self.nav_list.setCurrentRow(8))
        act_v_msa = view_menu.addAction("多重序列比對檢視器 (Alignment Explorer)")
        act_v_msa.triggered.connect(lambda: self.nav_list.setCurrentRow(5))
        act_v_model = view_menu.addAction("模型檢定結果 (Model Testing)")
        act_v_model.triggered.connect(lambda: self.nav_list.setCurrentRow(6))
        act_v_concat = view_menu.addAction("多基因超矩陣串聯 (Matrix Concatenator)")
        act_v_concat.triggered.connect(lambda: self.nav_list.setCurrentRow(9))

        # 4. 工具 (Tools)
        tools_menu = menubar.addMenu("工具 (Tools)")
        act_tools = tools_menu.addAction("外部核心工具箱管理 (Core Tools Manager)...")
        act_tools.triggered.connect(lambda: self.nav_list.setCurrentRow(10))

        # 5. 說明 (Help)
        help_menu = menubar.addMenu("說明 (Help)")
        act_about = help_menu.addAction("關於 PhyloCraft (About PhyloCraft)...")
        act_about.triggered.connect(self.show_about_dialog)
        act_help_eln = help_menu.addAction("電子實驗紀錄簿 (Electronic Lab Notebook)...")
        act_help_eln.triggered.connect(self.workstation_tab.open_eln_dialog)

    def open_analysis_preferences(self, profile_key: str):
        self.nav_list.setCurrentRow(0)
        self.workstation_tab.open_preferences_for_step(profile_key)

    def show_about_dialog(self):
        QMessageBox.about(
            self,
            "關於 PhyloCraft",
            "<h3>PhyloCraft</h3>"
            "<p><b>Molecular Evolutionary Genetics & Phylogenomics Platform</b></p>"
            "<p>專為分子演化生物學打造之科研工作站，提供精確直覺的「分析偏好設定表單 (Analysis Preferences)」與高可重現性實驗紀錄。</p>"
            "<p><b>整合核心引擎：</b><br>"
            "• <b>MAFFT</b>: 高速高品質多重序列比對<br>"
            "• <b>trimAl</b>: 保守演化位點自動化修剪<br>"
            "• <b>ModelFinder</b>: 80+ 種替代模型統計評選 (AIC / BIC)<br>"
            "• <b>IQ-TREE 2</b>: 超快最大概似法推論與雙重分支檢驗 (UFBoot2 / SH-aLRT)<br>"
            "• <b>LSD2</b>: 分子鐘時間樹定年 (Molecular Clock TimeTree)<br>"
            "• <b>SHA-256 ELN</b>: 論文級電子實驗紀錄簿與防偽審計軌跡</p>"
            "<p>授權協議: Academic Open Source License</p>",
        )

    def on_nav_row_changed(self, idx: int):
        self.stack.setCurrentIndex(idx)
        standalone_indices = {2, 3, 4, 6, 7, 9}
        if idx in standalone_indices:
            self.last_standalone_tool_idx = idx
            if hasattr(self, "standalone_hub_bar"):
                self.standalone_hub_bar.setVisible(True)
            if hasattr(self, "btn_tools_hub"):
                self.btn_tools_hub.setChecked(True)
            for b_idx, btn in self.ribbon_buttons.items():
                if b_idx != -1:
                    btn.setChecked(False)
            for s_idx, s_btn in getattr(self, "standalone_tool_buttons", {}).items():
                s_btn.setChecked(s_idx == idx)
        else:
            if hasattr(self, "standalone_hub_bar"):
                self.standalone_hub_bar.setVisible(False)
            if hasattr(self, "btn_tools_hub"):
                self.btn_tools_hub.setChecked(False)
            for b_idx, btn in self.ribbon_buttons.items():
                btn.setChecked(b_idx == idx)

        if hasattr(self, "workstation_tab") and self.workstation_tab.pm.current_project:
            p_name = self.workstation_tab.pm.current_project.name
            self.project_badge.setText(f"📁 專案: {p_name}")
            self.project_badge.setToolTip(f"當前專案: {p_name}")

    def sync_pipeline_to_workstation(self, fasta_p: str, tree_p: str, aln_p: str, model: str):
        if not fasta_p:
            return
        p_fasta = Path(fasta_p)
        self.workstation_tab.pm.update_step("raw", "completed", f"原始序列: {p_fasta.name}", [fasta_p])
        self.workstation_tab.pm.update_step("sanitize", "completed", "序列標頭清洗與長度品質分析通過")
        if aln_p:
            self.workstation_tab.pm.update_step("alignment", "completed", f"MAFFT 自動對齊完成: {Path(aln_p).name}", [aln_p])
            self.workstation_tab.pm.update_step("trimming", "completed", f"trimAl automated1 修剪完成", [aln_p])
        if model:
            self.workstation_tab.pm.update_step("modelfinder", "completed", f"ModelFinder 最適模型 (BIC): {model}")
        if tree_p:
            self.workstation_tab.pm.update_step("tree", "completed", f"IQ-TREE 最大概似建樹完成: {Path(tree_p).name}", [tree_p])
        if self.workstation_tab.pm.current_project:
            self.workstation_tab.display_project(self.workstation_tab.pm.current_project)

    def switch_to_tree_viewer(self, tree_path: str):
        self.tree_viewer_tab.load_tree(tree_path)
        self.nav_list.setCurrentRow(8)  # Tree viewer index

    def switch_to_msa_viewer(self, aln_path: str):
        self.msa_tab.load_alignment(aln_path)
        self.nav_list.setCurrentRow(5)  # MSA viewer index

    def switch_to_sanitizer(self, fasta_path: str):
        self.sanitizer_tab.file_edit.setText(fasta_path)
        self.sanitizer_tab.analyze_file(show_dialog=False)
        self.nav_list.setCurrentRow(2)  # Sanitizer tab index
        self.status_bar.showMessage(f"已載入序列至品質檢驗與清洗: {Path(fasta_path).name}", 4000)

    def switch_to_alignment(self, fasta_path: str):
        self.alignment_tab.in_edit.setText(fasta_path)
        p = Path(fasta_path)
        self.alignment_tab.out_edit.setText(str(p.parent / f"{p.stem}_aligned.fasta"))
        self.nav_list.setCurrentRow(3)  # Alignment tab index
        self.status_bar.showMessage(f"已載入序列至多重比對: {Path(fasta_path).name}", 4000)

    def switch_to_trimming(self, aln_path: str):
        self.trimming_tab.in_edit.setText(aln_path)
        p = Path(aln_path)
        self.trimming_tab.out_edit.setText(str(p.parent / f"{p.stem}_trimmed.fasta"))
        self.nav_list.setCurrentRow(4)  # Trimming tab index
        self.status_bar.showMessage(f"已載入比對序列至修剪: {Path(aln_path).name}", 4000)

    def switch_to_model_test(self, aln_path: str):
        self.model_test_tab.set_input_file(aln_path)
        self.nav_list.setCurrentRow(6)  # Model test index
        self.status_bar.showMessage(f"已載入比對序列至模型檢定: {Path(aln_path).name}", 4000)

    def switch_to_model_test_report(self, report_path: str):
        if report_path and Path(report_path).exists():
            self.model_test_tab.load_existing_report(report_path)
        self.nav_list.setCurrentRow(6)  # Model test index
        self.status_bar.showMessage(f"已載入 ModelFinder 檢定報告: {Path(report_path).name}", 4000)

    def handle_step_jump_with_data(self, step_key: str, file_path: str):
        if not file_path or not Path(file_path).exists():
            return
        p = Path(file_path)
        if step_key == "raw":
            self.sanitizer_tab.file_edit.setText(file_path)
            self.sanitizer_tab.analyze_file(show_dialog=False)
            self.msa_tab.load_alignment(file_path)
            self.status_bar.showMessage(f"已載入原始序列: {p.name}", 4000)
        elif step_key == "sanitize":
            self.sanitizer_tab.file_edit.setText(file_path)
            self.sanitizer_tab.analyze_file(show_dialog=False)
            self.status_bar.showMessage(f"已就緒序列品管清洗: {p.name}", 4000)
        elif step_key == "alignment":
            self.alignment_tab.in_edit.setText(file_path)
            self.alignment_tab.out_edit.setText(str(p.parent / f"{p.stem}_aligned.fasta"))
            self.alignment_tab.last_output_file = file_path
            self.alignment_tab.view_msa_btn.setEnabled(True)
            self.alignment_tab.to_trim_btn.setEnabled(True)
            self.alignment_tab.result_banner.show()
            self.alignment_tab.result_label.setText(f"✓ 比對已就緒: {p.name}")
            self.msa_tab.load_alignment(file_path)
        elif step_key == "trimming":
            self.trimming_tab.in_edit.setText(file_path)
            self.trimming_tab.out_edit.setText(str(p.parent / f"{p.stem}_trimmed.fasta"))
            self.trimming_tab.last_trimmed_file = file_path
            self.trimming_tab.last_output_file = file_path
            self.trimming_tab.view_msa_btn.setEnabled(True)
            self.trimming_tab.to_model_btn.setEnabled(True)
            self.trimming_tab.result_banner.show()
            self.trimming_tab.result_label.setText(f"✓ 修剪已就緒: {p.name}")
            self.msa_tab.load_alignment(file_path)
        elif step_key == "modelfinder":
            if p.suffix == ".iqtree":
                self.model_test_tab.load_existing_report(file_path)
            else:
                self.model_test_tab.set_input_file(file_path)
        elif step_key in ("tree", "tree_fasttree", "fasttree"):
            if p.suffix in (".treefile", ".nwk", ".tree"):
                self.tree_viewer_tab.load_tree(file_path)
            elif p.suffix in (".fasta", ".fa", ".phy", ".nex"):
                self.tree_tab.in_edit.setText(file_path)
                self.tree_tab.out_edit.setText(str(p.parent / f"{p.stem}_tree"))
            # Sync model if modelfinder completed
            if self.workstation_tab.pm.current_project:
                mf = self.workstation_tab.pm.current_project.steps.get("modelfinder")
                if mf and mf.parameters.get("best_model"):
                    best_m = mf.parameters["best_model"]
                    idx_m = self.tree_tab.model_combo.findText(best_m)
                    if idx_m >= 0:
                        self.tree_tab.model_combo.setCurrentIndex(idx_m)
                    else:
                        self.tree_tab.model_combo.insertItem(0, best_m)
                        self.tree_tab.model_combo.setCurrentIndex(0)
        elif step_key == "timetree":
            if p.suffix in (".timetree.nwk", ".timetree.nex", ".treefile", ".nwk", ".tree"):
                self.tree_viewer_tab.load_tree(file_path)
                if hasattr(self.tree_viewer_tab, "tree_canvas"):
                    self.tree_viewer_tab.tree_canvas.time_scale_cb.setChecked(True)

    def switch_to_tree_tab(self, model: str, file_path: str):
        self.tree_tab.set_model_and_input(model, file_path, source="模型評選 (ModelFinder)")
        self.nav_list.setCurrentRow(7)  # Tree tab index
        self.status_bar.showMessage(f"已套用最佳模型 {model} 並跳轉至建樹分頁", 5000)

    def switch_to_tree_from_trimming(self, file_path: str):
        self.tree_tab.set_input_file(file_path, source="trimAl 比對修剪")
        self.nav_list.setCurrentRow(7)  # Tree tab index
        self.status_bar.showMessage("已將修剪後序列傳送至建樹分頁，預設啟用 MFP 最佳模型評選", 5000)

    def switch_to_tree_from_concat(self, fasta_path: str, partition_path: str):
        self.tree_tab.set_input_file(fasta_path, source="多基因超矩陣串聯 (Concatenate)")
        self.tree_tab.part_edit.setText(partition_path)
        p = Path(fasta_path)
        self.tree_tab.out_edit.setText(str(p.parent / f"{p.stem}_partition_tree"))
        self.nav_list.setCurrentRow(7)  # Tree tab index
        self.status_bar.showMessage("已載入多基因超矩陣與分區設定檔，可直接開始分區建樹。", 5000)

    def update_status_bar(self):
        status = get_tool_status()
        found_count = sum(1 for v in status.values() if v["found"])
        total_count = len(status)
        if found_count == total_count:
            self.status_bar.showMessage(f"[就緒] 核心工具已齊全 ({found_count}/{total_count}) — 拖曳檔案至視窗即可快速載入")
        else:
            self.status_bar.showMessage(
                f"[提示] 核心工具尚未齊全 ({found_count}/{total_count}) — 請前往「系統工具」下載安裝"
            )

    # ================= Drag & Drop Support =================
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return

        current_tab = self.nav_list.currentRow()
        if current_tab == 9:
            self.concat_tab.dropEvent(event)
            return

        file_path = Path(urls[0].toLocalFile())
        if not file_path.exists():
            return

        suffix = file_path.suffix.lower()

        if file_path.is_dir() and (file_path / "project.json").exists():
            proj = self.workstation_tab.pm.open_project(file_path)
            if proj:
                self.workstation_tab.display_project(proj)
                self.nav_list.setCurrentRow(0)
                self.status_bar.showMessage(f"[成功] 已成功載入專案: {proj.name}", 4000)
                return
        elif suffix == ".json" and file_path.name == "project.json":
            proj = self.workstation_tab.pm.open_project(file_path)
            if proj:
                self.workstation_tab.display_project(proj)
                self.nav_list.setCurrentRow(0)
                self.status_bar.showMessage(f"[成功] 已成功載入專案: {proj.name}", 4000)
                return
        elif suffix in (".treefile", ".nwk", ".tree", ".newick"):
            self.switch_to_tree_viewer(str(file_path))
            self.status_bar.showMessage(f"已載入演化樹: {file_path.name}")
        elif suffix == ".iqtree":
            ok = self.model_test_tab.load_existing_report(file_path)
            if ok:
                self.nav_list.setCurrentRow(6)
                self.status_bar.showMessage(f"已載入 ModelFinder 檢定報告: {file_path.name}", 4000)
            else:
                self.status_bar.showMessage(f"[提示] 無法解析此 iqtree 報告之模型檢定結果: {file_path.name}", 4000)
        elif suffix in (".fasta", ".fa", ".fas", ".fna", ".faa", ".phy", ".nex"):
            current_tab = self.nav_list.currentRow()
            # Route to currently active tab if applicable
            if current_tab == 0:
                raw_edit = self.workstation_tab.block_canvas.cards["raw"].param_widgets.get("fasta_path")
                if raw_edit:
                    raw_edit.setText(str(file_path.resolve()))
                self.workstation_tab.block_canvas.cards["raw"].params_drawer.setVisible(True)
                self.workstation_tab.block_canvas.cards["raw"].params_expanded = True
                self.status_bar.showMessage(f"已載入至專案工作站原始序列: {file_path.name}", 4000)
            elif current_tab == 5:
                self.switch_to_msa_viewer(str(file_path))
            elif current_tab == 2:
                self.sanitizer_tab.file_edit.setText(str(file_path))
                self.sanitizer_tab.analyze_file()
            elif current_tab == 3:
                self.alignment_tab.in_edit.setText(str(file_path))
            elif current_tab == 4:
                self.trimming_tab.in_edit.setText(str(file_path))
            elif current_tab == 6:
                self.model_test_tab.set_input_file(str(file_path))
            elif current_tab == 7:
                self.tree_tab.in_edit.setText(str(file_path))
            else:
                # Default to Pipeline Tab
                self.pipeline_tab.input_edit.setText(str(file_path))
                self.nav_list.setCurrentRow(1)
            self.status_bar.showMessage(f"已載入檔案: {file_path.name}")

    def show_citations_dialog(self):
        msg = (
            "<b>PhyloCraft 核心演化生物學工具標準學術引用文獻：</b><br><br>"
            "• <b>MAFFT v7:</b> Katoh, K. & Standley, D.M. (2013) <i>Mol. Biol. Evol.</i> 30(4):772-780.<br>"
            "• <b>trimAl v1.4:</b> Capella-Gutierrez, S. et al. (2009) <i>Bioinformatics</i> 25(15):1972-1973.<br>"
            "• <b>ModelFinder:</b> Kalyaanamoorthy, S. et al. (2017) <i>Nature Methods</i> 14(6):587-589.<br>"
            "• <b>IQ-TREE 2:</b> Minh, B.Q. et al. (2020) <i>Mol. Biol. Evol.</i> 37(5):1530-1534.<br>"
            "• <b>LSD2:</b> To, T.H. et al. (2016) <i>Syst. Biol.</i> 65(1):82-97.<br>"
            "• <b>FastTree 2:</b> Price, M.N. et al. (2010) <i>PLoS ONE</i> 5(3):e9490.<br><br>"
            "提示：導出之電子實驗日誌 (ELN) 已自動將上述引用與完整分析參數整合為論文 Supplementary Material 格式。"
        )
        QMessageBox.information(self, "學術文獻引用 (Academic Citations)", msg)

    def show_help_dialog(self):
        msg = (
            "<b>PhyloCraft 平台使用指南：</b><br><br>"
            "1. <b>中央大白板</b>：整合標準生信模塊流水線，各卡片代表一個分析節點，支援單步執行、參數調整與旁路跳過。<br>"
            "2. <b>左側工具箱</b>：依類別展示生信工具模塊（輸入、比對、修剪、模型、建樹、定年、檢視器），點擊可聚焦畫布對應模塊。<br>"
            "3. <b>上方功能表與捷徑列</b>：可開啟專案、切換至演化樹製圖工作室 (Tree Explorer) 或多重比對檢視器 (Align Explorer)。<br>"
            "4. <b>實驗日誌 (ELN)</b>：分析完成後可自動編譯含方法學草稿與圖表之完整實驗紀錄。"
        )
        QMessageBox.information(self, "說明文件 (User Guide & Help)", msg)

    def show_bug_report_dialog(self):
        QMessageBox.information(
            self, "問題回報 (Report Issue)",
            "如在使用過程中遇到非預期錯誤或有新功能建議，歡迎至 GitHub 儲存庫提交 Issue，"
            "或透過電子實驗日誌 (ELN) 導出完整日誌以供除錯分析。"
        )

    def show_updates_dialog(self):
        QMessageBox.information(
            self, "檢查更新 (Check Updates)",
            "<b>目前核心程式庫狀態：</b><br>"
            "• IQ-TREE: 已就緒 (bin/iqtree3.exe)<br>"
            "• MAFFT: 已就緒 (bin/mafft-win)<br>"
            "• trimAl: 已就緒 (bin/trimal.exe)<br>"
            "• FastTree: 已就緒 (bin/fasttree.exe)<br><br>"
            "所有二進位分析引擎均為本機獨立封裝，離線環境可全功能順暢運行。"
        )

    def show_ai_consult_dialog(self):
        QMessageBox.information(
            self, "生信演化諮詢 (Ask Phylo-AI)",
            "<b>演化分析常見建議：</b><br><br>"
            "• <b>位點修剪</b>：若物種親緣關係相近，建議使用 automated1 啟發式；若散布較遠且有大量 Insertions/Deletions，可切換為 gappyout。<br>"
            "• <b>模型選擇</b>：蛋白質序列建議包含經驗替換矩陣 (如 LG, JTT, WAG)，核酸編碼序列建議開啟 FreeRate (+R) 或 Gamma (+G4) 異質率。<br>"
            "• <b>建樹支撐率</b>：期刊發表建議採 1000 次 UFBoot (支撐率 >= 95% 為高可信) 與 1000 次 SH-aLRT (>= 80% 為高可信)。"
        )

    def closeEvent(self, event):
        for tab in [
            self.workstation_tab,
            self.pipeline_tab,
            self.alignment_tab,
            self.trimming_tab,
            self.model_test_tab,
            self.tree_tab,
            self.tools_tab,
        ]:
            worker = getattr(tab, "worker", None)
            if worker and worker.isRunning():
                if hasattr(worker, "cancel"):
                    worker.cancel()
                worker.wait(800)
            check_w = getattr(tab, "check_worker", None)
            if check_w and check_w.isRunning():
                if hasattr(check_w, "cancel"):
                    check_w.cancel()
                check_w.terminate()
                check_w.wait(300)
            down_w = getattr(tab, "download_worker", None)
            if down_w and down_w.isRunning():
                if hasattr(down_w, "cancel"):
                    down_w.cancel()
                down_w.terminate()
                down_w.wait(300)
        event.accept()
