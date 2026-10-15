from pathlib import Path
from Bio import SeqIO
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QMessageBox,
    QFrame,
    QScrollArea,
    QSplitter,
)
from PySide6.QtCore import QThread, Signal, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from src.config import OUTPUT_DIR, DATA_DIR
from src.core.runners.iqtree_runner import IQTreeRunner, IQTreeResult
from src.ui.widgets.log_viewer import LogViewer


class IQTreeWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(IQTreeResult)

    def __init__(
        self,
        in_p: str,
        prefix_p: str,
        model: str,
        bootstrap: int,
        alrt: int,
        threads: str,
        partition_f: str | None,
        date_file: str | None = None,
        date_root: str | None = None,
        date_ci: int = 100,
        date_outlier: float | None = None,
    ):
        super().__init__()
        self.in_p = in_p
        self.prefix_p = prefix_p
        self.model = model
        self.bootstrap = bootstrap
        self.alrt = alrt
        self.threads = threads
        self.partition_f = partition_f
        self.date_file = date_file
        self.date_root = date_root
        self.date_ci = date_ci
        self.date_outlier = date_outlier
        self.runner = IQTreeRunner()

    def cancel(self):
        self.runner.cancel()

    def run(self):
        res = self.runner.run_inference(
            self.in_p,
            self.prefix_p,
            model=self.model,
            bootstrap=self.bootstrap,
            alrt=self.alrt,
            threads=self.threads,
            partition_file=self.partition_f if self.partition_f else None,
            date_file=self.date_file if self.date_file else None,
            date_root=self.date_root if self.date_root else None,
            date_ci=self.date_ci,
            date_outlier=self.date_outlier,
            log_callback=self.log_signal.emit,
        )
        self.finished_signal.emit(res)


class TreeTab(QWidget):
    """
    系統發育樹推論分頁 (IQ-TREE 2 Phylogenetic Inference)
    支援分區模型 (Partitioned Analysis) 與 LSD2 分子鐘時間樹定年 (Molecular Clock TimeTree)。
    """

    view_tree_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.worker: IQTreeWorker | None = None
        self.last_tree_file: str = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Form Scroll Area (Protects all inputs from squishing on small/scaled screens)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("background: transparent;")

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)

        # 0. Pipeline Breadcrumb Header (Clear Cross-Step Flow)
        pipeline_strip = QFrame()
        pipeline_strip.setStyleSheet("""
            QFrame {
                background-color: #F1F5F9;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 5px 12px;
            }
        """)
        ps_layout = QHBoxLayout(pipeline_strip)
        ps_layout.setContentsMargins(2, 2, 2, 2)
        ps_lbl = QLabel(
            "<span style='color:#64748B;'>① 序列清洗</span> ➔ "
            "<span style='color:#64748B;'>② 多序列比對 (MAFFT)</span> ➔ "
            "<span style='color:#64748B;'>③ 比對位點修剪 (trimAl)</span> ➔ "
            "<span style='color:#64748B;'>④ 模型評選</span> ➔ "
            "<span style='color:#0F766E; font-weight:bold; background-color:#CCFBF1; padding:3px 8px; border-radius:4px; border:1px solid #99F6E4;'>⑤ 系統發育建樹 (當前)</span> ➔ "
            "<span style='color:#64748B;'>⑥ 演化樹檢視</span>"
        )
        ps_lbl.setStyleSheet("font-size: 11px;")
        ps_layout.addWidget(ps_lbl)
        ps_layout.addStretch()
        form_layout.addWidget(pipeline_strip)

        # 1. Header Box (Modern Studio Header)
        header_box = QFrame()
        header_box.setStyleSheet("background-color: #FFFFFF; border-radius: 6px; padding: 10px 14px; border: 1px solid #CBD5E1;")
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(0, 0, 0, 0)

        t_vbox = QVBoxLayout()
        t_vbox.setSpacing(2)

        title_row = QHBoxLayout()
        h_title = QLabel("<b>🌳 系統發育樹推論與分子鐘定年 (Phylogenetic Inference & TimeTree)</b>")
        h_title.setStyleSheet("color: #0F172A; font-size: 14px;")
        title_row.addWidget(h_title)

        mode_badge = QLabel("🛠️ 獨立單工模式")
        mode_badge.setStyleSheet("color: #0F766E; background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 1px 8px; font-size: 10px; font-weight: bold;")
        title_row.addWidget(mode_badge)
        title_row.addStretch()
        t_vbox.addLayout(title_row)

        h_sub = QLabel("IQ-TREE 2 最大概似法建樹引擎，支援 UFBoot2 / SH-aLRT 雙重檢定、多基因分區與 LSD2 地質定年；免專案檔直接速算")
        h_sub.setStyleSheet("color: #64748B; font-size: 11px;")
        t_vbox.addWidget(h_sub)
        h_layout.addLayout(t_vbox, 1)

        info_btn = QLabel("💡 建樹與定年指引")
        info_btn.setStyleSheet("color: #008287; background-color: #F1F5F9; padding: 4px 10px; border-radius: 12px; font-size: 11px; border: 1px solid #CBD5E1; font-weight: 500;")
        info_btn.setToolTip(
            "IQ-TREE 是學術界公認最精確高效的最大概似法（Maximum Likelihood）演化樹工具。\n"
            "內建 ModelFinder 自動挑選 BIC 最優解；支援多基因分區模型（Partitioned Model），\n"
            "並整合 LSD2（Least-Squares Dating）演算法，可結合化石或採樣時間產生帶有絕對地質年代的時間樹（TimeTree）。"
        )
        h_layout.addWidget(info_btn)
        form_layout.addWidget(header_box)

        # 1.1 Dynamic Guidance & Source Banner (明確跨步驟引導)
        self.source_banner = QFrame()
        self.source_banner.setStyleSheet("""
            QFrame {
                background-color: #EFF6FF;
                border: 1px solid #BFDBFE;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        sb_layout = QHBoxLayout(self.source_banner)
        sb_layout.setContentsMargins(6, 4, 6, 4)
        self.source_label = QLabel(
            "<b>💡 步驟指引：</b>若您已於前置步驟（如 trimAl 修剪或模型評選）完成分析，序列檔案與最適模型會自動於此載入；"
            "您只需確認下方參數後，直接點擊<b>「▶ 開始構建演化樹」</b>即可一鍵推論！"
        )
        self.source_label.setStyleSheet("color: #1E40AF; font-size: 11px;")
        sb_layout.addWidget(self.source_label)
        form_layout.addWidget(self.source_banner)

        # 2. File setup (Clean Grid Layout)
        file_box = QGroupBox("步驟 1：比對序列與分區設定 (Files & Partitions)")
        f_grid = QGridLayout(file_box)
        f_grid.setContentsMargins(12, 14, 12, 12)
        f_grid.setHorizontalSpacing(10)
        f_grid.setVerticalSpacing(8)

        # Row 0: 比對序列檔
        lbl_in = QLabel("比對序列檔:")
        self.in_edit = QLineEdit()
        self.in_edit.setMinimumHeight(28)
        self.in_edit.setPlaceholderText("請選取或拖曳比對/修剪後之 FASTA 或超矩陣檔案...")
        in_btn = QPushButton("瀏覽 (Browse)...")
        in_btn.setFixedHeight(28)
        in_btn.setFixedWidth(115)
        in_btn.clicked.connect(self.browse_input)
        sample_btn = QPushButton("載入範例資料")
        sample_btn.setFixedHeight(28)
        sample_btn.setFixedWidth(115)
        sample_btn.setToolTip("載入內建靈長類 Cytb 基因測試序列")
        sample_btn.clicked.connect(self.load_sample)
        f_grid.addWidget(lbl_in, 0, 0)
        f_grid.addWidget(self.in_edit, 0, 1)
        f_grid.addWidget(in_btn, 0, 2)
        f_grid.addWidget(sample_btn, 0, 3)

        # Row 1: 輸出檔名前綴
        lbl_out = QLabel("輸出檔名前綴:")
        self.out_edit = QLineEdit(str(OUTPUT_DIR / "my_tree"))
        self.out_edit.setMinimumHeight(28)
        out_btn = QPushButton("更改位置...")
        out_btn.setFixedHeight(28)
        out_btn.setFixedWidth(115)
        out_btn.clicked.connect(self.browse_output)
        open_dir_btn = QPushButton("開啟資料夾")
        open_dir_btn.setFixedHeight(28)
        open_dir_btn.setFixedWidth(115)
        open_dir_btn.clicked.connect(self.open_output_dir)
        f_grid.addWidget(lbl_out, 1, 0)
        f_grid.addWidget(self.out_edit, 1, 1)
        f_grid.addWidget(out_btn, 1, 2)
        f_grid.addWidget(open_dir_btn, 1, 3)

        # Row 2: 分區模型檔
        lbl_part = QLabel("分區模型檔 (選填):")
        self.part_edit = QLineEdit()
        self.part_edit.setMinimumHeight(28)
        self.part_edit.setPlaceholderText("選填: 多基因超矩陣之 NEXUS/RAxML 分區檔 (若由超矩陣分頁跳轉會自動填入)")
        part_btn = QPushButton("瀏覽 (Browse)...")
        part_btn.setFixedHeight(28)
        part_btn.setFixedWidth(115)
        part_btn.clicked.connect(self.browse_partition)
        clear_part_btn = QPushButton("清除分區")
        clear_part_btn.setFixedHeight(28)
        clear_part_btn.setFixedWidth(115)
        clear_part_btn.setToolTip("清空分區檔案路徑")
        clear_part_btn.clicked.connect(lambda: self.part_edit.clear())
        f_grid.addWidget(lbl_part, 2, 0)
        f_grid.addWidget(self.part_edit, 2, 1)
        f_grid.addWidget(part_btn, 2, 2)
        f_grid.addWidget(clear_part_btn, 2, 3)

        f_grid.setColumnStretch(1, 1)
        form_layout.addWidget(file_box)

        # 3. Parameters
        param_box = QGroupBox("步驟 2：演化模型與統計檢驗設定 (IQ-TREE Parameters)")
        p_layout = QHBoxLayout(param_box)
        p_layout.setContentsMargins(12, 14, 12, 12)
        p_layout.setSpacing(10)

        p_layout.addWidget(QLabel("取代模式:"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumHeight(28)
        self.model_combo.setEditable(True)
        self.model_combo.addItems([
            "MFP (ModelFinder 自動檢驗 88+ 種模式並選出 BIC 最優解)",
            "GTR+G+I (核酸標準全參數模型)",
            "HKY+G (快速核酸模型)",
            "JC (最簡 Jukes-Cantor 模型)",
            "WAG+G+I (蛋白質通用模型)",
            "JTT+G+I (蛋白質常用模型)",
            "LG+G+I (高精確蛋白質模型)",
        ])
        p_layout.addWidget(self.model_combo, 2)

        p_layout.addWidget(QLabel("極速拔靴 (UFBoot):"))
        self.boot_spin = QSpinBox()
        self.boot_spin.setMinimumHeight(28)
        self.boot_spin.setRange(0, 10000)
        self.boot_spin.setValue(1000)
        self.boot_spin.setSingleStep(500)
        self.boot_spin.setToolTip("重複抽樣檢驗次數，建議維持 1000 次（值 ≥ 70% 代表分支可信）")
        p_layout.addWidget(self.boot_spin)

        p_layout.addWidget(QLabel("SH-aLRT 檢驗:"))
        self.alrt_spin = QSpinBox()
        self.alrt_spin.setMinimumHeight(28)
        self.alrt_spin.setRange(0, 10000)
        self.alrt_spin.setValue(1000)
        self.alrt_spin.setSingleStep(500)
        self.alrt_spin.setToolTip("SH-aLRT 似然比檢驗次數（可與 UFBoot 同步執行雙重驗證）")
        p_layout.addWidget(self.alrt_spin)

        p_layout.addWidget(QLabel("執行緒:"))
        self.thread_combo = QComboBox()
        self.thread_combo.setMinimumHeight(28)
        self.thread_combo.addItems(["AUTO", "1", "2", "4", "8", "16"])
        p_layout.addWidget(self.thread_combo)

        form_layout.addWidget(param_box)

        # 4. LSD2 Molecular Clock Dating Group (Clean Grid & Symmetrical Alignment)
        dating_box = QGroupBox("步驟 3：LSD2 分子鐘定年與時間樹構建 (TimeTree Dating - Optional)")
        d_layout = QVBoxLayout(dating_box)
        d_layout.setContentsMargins(12, 12, 12, 12)
        d_layout.setSpacing(8)

        self.date_enable_cb = QCheckBox("啟用 LSD2 分子鐘時間樹定年 (Reconstruct TimeTree)")
        self.date_enable_cb.setToolTip("整合 LSD2 演算法，根據化石校準或採樣時間將分枝長度轉換為真實時間（百萬年前 Mya / 年）")
        self.date_enable_cb.toggled.connect(self.on_dating_toggled)
        d_layout.addWidget(self.date_enable_cb)

        self.dating_opts_widget = QWidget()
        dow_grid = QGridLayout(self.dating_opts_widget)
        dow_grid.setContentsMargins(0, 4, 0, 0)
        dow_grid.setHorizontalSpacing(10)
        dow_grid.setVerticalSpacing(8)

        # Row 0: 校準檔 (Date File)
        lbl_date = QLabel("校準檔 (Date File):")
        self.date_file_edit = QLineEdit()
        self.date_file_edit.setMinimumHeight(28)
        self.date_file_edit.setPlaceholderText("包含物種採樣時間或化石校準之文字檔 (如 TaxonName 0 或 mrca(A,B) min max)...")
        df_btn = QPushButton("瀏覽 (Browse)...")
        df_btn.setFixedHeight(28)
        df_btn.setFixedWidth(115)
        df_btn.clicked.connect(self.browse_date_file)

        gen_tpl_btn = QPushButton("自動生成範本")
        gen_tpl_btn.setFixedHeight(28)
        gen_tpl_btn.setFixedWidth(115)
        gen_tpl_btn.setToolTip("根據目前序列自動擷取所有物種名稱，並產出標準 dates.txt 範本檔案")
        gen_tpl_btn.clicked.connect(self.generate_date_template)

        dow_grid.addWidget(lbl_date, 0, 0)
        dow_grid.addWidget(self.date_file_edit, 0, 1)
        dow_grid.addWidget(df_btn, 0, 2)
        dow_grid.addWidget(gen_tpl_btn, 0, 3)
        dow_grid.setColumnStretch(1, 1)

        # Row 1: 參數整合列 (根年代 / 置信抽樣 / 離群值)
        param_widget = QWidget()
        pw_layout = QHBoxLayout(param_widget)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        pw_layout.setSpacing(16)

        pw_layout.addWidget(QLabel("根年代 (--date-root):"))
        self.date_root_edit = QLineEdit()
        self.date_root_edit.setMinimumHeight(28)
        self.date_root_edit.setPlaceholderText("選填: 如 1950 或 65.0 (Mya)")
        self.date_root_edit.setFixedWidth(160)
        pw_layout.addWidget(self.date_root_edit)

        pw_layout.addWidget(QLabel("置信抽樣 (--date-ci):"))
        self.date_ci_spin = QSpinBox()
        self.date_ci_spin.setMinimumHeight(28)
        self.date_ci_spin.setRange(0, 1000)
        self.date_ci_spin.setValue(100)
        self.date_ci_spin.setFixedWidth(90)
        pw_layout.addWidget(self.date_ci_spin)

        pw_layout.addWidget(QLabel("離群值 Z-Score:"))
        self.date_outlier_spin = QDoubleSpinBox()
        self.date_outlier_spin.setMinimumHeight(28)
        self.date_outlier_spin.setRange(0.0, 10.0)
        self.date_outlier_spin.setValue(3.0)
        self.date_outlier_spin.setSingleStep(0.5)
        self.date_outlier_spin.setFixedWidth(90)
        pw_layout.addWidget(self.date_outlier_spin)

        pw_layout.addStretch(1)
        dow_grid.addWidget(param_widget, 1, 1, 1, 3)

        d_layout.addWidget(self.dating_opts_widget)
        self.dating_opts_widget.setVisible(False)  # Collapsed by default to maximize visible canvas space
        form_layout.addWidget(dating_box)

        # 5. Step 4: Execution Actions & Next Steps
        action_box = QGroupBox("步驟 4：極速推論與樹檢視銜接 (Run & View Tree)")
        ab_layout = QVBoxLayout(action_box)
        ab_layout.setContentsMargins(12, 14, 12, 12)
        ab_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.run_btn = QPushButton("▶ 開始構建演化樹 (Run IQ-TREE)")
        self.run_btn.setObjectName("primary_button")
        self.run_btn.setFixedHeight(36)
        self.run_btn.setMinimumWidth(180)
        self.run_btn.clicked.connect(self.start_iqtree)
        btn_row.addWidget(self.run_btn, 3)

        self.cancel_btn = QPushButton("■ 停止 (Stop)")
        self.cancel_btn.setObjectName("danger_button")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setMinimumWidth(85)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_iqtree)
        btn_row.addWidget(self.cancel_btn, 1)

        self.view_btn = QPushButton("🌲 檢視演化樹 (View Tree) ➔")
        self.view_btn.setObjectName("success_button")
        self.view_btn.setFixedHeight(36)
        self.view_btn.setEnabled(False)
        self.view_btn.setToolTip("建樹完成後，點擊可直接於演化樹製圖工坊中進行定根、支持度數值著色與發表級圖檔匯出")
        self.view_btn.clicked.connect(self.open_tree_viewer)
        btn_row.addWidget(self.view_btn, 2)

        ab_layout.addLayout(btn_row)

        # Dynamic Result Banner
        self.result_banner = QFrame()
        self.result_banner.setStyleSheet("background-color: #ECFDF5; border: 1px solid #6EE7B7; border-radius: 6px; padding: 8px 12px;")
        rb_layout = QHBoxLayout(self.result_banner)
        rb_layout.setContentsMargins(4, 2, 4, 2)
        self.result_label = QLabel("✓ 系統發育建樹已完成！可點擊上方綠色按鈕直接於演化樹製圖工坊開啟。")
        self.result_label.setStyleSheet("color: #065F46; font-size: 11px; font-weight: bold;")
        rb_layout.addWidget(self.result_label)
        self.result_banner.setVisible(False)
        ab_layout.addWidget(self.result_banner)

        form_layout.addWidget(action_box)
        form_layout.addStretch()

        self.scroll.setWidget(form_container)

        # Splitter hosting Form Scroll Area + Collapsible Log Viewer
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet("""
            QSplitter::handle:vertical {
                height: 6px;
                background-color: #E2E8F0;
                border-top: 1px solid #CBD5E1;
                border-bottom: 1px solid #CBD5E1;
                margin: 0px 4px;
                border-radius: 2px;
            }
            QSplitter::handle:vertical:hover {
                background-color: #008287;
            }
        """)
        splitter.addWidget(self.scroll)

        self.log_viewer = LogViewer("IQ-TREE 即時日誌 (Console Output)")
        splitter.addWidget(self.log_viewer)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    def on_dating_toggled(self, checked: bool):
        self.dating_opts_widget.setVisible(checked)

    def browse_date_file(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "選取時間校準檔案", "", "文字檔案 (*.txt *.date);;所有檔案 (*)"
        )
        if fp:
            self.date_file_edit.setText(fp)

    def generate_date_template(self):
        in_f = self.in_edit.text().strip()
        if not in_f or not Path(in_f).exists():
            QMessageBox.warning(self, "警告", "請先選取序列檔案，系統才能為您擷取所有物種名稱。")
            return

        try:
            with open(in_f, "r", encoding="utf-8", errors="replace") as handle:
                records = list(SeqIO.parse(handle, "fasta"))
            if not records:
                with open(in_f, "r", encoding="utf-8", errors="replace") as handle:
                    records = list(SeqIO.parse(handle, "phylip"))
            taxa = sorted([r.id for r in records])
        except Exception:
            taxa = []

        if not taxa:
            QMessageBox.warning(self, "錯誤", "無法從指定的檔案中解析序列物種名稱。")
            return

        p = Path(in_f)
        tpl_path = p.parent / f"{p.stem}_dates_template.txt"

        lines = [
            "# IQ-TREE LSD2 日期與化石校準設定檔 (Date & Calibration File)",
            "# 格式說明:",
            "# 1. 末端物種時間 (Tip Date): 物種名稱 年代 (如現生物種為 0 或現代年分 2024)",
            "# 2. 節點化石校準 (MRCA Calibration): mrca(物種A,物種B) 下限 上限 (如 mrca(A,B) 60 75)",
            "# -------------------------------------------------------------",
        ]
        for t in taxa:
            lines.append(f"{t} 0")

        if len(taxa) >= 2:
            lines.append("")
            lines.append(f"# [範例] 節點化石校準 (請依實際研究修改物種與年代區間):")
            lines.append(f"# mrca({taxa[0]},{taxa[1]}) 25.0 32.0")

        tpl_path.write_text("\n".join(lines), encoding="utf-8")
        self.date_file_edit.setText(str(tpl_path))

        QMessageBox.information(
            self,
            "校準範本已生成",
            f"已成功為 {len(taxa)} 個物種生成標準定年校準檔。\n\n"
            f"儲存位置:\n{tpl_path}\n\n"
            f"所有物種預設年代為 0（代表現代 Extant）。若需添加化石校準約束，\n"
            f"可直接以記事本打開該檔案並依照註解添加 mrca(A, B) 年代區間。",
        )

    def set_input_file(self, file_path: str, source: str = "trimAl 比對修剪"):
        if not file_path:
            return
        self.in_edit.setText(file_path)
        p = Path(file_path)
        self.out_edit.setText(str(p.parent / f"{p.stem}_tree"))
        if hasattr(self, "source_banner") and hasattr(self, "source_label"):
            self.source_banner.setStyleSheet("""
                QFrame {
                    background-color: #ECFDF5;
                    border: 1px solid #6EE7B7;
                    border-radius: 6px;
                    padding: 8px 12px;
                }
            """)
            self.source_label.setText(
                f"<b>✓ 已自動從【{source}】載入比對序列：</b><code style='color:#065F46; font-weight:bold;'>{p.name}</code><br>"
                f"<span style='color:#047857;'>👉 系統預設採用 <b>MFP (ModelFinder Plus)</b> 自動評選最佳模型！請確認下方參數後，直接點擊<b>「▶ 開始構建演化樹」</b>即可！</span>"
            )
            self.source_label.setStyleSheet("color: #065F46; font-size: 11px;")
        if hasattr(self, "scroll") and self.scroll:
            self.scroll.verticalScrollBar().setValue(0)

    def set_model_and_input(self, model: str, input_file: str = "", source: str = "模型評選 (ModelFinder)"):
        if input_file:
            self.in_edit.setText(input_file)
            p = Path(input_file)
            self.out_edit.setText(str(p.parent / f"{p.stem}_tree"))
        if model:
            found_idx = -1
            for i in range(self.model_combo.count()):
                text = self.model_combo.itemText(i)
                if text.startswith(model) or text.split()[0] == model:
                    found_idx = i
                    break
            if found_idx >= 0:
                self.model_combo.setCurrentIndex(found_idx)
            else:
                self.model_combo.insertItem(0, f"{model} (⭐ ModelFinder 推薦模型)")
                self.model_combo.setCurrentIndex(0)

        if hasattr(self, "source_banner") and hasattr(self, "source_label"):
            p_name = Path(input_file).name if input_file else "已就緒"
            self.source_banner.setStyleSheet("""
                QFrame {
                    background-color: #ECFDF5;
                    border: 1px solid #6EE7B7;
                    border-radius: 6px;
                    padding: 8px 12px;
                }
            """)
            self.source_label.setText(
                f"<b>✓ 已成功從【{source}】載入序列並套用最優替代模型！</b><br>"
                f"• 序列檔案：<code style='color:#065F46; font-weight:bold;'>{p_name}</code> ｜ "
                f"• 最適模型：<code style='color:#065F46; font-weight:bold;'>{model}</code><br>"
                f"<span style='color:#047857;'>👉 最佳模型已就緒！請直接點擊下方<b>「▶ 開始構建演化樹 (Run IQ-TREE)」</b>即可開始進行最大概似法推論。</span>"
            )
            self.source_label.setStyleSheet("color: #065F46; font-size: 11px;")
        if hasattr(self, "scroll") and self.scroll:
            self.scroll.verticalScrollBar().setValue(0)

    def browse_input(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "選取比對檔案", "", "比對檔案 (*.fasta *.fa *.phy *.nex);;所有檔案 (*)"
        )
        if fp:
            self.in_edit.setText(fp)
            p = Path(fp)
            self.out_edit.setText(str(p.parent / f"{p.stem}_iqtree"))

    def load_sample(self):
        sample = DATA_DIR / "primates_cytb.fasta"
        if sample.exists():
            self.in_edit.setText(str(sample))
            self.out_edit.setText(str(OUTPUT_DIR / "primates_iqtree"))

    def browse_output(self):
        fp, _ = QFileDialog.getSaveFileName(self, "指定輸出檔名前綴", self.out_edit.text())
        if fp:
            self.out_edit.setText(fp)

    def browse_partition(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "選取分區設定檔", "", "分區檔案 (*.txt *.nex *.partition);;所有檔案 (*)"
        )
        if fp:
            self.part_edit.setText(fp)

    def open_output_dir(self):
        out_f = self.out_edit.text().strip()
        folder = Path(out_f).parent if out_f else OUTPUT_DIR
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def start_iqtree(self):
        in_f = self.in_edit.text().strip()
        out_f = self.out_edit.text().strip()
        if not in_f or not Path(in_f).exists():
            QMessageBox.warning(self, "警告", "請先選取有效的比對序列檔案。")
            return

        model_raw = self.model_combo.currentText().strip()
        model = model_raw.split()[0] if "(" in model_raw else model_raw
        boot = self.boot_spin.value()
        alrt = self.alrt_spin.value()
        th_raw = self.thread_combo.currentText()
        th = "AUTO" if "AUTO" in th_raw else th_raw
        part = self.part_edit.text().strip()

        # Dating parameters
        is_dating = self.date_enable_cb.isChecked()
        df = self.date_file_edit.text().strip() if is_dating else None
        dr = self.date_root_edit.text().strip() if is_dating else None
        d_ci = self.date_ci_spin.value() if is_dating else 0
        d_outlier = self.date_outlier_spin.value() if is_dating else None

        if is_dating and not df:
            QMessageBox.warning(
                self, "缺少校準檔", "您已勾選啟用 LSD2 分子鐘定年，請指定時間校準檔或點選「自動生成校準範本」。"
            )
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("⏳ 正在推論演化樹中... (Computing IQ-TREE)")
        self.cancel_btn.setEnabled(True)
        self.view_btn.setEnabled(False)
        if hasattr(self, "result_banner"):
            self.result_banner.setVisible(False)
        self.log_viewer.clear_log()

        self.worker = IQTreeWorker(
            in_f,
            out_f,
            model,
            boot,
            alrt,
            th,
            part,
            date_file=df,
            date_root=dr,
            date_ci=d_ci,
            date_outlier=d_outlier,
        )
        self.worker.log_signal.connect(self.log_viewer.append_log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def cancel_iqtree(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.run_btn.setText("▶ 開始構建演化樹 (Run IQ-TREE)")
            self.run_btn.setEnabled(True)

    def on_finished(self, res: IQTreeResult):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶ 重新構建演化樹 (Run IQ-TREE)")
        self.cancel_btn.setEnabled(False)
        if res.success:
            self.last_tree_file = res.timetree_file if res.timetree_file else res.tree_file
            self.view_btn.setEnabled(True)

            if hasattr(self, "result_banner"):
                self.result_banner.setVisible(True)
                self.result_label.setText(
                    f"✓ 演化樹構建成功！產出：{Path(self.last_tree_file).name} ｜ 可直接點選上方綠色按鈕前往「演化樹檢視與製圖」。"
                )

            if res.timetree_file:
                self.view_btn.setText("🌲 立即檢視分子鐘時間樹 (View TimeTree) ➔")
                QMessageBox.information(
                    self,
                    "分子鐘定年與建樹成功",
                    f"IQ-TREE 2 與 LSD2 分子鐘定年完成。\n\n"
                    f"• 時間樹檔案 (TimeTree): {Path(res.timetree_file).name}\n"
                    f"• 最佳替代模型: {res.best_model or '已寫入報告'}\n"
                    f"• 推算分子演化速率: {res.rate_estimate or '請見 LSD 報告'} subst/site\n"
                    f"• 根節點年齡 (tMRCA): {res.tmrca_estimate or '推算完成'}\n\n"
                    f"可點選上方「🌲 立即檢視分子鐘時間樹」直接繪製帶有時間刻度的論文圖表！",
                )
            else:
                self.view_btn.setText("🌲 立即檢視演化樹 (View Tree) ➔")
                QMessageBox.information(
                    self,
                    "建樹完成",
                    f"IQ-TREE 2 建樹完成。\n\n"
                    f"• 演化樹檔案: {Path(res.tree_file).name}\n"
                    f"• 最佳模型: {res.best_model or '已寫入報告檔'}\n\n"
                    f"可點選上方「🌲 立即檢視演化樹」進行定根、支持度著色與發表級製圖！",
                )
        else:
            self.run_btn.setText("▶ 開始構建演化樹 (Run IQ-TREE)")
            if hasattr(self, "result_banner"):
                self.result_banner.setVisible(False)
            QMessageBox.critical(self, "建樹錯誤", f"IQ-TREE 2 執行失敗:\n{res.message}")

    def open_tree_viewer(self):
        if self.last_tree_file:
            self.view_tree_requested.emit(self.last_tree_file)
