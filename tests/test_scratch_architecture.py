"""
Unit and Integration Test Suite for Scratch Architecture Components:
- ScratchHatBlock
- ScratchPuzzleBlock
- ScratchWorkspaceCanvas
- ScratchStageWidget
- Full Stack Snapping, Insertion, and Cycle Prevention
"""

import sys
import os
os.environ["HEADLESS_TEST"] = "1"
import shutil
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from PySide6.QtWidgets import QApplication, QPushButton, QComboBox, QLineEdit, QTextEdit
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QMouseEvent

# Ensure headless Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from src.core.project_manager import ProjectManager, PhyloProject, STEP_KEYS
from src.ui.widgets.scratch_blocks import ScratchHatBlock, ScratchPuzzleBlock
from src.ui.widgets.scratch_canvas import ScratchWorkspaceCanvas
from src.ui.widgets.scratch_stage import ScratchStageWidget
from src.ui.tabs.workstation_tab import WorkstationTab
from src.config import OUTPUT_DIR, DATA_DIR


def run_scratch_tests():
    app = QApplication.instance() or QApplication(sys.argv)
    test_dir = Path(tempfile.mkdtemp(prefix="scratch_test_"))

    print("\n" + "=" * 60)
    print("🧩 STARTING SCRATCH BIOINFORMATICS ARCHITECTURE AUDIT")
    print("=" * 60)

    try:
        # -------------------------------------------------------------
        # Test 1: ScratchHatBlock
        # -------------------------------------------------------------
        print("\n[Scratch 1/5] Testing ScratchHatBlock Event Handling...")
        canvas = ScratchWorkspaceCanvas()
        canvas.show()
        app.processEvents()
        hat = canvas.hat_block
        assert hat is not None
        assert hat.upstream_block is None

        # Verify Hat click emission
        clicked_fired = []
        hat.clicked.connect(lambda: clicked_fired.append(True))
        # Simulate click without movement
        p_event = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(20, 20), QPointF(20, 20), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        hat.mousePressEvent(p_event)
        r_event = QMouseEvent(QMouseEvent.MouseButtonRelease, QPointF(20, 20), QPointF(20, 20), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        hat.mouseReleaseEvent(r_event)
        assert len(clicked_fired) == 1, "Hat block click was not emitted!"
        print("  ✓ Hat block click & signal emission verified!")

        # -------------------------------------------------------------
        # Test 2: ScratchPuzzleBlock Hit Testing & Drawers
        # -------------------------------------------------------------
        print("\n[Scratch 2/5] Testing ScratchPuzzleBlock Hit Testing & Drawers...")
        raw_card = canvas.cards["raw"]
        assert raw_card is not None

        # Test expanding parameter drawer
        raw_card.toggle_params()
        assert raw_card.params_expanded is True
        assert not raw_card.params_drawer.isHidden()

        # Test expanding notes drawer and typing notes
        raw_card.toggle_notes()
        assert raw_card.notes_expanded is True
        assert not raw_card.note_drawer.isHidden()
        raw_card.note_edit.setPlainText("測試實驗記錄備忘")
        assert "測試實驗記錄備忘" in raw_card.note_edit.toPlainText()
        assert "8 字" in raw_card.note_toggle_btn.text()

        # Test hit testing on note_edit viewport: should NOT initiate dragging
        note_pos = raw_card.note_edit.mapTo(raw_card, QPoint(10, 10))
        press_evt = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(note_pos), QPointF(note_pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        raw_card.mousePressEvent(press_evt)
        assert raw_card.is_dragging is False, "Clicking note_edit initiated block dragging!"

        # Test hit testing on run button: should NOT initiate dragging
        btn_pos = raw_card.run_btn.mapTo(raw_card, QPoint(5, 5))
        press_btn = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(btn_pos), QPointF(btn_pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        raw_card.mousePressEvent(press_btn)
        assert raw_card.is_dragging is False, "Clicking run_btn initiated block dragging!"

        # Test clicking summary_chip directly triggers inspect_requested without drag
        inspect_fired = []
        raw_card.inspect_requested.connect(lambda k: inspect_fired.append(k))
        chip_pos = raw_card.summary_chip.mapTo(raw_card, QPoint(10, 10))
        press_chip = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(chip_pos), QPointF(chip_pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        raw_card.mousePressEvent(press_chip)
        assert raw_card.is_dragging is False, "Clicking summary_chip initiated block dragging!"
        assert len(inspect_fired) == 1 and inspect_fired[0] == "raw", "Clicking summary_chip did not emit inspect_requested!"

        # Test inspect_btn is always enabled and emits inspect_requested
        assert raw_card.inspect_btn.isEnabled() is True
        raw_card.inspect_btn.click()
        assert len(inspect_fired) == 2

        # Test collapsing drawers
        raw_card.toggle_params()
        assert raw_card.params_expanded is False
        raw_card.toggle_notes()
        assert raw_card.notes_expanded is False

        # Test running glow state
        raw_card.set_running_state(True)
        assert raw_card.is_running is True
        raw_card.set_running_state(False)
        assert raw_card.is_running is False
        print("  ✓ Interactive controls hit-testing, drawers, and glow state verified!")

        # -------------------------------------------------------------
        # Test 3: ScratchWorkspaceCanvas Snapping & Cycle Prevention
        # -------------------------------------------------------------
        print("\n[Scratch 3/5] Testing Magnetic Snapping & Cycle Prevention...")
        canvas.auto_arrange()

        # Verify initial linear stack
        seq = canvas.get_execution_sequence()
        assert seq == ["raw", "sanitize", "alignment", "trimming", "modelfinder", "tree", "timetree"]

        # Detach trimming and move it away
        trim_card = canvas.cards["trimming"]
        trim_card.move(500, 500)
        trim_card.upstream_block = None

        # Test Cycle Prevention: Try snapping raw (ancestor) below tree (descendant)
        canvas.cards["raw"].move(canvas.cards["tree"].x(), canvas.cards["tree"].y() + canvas.cards["tree"].height() - 2)
        # Attempt snap
        canvas.check_block_snap(canvas.cards["raw"])
        # Verify no cycle was created
        visited = set()
        curr = canvas.hat_block
        infinite_loop = False
        count = 0
        while curr:
            if id(curr) in visited:
                infinite_loop = True
                break
            visited.add(id(curr))
            curr = getattr(curr, "downstream_block", None)
            count += 1
            if count > 20:
                infinite_loop = True
                break
        assert not infinite_loop, "A cyclic loop was created in the block stack!"
        print("  ✓ Strict Cycle Prevention verified (ancestors cannot snap below descendants)!")

        # Test auto_arrange restoring clean stack
        canvas.auto_arrange()
        seq_after = canvas.get_execution_sequence()
        assert seq_after == ["raw", "sanitize", "alignment", "trimming", "modelfinder", "tree", "timetree"]

        # Test dynamic container expansion
        prev_w = canvas.container.width()
        prev_h = canvas.container.height()
        canvas.cards["timetree"].move(2000, 1800)
        canvas.update_container_bounds()
        assert canvas.container.width() >= 2300, "Container did not expand horizontally!"
        assert canvas.container.height() >= 2100, "Container did not expand vertically!"

        # Reset layout
        canvas.auto_arrange()
        print("  ✓ Stack auto-alignment & dynamic container bounds expansion verified!")

        # -------------------------------------------------------------
        # Test 4: ScratchStageWidget Outcomes & Controls
        # -------------------------------------------------------------
        print("\n[Scratch 4/5] Testing ScratchStageWidget Controls & Modes...")
        stage = ScratchStageWidget()

        # Test Mode Switching
        stage.switch_stage_view(0)
        assert stage.stack.currentIndex() == 0
        stage.switch_stage_view(1)
        assert stage.stack.currentIndex() == 1
        stage.switch_stage_view(2)
        assert stage.stack.currentIndex() == 2

        # Test Attributes Bar Updating
        stage.update_attributes(taxa=6, sites=1140, model="F81+F", boot=1000)
        assert "6" in stage.pill_taxa.text()
        assert "1140" in stage.pill_sites.text()
        assert "F81+F" in stage.pill_model.text()
        assert "1000" in stage.pill_boot.text()

        # Test loading tree into stage and exporting publication image
        primates_tree = test_dir / "sample.tree"
        primates_tree.write_text("((A:0.1,B:0.2)90:0.3,C:0.4);\n", encoding="utf-8")
        stage.load_tree_file(primates_tree)
        assert stage.tree_canvas.tree is not None
        out_stage_img = test_dir / "stage_tree_export.png"
        stage.tree_canvas.export_image(file_path=out_stage_img, dpi=300, show_alert=False)
        assert out_stage_img.exists() and out_stage_img.stat().st_size > 0

        # Test Artifacts Library Chips
        selected_artifacts = []
        stage.artifact_selected.connect(lambda k: selected_artifacts.append(k))
        stage.art_buttons["tree"].click()
        assert "tree" in selected_artifacts
        stage.art_buttons["alignment"].click()
        assert "alignment" in selected_artifacts

        # Test Green Flag & Stop Buttons
        flag_ran = []
        stop_ran = []
        stage.run_pipeline_requested.connect(lambda: flag_ran.append(True))
        stage.stop_pipeline_requested.connect(lambda: stop_ran.append(True))
        stage.flag_btn.click()
        assert len(flag_ran) == 1
        stage.stop_btn.setEnabled(True)
        stage.stop_btn.click()
        assert len(stop_ran) == 1
        print("  ✓ Stage modes, attributes, artifact library, and run/stop controls verified!")

        # -------------------------------------------------------------
        # Test 5: Full WorkstationTab Scratch Integration
        # -------------------------------------------------------------
        print("\n[Scratch 5/5] Testing WorkstationTab Scratch Integration...")
        w_tab = WorkstationTab()
        w_tab.load_demo_project(show_alert=False, target_dir=test_dir)

        # Verify Stage attributes synced from demo project
        assert "6" in w_tab.stage.pill_taxa.text()
        assert "1140" in w_tab.stage.pill_sites.text()
        assert "F81+F" in w_tab.stage.pill_model.text()
        assert "1000" in w_tab.stage.pill_boot.text()

        # Verify execution sequence matches enabled blocks
        w_tab.preset_combo.setCurrentIndex(1)  # Fast topology (bypasses trimming & timetree)
        seq_fast = w_tab.block_canvas.get_execution_sequence()
        assert "trimming" not in seq_fast
        assert "timetree" not in seq_fast
        assert "raw" in seq_fast
        assert "tree" in seq_fast

        w_tab.preset_combo.setCurrentIndex(0)  # Standard
        seq_std = w_tab.block_canvas.get_execution_sequence()
        assert "trimming" in seq_std
        assert "timetree" not in seq_std

        # Verify Multi-Tab Canvas System
        assert w_tab.workflow_tabs.count() == 3
        custom_c = w_tab.create_canvas_tab("測試自訂畫布", preset_idx=2)
        assert w_tab.workflow_tabs.count() == 4
        w_tab.workflow_tabs.setCurrentWidget(custom_c)
        assert w_tab.block_canvas == custom_c
        assert "timetree" in w_tab.block_canvas.get_execution_sequence()

        # Verify Layout Preset Switching
        w_tab.show()
        w_tab.set_layout_mode("canvas_only")
        assert w_tab.toolbox.isHidden()
        assert w_tab.right_container.isHidden()
        assert not w_tab.canvas_box.isHidden()

        w_tab.set_layout_mode("split")
        assert w_tab.toolbox.isHidden()
        assert not w_tab.right_container.isHidden()

        w_tab.set_layout_mode("full")
        assert not w_tab.toolbox.isHidden()
        assert not w_tab.right_container.isHidden()

        # Verify Stage Pop-out & Docking
        w_tab.set_layout_mode("popout")
        assert w_tab.stage_dialog is not None
        assert w_tab.stage.is_popped_out is True
        w_tab.dock_stage()
        assert w_tab.stage_dialog is None
        assert w_tab.stage.is_popped_out is False

        # Verify Branch Forking creates dedicated workflow tab
        prev_tab_count = w_tab.workflow_tabs.count()
        w_tab.fork_branch("alignment", "Branch_Flexible_Test")
        assert w_tab.workflow_tabs.count() == prev_tab_count + 1
        assert "分支" in w_tab.workflow_tabs.tabText(w_tab.workflow_tabs.currentIndex())

        # Verify Live Terminal Code Runner Console toggle & collapse
        assert hasattr(w_tab, "live_console")
        assert w_tab.live_console.is_collapsed is True
        w_tab.toggle_terminal_console()
        assert w_tab.live_console.is_collapsed is False
        assert w_tab.btn_toggle_terminal.isChecked() is True
        w_tab.toggle_terminal_console()
        assert w_tab.live_console.is_collapsed is True
        assert w_tab.btn_toggle_terminal.isChecked() is False

        # Verify Inspector text area collapse toggle & Right Tab switching
        assert hasattr(w_tab, "btn_toggle_inspector")
        w_tab.right_tabs.setCurrentIndex(1)
        app.processEvents()
        assert w_tab.inspector_text.isVisible() is True
        w_tab.toggle_inspector_visibility()
        assert w_tab.inspector_text.isVisible() is False
        w_tab.inspect_step_data("raw")
        assert w_tab.inspector_text.isVisible() is True

        # Verify Top Bar & Side Panel Collapsible Controls
        assert hasattr(w_tab, "btn_toggle_top_bar")
        assert w_tab.tb_row1_widget.isVisible() is True
        w_tab.toggle_top_bar()
        assert w_tab.tb_row1_widget.isVisible() is False
        w_tab.toggle_top_bar()
        assert w_tab.tb_row1_widget.isVisible() is True

        # Verify Stage Artifacts Box Collapsible Toggle
        w_tab.right_tabs.setCurrentIndex(0)
        app.processEvents()
        assert hasattr(w_tab.stage, "btn_toggle_lib")
        assert w_tab.stage.lib_box.isVisible() is False
        w_tab.stage.toggle_lib_box()
        assert w_tab.stage.lib_box.isVisible() is True
        w_tab.stage.toggle_lib_box()
        assert w_tab.stage.lib_box.isVisible() is False

        # Clean close
        canvas.close()
        stage.close()
        w_tab.close()
        app.processEvents()
        print("  ✓ WorkstationTab Multi-Tab, Layout Switcher & Scratch Integration fully verified!")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        recent_f = OUTPUT_DIR / ".recent_projects.json"
        if recent_f.exists():
            recent_f.unlink(missing_ok=True)
        for p in OUTPUT_DIR.glob("*.phylo"):
            shutil.rmtree(p, ignore_errors=True)
        for p in OUTPUT_DIR.glob("*scratch_test*"):
            shutil.rmtree(p, ignore_errors=True)
        app.processEvents()

    print("\n" + "=" * 60)
    print("🎉 ALL 5 SCRATCH ARCHITECTURE TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 60)


if __name__ == "__main__":
    run_scratch_tests()
    sys.exit(0)
