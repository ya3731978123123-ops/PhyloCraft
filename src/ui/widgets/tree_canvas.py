from pathlib import Path
import copy
import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QSpinBox,
    QLabel,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QScrollArea,
    QSlider,
    QGroupBox,
    QLineEdit,
)
from PySide6.QtCore import Qt

import matplotlib
matplotlib.use("QtAgg")
matplotlib.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Segoe UI", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from Bio import Phylo


class TreeCanvasWidget(QWidget):
    """
    Publication-grade Tree Viewer with Independent Horizontal & Vertical Scaling,
    Circular Layout, Ladderize, and Robust Rooting.
    """

    def __init__(self, parent: QWidget | None = None, compact_mode: bool = False):
        super().__init__(parent)
        self.compact_mode = compact_mode
        self.current_tree_file: Path | None = None
        self.original_tree: Phylo.BaseTree.Tree | None = None
        self.tree: Phylo.BaseTree.Tree | None = None
        self.h_scale = 1.0  # Horizontal branch stretch (0.5x to 15x)
        self.v_scale = 1.0  # Vertical spacing
        self.search_query: str = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Control Panel Box (Spacious 3-Row Categorized Layout)
        self.ctrl_box = QGroupBox("演化樹外觀與自由縮放控制器 (Tree Display && Free Scaling)")
        ctrl_box = self.ctrl_box
        c_layout = QVBoxLayout(ctrl_box)
        c_layout.setContentsMargins(10, 6, 10, 6)
        c_layout.setSpacing(6)

        # ---------------- Row 1: Layout, Topology & Styling ----------------
        r1 = QHBoxLayout()
        r1.setSpacing(6)

        r1.addWidget(QLabel("版型:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems([
            "標準矩形樹",
            "環狀放射樹",
        ])
        self.layout_combo.setMinimumWidth(100)
        self.layout_combo.setToolTip("物種超過 30 個時，強烈推薦切換為環狀放射樹")
        self.layout_combo.currentIndexChanged.connect(self.redraw_tree)
        r1.addWidget(self.layout_combo)

        r1.addWidget(QLabel("分枝:"))
        self.branch_combo = QComboBox()
        self.branch_combo.addItems([
            "真實長度",
            "等長拓撲",
        ])
        self.branch_combo.setMinimumWidth(90)
        self.branch_combo.currentIndexChanged.connect(self.redraw_tree)
        r1.addWidget(self.branch_combo)

        self.ladderize_cb = QCheckBox("階梯排序")
        self.ladderize_cb.setChecked(True)
        self.ladderize_cb.setToolTip("依支系物種多寡自動由小到大排序，消除雜亂分枝（期刊必備）")
        self.ladderize_cb.stateChanged.connect(self.redraw_tree)
        r1.addWidget(self.ladderize_cb)

        self.align_tips_cb = QCheckBox("對齊虛線")
        self.align_tips_cb.setChecked(False)
        self.align_tips_cb.setToolTip("勾選後末端物種名稱齊列於右側邊界並連引導虛線")
        self.align_tips_cb.stateChanged.connect(self.redraw_tree)
        r1.addWidget(self.align_tips_cb)

        self.time_scale_cb = QCheckBox("時間軸")
        self.time_scale_cb.setChecked(False)
        self.time_scale_cb.setToolTip("顯示地質年代時間軸刻度（適用於 LSD2 分子鐘 TimeTree）")
        self.time_scale_cb.stateChanged.connect(self.redraw_tree)
        r1.addWidget(self.time_scale_cb)

        r1.addWidget(QLabel("支持度:"))
        self.support_combo = QComboBox()
        self.support_combo.addItems([
            "UFBoot ≥ 70%",
            "UFBoot ≥ 90%",
            "SH-aLRT / UFBoot",
            "全部顯示",
            "不顯示",
        ])
        self.support_combo.setMinimumWidth(110)
        self.support_combo.currentIndexChanged.connect(self.redraw_tree)
        r1.addWidget(self.support_combo)

        r1.addWidget(QLabel("配色:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["白色論文", "暗色科技"])
        self.theme_combo.setMinimumWidth(80)
        self.theme_combo.currentIndexChanged.connect(self.redraw_tree)
        r1.addWidget(self.theme_combo)

        r1.addStretch()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜尋物種...")
        self.search_edit.setFixedWidth(100)
        self.search_edit.textChanged.connect(self.on_search_changed)
        r1.addWidget(self.search_edit)

        self.newick_btn = QPushButton("複製 Newick")
        self.newick_btn.setToolTip("複製當前演化樹之 Newick 字串至系統剪貼簿")
        self.newick_btn.clicked.connect(self.copy_newick)
        r1.addWidget(self.newick_btn)

        self.export_btn = QPushButton("導出插圖 (Export)...")
        self.export_btn.setObjectName("primary_button")
        self.export_btn.setFixedHeight(28)
        self.export_btn.setToolTip("輸出 300 DPI 國際期刊標準高解析度論文插圖 (Export High-Res Image)")
        self.export_btn.clicked.connect(self.export_image)
        r1.addWidget(self.export_btn)

        c_layout.addLayout(r1)

        # ---------------- Row 2: Scaling, Rooting & Interactive Tools ----------------
        r2 = QHBoxLayout()
        r2.setSpacing(6)

        r2.addWidget(QLabel("水平:"))
        self.h_slider = QSlider(Qt.Horizontal)
        self.h_slider.setRange(5, 80)
        self.h_slider.setValue(10)
        self.h_slider.setFixedWidth(70)
        self.h_slider.setToolTip("自由拉伸分枝水平長度（0.5x ~ 8.0x）")
        self.h_slider.valueChanged.connect(self.on_h_scale_changed)
        r2.addWidget(self.h_slider)
        self.h_label = QLabel("1.0x")
        self.h_label.setStyleSheet("color: #006644; font-weight: bold;")
        self.h_label.setFixedWidth(34)
        r2.addWidget(self.h_label)

        r2.addWidget(QLabel("垂直:"))
        self.v_slider = QSlider(Qt.Horizontal)
        self.v_slider.setRange(2, 40)
        self.v_slider.setValue(12)
        self.v_slider.setFixedWidth(60)
        self.v_slider.setToolTip("調整縱向物種行距 (2 ~ 40)")
        self.v_slider.valueChanged.connect(self.on_v_scale_changed)
        r2.addWidget(self.v_slider)

        r2.addWidget(QLabel("字體:"))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(4, 24)
        self.font_spin.setValue(10)
        self.font_spin.setFixedWidth(72)
        self.font_spin.setFixedHeight(26)
        self.font_spin.setSuffix(" pt")
        self.font_spin.setStyleSheet("""
            QSpinBox {
                padding-left: 4px;
                padding-right: 18px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                height: 12px;
                border-left: 1px solid #cbd5e1;
                border-bottom: 1px solid #e2e8f0;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                height: 12px;
                border-left: 1px solid #cbd5e1;
            }
        """)
        self.font_spin.setToolTip("調整演化樹末端物種標籤字體大小 (4 ~ 24 pt)")
        self.font_spin.valueChanged.connect(self.redraw_tree)
        r2.addWidget(self.font_spin)

        self.reset_view_btn = QPushButton("重設")
        self.reset_view_btn.setFixedWidth(46)
        self.reset_view_btn.setToolTip("重設分枝拉伸與字體大小至預設標準視圖")
        self.reset_view_btn.clicked.connect(self.reset_view)
        r2.addWidget(self.reset_view_btn)

        self.fit_view_btn = QPushButton("適應視窗")
        self.fit_view_btn.setToolTip("依視窗高度自動計算最佳行距與字級，將全部分枝容納於單一畫面")
        self.fit_view_btn.clicked.connect(self.fit_to_view)
        r2.addWidget(self.fit_view_btn)

        r2.addSpacing(6)
        r2.addWidget(QLabel("|"))
        r2.addSpacing(6)

        self.midpoint_btn = QPushButton("中點定根")
        self.midpoint_btn.setToolTip("以樹的最長路徑中點為根（無指定外群時的最佳客觀選擇）")
        self.midpoint_btn.clicked.connect(self.apply_midpoint_root)
        r2.addWidget(self.midpoint_btn)

        self.outgroup_combo = QComboBox()
        self.outgroup_combo.setMinimumWidth(220)
        self.outgroup_combo.setMaximumWidth(320)
        self.outgroup_combo.setToolTip("選取作為演化基底的外群物種")
        r2.addWidget(self.outgroup_combo)

        self.outgroup_btn = QPushButton("套用外群")
        self.outgroup_btn.setToolTip("以外群下拉選單所選之物種為根進行重新定根")
        self.outgroup_btn.clicked.connect(self.apply_outgroup_root)
        r2.addWidget(self.outgroup_btn)

        self.reset_root_btn = QPushButton("復原樹")
        self.reset_root_btn.setToolTip("復原為演化推論原生樹形")
        self.reset_root_btn.clicked.connect(self.reset_root)
        r2.addWidget(self.reset_root_btn)

        self.root_status_label = QLabel("")
        self.root_status_label.setStyleSheet("color: #006644; font-weight: bold;")
        r2.addWidget(self.root_status_label)

        r2.addStretch()

        c_layout.addLayout(r2)

        layout.addWidget(ctrl_box)

        # Matplotlib Figure & ScrollArea
        self.fig = plt.figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.mpl_connect("button_press_event", self.on_canvas_clicked)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: 1px solid #e2e8f0; background-color: #ffffff;")
        self.scroll_area.setWidget(self.canvas)
        layout.addWidget(self.scroll_area, 1)

        self.draw_placeholder()
        if self.compact_mode:
            self.ctrl_box.setVisible(False)

    def on_search_changed(self, text: str):
        self.search_query = text.strip().lower()
        self.redraw_tree()

    def reset_view(self):
        self.h_slider.setValue(10)
        self.v_slider.setValue(12)
        self.font_spin.setValue(10)
        self.search_edit.clear()
        self.search_query = ""
        self.redraw_tree()

    def fit_to_view(self):
        if not self.tree:
            return
        leaves = self.tree.get_terminals()
        num_leaves = len(leaves)
        if num_leaves == 0:
            return

        viewport_h = self.scroll_area.viewport().height() if self.scroll_area.viewport() else 500
        # Target height in inches so that canvas fits viewport without scroll
        target_h_in = max(4.0, (viewport_h - 30) / 100.0)
        # v_scale = target_h_in / (num_leaves * 0.42), and v_val = v_scale * 12
        v_opt = int(round((target_h_in / (num_leaves * 0.42)) * 12.0))
        v_opt = max(2, min(40, v_opt))
        self.v_slider.setValue(v_opt)

        if num_leaves > 60:
            self.font_spin.setValue(7)
        elif num_leaves > 35:
            self.font_spin.setValue(8)
        else:
            self.font_spin.setValue(10)

        self.h_slider.setValue(12)
        self.redraw_tree()

    def on_h_scale_changed(self, val: int):
        self.h_scale = val / 10.0
        self.h_label.setText(f"{self.h_scale:.1f}x")
        self.redraw_tree()

    def on_v_scale_changed(self, val: int):
        self.v_scale = val / 12.0
        self.redraw_tree()

    def draw_placeholder(self):
        self.fig.clear()
        self.canvas.setMinimumSize(400, 300)
        ax = self.fig.add_subplot(111)
        self.fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")
        ax.text(
            0.5, 0.5,
            "尚未載入演化樹。\n可直接拖曳 .treefile 或 .nwk 檔案至此，或於分析完成後自動載入。",
            ha="center", va="center", color="#5b6078", fontsize=12,
            transform=ax.transAxes,
        )
        ax.axis("off")
        self.canvas.draw()

    def detect_candidate_outgroups(self, tree: Phylo.BaseTree.Tree) -> list[str]:
        """
        Returns terminal taxa for outgroup selection:
        1. Prioritizes explicitly annotated outgroups (containing 'outgroup', '_og', or '外群' in label).
        2. Followed by cleanly sorted terminal taxa.
        Avoids brittle hardcoded species dictionaries or misleading rate-based heuristics.
        """
        terminals = [t.name for t in tree.get_terminals() if t.name]
        if not terminals:
            return []
        tagged = [t for t in terminals if any(k in t.lower() for k in ("outgroup", "_og", "外群"))]
        untagged = sorted([t for t in terminals if t not in tagged])
        return tagged + untagged

    def load_tree_file(self, tree_path: str | Path, show_alert: bool = True):
        self.current_tree_file = Path(tree_path)
        try:
            self.original_tree = Phylo.read(str(self.current_tree_file), "newick")
            self.tree = copy.deepcopy(self.original_tree)

            self.outgroup_combo.clear()
            terminals = [t.name for t in self.tree.get_terminals() if t.name]
            candidates = self.detect_candidate_outgroups(self.tree)

            def make_og_label(name: str) -> str:
                name_lower = name.lower()
                is_tagged = any(k in name_lower for k in ("outgroup", "_og", "外群"))
                tag = " [標註外群]" if is_tagged else ""
                if len(name) > 24:
                    short = f"{name[:12]}...{name[-8:]}"
                else:
                    short = name
                return f"{short}{tag}"

            for idx, t in enumerate(candidates):
                self.outgroup_combo.addItem(make_og_label(t), userData=t)
                self.outgroup_combo.setItemData(idx, f"完整物種 ID: {t}", Qt.ToolTipRole)

            if "timetree" in str(self.current_tree_file).lower():
                self.time_scale_cb.setChecked(True)

            self.root_status_label.setText("")
            self.redraw_tree()
        except Exception as e:
            if show_alert:
                QMessageBox.critical(self, "載入失敗", f"無法解析演化樹檔案:\n{str(e)}")
            else:
                raise

    def apply_midpoint_root(self):
        if not self.tree:
            return
        try:
            self.tree.root_at_midpoint()
            self.redraw_tree()
            self.root_status_label.setText("✓ 已套用中點定根 (Midpoint)")
        except Exception as e:
            self.root_status_label.setText(f"[錯誤] {str(e)}")

    def apply_outgroup_root(self):
        if not self.tree:
            return
        raw_data = self.outgroup_combo.currentData()
        if raw_data:
            outgroup_name = str(raw_data).strip()
        else:
            raw_text = self.outgroup_combo.currentText().strip()
            if not raw_text:
                return
            outgroup_name = raw_text.split(" [標註外群]")[0].split(" (推薦外群")[0].split(" (⭐")[0].strip()

        try:
            self.tree.root_with_outgroup({"name": outgroup_name})
            # Balance root branch length so outgroup has an actual horizontal branch line
            if len(self.tree.root.clades) == 2:
                c1, c2 = self.tree.root.clades
                total_len = (c1.branch_length or 0.0) + (c2.branch_length or 0.0)
                if total_len > 0:
                    c1.branch_length = total_len / 2.0
                    c2.branch_length = total_len / 2.0
                else:
                    c1.branch_length = 0.001
                    c2.branch_length = 0.001

            self.redraw_tree()
            self.root_status_label.setText(f"✓ 已以外群定根: {outgroup_name}")
        except Exception as e:
            self.root_status_label.setText(f"[錯誤] {str(e)}")

    def reset_root(self):
        if self.original_tree:
            self.tree = copy.deepcopy(self.original_tree)
            self.redraw_tree()
            self.root_status_label.setText("✓ 已復原為原始樹")

    def on_canvas_clicked(self, event):
        """Allows direct canvas click / double-click on any taxon branch or label to set outgroup & reroot."""
        if not event.inaxes or event.xdata is None or event.ydata is None or not self.tree:
            return
        clicked_leaf = None
        min_dy = 0.50
        for name, (lx, ly, tx) in getattr(self, "leaf_positions", {}).items():
            dy = abs(ly - event.ydata)
            if dy < min_dy and event.xdata >= (lx * 0.3):
                min_dy = dy
                clicked_leaf = name

        if clicked_leaf:
            # Sync selection in outgroup_combo
            for idx in range(self.outgroup_combo.count()):
                data = self.outgroup_combo.itemData(idx)
                if data == clicked_leaf or clicked_leaf in str(data):
                    self.outgroup_combo.setCurrentIndex(idx)
                    break

            # If double click or right click, automatically reroot
            if getattr(event, "dblclick", False) or getattr(event, "button", 1) == 3:
                self.apply_outgroup_root()
                self.root_status_label.setText(f"✓ 已點選分支定根: {clicked_leaf}")
            else:
                self.root_status_label.setText(f"已選取外群: {clicked_leaf} (點擊「套用外群」或雙擊即可定根)")

    def redraw_tree(self):
        if not self.tree:
            self.draw_placeholder()
            return

        self.fig.clear()
        is_circular = self.layout_combo.currentIndex() == 1
        is_cladogram = self.branch_combo.currentIndex() == 1
        do_ladderize = self.ladderize_cb.isChecked()
        align_tips = self.align_tips_cb.isChecked()
        support_mode = self.support_combo.currentIndex()
        font_size = self.font_spin.value()

        active_tree = copy.deepcopy(self.tree)
        if do_ladderize:
            active_tree.ladderize()

        if is_cladogram:
            for c in active_tree.find_clades():
                c.branch_length = 1.0

        leaves = active_tree.get_terminals()
        num_leaves = len(leaves)

        if is_circular:
            self.render_circular_tree(active_tree, leaves, num_leaves, is_cladogram, support_mode, font_size)
        else:
            self.render_rectangular_tree(active_tree, leaves, num_leaves, is_cladogram, align_tips, support_mode, font_size)

    def render_rectangular_tree(self, tree, leaves, num_leaves, is_cladogram, align_tips, support_mode, font_size):
        # Dynamic canvas size based on taxa count and viewport dimensions
        vp = self.scroll_area.viewport()
        vp_w = max(280, vp.width()) if vp and vp.width() > 50 else 320
        vp_h = max(300, vp.height()) if vp and vp.height() > 50 else 380

        if self.compact_mode:
            # In compact mode (Stage), gracefully fill available viewport to eliminate empty void below tree!
            base_w = (vp_w - 4) / 100.0
            calc_width = max(base_w, base_w * self.h_scale)
            base_h = (vp_h - 6) / 100.0
            needed_h = max(2.6, (num_leaves + 2.0) * 0.38 * self.v_scale)
            calc_height = max(base_h, needed_h)
            font_size = min(font_size, 9)
        else:
            calc_height = max(5.0, num_leaves * 0.42 * self.v_scale)
            calc_width = max(9.5, 9.5 * min(3.0, self.h_scale))

        w_px = int(calc_width * 100)
        h_px = int(calc_height * 100)
        self.fig.set_size_inches(calc_width, calc_height)
        self.canvas.setMinimumSize(w_px, h_px)
        self.canvas.resize(w_px, h_px)

        ax = self.fig.add_subplot(111)
        is_paper = self.theme_combo.currentIndex() == 0

        bg_color = "#ffffff" if is_paper else "#181926"
        branch_color = "#2c3e50" if is_paper else "#8aadf4"
        text_color = "#2c3e50" if is_paper else "#cad3f5"
        leader_color = "#bdc3c7" if is_paper else "#494d64"
        badge_bg = "#ffffff" if is_paper else "#1e2030"

        self.fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        # Coordinates
        raw_x_coords = {}
        y_coords = {leaf: i for i, leaf in enumerate(leaves)}

        def get_x_coords(clade, curr_x=0.0):
            bl = clade.branch_length if clade.branch_length is not None else 0.0
            node_x = curr_x + bl
            raw_x_coords[clade] = node_x
            for child in clade.clades:
                get_x_coords(child, node_x)

        get_x_coords(tree.root, 0.0)

        def get_y_coords(clade):
            if clade.is_terminal():
                return y_coords[clade]
            child_ys = [get_y_coords(c) for c in clade.clades]
            y = (child_ys[0] + child_ys[-1]) / 2.0
            y_coords[clade] = y
            return y

        get_y_coords(tree.root)

        max_raw_x = max(raw_x_coords.values()) if raw_x_coords.values() else 1.0
        if max_raw_x == 0:
            max_raw_x = 1.0

        # Apply Horizontal Scaling to branches
        x_coords = {clade: x * self.h_scale for clade, x in raw_x_coords.items()}
        max_x = max_raw_x * self.h_scale

        target_x = max_x * 1.04
        min_stub = max_x * 0.015 if not is_cladogram else 0.0

        # Draw branches & support
        for clade in tree.find_clades():
            px = x_coords[clade]
            py = y_coords[clade]

            if not clade.is_terminal() and clade.clades:
                c_ys = [y_coords[c] for c in clade.clades]
                ax.plot([px, px], [min(c_ys), max(c_ys)], color=branch_color, lw=1.8, solid_capstyle="round")

            for child in clade.clades:
                cx = x_coords[child]
                cy = y_coords[child]

                draw_cx = max(cx, px + min_stub) if child.is_terminal() else cx
                ax.plot([px, draw_cx], [cy, cy], color=branch_color, lw=1.8, solid_capstyle="round")

                supp_text = child.name or ""
                if not child.is_terminal() and supp_text and support_mode != 4:
                    should_draw, display_str = self.parse_support(supp_text, support_mode)
                    if should_draw and display_str:
                        # Position text to the right of ancestor node px so it never overlaps the vertical branch line
                        text_x = px + max(max_x * 0.006, (cx - px) * 0.18)
                        ax.text(
                            text_x, cy + 0.08, display_str,
                            fontsize=max(6, font_size - 2),
                            color="#c0392b" if is_paper else "#f5a97f",
                            fontweight="bold",
                            ha="left", va="bottom",
                            bbox=dict(
                                boxstyle="round,pad=0.15",
                                facecolor=badge_bg,
                                edgecolor="#cbd5e1" if is_paper else "#363a4f",
                                lw=0.5,
                                alpha=0.92,
                            ),
                        )

        # Draw Leaf labels
        query = self.search_query.strip().lower()
        self.leaf_positions = {}
        for leaf in leaves:
            raw_lx = x_coords[leaf]
            lx = max(raw_lx, raw_lx + min_stub) if not is_cladogram else raw_lx
            ly = y_coords[leaf]
            label = leaf.name.replace("_", " ") if leaf.name else "unnamed"
            is_matched = bool(query and query in label.lower())

            if align_tips:
                if target_x > lx:
                    ax.plot([lx, target_x], [ly, ly], color=leader_color, lw=0.8, ls=":")
                text_x = target_x + max_x * 0.02
            else:
                text_x = lx + max_x * 0.02

            if leaf.name:
                self.leaf_positions[leaf.name] = (lx, ly, text_x)

            lbl_color = "#f5a97f" if is_matched else text_color
            lbl_weight = "bold" if is_matched else "normal"
            display_label = f"[*] {label}" if is_matched else label

            ax.text(
                text_x, ly, display_label,
                fontsize=font_size + (1 if is_matched else 0),
                fontstyle="italic",
                fontweight=lbl_weight,
                color=lbl_color,
                va="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#24273a", edgecolor="#f5a97f", lw=1.5) if is_matched else None,
            )

        # Scale bar or Geological Time Scale
        if self.time_scale_cb.isChecked():
            num_ticks = 2 if self.compact_mode else 5
            scale_y = -0.55 if self.compact_mode else -0.70
            tick_h = 0.12 if self.compact_mode else 0.15
            label_y = scale_y - (0.20 if self.compact_mode else 0.25)
            title_y = scale_y - (0.50 if self.compact_mode else 0.70)
            ylim_bottom = -1.15 if self.compact_mode else -1.60

            ax.plot([0, max_x], [scale_y, scale_y], color=branch_color, lw=2.0)
            for i in range(num_ticks + 1):
                frac = i / num_ticks
                tx = frac * max_x
                age = (1.0 - frac) * max_raw_x
                ax.plot([tx, tx], [scale_y, scale_y - tick_h], color=branch_color, lw=1.5)
                ax.plot([tx, tx], [scale_y, num_leaves - 0.5], color=leader_color, lw=0.6, ls=":", alpha=0.35)

                if i == num_ticks:
                    lbl = "0 (現今)" if self.compact_mode else "0 (現今/Present)"
                else:
                    if max_raw_x >= 10.0:
                        lbl = f"{age:.1f} Ma"
                    elif max_raw_x >= 1.0:
                        lbl = f"{age:.2f} Ma"
                    else:
                        lbl = f"{age:g}"

                ax.text(
                    tx, label_y, lbl,
                    ha="center", va="top", fontsize=max(6, font_size - (2 if self.compact_mode else 2)),
                    color=text_color, fontweight="bold"
                )

            title_text = "地質年代時間軸 (Ma)" if self.compact_mode else "地質年代時間軸 (Geological Time Scale)"
            ax.text(
                max_x * 0.5, title_y, title_text,
                ha="center", va="top", fontsize=max(7, font_size - 1),
                color="#008287" if is_paper else "#8aadf4", fontweight="bold"
            )
            ax.set_ylim(ylim_bottom, num_leaves - 0.2)
        elif not is_cladogram:
            pow10 = 10 ** np.floor(np.log10(max_raw_x))
            normalized = max_raw_x / pow10
            scale_len_raw = pow10 * (1.0 if normalized >= 5 else (0.5 if normalized >= 2 else 0.2))
            drawn_scale_len = scale_len_raw * self.h_scale
            scale_y = -0.50 if self.compact_mode else -0.60
            label_y = scale_y - 0.20
            ylim_bottom = -0.95 if self.compact_mode else -1.20

            ax.plot([0, drawn_scale_len], [scale_y, scale_y], color=branch_color, lw=2.5, solid_capstyle="butt")
            ax.text(
                drawn_scale_len * 0.5, label_y, f"{scale_len_raw:g} substitutions/site",
                ha="center", va="top", fontsize=max(6, font_size - 2), color=text_color
            )
            ax.set_ylim(ylim_bottom, num_leaves - 0.2)
        else:
            ax.set_ylim(-0.4 if self.compact_mode else -0.5, num_leaves - 0.2)

        if self.compact_mode:
            x_max_limit = (target_x + max_x * 0.95) if align_tips else (max_x * 2.25)
        else:
            x_max_limit = (target_x + max_x * 0.65) if align_tips else (max_x * 1.68)

        ax.set_xlim(-max_x * 0.04, x_max_limit)
        ax.axis("off")

        if self.compact_mode:
            self.fig.subplots_adjust(left=0.06, right=0.96, top=0.96, bottom=0.10)
        else:
            self.fig.tight_layout()

        self.canvas.draw()

    def render_circular_tree(self, tree, leaves, num_leaves, is_cladogram, support_mode, font_size):
        dim = max(7.5, min(16.0, (5.5 + num_leaves * 0.14) * (self.h_scale ** 0.5)))
        dim_px = int(dim * 100)
        self.fig.set_size_inches(dim, dim)
        self.canvas.setMinimumSize(dim_px, dim_px)
        self.canvas.resize(dim_px, dim_px)

        ax = self.fig.add_subplot(111, polar=True)
        is_paper = self.theme_combo.currentIndex() == 0
        bg_color = "#ffffff" if is_paper else "#181926"
        branch_color = "#2c3e50" if is_paper else "#8aadf4"
        text_color = "#2c3e50" if is_paper else "#cad3f5"
        badge_bg = "#ffffff" if is_paper else "#1e2030"

        self.fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        start_angle = np.deg2rad(15)
        end_angle = np.deg2rad(345)
        angles = np.linspace(start_angle, end_angle, num_leaves)
        theta_coords = {leaf: angles[i] for i, leaf in enumerate(leaves)}

        r_coords = {}
        def get_r_coords(clade, curr_r=0.0):
            bl = clade.branch_length if clade.branch_length is not None else 0.01
            node_r = curr_r + bl
            r_coords[clade] = node_r
            for child in clade.clades:
                get_r_coords(child, node_r)

        root_offset = 0.05 if is_cladogram else (max(0.001, (tree.root.branch_length or 0.01) * 0.2))
        get_r_coords(tree.root, root_offset)

        def get_theta_coords(clade):
            if clade.is_terminal():
                return theta_coords[clade]
            child_thetas = [get_theta_coords(c) for c in clade.clades]
            t = np.mean(child_thetas)
            theta_coords[clade] = t
            return t

        get_theta_coords(tree.root)
        max_r = max(r_coords.values()) if r_coords.values() else 1.0

        for clade in tree.find_clades():
            pr = r_coords[clade]
            pt = theta_coords[clade]

            if not clade.is_terminal() and clade.clades:
                child_thetas = [theta_coords[c] for c in clade.clades]
                min_t, max_t = min(child_thetas), max(child_thetas)
                t_arc = np.linspace(min_t, max_t, 35)
                ax.plot(t_arc, [pr] * len(t_arc), color=branch_color, lw=1.4)

            for child in clade.clades:
                cr = r_coords[child]
                ct = theta_coords[child]
                ax.plot([ct, ct], [pr, cr], color=branch_color, lw=1.4)

                supp_text = child.name or ""
                if not child.is_terminal() and supp_text and support_mode != 4:
                    should_draw, display_str = self.parse_support(supp_text, support_mode)
                    if should_draw and display_str:
                        ax.text(
                            ct, pr + (cr - pr) * 0.5, display_str,
                            fontsize=max(5, font_size - 3), color="#c0392b" if is_paper else "#f5a97f",
                            fontweight="bold", ha="center", va="center",
                            bbox=dict(boxstyle="round,pad=0.1", facecolor=badge_bg, edgecolor="none", alpha=0.85),
                        )

        query = self.search_query.strip().lower()
        for leaf in leaves:
            lr = r_coords[leaf]
            lt = theta_coords[leaf]
            label = leaf.name.replace("_", " ") if leaf.name else "unnamed"
            is_matched = bool(query and query in label.lower())
            deg = np.rad2deg(lt)

            if 90 < deg < 270:
                rot = deg + 180
                ha = "right"
            else:
                rot = deg
                ha = "left"

            lbl_color = "#f5a97f" if is_matched else text_color
            lbl_weight = "bold" if is_matched else "normal"
            display_label = f"[*] {label}" if is_matched else label

            ax.text(
                lt, max_r * 1.03, display_label,
                fontsize=max(6, font_size - 1) + (1 if is_matched else 0),
                fontstyle="italic",
                fontweight=lbl_weight,
                color=lbl_color,
                rotation=rot,
                rotation_mode="anchor",
                ha=ha,
                va="center",
            )

        ax.set_ylim(0, max_r * 1.45)
        ax.axis("off")
        self.fig.tight_layout()
        self.canvas.draw()

    def parse_support(self, supp_text: str, support_mode: int) -> tuple[bool, str]:
        alrt_val = None
        ufboot_val = None

        if "/" in supp_text:
            parts = supp_text.split("/")
            try:
                alrt_val = float(parts[0])
                ufboot_val = float(parts[1])
            except ValueError:
                pass
        else:
            try:
                ufboot_val = float(supp_text)
            except ValueError:
                pass

        if support_mode == 0:  # UFBoot >= 70%
            if ufboot_val is not None and ufboot_val >= 70:
                return True, f"{int(ufboot_val)}"
        elif support_mode == 1:  # UFBoot >= 90%
            if ufboot_val is not None and ufboot_val >= 90:
                return True, f"{int(ufboot_val)}"
        elif support_mode == 2:  # Full SH-aLRT / UFBoot
            return True, supp_text
        elif support_mode == 3:  # Show all
            return True, supp_text

        return False, ""

    def export_image(self, file_path: str | Path | None = None, dpi: int = 300, show_alert: bool = True):
        if not self.tree:
            if show_alert:
                QMessageBox.warning(self, "警告", "目前尚未載入演化樹。")
            return

        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "儲存 300 DPI 論文發表級演化樹",
                "phylogenetic_tree_publication.png",
                "PNG 高清圖 (*.png);;SVG 向量圖 (*.svg);;PDF 文件 (*.pdf)",
            )

        if file_path:
            try:
                self.fig.savefig(str(file_path), dpi=dpi, bbox_inches="tight", facecolor=self.fig.get_facecolor())
                if show_alert:
                    QMessageBox.information(
                        self, "輸出成功", f"已成功產出發表級演化樹圖片！\n路徑: {file_path}"
                    )
            except Exception as e:
                if show_alert:
                    QMessageBox.critical(self, "輸出失敗", f"無法儲存圖片:\n{str(e)}")

    def copy_newick(self):
        if not self.tree:
            if not self.current_tree_file or not self.current_tree_file.exists():
                QMessageBox.warning(self, "警告", "找不到 Newick 樹檔。")
                return
            with open(self.current_tree_file, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            import io
            buf = io.StringIO()
            Phylo.write(self.tree, buf, "newick")
            content = buf.getvalue().strip()

        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(content)
        self.root_status_label.setText("✓ Newick 字串已複製")
