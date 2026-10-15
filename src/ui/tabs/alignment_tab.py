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
    QCheckBox,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from src.config import DATA_DIR, OUTPUT_DIR
from src.core.runners.mafft_runner import MafftRunner
from src.ui.widgets.log_viewer import LogViewer


class AlignmentWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, input_fa: str, output_fa: str, algorithm: str, adjust_direction: bool):
        super().__init__()
        self.input_fa = input_fa
        self.output_fa = output_fa
        self.algorithm = algorithm
        self.adjust_direction = adjust_direction
        self.runner = MafftRunner()

    def cancel(self):
        self.runner.cancel()

    def run(self):
        ok, msg = self.runner.run_alignment(
            self.input_fa,
            self.output_fa,
            algorithm=self.algorithm,
            adjust_direction=self.adjust_direction,
            log_callback=self.log_signal.emit,
        )
        self.finished_signal.emit(ok, msg)


class AlignmentTab(QWidget):
    """
    Dedicated MAFFT Alignment Tab with Direct MSA Viewing & Folder Launcher
    """

    view_msa_requested = Signal(str)
    trim_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.worker: AlignmentWorker | None = None
        self.last_output_file: str = ""
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
        h_title = QLabel("<b>🧬 多重序列比對 (Multiple Sequence Alignment - MAFFT)</b>")
        h_title.setStyleSheet("color: #0F172A; font-size: 14px;")
        title_row.addWidget(h_title)

        mode_badge = QLabel("🛠️ 獨立單工模式")
        mode_badge.setStyleSheet("color: #0F766E; background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 1px 8px; font-size: 10px; font-weight: bold;")
        title_row.addWidget(mode_badge)
        title_row.addStretch()
        t_vbox.addLayout(title_row)

        h_sub = QLabel("調用 MAFFT 高速與高精確度同源位點對齊引擎，支援自動演算法切換與反向校正；無需專案檔，載入單檔即刻極速運算")
        h_sub.setStyleSheet("color: #64748B; font-size: 11px;")
        t_vbox.addWidget(h_sub)
        h_layout.addLayout(t_vbox, 1)

        info_btn = QLabel("💡 比對指引")
        info_btn.setStyleSheet("color: #008287; background-color: #F1F5F9; padding: 4px 10px; border-radius: 12px; font-size: 11px; border: 1px solid #CBD5E1; font-weight: 500;")
        info_btn.setToolTip(
            "MAFFT 是演化學廣泛使用的高速、高精度多重序列比對工具。\n"
            "建議使用「auto」，系統將自動依據序列數量與長度切換最適演算法；若序列可能包含反向互補鏈，請勾選「反向校正」。"
        )
        h_layout.addWidget(info_btn)
        layout.addWidget(header_box)

        # Step 1: File Setup (Clean Card Grid Layout)
        file_box = QGroupBox("步驟 1：輸入與輸出檔案 (Files)")
        f_grid = QGridLayout(file_box)
        f_grid.setContentsMargins(12, 14, 12, 12)
        f_grid.setHorizontalSpacing(10)
        f_grid.setVerticalSpacing(8)

        # Row 0: 輸入 FASTA 檔
        lbl_in = QLabel("輸入 FASTA 檔:")
        lbl_in.setStyleSheet("font-weight: 600; color: #334155;")
        self.in_edit = QLineEdit()
        self.in_edit.setMinimumHeight(30)
        self.in_edit.setPlaceholderText("請選取或拖曳未比對之 FASTA 檔案 (*.fasta, *.fa)...")
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

        # Row 1: 比對輸出路徑
        lbl_out = QLabel("比對輸出路徑:")
        lbl_out.setStyleSheet("font-weight: 600; color: #334155;")
        self.out_edit = QLineEdit(str(OUTPUT_DIR / "aligned.fasta"))
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

        # Step 2: Parameters
        param_box = QGroupBox("步驟 2：比對演算法策略 (MAFFT Parameters)")
        p_layout = QHBoxLayout(param_box)
        p_layout.setContentsMargins(12, 14, 12, 12)
        p_layout.setSpacing(12)

        lbl_strat = QLabel("演算法模式:")
        lbl_strat.setStyleSheet("font-weight: 600; color: #334155;")
        p_layout.addWidget(lbl_strat)
        self.strategy_combo = QComboBox()
        self.strategy_combo.setMinimumHeight(30)
        self.strategy_combo.addItems([
            "auto (自動依數據規模挑選最適模式)",
            "linsi (L-INS-i: 極高精準度，適用 <200 條序列)",
            "ginsi (G-INS-i: 全域全對齊精確模式)",
            "einsi (E-INS-i: 適用具有大型內部缺損/內含子之序列)",
            "fft-ns-2 (極速漸進式比對，適用巨量數據)",
        ])
        p_layout.addWidget(self.strategy_combo, 1)

        self.adjust_cb = QCheckBox("自動反向校正 (--adjustdirection)")
        self.adjust_cb.setToolTip("自動偵測並將反向互補（Reverse-complement）之序列翻轉為正確方向")
        self.adjust_cb.setChecked(False)
        p_layout.addWidget(self.adjust_cb)

        layout.addWidget(param_box)

        # Step 3: Execution Actions & Next Steps
        action_box = QGroupBox("步驟 3：極速執行與成果銜接 (Run & Next Steps)")
        ab_layout = QVBoxLayout(action_box)
        ab_layout.setContentsMargins(12, 14, 12, 12)
        ab_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.run_btn = QPushButton("▶ 開始多重比對 (Run MAFFT)")
        self.run_btn.setObjectName("primary_button")
        self.run_btn.setFixedHeight(34)
        self.run_btn.setMinimumWidth(180)
        self.run_btn.clicked.connect(self.start_alignment)
        btn_row.addWidget(self.run_btn, 3)

        self.cancel_btn = QPushButton("■ 停止 (Stop)")
        self.cancel_btn.setObjectName("danger_button")
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_alignment)
        btn_row.addWidget(self.cancel_btn, 1)

        self.view_msa_btn = QPushButton("🧬 檢視比對 (View MSA)")
        self.view_msa_btn.setFixedHeight(34)
        self.view_msa_btn.setEnabled(False)
        self.view_msa_btn.setToolTip("直接於 PhyloCraft 內建比對矩陣檢視器中開啟分析成果")
        self.view_msa_btn.clicked.connect(self.open_msa_viewer)
        btn_row.addWidget(self.view_msa_btn, 2)

        self.to_trim_btn = QPushButton("✂️ 前往修剪 (trimAl) ➔")
        self.to_trim_btn.setObjectName("primary_button")
        self.to_trim_btn.setFixedHeight(34)
        self.to_trim_btn.setEnabled(False)
        self.to_trim_btn.setToolTip("一鍵將此比對結果送往 trimAl 修剪雜訊位點")
        self.to_trim_btn.clicked.connect(self.open_trim)
        btn_row.addWidget(self.to_trim_btn, 2)

        ab_layout.addLayout(btn_row)

        # Dynamic Result Banner
        self.result_banner = QFrame()
        self.result_banner.setStyleSheet("background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 4px 8px;")
        rb_layout = QHBoxLayout(self.result_banner)
        rb_layout.setContentsMargins(4, 2, 4, 2)
        self.result_label = QLabel("✓ 多重比對已完成！可點擊上方按鈕直接檢視比對或前往修剪。")
        self.result_label.setStyleSheet("color: #0F766E; font-size: 11px; font-weight: bold;")
        rb_layout.addWidget(self.result_label)
        self.result_banner.setVisible(False)
        ab_layout.addWidget(self.result_banner)

        layout.addWidget(action_box)

        # Step 4: Collapsible Console Log
        self.log_viewer = LogViewer("MAFFT 即時日誌 (Console Output)")
        layout.addWidget(self.log_viewer, 1)

    def browse_input(self):
        fp, _ = QFileDialog.getOpenFileName(self, "選取 FASTA 檔案", "", "FASTA 檔案 (*.fasta *.fa *.fas);;所有檔案 (*)")
        if fp:
            self.in_edit.setText(fp)
            p = Path(fp)
            self.out_edit.setText(str(p.parent / f"{p.stem}_mafft_aligned.fasta"))

    def load_sample(self):
        s = DATA_DIR / "primates_cytb.fasta"
        if s.exists():
            self.in_edit.setText(str(s))
            self.out_edit.setText(str(OUTPUT_DIR / "primates_cytb_aligned.fasta"))

    def browse_output(self):
        fp, _ = QFileDialog.getSaveFileName(self, "儲存比對檔案", self.out_edit.text(), "FASTA (*.fasta)")
        if fp:
            self.out_edit.setText(fp)

    def open_output_dir(self):
        out_f = self.out_edit.text().strip()
        folder = Path(out_f).parent if out_f else OUTPUT_DIR
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def start_alignment(self):
        in_f = self.in_edit.text().strip()
        out_f = self.out_edit.text().strip()

        if not in_f or not Path(in_f).exists():
            QMessageBox.warning(self, "警告", "請先選取有效的輸入檔案。")
            return

        strat = self.strategy_combo.currentText().split()[0]
        adj = self.adjust_cb.isChecked()

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.view_msa_btn.setEnabled(False)
        self.log_viewer.clear_log()

        self.worker = AlignmentWorker(in_f, out_f, strat, adj)
        self.worker.log_signal.connect(self.log_viewer.append_log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def cancel_alignment(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)

    def on_finished(self, success: bool, msg: str):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if success:
            self.last_output_file = self.out_edit.text().strip()
            self.view_msa_btn.setEnabled(True)
            self.to_trim_btn.setEnabled(True)
            if hasattr(self, "result_banner"):
                self.result_banner.setVisible(True)
                self.result_label.setText(
                    f"✓ 多重比對成功！已生成：{Path(self.last_output_file).name} ｜ 可直接於上方點擊「檢視比對」或「前往修剪」進行下一步。"
                )
            QMessageBox.information(
                self, "比對完成", f"多重比對已完成。\n已儲存至: {Path(self.last_output_file).name}\n可點選「檢視比對」或「前往修剪」進行下一步。"
            )
        else:
            if hasattr(self, "result_banner"):
                self.result_banner.setVisible(False)
            QMessageBox.critical(self, "比對錯誤", f"MAFFT 執行失敗:\n{msg}")

    def open_msa_viewer(self):
        if self.last_output_file and Path(self.last_output_file).exists():
            self.view_msa_requested.emit(self.last_output_file)

    def open_trim(self):
        if self.last_output_file and Path(self.last_output_file).exists():
            self.trim_requested.emit(self.last_output_file)
