from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QTextEdit,
    QTextBrowser,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication

from src.core.project_manager import PhyloProject
from src.core.eln_generator import ELNGenerator


class ELNViewerDialog(QDialog):
    """
    Phase 3: Publication-Grade Interactive Electronic Lab Notebook (ELN) Viewer.
    Provides researchers with a multi-tab workbench for:
    - Interactive Rich Visual Notebook
    - Auto-Drafted Materials & Methods (English & Traditional Chinese)
    - Literature Bibliography & BibTeX Generator
    - Cryptographic SHA-256 Data Integrity Audit
    - Standalone HTML Browser Print-to-PDF & Bundled ZIP Export
    """

    def __init__(self, project: PhyloProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self.md_content = ELNGenerator.generate_markdown(self.project)
        self.html_content = ELNGenerator.generate_html(self.project)
        self.methods = ELNGenerator.generate_materials_and_methods(self.project)
        self.bibtex = ELNGenerator.generate_bibtex(self.project)
        self.audit_records = ELNGenerator.get_audit_trail(self.project)

        self.setWindowTitle(f"論文級電子實驗紀錄簿 (Electronic Lab Notebook) — {self.project.name}")
        self.resize(1000, 700)
        self.setMinimumSize(850, 550)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # 1. Header Banner
        header = QWidget()
        header.setStyleSheet("background-color: #f8fafc; border-radius: 8px; padding: 10px 14px; border: 1px solid #e2e8f0;")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(4)

        t_row = QHBoxLayout()
        title = QLabel(f"<b>演化生物學電子實驗紀錄簿 (Electronic Lab Notebook - ELN)</b>")
        title.setStyleSheet("color: #006644; font-size: 16px; font-weight: bold;")
        t_row.addWidget(title)
        t_row.addStretch()

        badge = QLabel("符合期刊 Systematic Biology / MBE 論文規格")
        badge.setStyleSheet("color: #15803d; font-size: 11px; background-color: #dcfce7; padding: 3px 8px; border-radius: 10px; border: 1px solid #86efac;")
        t_row.addWidget(badge)
        h_layout.addLayout(t_row)

        sub_info = QLabel(
            f"<b>專案:</b> <code style='color:#006644;'>{self.project.name}</code> ｜ "
            f"<b>研究負責人:</b> {self.project.author} ｜ "
            f"<b>最後同步:</b> {self.project.updated_at} ｜ "
            f"<b>路徑:</b> <span style='color:#64748b;'>{self.project.project_dir}</span>"
        )
        sub_info.setStyleSheet("font-size: 12px; color: #1e293b;")
        h_layout.addWidget(sub_info)

        main_layout.addWidget(header)

        # 2. Main Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #64748b;
                padding: 8px 16px;
                border: 1px solid #e2e8f0;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #006644;
                border-bottom: 2px solid #006644;
            }
        """)

        # Tab 1: Visual ELN Preview
        tab_visual = QWidget()
        tv_layout = QVBoxLayout(tab_visual)
        tv_layout.setContentsMargins(12, 12, 12, 12)

        self.html_browser = QTextBrowser()
        self.html_browser.setOpenExternalLinks(True)
        self.html_browser.setHtml(self.html_content)
        self.html_browser.setStyleSheet("background-color: #ffffff; border: none;")
        tv_layout.addWidget(self.html_browser)
        tabs.addTab(tab_visual, "視覺化實驗日誌 (Visual ELN)")

        # Tab 2: Materials & Methods Draft
        tab_methods = QWidget()
        tm_layout = QVBoxLayout(tab_methods)
        tm_layout.setContentsMargins(12, 12, 12, 12)
        tm_layout.setSpacing(10)

        # English Methods Box
        en_row = QHBoxLayout()
        en_row.addWidget(QLabel("<b>Academic English (適用於國際英文期刊投稿):</b>"))
        en_row.addStretch()
        copy_en_btn = QPushButton("複製英文段落")
        copy_en_btn.setFixedHeight(26)
        copy_en_btn.clicked.connect(lambda: self.copy_text(self.methods["english"], copy_en_btn))
        en_row.addWidget(copy_en_btn)
        tm_layout.addLayout(en_row)

        self.en_edit = QTextEdit()
        self.en_edit.setReadOnly(True)
        self.en_edit.setPlainText(self.methods["english"])
        self.en_edit.setStyleSheet("background-color: #ffffff; color: #1e293b; font-size: 13px; font-family: Georgia, serif; line-height: 1.6; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px;")
        tm_layout.addWidget(self.en_edit, 1)

        # Traditional Chinese Methods Box
        zh_row = QHBoxLayout()
        zh_row.addWidget(QLabel("<b>繁體中文學術版（適用於學位論文或國科會報告）:</b>"))
        zh_row.addStretch()
        copy_zh_btn = QPushButton("複製繁中段落")
        copy_zh_btn.setFixedHeight(26)
        copy_zh_btn.clicked.connect(lambda: self.copy_text(self.methods["chinese"], copy_zh_btn))
        zh_row.addWidget(copy_zh_btn)
        tm_layout.addLayout(zh_row)

        self.zh_edit = QTextEdit()
        self.zh_edit.setReadOnly(True)
        self.zh_edit.setPlainText(self.methods["chinese"])
        self.zh_edit.setStyleSheet("background-color: #ffffff; color: #1e293b; font-size: 13px; font-family: -apple-system, sans-serif; line-height: 1.6; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px;")
        tm_layout.addWidget(self.zh_edit, 1)

        tabs.addTab(tab_methods, "論文方法草稿 (Methods Draft)")

        # Tab 3: Literature Citations & BibTeX
        tab_cites = QWidget()
        tc_layout = QVBoxLayout(tab_cites)
        tc_layout.setContentsMargins(12, 12, 12, 12)
        tc_layout.setSpacing(10)

        tc_layout.addWidget(QLabel("<b>正式學術期刊引用清單 (APA Formatted References):</b>"))
        self.cites_edit = QTextEdit()
        self.cites_edit.setReadOnly(True)
        cites_text = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(ELNGenerator.generate_citations_list(self.project), 1))
        self.cites_edit.setPlainText(cites_text)
        self.cites_edit.setFixedHeight(160)
        self.cites_edit.setStyleSheet("background-color: #ffffff; color: #1e293b; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 6px;")
        tc_layout.addWidget(self.cites_edit)

        bib_row = QHBoxLayout()
        bib_row.addWidget(QLabel("<b>BibTeX 條目 (可直接導入 Overleaf / LaTeX / EndNote / Zotero):</b>"))
        bib_row.addStretch()
        copy_bib_btn = QPushButton("複製 BibTeX")
        copy_bib_btn.setFixedHeight(26)
        copy_bib_btn.clicked.connect(lambda: self.copy_text(self.bibtex, copy_bib_btn))
        bib_row.addWidget(copy_bib_btn)
        tc_layout.addLayout(bib_row)

        self.bib_edit = QTextEdit()
        self.bib_edit.setReadOnly(True)
        self.bib_edit.setPlainText(self.bibtex)
        self.bib_edit.setStyleSheet("background-color: #f8fafc; color: #006644; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 6px;")
        tc_layout.addWidget(self.bib_edit, 1)

        tabs.addTab(tab_cites, "參考文獻與 BibTeX (Citations)")

        # Tab 4: Cryptographic SHA-256 Audit Trail
        tab_audit = QWidget()
        ta_layout = QVBoxLayout(tab_audit)
        ta_layout.setContentsMargins(12, 12, 12, 12)

        audit_hint = QLabel("<b>數據全生命週期防偽審計 (Cryptographic Checksum Verification):</b><br>"
                            "<span style='color: #64748b; font-size: 11px;'>依循國際期刊規範，所有輸出檔案均計算 SHA-256 數位指紋，確保實驗數據不可竄改且保證科學研究之嚴謹重現性。</span>")
        ta_layout.addWidget(audit_hint)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(4)
        self.audit_table.setHorizontalHeaderLabels(["階段模組", "檔案名稱", "大小", "SHA-256 數位指紋 (Checksum)"])
        self.audit_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.audit_table.verticalHeader().setVisible(False)
        self.audit_table.setStyleSheet("background-color: #ffffff; color: #1e293b; font-size: 12px; border: 1px solid #e2e8f0; border-radius: 6px;")

        self.audit_table.setRowCount(len(self.audit_records))
        for r_idx, r in enumerate(self.audit_records):
            item_mod = QTableWidgetItem(r["step_title"])
            item_mod.setFlags(item_mod.flags() ^ Qt.ItemIsEditable)

            item_fn = QTableWidgetItem(r["filename"])
            item_fn.setToolTip(r["path"])
            item_fn.setFlags(item_fn.flags() ^ Qt.ItemIsEditable)

            item_sz = QTableWidgetItem(r["size_fmt"])
            item_sz.setFlags(item_sz.flags() ^ Qt.ItemIsEditable)

            item_sha = QTableWidgetItem(r["sha256"])
            item_sha.setFlags(item_sha.flags() ^ Qt.ItemIsEditable)

            self.audit_table.setItem(r_idx, 0, item_mod)
            self.audit_table.setItem(r_idx, 1, item_fn)
            self.audit_table.setItem(r_idx, 2, item_sz)
            self.audit_table.setItem(r_idx, 3, item_sha)

        ta_layout.addWidget(self.audit_table, 1)

        copy_audit_btn = QPushButton("複製完整雜湊審計表 (Markdown 格式)")
        copy_audit_btn.clicked.connect(self.copy_audit_table)
        ta_layout.addWidget(copy_audit_btn)

        tabs.addTab(tab_audit, "數據防偽審計 (Audit Trail)")

        # Tab 5: Raw Markdown
        tab_md = QWidget()
        tmd_layout = QVBoxLayout(tab_md)
        tmd_layout.setContentsMargins(12, 12, 12, 12)

        self.md_edit = QTextEdit()
        self.md_edit.setReadOnly(True)
        self.md_edit.setPlainText(self.md_content)
        self.md_edit.setStyleSheet("background-color: #f8fafc; color: #1e293b; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 6px;")
        tmd_layout.addWidget(self.md_edit, 1)

        copy_md_btn = QPushButton("複製完整 Markdown")
        copy_md_btn.clicked.connect(lambda: self.copy_text(self.md_content, copy_md_btn))
        tmd_layout.addWidget(copy_md_btn)

        tabs.addTab(tab_md, "Markdown 原文")

        main_layout.addWidget(tabs, 1)

        # 3. Bottom Action Toolbar
        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        open_browser_btn = QPushButton("在瀏覽器開啟 (支援列印 / 存為 PDF)")
        open_browser_btn.setFixedHeight(34)
        open_browser_btn.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 4px 14px;")
        open_browser_btn.setToolTip("使用預設瀏覽器開啟 HTML 格式紀錄簿，可直接按 Ctrl+P 列印或另存為高品質論文補充資料 PDF")
        open_browser_btn.clicked.connect(self.open_in_browser)
        action_bar.addWidget(open_browser_btn)

        export_zip_btn = QPushButton("導出論文補充資料包 (Export ZIP)")
        export_zip_btn.setFixedHeight(34)
        export_zip_btn.setStyleSheet("background-color: #006644; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 4px 14px;")
        export_zip_btn.setToolTip("一鍵打包 HTML、Markdown、論文方法草稿、BibTeX 文獻與全部分析資料集為標準 ZIP 壓縮包")
        export_zip_btn.clicked.connect(self.export_zip_package)
        action_bar.addWidget(export_zip_btn)

        open_dir_btn = QPushButton("開啟專案目錄")
        open_dir_btn.setFixedHeight(34)
        open_dir_btn.clicked.connect(self.open_project_directory)
        action_bar.addWidget(open_dir_btn)

        action_bar.addStretch()

        close_btn = QPushButton("關閉")
        close_btn.setFixedHeight(34)
        close_btn.clicked.connect(self.accept)
        action_bar.addWidget(close_btn)

        main_layout.addLayout(action_bar)

    def copy_text(self, text: str, btn: QPushButton | None = None):
        QGuiApplication.clipboard().setText(text)
        if btn:
            orig = btn.text()
            btn.setText("✓ 已複製到剪貼簿！")
            btn.setStyleSheet("color: #a6da95; font-weight: bold;")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1800, lambda: (btn.setText(orig), btn.setStyleSheet("")))

    def copy_audit_table(self):
        lines = ["| 階段模組 | 檔案名稱 | 大小 | SHA-256 數位指紋 (Checksum) |", "| :--- | :--- | :--- | :--- |"]
        for r in self.audit_records:
            lines.append(f"| {r['step_title']} | `{r['filename']}` | {r['size_fmt']} | `{r['sha256']}` |")
        self.copy_text("\n".join(lines))
        QMessageBox.information(self, "複製成功", "已將完整數據防偽 SHA-256 審計表複製至剪貼簿！")

    def open_in_browser(self):
        html_file = Path(self.project.project_dir) / "lab_notebook.html"
        if not html_file.exists():
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(self.html_content)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(html_file.resolve())))

    def export_zip_package(self):
        suggested_name = f"{self.project.name}_Supplementary_Materials.zip"
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "導出論文補充資料壓縮包 (Supplementary Materials ZIP)",
            str(Path(self.project.project_dir).parent / suggested_name),
            "ZIP Archives (*.zip);;All Files (*)"
        )
        if not target_path:
            return

        try:
            saved_zip = ELNGenerator.export_supplementary_zip(self.project, target_path)
            QMessageBox.information(
                self,
                "導出成功",
                f"論文補充資料包已成功打包完成！\n\n"
                f"儲存位置:\n{saved_zip}\n\n"
                f"內含:\n"
                f"• 視覺化電子實驗日誌 (HTML)\n"
                f"• Markdown 完整紀錄簿 (.md)\n"
                f"• 論文方法段落草稿 (中英雙語 .txt)\n"
                f"• 參考文獻庫 (references.bib)\n"
                f"• 全套分析序列與演化樹數據集 (01_raw ~ 07_timetree)"
            )
        except Exception as e:
            QMessageBox.critical(self, "導出失敗", f"打包過程發生錯誤: {str(e)}")

    def open_project_directory(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.project.project_dir).resolve())))
