import json
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from src.config import OUTPUT_DIR, DATA_DIR


STEP_KEYS = [
    "raw",
    "sanitize",
    "alignment",
    "trimming",
    "modelfinder",
    "tree",
    "timetree",
]

STEP_TITLES = {
    "raw": ("序列輸入 (Sequence Input)", "01_raw"),
    "sanitize": ("序列品管檢驗 (Sanitization & QC)", "02_sanitized"),
    "alignment": ("多重序列比對 (MAFFT Alignment)", "03_alignment"),
    "trimming": ("比對位點修剪 (trimAl Trimming)", "04_trimming"),
    "modelfinder": ("替代模型檢定 (ModelFinder Selection)", "05_modelfinder"),
    "tree": ("最大概似法建樹 (IQ-TREE Inference)", "06_phylogeny"),
    "timetree": ("分子鐘定年 (LSD2 TimeTree)", "07_timetree"),
}


@dataclass
class StepRecord:
    status: str = "pending"  # "pending", "running", "completed", "failed"
    timestamp: str = ""
    parameters: dict = field(default_factory=dict)
    command_line: str = ""
    output_files: list[str] = field(default_factory=list)
    summary: str = "尚未執行"
    student_notes: str = ""


@dataclass
class PhyloProject:
    name: str
    project_dir: str
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    description: str = "分子演化學與生物資訊學研究專案"
    author: str = "Researcher (Bioinformatics)"
    steps: dict[str, StepRecord] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "PhyloProject":
        steps_raw = data.get("steps", {})
        steps = {}
        for k in STEP_KEYS:
            if k in steps_raw:
                s_data = steps_raw[k]
                steps[k] = StepRecord(
                    status=s_data.get("status", "pending"),
                    timestamp=s_data.get("timestamp", ""),
                    parameters=s_data.get("parameters", {}),
                    command_line=s_data.get("command_line", ""),
                    output_files=s_data.get("output_files", []),
                    summary=s_data.get("summary", "尚未執行"),
                    student_notes=s_data.get("student_notes", ""),
                )
            else:
                steps[k] = StepRecord()

        return cls(
            name=data.get("name", "未命名專案"),
            project_dir=data.get("project_dir", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            description=data.get("description", ""),
            author=data.get("author", "研究生"),
            steps=steps,
        )


class ProjectManager:
    """
    Manages PhyloCraft project directories, JSON persistence, step artifacts,
    and student research lab notebook history.
    """

    RECENT_PROJECTS_FILE = OUTPUT_DIR / ".recent_projects.json"

    def __init__(self):
        self.current_project: PhyloProject | None = None

    def create_project(self, name: str, base_dir: Path | str, author: str = "研究生", description: str = "") -> PhyloProject:
        import re
        clean_name = re.sub(r'[\\/*?:"<>|]', "_", name.strip()) or "Unnamed_Project"
        p_dir = Path(base_dir) / f"{clean_name}.phylo"
        p_dir.mkdir(parents=True, exist_ok=True)

        # Create structured subfolders for each step
        for _, sub in STEP_TITLES.values():
            (p_dir / sub).mkdir(parents=True, exist_ok=True)
        (p_dir / "notes").mkdir(parents=True, exist_ok=True)

        steps = {k: StepRecord() for k in STEP_KEYS}
        proj = PhyloProject(
            name=clean_name,
            project_dir=str(p_dir.resolve()),
            author=author,
            description=description or f"針對 {clean_name} 進行之標準分子演化與系統發育分析專案",
            steps=steps,
        )
        self.current_project = proj
        self.save_project()
        self._add_to_recent(str(p_dir))
        return proj

    def open_project(self, project_path: Path | str) -> PhyloProject | None:
        p = Path(project_path)
        if p.is_file() and p.name == "project.json":
            json_file = p
            p_dir = p.parent
        elif p.is_dir():
            json_file = p / "project.json"
            p_dir = p
        else:
            return None

        if not json_file.exists():
            return None

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["project_dir"] = str(p_dir.resolve())
            proj = PhyloProject.from_dict(data)
            self.current_project = proj
            self._add_to_recent(str(p_dir))
            return proj
        except Exception:
            return None

    def save_project(self) -> bool:
        if not self.current_project:
            return False
        p_dir = Path(self.current_project.project_dir)
        p_dir.mkdir(parents=True, exist_ok=True)

        self.current_project.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        json_file = p_dir / "project.json"

        try:
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(self.current_project.to_dict(), f, indent=2, ensure_ascii=False)
            self.generate_lab_notebook()
            return True
        except Exception:
            return False

    def update_step(
        self,
        step_key: str,
        status: str | None = None,
        summary: str = "",
        output_files: list[str] | None = None,
        parameters: dict | None = None,
        command_line: str = "",
        student_notes: str | None = None,
    ):
        if not self.current_project or step_key not in self.current_project.steps:
            return

        rec = self.current_project.steps[step_key]
        if status is not None:
            rec.status = status
        rec.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if summary:
            rec.summary = summary
        if output_files is not None:
            # Copy or reference files into step subfolder
            step_subfolder = STEP_TITLES[step_key][1]
            target_sub = Path(self.current_project.project_dir) / step_subfolder
            target_sub.mkdir(parents=True, exist_ok=True)
            saved_paths = []
            for src_p in output_files:
                if not src_p or not str(src_p).strip():
                    continue
                p_src = Path(src_p)
                if p_src.is_file():
                    dest = target_sub / p_src.name
                    if p_src.resolve() != dest.resolve():
                        try:
                            shutil.copy2(p_src, dest)
                            saved_paths.append(str(dest.resolve()))
                        except Exception:
                            saved_paths.append(str(p_src.resolve()))
                    else:
                        saved_paths.append(str(dest.resolve()))
                elif p_src.is_dir():
                    dest = target_sub / p_src.name
                    if p_src.resolve() != dest.resolve():
                        try:
                            shutil.copytree(p_src, dest, dirs_exist_ok=True)
                            saved_paths.append(str(dest.resolve()))
                        except Exception:
                            saved_paths.append(str(p_src.resolve()))
                    else:
                        saved_paths.append(str(dest.resolve()))
                else:
                    saved_paths.append(str(src_p))
            rec.output_files = saved_paths

        if parameters is not None:
            rec.parameters = parameters
        if command_line:
            rec.command_line = command_line
        if student_notes is not None:
            rec.student_notes = student_notes

        self.save_project()

    def update_student_notes(self, step_key: str, notes: str):
        if not self.current_project or step_key not in self.current_project.steps:
            return
        self.current_project.steps[step_key].student_notes = notes
        self.save_project()

    def generate_lab_notebook(self) -> str:
        """
        Automatically compiles academic Electronic Lab Notebook (ELN) documents (Markdown & Standalone HTML).
        """
        if not self.current_project:
            return ""

        from src.core.eln_generator import ELNGenerator
        proj = self.current_project
        md_content = ELNGenerator.generate_markdown(proj)
        html_content = ELNGenerator.generate_html(proj)

        p_dir = Path(proj.project_dir)
        p_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(p_dir / "lab_notebook.md", "w", encoding="utf-8") as f:
                f.write(md_content)
        except Exception:
            pass

        try:
            with open(p_dir / "lab_notebook.html", "w", encoding="utf-8") as f:
                f.write(html_content)
        except Exception:
            pass

        return md_content

    def export_supplementary_package(self, zip_path: Path | str) -> str:
        if not self.current_project:
            return ""
        from src.core.eln_generator import ELNGenerator
        return ELNGenerator.export_supplementary_zip(self.current_project, zip_path)

    def _add_to_recent(self, proj_dir: str):
        recents = self.get_recent_projects()
        if proj_dir in recents:
            recents.remove(proj_dir)
        recents.insert(0, proj_dir)
        recents = recents[:10]
        try:
            self.RECENT_PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.RECENT_PROJECTS_FILE, "w", encoding="utf-8") as f:
                json.dump(recents, f, ensure_ascii=False)
        except Exception:
            pass

    def get_recent_projects(self) -> list[str]:
        if not self.RECENT_PROJECTS_FILE.exists():
            return []
        try:
            with open(self.RECENT_PROJECTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
