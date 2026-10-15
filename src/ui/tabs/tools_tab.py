import re
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)
from PySide6.QtCore import QThread, Signal, Qt
from src.config import find_tool, BIN_DIR
from src.core.tools_installer import (
    TOOL_METADATA,
    get_installed_tool_version,
    query_online_tool_info,
    download_and_extract_tool,
    test_tool_execution,
)


def parse_ver(v_str: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v_str)
    return tuple(map(int, nums)) if nums else (0,)


class CheckUpdatesWorker(QThread):
    tool_checked_signal = Signal(str, dict)
    finished_signal = Signal()

    def __init__(self, tool_keys: list[str]):
        super().__init__()
        self.tool_keys = tool_keys
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        for key in self.tool_keys:
            if self._is_cancelled:
                break
            info = query_online_tool_info(key)
            if self._is_cancelled:
                break
            self.tool_checked_signal.emit(key, info)
        self.finished_signal.emit()


class DownloadWorker(QThread):
    progress_signal = Signal(int, str)
    finished_signal = Signal(bool, str)

    def __init__(self, download_tasks: list[tuple[str, str | None]]):
        super().__init__()
        self.download_tasks = download_tasks
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        for key, url in self.download_tasks:
            if self._is_cancelled:
                break
            ok, msg = download_and_extract_tool(
                key, download_url=url, progress_callback=self.progress_signal.emit
            )
            if not ok:
                self.finished_signal.emit(False, msg)
                return
        if not self._is_cancelled:
            self.finished_signal.emit(True, "所有選定的生物資訊工具均已成功下載並配置完畢。")


class ToolsTab(QWidget):
    """
    外部工具箱管理中心 (Toolbox Manager)
    支援線上檢查 IQ-TREE 2、MAFFT、trimAl、FastTree 等工具最新釋出版本，
    並提供無痛一鍵下載、解壓縮、安裝與健康診斷功能。
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.download_worker: DownloadWorker | None = None
        self.check_worker: CheckUpdatesWorker | None = None
        self.online_info: dict[str, dict] = {}
        self.init_ui()
        self.refresh_tools_table()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 1. Header Box
        header_box = QGroupBox("外部工具箱管理 (Evolutionary Tools Manager)")
        h_layout = QVBoxLayout(header_box)
        desc = QLabel(
            "PhyloCraft 整合當代演化學期刊公認的標準分析引擎。\n"
            "無需手動設定終端機 PATH 環境變數，支援透過網路即時查詢最新版本，\n"
            "點選「下載/更新」，程式即自動由官方 GitHub / 伺服器下載並部署 Windows 執行檔。"
        )
        desc.setStyleSheet("color: #475569; font-size: 13px; line-height: 1.5;")
        h_layout.addWidget(desc)
        layout.addWidget(header_box)

        # 2. Tools Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "軟體名稱 (Tool)",
            "學術功能與用途 (Role)",
            "本地版本 (Installed)",
            "線上最新版 (Latest)",
            "狀態 (Status)",
            "操作 (Actions)",
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table, 1)

        # 3. Actions Toolbar & Progress Bar
        btn_box = QGroupBox("工具管理操作 (Toolbox Actions)")
        b_layout = QVBoxLayout(btn_box)

        btn_row = QHBoxLayout()
        self.check_updates_btn = QPushButton("檢查線上更新 (Check Updates)")
        self.check_updates_btn.setFixedHeight(34)
        self.check_updates_btn.setToolTip("檢查官方釋出之最新版本 (Check Online Releases)")
        self.check_updates_btn.clicked.connect(self.check_all_updates)
        btn_row.addWidget(self.check_updates_btn)

        self.download_all_btn = QPushButton("下載/更新全部")
        self.download_all_btn.setObjectName("primary_button")
        self.download_all_btn.setFixedHeight(34)
        self.download_all_btn.setToolTip("自動下載並更新外部二進位工具 (Download / Update All)")
        self.download_all_btn.clicked.connect(self.download_all)
        btn_row.addWidget(self.download_all_btn)

        self.diag_btn = QPushButton("執行診斷 (Run Diagnostics)")
        self.diag_btn.setFixedHeight(34)
        self.diag_btn.setToolTip("呼叫本機所有執行檔以驗證相容性 (Run Diagnostics)")
        self.diag_btn.clicked.connect(self.run_diagnostics)
        btn_row.addWidget(self.diag_btn)

        self.refresh_btn = QPushButton("重新整理 (Refresh)")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.setToolTip("重新讀取本機已安裝工具版本 (Refresh Status)")
        self.refresh_btn.clicked.connect(self.refresh_tools_table)
        btn_row.addWidget(self.refresh_btn)

        b_layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("工具箱準備就緒")
        b_layout.addWidget(self.progress_bar)

        layout.addWidget(btn_box)

    def refresh_tools_table(self):
        tool_keys = list(TOOL_METADATA.keys())
        self.table.clearContents()
        self.table.setRowCount(len(tool_keys))

        for row, key in enumerate(tool_keys):
            info = TOOL_METADATA[key]
            installed_ver = get_installed_tool_version(key)
            is_installed = installed_ver not in ("未安裝", "")

            # 0: Tool Name
            name_item = QTableWidgetItem(info["name"])
            name_item.setFlags(name_item.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)

            # 1: Role
            role_item = QTableWidgetItem(info["role"])
            role_item.setFlags(role_item.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 1, role_item)

            # 2: Installed Version
            clean_inst = installed_ver.lstrip("v")
            local_ver_item = QTableWidgetItem(f"v{clean_inst}" if is_installed else "未安裝")
            local_ver_item.setTextAlignment(Qt.AlignCenter)
            local_ver_item.setForeground(Qt.green if is_installed else Qt.red)
            local_ver_item.setFlags(local_ver_item.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 2, local_ver_item)

            # 3: Online Version
            online = self.online_info.get(key, {})
            latest_ver = online.get("latest_version")
            if latest_ver:
                clean_latest = latest_ver.lstrip("v")
                online_item = QTableWidgetItem(f"v{clean_latest}")
            else:
                online_item = QTableWidgetItem("查詢中...")
                online_item.setForeground(Qt.gray)
            online_item.setTextAlignment(Qt.AlignCenter)
            online_item.setFlags(online_item.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 3, online_item)

            # 4: Status
            if not is_installed:
                status_str = "尚未安裝"
                color = Qt.red
            elif latest_ver and parse_ver(latest_ver) > parse_ver(installed_ver):
                status_str = f"可更新至 v{latest_ver}"
                color = Qt.yellow
            else:
                status_str = "已就緒 (最新版)"
                color = Qt.green

            status_item = QTableWidgetItem(status_str)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(color)
            status_item.setFlags(status_item.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 4, status_item)

            # 5: Action Widget
            act_container = QWidget()
            act_layout = QHBoxLayout(act_container)
            act_layout.setContentsMargins(6, 4, 6, 4)
            act_layout.setSpacing(8)

            dl_btn = QPushButton("下載" if not is_installed else "更新/重載")
            dl_btn.setObjectName("table_btn")
            dl_btn.setFixedHeight(28)
            dl_btn.setMinimumWidth(85)
            dl_btn.clicked.connect(lambda _, k=key: self.download_single(k))
            act_layout.addWidget(dl_btn)

            test_btn = QPushButton("測試")
            test_btn.setObjectName("table_btn")
            test_btn.setFixedHeight(28)
            test_btn.setMinimumWidth(55)
            test_btn.clicked.connect(lambda _, k=key: self.test_single(k))
            act_layout.addWidget(test_btn)

            self.table.setCellWidget(row, 5, act_container)

    def check_all_updates(self):
        self.check_updates_btn.setEnabled(False)
        self.progress_bar.setFormat("正在連線查詢 GitHub 及官方伺服器最新版本資訊...")
        self.progress_bar.setValue(20)

        tool_keys = list(TOOL_METADATA.keys())
        self.check_worker = CheckUpdatesWorker(tool_keys)
        self.check_worker.tool_checked_signal.connect(self.on_tool_checked)
        self.check_worker.finished_signal.connect(self.on_check_finished)
        self.check_worker.start()

    def on_tool_checked(self, key: str, info: dict):
        self.online_info[key] = info
        # Only update the specific row's cells instead of rebuilding the entire table
        tool_keys = list(TOOL_METADATA.keys())
        if key in tool_keys:
            row = tool_keys.index(key)
            installed_ver = get_installed_tool_version(key)
            is_installed = installed_ver not in ("未安裝", "")
            latest_ver = info.get("latest_version")

            if latest_ver:
                item_online = QTableWidgetItem(f"v{str(latest_ver).lstrip('v')}")
                item_online.setTextAlignment(Qt.AlignCenter)
                item_online.setFlags(item_online.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row, 3, item_online)

            if not is_installed:
                status_str = "[未安裝]"
                color = Qt.red
            elif latest_ver and parse_ver(latest_ver) > parse_ver(installed_ver):
                status_str = f"[可更新] v{str(latest_ver).lstrip('v')}"
                color = Qt.yellow
            else:
                status_str = "[最新版]"
                color = Qt.green

            status_item = QTableWidgetItem(status_str)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(color)
            status_item.setFlags(status_item.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 4, status_item)

    def on_check_finished(self):
        self.check_updates_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("最新版本資訊查詢完畢")

    def download_single(self, key: str):
        self.download_all_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        info = self.online_info.get(key, {})
        download_url = info.get("download_url")

        self.download_worker = DownloadWorker([(key, download_url)])
        self.download_worker.progress_signal.connect(self.on_progress)
        self.download_worker.finished_signal.connect(self.on_download_finished)
        self.download_worker.start()

    def download_all(self):
        self.download_all_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        tasks = []
        for key in TOOL_METADATA.keys():
            info = self.online_info.get(key, {})
            tasks.append((key, info.get("download_url")))

        self.download_worker = DownloadWorker(tasks)
        self.download_worker.progress_signal.connect(self.on_progress)
        self.download_worker.finished_signal.connect(self.on_download_finished)
        self.download_worker.start()

    def test_single(self, key: str):
        ok, diag = test_tool_execution(key)
        name = TOOL_METADATA[key]["name"]
        if ok:
            QMessageBox.information(self, f"{name} 診斷正常", f"{name} 執行成功。\n\n回傳資訊:\n{diag.strip()}")
        else:
            QMessageBox.critical(self, f"{name} 診斷失敗", f"{name} 無法正常執行:\n{diag}")

    def run_diagnostics(self):
        reports = []
        for key, meta in TOOL_METADATA.items():
            ok, diag = test_tool_execution(key)
            status_prefix = "[正常]" if ok else "[異常]"
            summary_line = diag.strip().splitlines()[0] if diag.strip() else "無回傳"
            reports.append(f"{status_prefix} {meta['name']}: {summary_line}")

        msg = "\n".join(reports)
        QMessageBox.information(self, "工具箱全體健康檢查結果", f"本機工具測試結果如下：\n\n{msg}")

    def on_progress(self, percent: int, msg: str):
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{percent}% - {msg}")

    def on_download_finished(self, success: bool, msg: str):
        self.download_all_btn.setEnabled(True)
        self.refresh_tools_table()
        if success:
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("工具安裝成功")
            QMessageBox.information(self, "成功", msg)
        else:
            self.progress_bar.setFormat("下載發生錯誤")
            QMessageBox.critical(self, "錯誤", msg)
