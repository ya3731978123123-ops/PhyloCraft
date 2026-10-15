from pathlib import Path
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
    QDoubleSpinBox,
    QCheckBox,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from src.config import OUTPUT_DIR, DATA_DIR
from src.core.runners.trimal_runner import TrimalRunner
from src.ui.widgets.log_viewer import LogViewer


class TrimmingWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, in_p: str, out_p: str, method: str, gt: float, st: float, html: bool):
        super().__init__()
        self.in_p = in_p
        self.out_p = out_p
        self.method = method
        self.gt = gt
        self.st = st
        self.html = html
        self.runner = TrimalRunner()

    def cancel(self):
        self.runner.cancel()

    def run(self):
        ok, msg = self.runner.run_trimming(
            self.in_p,
            self.out_p,
            method=self.method,
            gap_threshold=self.gt,
            similarity_threshold=self.st,
            save_html=self.html,
            log_callback=self.log_signal.emit,
        )
        self.finished_signal.emit(ok, msg)


class TrimmingTab(QWidget):
    """
    Dedicated trimAl Trimming Tab with Folder Launcher & Direct MSA View
    """

    view_msa_requested = Signal(str)
    test_model_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.worker: TrimmingWorker | None = None
        self.last_trimmed_file: str = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Top Standalone Header Banner
        header_box = QFrame()
        header_box.setStyleSheet("background-color: #FFFFFF; border-radius: 6px; padding: 10px 14px; border: 1px solid #CBD5E1;")
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(0, 0, 0, 0)

        t_vbox = QVBoxLayout()
        t_vbox.setSpacing(2)

        title_row = QHBoxLayout()
        h_title = QLabel("<b>✂️ 比對修剪與品質過濾 (Alignment Trimming - trimAl)</b>")
        h_title.setStyleSheet("color: #0F172A; font-size: 14px;")
        title_row.addWidget(h_title)

        mode_badge = QLabel("🛠️ 獨立單工模式")
        mode_badge.setStyleSheet("color: #0F766E; background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 1px 8px; font-size: 10px; font-weight: bold;")
        title_row.addWidget(mode_badge)
        title_row.addStretch()
        t_vbox.addLayout(title_row)

        h_sub = QLabel("trimAl 自動過濾長空缺 (Gap) 與低保守雜訊位點，大幅提升後續系統發育樹拓撲訊噪比；支援 automated1 啟發式 ML 優化")
        h_sub.setStyleSheet("color: #64748B; font-size: 11px;")
        t_vbox.addWidget(h_sub)
        h_layout.addLayout(t_vbox, 1)

        info_btn = QLabel("💡 修剪指引")
        info_btn.setStyleSheet("color: #008287; background-color: #F1F5F9; padding: 4px 10px; border-radius: 12px; font-size: 11px; border: 1px solid #CBD5E1; font-weight: 500;")
        info_btn.setToolTip(
            "trimAl 能過濾比對中過度混亂或充滿空缺（Gap）的位點，提升演化樹訊噪比。\n"
            "建議使用「automated1」，這是針對 ML 系統發育樹所設計的最佳啟發式演算法。"
        )
        h_layout.addWidget(info_btn)
        layout.addWidget(header_box)

        # Step 1: File setup (Clean Grid Layout)
        file_box = QGroupBox("步驟 1：輸入與輸出檔案 (Files)")
        f_grid = QGridLayout(file_box)
        f_grid.setContentsMargins(12, 14, 12, 12)
        f_grid.setHorizontalSpacing(10)
        f_grid.setVerticalSpacing(8)

        # Row 0: 已比對之 FASTA 檔
        lbl_in = QLabel("已比對之 FASTA 檔:")
        lbl_in.setStyleSheet("font-weight: 600; color: #334155;")
        self.in_edit = QLineEdit()
        self.in_edit.setMinimumHeight(30)
        self.in_edit.setPlaceholderText("請選取或拖曳已比對完成之序列檔案 (*.fasta, *.fa)...")
        in_btn = QPushButton("瀏覽 (Browse)...")
        in_btn.setFixedHeight(30)
        in_btn.setFixedWidth(115)
        in_btn.clicked.connect(self.browse_input)
        sample_btn = QPushButton("💡 載入範例資料")
        sample_btn.setFixedHeight(30)
        sample_btn.setFixedWidth(120)
        sample_btn.clicked.connect(self.load_sample)
        f_grid.addWidget(lbl_in, 0, 0)
        f_grid.addWidget(self.in_edit, 0, 1)
        f_grid.addWidget(in_btn, 0, 2)
        f_grid.addWidget(sample_btn, 0, 3)

        # Row 1: 修剪後儲存路徑
        lbl_out = QLabel("修剪後儲存路徑:")
        lbl_out.setStyleSheet("font-weight: 600; color: #334155;")
        self.out_edit = QLineEdit()
        self.out_edit.setMinimumHeight(30)
        out_btn = QPushButton("更改位置...")
        out_btn.setFixedHeight(30)
        out_btn.setFixedWidth(115)
        out_btn.clicked.connect(self.browse_output)
        open_dir_btn = QPushButton("開啟資料夾")
        open_dir_btn.setFixedHeight(30)
        open_dir_btn.setFixedWidth(120)
        open_dir_btn.clicked.connect(self.open_output_dir)
        f_grid.addWidget(lbl_out, 1, 0)
        f_grid.addWidget(self.out_edit, 1, 1)
        f_grid.addWidget(out_btn, 1, 2)
        f_grid.addWidget(open_dir_btn, 1, 3)

        f_grid.setColumnStretch(1, 1)
        layout.addWidget(file_box)

        # Step 2: Trimming Methods
        method_box = QGroupBox("步驟 2：修剪策略與參數 (trimAl Options)")
        m_layout = QVBoxLayout(method_box)
        m_layout.setContentsMargins(12, 14, 12, 12)
        m_layout.setSpacing(10)

        m_row = QHBoxLayout()
        lbl_m = QLabel("修剪模式:")
        lbl_m.setStyleSheet("font-weight: 600; color: #334155;")
        m_row.addWidget(lbl_m)
        self.method_combo = QComboBox()
        self.method_combo.setMinimumHeight(30)
        self.method_combo.addItems([
            "automated1 (啟發式平衡修剪 - 針對 ML 建樹優化)",
            "gappyout (去除包含大量 Gap 缺損之位點)",
            "strict (嚴格模式 - 嚴格過濾低保守度位點)",
            "strictplus (極端嚴格 - 超保守過濾)",
            "custom (自訂 Gap 與 Similarity 閾值)",
        ])
        self.method_combo.currentIndexChanged.connect(self.on_method_changed)
        m_row.addWidget(self.method_combo, 1)
        m_layout.addLayout(m_row)

        # Custom thresholds
        self.thresh_row = QHBoxLayout()
        self.thresh_row.addWidget(QLabel("Gap 容忍比例 (-gt 0~1):"))
        self.gt_spin = QDoubleSpinBox()
        self.gt_spin.setMinimumHeight(28)
        self.gt_spin.setRange(0.0, 1.0)
        self.gt_spin.setSingleStep(0.05)
        self.gt_spin.setValue(0.8)
        self.gt_spin.setEnabled(False)
        self.thresh_row.addWidget(self.gt_spin)

        self.thresh_row.addWidget(QLabel("相似度閾值 (-st 0~1):"))
        self.st_spin = QDoubleSpinBox()
        self.st_spin.setMinimumHeight(28)
        self.st_spin.setRange(0.0, 1.0)
        self.st_spin.setSingleStep(0.001)
        self.st_spin.setValue(0.001)
        self.st_spin.setEnabled(False)
        self.thresh_row.addWidget(self.st_spin)

        self.html_cb = QCheckBox("產生視覺化 HTML 報告")
        self.html_cb.setChecked(True)
        self.thresh_row.addWidget(self.html_cb)
        self.thresh_row.addStretch()

        m_layout.addLayout(self.thresh_row)
        layout.addWidget(method_box)

        # Step 3: Execution Actions & Next Steps
        action_box = QGroupBox("步驟 3：極速執行與成果銜接 (Run & Next Steps)")
        ab_layout = QVBoxLayout(action_box)
        ab_layout.setContentsMargins(12, 14, 12, 12)
        ab_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.run_btn = QPushButton("▶ 開始位點修剪 (Run trimAl)")
        self.run_btn.setObjectName("primary_button")
        self.run_btn.setFixedHeight(34)
        self.run_btn.setMinimumWidth(180)
        self.run_btn.clicked.connect(self.start_trimming)
        btn_row.addWidget(self.run_btn, 3)

        self.cancel_btn = QPushButton("■ 停止 (Stop)")
        self.cancel_btn.setObjectName("danger_button")
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_trimming)
        btn_row.addWidget(self.cancel_btn, 1)

        self.view_msa_btn = QPushButton("🧬 檢視比對 (View MSA)")
        self.view_msa_btn.setFixedHeight(34)
        self.view_msa_btn.setEnabled(False)
        self.view_msa_btn.setToolTip("直接於 PhyloCraft 內建比對矩陣檢視器中檢驗修剪後的對齊位點")
        self.view_msa_btn.clicked.connect(self.open_msa_viewer)
        btn_row.addWidget(self.view_msa_btn, 2)

        self.to_model_btn = QPushButton("🔬 前往模型檢定 (ModelFinder) ➔")
        self.to_model_btn.setObjectName("primary_button")
        self.to_model_btn.setFixedHeight(34)
        self.to_model_btn.setEnabled(False)
        self.to_model_btn.setToolTip("一鍵將修剪後的高品質序列送往 ModelFinder 檢定最適替代模型")
        self.to_model_btn.clicked.connect(self.open_model_test)
        btn_row.addWidget(self.to_model_btn, 2)

        ab_layout.addLayout(btn_row)

        # Dynamic Result Banner
        self.result_banner = QFrame()
        self.result_banner.setStyleSheet("background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 4px 8px;")
        rb_layout = QHBoxLayout(self.result_banner)
        rb_layout.setContentsMargins(4, 2, 4, 2)
        self.result_label = QLabel("✓ 位點修剪已完成！可點擊上方按鈕直接檢視比對或前往模型檢定。")
        self.result_label.setStyleSheet("color: #0F766E; font-size: 11px; font-weight: bold;")
        rb_layout.addWidget(self.result_label)
        self.result_banner.setVisible(False)
        ab_layout.addWidget(self.result_banner)

        layout.addWidget(action_box)

        # Step 4: Collapsible Console Log
        self.log_viewer = LogViewer("trimAl 即時日誌 (Console Output)")
        layout.addWidget(self.log_viewer, 1)

    def on_method_changed(self):
        is_custom = "custom" in self.method_combo.currentText()
        self.gt_spin.setEnabled(is_custom)
        self.st_spin.setEnabled(is_custom)

    def browse_input(self):
        fp, _ = QFileDialog.getOpenFileName(self, "選取比對檔案", "", "FASTA 檔案 (*.fasta *.fa *.fas);;所有檔案 (*)")
        if fp:
            self.in_edit.setText(fp)
            p = Path(fp)
            self.out_edit.setText(str(p.parent / f"{p.stem}_trimmed.fasta"))

    def load_sample(self):
        sample = DATA_DIR / "primates_cytb.fasta"
        if sample.exists():
            self.in_edit.setText(str(sample))
            self.out_edit.setText(str(OUTPUT_DIR / "primates_trimmed.fasta"))

    def browse_output(self):
        fp, _ = QFileDialog.getSaveFileName(self, "儲存修剪檔案", self.out_edit.text(), "FASTA (*.fasta)")
        if fp:
            self.out_edit.setText(fp)

    def open_output_dir(self):
        out_f = self.out_edit.text().strip()
        folder = Path(out_f).parent if out_f else OUTPUT_DIR
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def start_trimming(self):
        in_f = self.in_edit.text().strip()
        out_f = self.out_edit.text().strip()
        if not in_f or not Path(in_f).exists():
            QMessageBox.warning(self, "警告", "請先選取有效的比對檔案。")
            return

        method = self.method_combo.currentText().split()[0]
        gt = self.gt_spin.value()
        st = self.st_spin.value()
        html = self.html_cb.isChecked()

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.view_msa_btn.setEnabled(False)
        self.log_viewer.clear_log()

        self.worker = TrimmingWorker(in_f, out_f, method, gt, st, html)
        self.worker.log_signal.connect(self.log_viewer.append_log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def cancel_trimming(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)

    def on_finished(self, success: bool, msg: str):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if success:
            self.last_trimmed_file = self.out_edit.text().strip()
            self.view_msa_btn.setEnabled(True)
            self.to_model_btn.setEnabled(True)
            if hasattr(self, "result_banner"):
                self.result_banner.setVisible(True)
                self.result_label.setText(
                    f"✓ 位點修剪成功！已生成：{Path(self.last_trimmed_file).name} ｜ 可直接於上方點擊「檢視比對」或「前往模型檢定」進行下一步。"
                )
            QMessageBox.information(
                self, "修剪完成", f"比對修剪順利完成！\n已儲存至: {Path(self.last_trimmed_file).name}\n可點選「檢視比對」或「模型檢定」進行下一步。"
            )
        else:
            if hasattr(self, "result_banner"):
                self.result_banner.setVisible(False)
            QMessageBox.critical(self, "修剪錯誤", f"trimAl 執行失敗:\n{msg}")

    def open_msa_viewer(self):
        if self.last_trimmed_file and Path(self.last_trimmed_file).exists():
            self.view_msa_requested.emit(self.last_trimmed_file)

    def open_model_test(self):
        if self.last_trimmed_file and Path(self.last_trimmed_file).exists():
            self.test_model_requested.emit(self.last_trimmed_file)
