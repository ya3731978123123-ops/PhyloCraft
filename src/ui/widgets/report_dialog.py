from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QApplication,
)
from PySide6.QtCore import Qt
from src.core.iqtree_parser import IQTreeReportData


class PublicationReportDialog(QDialog):
    """
    Academic Methods & Publication Report Dialog.
    Translates raw analytical outputs into peer-reviewed paper format.
    """

    def __init__(self, report_data: IQTreeReportData, parent: QWidget | None = None):
        super().__init__(parent)
        self.report = report_data
        self.setWindowTitle("論文級分析報告與方法 (Academic Methods & Report)")
        self.resize(850, 620)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Title
        title_label = QLabel("<b>主流期刊標準演化分析報告 (Publication Methods & Audit)</b>")
        title_label.setStyleSheet("color: #8aadf4; font-size: 16px;")
        layout.addWidget(title_label)

        sub_label = QLabel(
            "系統已依據實際執行的分析參數與結果，自動生成符合國際期刊（如 Syst. Biol., MBE, Nature Comm.）標準之\n"
            "Materials & Methods 段落、模型選擇統計表與參考文獻清單，方便直接複製貼入學術論文或研究報告中。"
        )
        sub_label.setStyleSheet("color: #cad3f5; font-size: 12px; line-height: 1.4;")
        layout.addWidget(sub_label)

        # Tab Widget
        tabs = QTabWidget()

        # Tab 1: Methods (English & Chinese)
        methods_tab = QWidget()
        m_layout = QVBoxLayout(methods_tab)

        m_layout.addWidget(QLabel("<b>Academic English (適用於國際期刊投稿):</b>"))
        self.en_edit = QTextEdit(self.report.english_methods)
        self.en_edit.setReadOnly(True)
        self.en_edit.setStyleSheet("background-color: #ffffff; color: #1e293b; font-size: 13px; line-height: 1.5; border: 1px solid #cbd5e1; border-radius: 6px;")
        m_layout.addWidget(self.en_edit, 1)

        copy_en_btn = QPushButton("複製英文 Materials & Methods")
        copy_en_btn.clicked.connect(lambda: self.copy_to_clip(self.en_edit.toPlainText()))
        m_layout.addWidget(copy_en_btn)

        m_layout.addWidget(QLabel("<b>繁體中文（適用於碩博士論文或專題結案報告）:</b>"))
        self.zh_edit = QTextEdit(self.report.chinese_methods)
        self.zh_edit.setReadOnly(True)
        self.zh_edit.setStyleSheet("background-color: #ffffff; color: #1e293b; font-size: 13px; line-height: 1.5; border: 1px solid #cbd5e1; border-radius: 6px;")
        m_layout.addWidget(self.zh_edit, 1)

        copy_zh_btn = QPushButton("複製中文方法段落")
        copy_zh_btn.clicked.connect(lambda: self.copy_to_clip(self.zh_edit.toPlainText()))
        m_layout.addWidget(copy_zh_btn)

        tabs.addTab(methods_tab, "論文方法段落 (Methods)")

        # Tab 2: Statistics & Model Selection
        stats_tab = QWidget()
        s_layout = QVBoxLayout(stats_tab)

        s_layout.addWidget(QLabel("<b>分析矩陣品質指標 (Dataset & Quality Metrics):</b>"))
        stats_table = QTableWidget()
        stats_table.setColumnCount(2)
        stats_table.setHorizontalHeaderLabels(["指標項目 (Metric)", "數值 (Value)"])
        stats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        stats_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        stats_table.verticalHeader().setVisible(False)
        stats_table.verticalHeader().setDefaultSectionSize(26)
        stats_table.setFixedHeight(292)

        metrics = [
            ("物種數量 (Number of Taxa)", str(self.report.taxa_count)),
            ("比對後總位點數 (Alignment Length)", f"{self.report.site_count} bp"),
            ("恆定位點數與比例 (Constant Sites)", f"{self.report.constant_sites} ({self.report.constant_pct:.1f}%)"),
            ("簡約訊息位點數 (Parsimony-Informative Sites)", str(self.report.parsimony_informative_sites)),
            ("相異位點模式數 (Distinct Site Patterns)", str(self.report.distinct_patterns)),
            ("BIC 最適模型 (Best Model by BIC)", self.report.best_model),
            ("最佳對數似然值 (Log-likelihood, ln L)", f"{self.report.log_likelihood:.4f}"),
            ("赤池資訊準則 (AIC Score)", f"{self.report.aic:.4f}"),
            ("貝氏資訊準則 (BIC Score)", f"{self.report.bic:.4f}"),
            ("演化樹總分枝長度 (Tree Length)", f"{self.report.tree_length:.4f} substitutions/site"),
        ]
        stats_table.setRowCount(len(metrics))
        for row, (k, v) in enumerate(metrics):
            stats_table.setItem(row, 0, QTableWidgetItem(k))
            item_v = QTableWidgetItem(v)
            item_v.setForeground(Qt.cyan)
            stats_table.setItem(row, 1, item_v)
        s_layout.addWidget(stats_table)

        if self.report.top_models:
            s_layout.addWidget(QLabel("<b>ModelFinder 模型候選排行 (Top 5 Models by BIC):</b>"))
            model_table = QTableWidget()
            model_table.setColumnCount(5)
            model_table.setHorizontalHeaderLabels(["模型名稱", "Log-Likelihood", "AIC", "BIC", "BIC 權重 (w-BIC)"])
            model_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            model_table.verticalHeader().setVisible(False)
            model_table.verticalHeader().setDefaultSectionSize(26)
            model_table.setFixedHeight(162)
            model_table.setRowCount(len(self.report.top_models))

            for row, m in enumerate(self.report.top_models):
                model_table.setItem(row, 0, QTableWidgetItem(m.model))
                model_table.setItem(row, 1, QTableWidgetItem(f"{m.logl:.3f}"))
                model_table.setItem(row, 2, QTableWidgetItem(f"{m.aic:.3f}"))
                model_table.setItem(row, 3, QTableWidgetItem(f"{m.bic:.3f}"))
                model_table.setItem(row, 4, QTableWidgetItem(f"{m.w_bic:.4f}"))
            s_layout.addWidget(model_table)

        s_layout.addStretch()

        tabs.addTab(stats_tab, "品質指標與模型評比 (Metrics & Models)")

        # Tab 3: Citations & BibTeX
        cite_tab = QWidget()
        c_layout = QVBoxLayout(cite_tab)

        c_layout.addWidget(QLabel("<b>學術參考文獻 (APA Format References):</b>"))
        cite_text = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(self.report.citations))
        self.cite_edit = QTextEdit(cite_text)
        self.cite_edit.setReadOnly(True)
        self.cite_edit.setStyleSheet("background-color: #ffffff; color: #1e293b; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 6px;")
        c_layout.addWidget(self.cite_edit, 1)

        copy_cite_btn = QPushButton("複製參考文獻清單")
        copy_cite_btn.clicked.connect(lambda: self.copy_to_clip(self.cite_edit.toPlainText()))
        c_layout.addWidget(copy_cite_btn)

        c_layout.addWidget(QLabel("<b>BibTeX 格式 (適用於 LaTeX / Zotero / EndNote 匯入):</b>"))
        self.bib_edit = QTextEdit(self.report.bibtex)
        self.bib_edit.setReadOnly(True)
        self.bib_edit.setStyleSheet("background-color: #f8fafc; color: #006644; font-size: 11px; font-family: Consolas; border: 1px solid #cbd5e1; border-radius: 6px;")
        c_layout.addWidget(self.bib_edit, 1)

        copy_bib_btn = QPushButton("複製 BibTeX 代碼")
        copy_bib_btn.clicked.connect(lambda: self.copy_to_clip(self.bib_edit.toPlainText()))
        c_layout.addWidget(copy_bib_btn)

        tabs.addTab(cite_tab, "參考文獻與 BibTeX (Citations)")

        layout.addWidget(tabs, 1)

        # Close Button
        close_btn = QPushButton("關閉 (Close)")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def copy_to_clip(self, text: str):
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "已複製", "內容已成功複製至剪貼簿！")
