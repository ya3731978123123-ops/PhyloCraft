"""
Scratch Workspace Canvas (中間大空白工作台)
Inspired by Scratch's central workspace:
- Pure white expansive canvas (#FFFFFF)
- Free-form movable blocks with automatic magnetic snap (卡榫自動吸附)
- Dynamic Block Addition & Removal (可自由新增、刪除、複製積木)
- Stack management: dragging a parent block moves its entire downstream child stack
- Top Hat Block: '當 點擊綠旗 (When Green Flag Clicked)'
- Floating toolbar: Add Block (➕ 新增積木), Auto-Align (一鍵自動整列), Zen Mode (🖥️ 純淨畫布), Zoom (+) (-) (=)
- Canvas panning by dragging on empty canvas
- 100% compatible with existing test suite and ProjectManager
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QPushButton,
    QFrame,
    QLabel,
    QMenu,
)
from PySide6.QtCore import Qt, Signal, QPoint

from src.core.project_manager import STEP_KEYS, PhyloProject, StepRecord
from src.ui.widgets.scratch_blocks import ScratchHatBlock, ScratchPuzzleBlock, STEP_TITLES_EXTENDED


class ScratchCanvasContainer(QWidget):
    """
    Expansive White Container widget hosting freely-positioned Scratch blocks.
    Supports mouse dragging on empty background to pan the scroll area.
    """

    def __init__(self, scroll_area: QScrollArea, parent: QWidget | None = None):
        super().__init__(parent)
        self.scroll_area = scroll_area
        self.setStyleSheet("background-color: #FFFFFF;")
        self.setMinimumSize(1600, 1400)
        self.panning = False
        self.pan_start_pos = QPoint()
        self.h_start = 0
        self.v_start = 0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.panning = True
            self.pan_start_pos = event.globalPosition().toPoint()
            self.h_start = self.scroll_area.horizontalScrollBar().value()
            self.v_start = self.scroll_area.verticalScrollBar().value()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.panning:
            delta = event.globalPosition().toPoint() - self.pan_start_pos
            self.scroll_area.horizontalScrollBar().setValue(self.h_start - delta.x())
            self.scroll_area.verticalScrollBar().setValue(self.v_start - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.panning:
            self.panning = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class ScratchWorkspaceCanvas(QWidget):
    """
    Scratch-style Central White Canvas.
    Hosts interlocking puzzle blocks on an expansive white background with magnetic snapping.
    Supports dynamic block creation, deletion, multi-branching, and auto-alignment.
    """

    step_jump_requested = Signal(str)
    inspect_step_requested = Signal(str)
    run_step_requested = Signal(str)
    fork_step_requested = Signal(str)
    project_note_saved = Signal(str, str)
    open_preferences_requested = Signal(str)
    flag_clicked = Signal()
    block_added = Signal(object)
    block_removed = Signal(object)
    zen_mode_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.cards: dict[str, ScratchPuzzleBlock] = {}
        self.blocks: list[ScratchPuzzleBlock] = []
        self.block_counter: int = 0
        self.zoom_level = 1.0
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Canvas Action Toolbar (➕ 新增積木 + 🪄 一鍵自動整列 + 🖥️ 純淨畫布 + 視野縮放)
        self.canvas_toolbar = QFrame()
        self.canvas_toolbar.setFixedHeight(36)
        self.canvas_toolbar.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-bottom: 1px solid #CBD5E1;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
        """)
        tb_layout = QHBoxLayout(self.canvas_toolbar)
        tb_layout.setContentsMargins(10, 3, 10, 3)
        tb_layout.setSpacing(6)

        # Add Block Quick Button with Menu
        self.btn_add_block = QPushButton("➕ 新增積木")
        self.btn_add_block.setFixedHeight(26)
        self.btn_add_block.setCursor(Qt.PointingHandCursor)
        self.btn_add_block.setStyleSheet("""
            QPushButton {
                background-color: #008287;
                color: #FFFFFF;
                border: 1px solid #00666B;
                border-radius: 4px;
                padding: 2px 14px 2px 6px;
                font-size: 11px;
                font-weight: bold;
                min-width: 84px;
            }
            QPushButton:hover {
                background-color: #00666B;
            }
        """)
        add_menu = QMenu(self)
        add_menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px;
                font-size: 11px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #E6F7F7;
                color: #008287;
            }
        """)

        tools_list = [
            ("raw", "📁 01. 原始序列輸入 (FASTA Input)"),
            ("sanitize", "🧹 02. IUPAC 品管清洗 (Sanitize QC)"),
            ("alignment", "🧬 03. MAFFT 多重比對 (MAFFT Align)"),
            ("alignment_muscle", "🧬 03B. MUSCLE 結構感知比對 (MUSCLE)"),
            ("trimming", "✂️ 04. trimAl 保守位點修剪 (trimAl)"),
            ("modelfinder", "🔬 05. ModelFinder 最佳模式評選 (ModelFinder)"),
            ("tree", "🌳 06. IQ-TREE 2 ML 建樹 (IQ-TREE)"),
            ("tree_fasttree", "⚡ 06B. FastTree 2 超極速建樹 (FastTree)"),
            ("timetree", "⏱ 07. LSD2 分子鐘定年 (TimeTree)"),
        ]
        for key, name in tools_list:
            act = add_menu.addAction(name)
            act.triggered.connect(lambda chk=False, k=key: self.add_block(k, auto_snap=True))
        self.btn_add_block.setMenu(add_menu)
        tb_layout.addWidget(self.btn_add_block)

        self.btn_align = QPushButton("🪄 整列")
        self.btn_align.setFixedHeight(26)
        self.btn_align.setCursor(Qt.PointingHandCursor)
        self.btn_align.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #008287;
                border: 1px solid #008287;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        self.btn_align.setToolTip("自動磁吸整列所有積木為標準生物演化分析流水線 (Auto-Align)")
        self.btn_align.clicked.connect(self.auto_arrange)
        tb_layout.addWidget(self.btn_align)

        self.btn_reset_stack = QPushButton("↺ 重置")
        self.btn_reset_stack.setFixedHeight(26)
        self.btn_reset_stack.setCursor(Qt.PointingHandCursor)
        self.btn_reset_stack.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                color: #0F172A;
            }
        """)
        self.btn_reset_stack.setToolTip("清空並重新加載 7 步標準演化分析積木鏈 (Reset Standard Pipeline)")
        self.btn_reset_stack.clicked.connect(self.load_default_pipeline)
        tb_layout.addWidget(self.btn_reset_stack)

        self.btn_zen = QPushButton("🖥️ 純淨")
        self.btn_zen.setFixedHeight(26)
        self.btn_zen.setCheckable(True)
        self.btn_zen.setCursor(Qt.PointingHandCursor)
        self.btn_zen.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                color: #008287;
            }
            QPushButton:checked {
                background-color: #008287;
                color: #FFFFFF;
                font-weight: bold;
            }
        """)
        self.btn_zen.setToolTip("一鍵收合左右側邊欄與日誌，享受 100% 全螢幕沉浸式積木畫布")
        self.btn_zen.toggled.connect(self.zen_mode_toggled.emit)
        tb_layout.addWidget(self.btn_zen)

        tb_layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #CBD5E1; max-height: 18px;")
        tb_layout.addWidget(sep)

        self.zoom_lbl = QLabel("視野: 100%")
        self.zoom_lbl.setStyleSheet("color: #475569; font-size: 11px; font-weight: 500; border: none; background: transparent;")
        tb_layout.addWidget(self.zoom_lbl)

        btn_style = """
            QPushButton {
                background-color: #FFFFFF;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #008287;
            }
        """

        self.btn_plus = QPushButton("➕ 放大")
        self.btn_plus.setFixedHeight(24)
        self.btn_plus.setStyleSheet(btn_style)
        self.btn_plus.setToolTip("放大積木畫布視野")
        self.btn_plus.clicked.connect(self.zoom_in)
        tb_layout.addWidget(self.btn_plus)

        self.btn_minus = QPushButton("➖ 縮小")
        self.btn_minus.setFixedHeight(24)
        self.btn_minus.setStyleSheet(btn_style)
        self.btn_minus.setToolTip("縮小積木畫布視野")
        self.btn_minus.clicked.connect(self.zoom_out)
        tb_layout.addWidget(self.btn_minus)

        self.btn_reset = QPushButton("↺ 100%")
        self.btn_reset.setFixedHeight(24)
        self.btn_reset.setStyleSheet(btn_style)
        self.btn_reset.setToolTip("重置積木畫布視野為 100%")
        self.btn_reset.clicked.connect(self.zoom_reset)
        tb_layout.addWidget(self.btn_reset)

        main_layout.addWidget(self.canvas_toolbar)
        self.action_bar = self.canvas_toolbar

        # 2. Scrollable Pure White Canvas (中間大空白)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setStyleSheet("""
            QScrollArea {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }
        """)

        self.container = ScratchCanvasContainer(self.scroll)
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll, 1)

        # Top Hat Block: '當 點擊綠旗 (When Green Flag Clicked)'
        self.hat_block = ScratchHatBlock(self.container)
        self.hat_block.canvas = self
        self.hat_block.clicked.connect(self.flag_clicked.emit)

        # Load standard pipeline
        self.load_default_pipeline()

    def load_default_pipeline(self):
        """Builds or resets to the standard 7-step Scratch pipeline."""
        # Clear existing non-hat blocks
        for b in list(self.blocks):
            b.hide()
            b.deleteLater()
        self.blocks.clear()
        self.cards.clear()

        # Instantiate standard blocks
        for step_key in STEP_KEYS:
            card = ScratchPuzzleBlock(step_key, self.container, instance_id=step_key)
            card.canvas = self
            card.jump_tab_requested.connect(self.step_jump_requested.emit)
            card.inspect_requested.connect(self.inspect_step_requested.emit)
            card.run_single_requested.connect(self.run_step_requested.emit)
            card.fork_requested.connect(self.fork_step_requested.emit)
            card.note_changed.connect(self.project_note_saved.emit)
            card.open_preferences_requested.connect(self.open_preferences_requested.emit)
            card.delete_requested.connect(self.remove_block)

            self.cards[step_key] = card
            self.blocks.append(card)

        self.auto_arrange()

    def add_block(
        self,
        module_type: str,
        pos: QPoint | None = None,
        auto_snap: bool = True,
        custom_title: str | None = None,
    ) -> ScratchPuzzleBlock:
        """
        Dynamically instantiates and mounts a new Scratch block onto the canvas.
        Can snap magnetically to the chain or sit at a custom position.
        """
        self.block_counter += 1
        inst_id = f"{module_type}_{self.block_counter}"
        if module_type in STEP_KEYS and module_type not in self.cards:
            inst_id = module_type

        card = ScratchPuzzleBlock(module_type, self.container, instance_id=inst_id, custom_title=custom_title)
        card.canvas = self
        card.jump_tab_requested.connect(self.step_jump_requested.emit)
        card.inspect_requested.connect(self.inspect_step_requested.emit)
        card.run_single_requested.connect(self.run_step_requested.emit)
        card.fork_requested.connect(self.fork_step_requested.emit)
        card.note_changed.connect(self.project_note_saved.emit)
        card.open_preferences_requested.connect(self.open_preferences_requested.emit)
        card.delete_requested.connect(self.remove_block)

        self.cards[inst_id] = card
        if module_type not in self.cards:
            self.cards[module_type] = card
        self.blocks.append(card)

        # Apply current zoom level
        card.setMinimumWidth(int(500 * self.zoom_level))
        card.adjustSize()

        if pos is not None:
            card.move(pos)
        elif auto_snap:
            # Snap below lowest tail of current chain
            tail = self.hat_block
            visited = {id(self.hat_block)}
            while getattr(tail, "downstream_block", None):
                nxt = tail.downstream_block
                if id(nxt) in visited:
                    break
                visited.add(id(nxt))
                tail = nxt

            target_y = tail.y() + tail.height() - 4
            card.move(tail.x(), target_y)
            tail.downstream_block = card
            card.upstream_block = tail
        else:
            offset = (len(self.blocks) % 5) * 30
            card.move(80 + offset, 100 + offset)

        card.show()
        self.update_container_bounds()
        self.block_added.emit(card)
        return card

    def remove_block(self, card: ScratchPuzzleBlock):
        """
        Removes a block from the canvas and smoothly heals the upstream/downstream connection.
        """
        up = getattr(card, "upstream_block", None)
        down = getattr(card, "downstream_block", None)

        if up:
            up.downstream_block = down
        if down:
            down.upstream_block = up
            # Shift downstream chain up to close gap
            target_y = (up.y() + up.height() - 4) if up else card.y()
            shift_dy = target_y - down.y()
            shift_dx = (up.x() if up else card.x()) - down.x()
            scurr = down
            s_vis = {id(card)}
            while scurr and id(scurr) not in s_vis:
                s_vis.add(id(scurr))
                scurr.move(scurr.x() + shift_dx, scurr.y() + shift_dy)
                scurr = getattr(scurr, "downstream_block", None)

        card.upstream_block = None
        card.downstream_block = None

        keys_to_del = [k for k, v in self.cards.items() if v is card]
        for k in keys_to_del:
            self.cards.pop(k, None)
        if card in self.blocks:
            self.blocks.remove(card)

        card.hide()
        card.deleteLater()
        self.update_container_bounds()
        self.block_removed.emit(card)

    def auto_arrange(self):
        """
        Arranges all active blocks into a neat, magnetically-snapped Scratch pipeline stack.
        """
        start_x = 50
        curr_y = 35

        self.hat_block.move(start_x, curr_y)
        self.hat_block.upstream_block = None
        self.hat_block.show()

        prev = self.hat_block
        curr_y += self.hat_block.height() - 4

        # Arrange in order: standard STEP_KEYS first if present, then extra dynamic blocks
        ordered_blocks = []
        for step_key in STEP_KEYS:
            if step_key in self.cards and self.cards[step_key] not in ordered_blocks and self.cards[step_key].isVisible():
                ordered_blocks.append(self.cards[step_key])
        for b in self.blocks:
            if b not in ordered_blocks and b.isVisible():
                ordered_blocks.append(b)

        for card in ordered_blocks:
            card.move(start_x, curr_y)
            card.show()
            prev.downstream_block = card
            card.upstream_block = prev
            prev = card
            curr_y += card.height() - 4

        # Disconnect end of chain
        prev.downstream_block = None
        self.update_container_bounds()

    def _is_descendant(self, start: QWidget, target: QWidget) -> bool:
        """
        Checks whether target is already in start's downstream chain.
        Guarded against cycles using visited set.
        """
        curr = getattr(start, "downstream_block", None)
        visited = {id(start)}
        while curr:
            if curr is target:
                return True
            if id(curr) in visited:
                break
            visited.add(id(curr))
            curr = getattr(curr, "downstream_block", None)
        return False

    def update_container_bounds(self):
        """
        Dynamically adjusts container size to ensure no blocks are clipped.
        """
        raw_list = [self.hat_block] + list(self.cards.values()) + self.blocks
        unique_blocks = list({id(b): b for b in raw_list}.values())
        max_x = max((b.x() + b.width() for b in unique_blocks if b.isVisible()), default=500)
        max_y = max((b.y() + b.height() for b in unique_blocks if b.isVisible()), default=600)
        needed_w = max(1600, max_x + 300)
        needed_h = max(1400, max_y + 300)
        if needed_w > self.container.width() or needed_h > self.container.height():
            self.container.setMinimumSize(max(self.container.width(), needed_w), max(self.container.height(), needed_h))

    def check_block_snap(self, block: QWidget):
        """
        Magnetic snapping detector.
        If block's top notch is close to another block's bottom tab, snap it!
        Protected against cyclic linkages.
        """
        raw_list = [self.hat_block] + list(self.cards.values()) + self.blocks
        candidates = list({id(b): b for b in raw_list}.values())
        b_x = block.x()
        b_y = block.y()

        # 1. Check if 'block' should snap BELOW another block
        for other in candidates:
            if other is block:
                continue
            # Cyclic prevention: cannot snap below own downstream descendant!
            if self._is_descendant(block, other):
                continue

            o_x = other.x()
            target_y = other.y() + other.height() - 4

            if abs(b_x - o_x) < 70 and abs(b_y - target_y) < 32:
                # Snap!
                dx = o_x - b_x
                dy = target_y - b_y
                block.move(o_x, target_y)

                # Move downstream children along with it
                curr = getattr(block, "downstream_block", None)
                visited = {id(block)}
                while curr and id(curr) not in visited:
                    visited.add(id(curr))
                    curr.move(curr.x() + dx, curr.y() + dy)
                    curr = getattr(curr, "downstream_block", None)

                # Link: if other already had a downstream block, connect it to tail of block
                old_down = getattr(other, "downstream_block", None)
                if old_down and old_down is not block:
                    tail = block
                    t_visited = {id(block)}
                    while getattr(tail, "downstream_block", None):
                        nxt = tail.downstream_block
                        if id(nxt) in t_visited:
                            break
                        t_visited.add(id(nxt))
                        tail = nxt
                    tail.downstream_block = old_down
                    old_down.upstream_block = tail
                    # Shift old_down chain down to make room
                    shift_target_y = tail.y() + tail.height() - 4
                    shift_dy = shift_target_y - old_down.y()
                    shift_dx = tail.x() - old_down.x()
                    scurr = old_down
                    s_vis = {id(tail)}
                    while scurr and id(scurr) not in s_vis:
                        s_vis.add(id(scurr))
                        scurr.move(scurr.x() + shift_dx, scurr.y() + shift_dy)
                        scurr = getattr(scurr, "downstream_block", None)

                if hasattr(block, "upstream_block"):
                    block.upstream_block = other
                other.downstream_block = block
                self.update_container_bounds()
                return

        # 2. Check if another block should snap BELOW 'block'
        my_target_y = block.y() + block.height() - 4
        for other in candidates:
            if other is block or other is self.hat_block:
                continue
            if self._is_descendant(other, block):
                continue

            o_x = other.x()
            o_y = other.y()

            if abs(b_x - o_x) < 70 and abs(my_target_y - o_y) < 32:
                dx = b_x - o_x
                dy = my_target_y - o_y
                other.move(b_x, my_target_y)

                curr = getattr(other, "downstream_block", None)
                visited = {id(other)}
                while curr and id(curr) not in visited:
                    visited.add(id(curr))
                    curr.move(curr.x() + dx, curr.y() + dy)
                    curr = getattr(curr, "downstream_block", None)

                other.upstream_block = block
                block.downstream_block = other
                self.update_container_bounds()
                return

    def get_execution_sequence(self) -> list[str]:
        """
        Traverses the connected stack starting from the Hat block.
        Returns the ordered list of enabled step keys in the active Scratch script.
        """
        seq = []
        curr = self.hat_block.downstream_block
        visited = {id(self.hat_block)}
        while curr and id(curr) not in visited:
            visited.add(id(curr))
            if hasattr(curr, "step_key") and curr.enable_cb.isChecked():
                seq.append(curr.step_key)
            curr = getattr(curr, "downstream_block", None)

        if not seq:
            # Fallback to all enabled steps if disconnected
            seq = [k for k in STEP_KEYS if k in self.cards and self.cards[k].enable_cb.isChecked()]
        return seq

    def zoom_in(self):
        self.zoom_level = min(1.4, self.zoom_level + 0.1)
        self.apply_zoom()

    def zoom_out(self):
        self.zoom_level = max(0.75, self.zoom_level - 0.1)
        self.apply_zoom()

    def zoom_reset(self):
        self.zoom_level = 1.0
        self.apply_zoom()

    def apply_zoom(self):
        for card in list(self.cards.values()) + self.blocks:
            card.setMinimumWidth(int(500 * self.zoom_level))
            card.adjustSize()
        self.hat_block.setMinimumWidth(int(340 * self.zoom_level))
        self.hat_block.adjustSize()
        self.auto_arrange()
        if hasattr(self, "zoom_lbl"):
            self.zoom_lbl.setText(f"視野: {int(self.zoom_level * 100)}%")

    def load_project_state(self, project: PhyloProject):
        for step_key, card in self.cards.items():
            record = project.steps.get(step_key, StepRecord())
            card.set_record(record)
