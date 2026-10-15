import re
from pathlib import Path
from typing import Callable
from dataclasses import dataclass, field
from src.config import find_tool
from src.core.runners.base_runner import CommandRunner


@dataclass
class CandidateModel:
    rank: int
    model: str
    logl: float
    aic: float
    w_aic: float
    aicc: float
    w_aicc: float
    bic: float
    w_bic: float
    in_conf_set: bool = False
    delta_bic: float = 0.0


@dataclass
class ModelFinderResult:
    success: bool
    best_model: str = ""
    criterion: str = "BIC"
    candidate_models: list[CandidateModel] = field(default_factory=list)
    base_frequencies: dict[str, float] = field(default_factory=dict)
    rate_parameters: dict[str, float] = field(default_factory=dict)
    rate_matrix: list[list[float]] = field(default_factory=list)
    rate_heterogeneity: str = ""
    tree_length: float = 0.0
    taxa_count: int = 0
    site_count: int = 0
    constant_sites: int = 0
    parsimony_informative_sites: int = 0
    iqtree_report: str = ""
    log_file: str = ""
    message: str = ""


class ModelFinderRunner:
    """
    Subprocess runner for ModelFinder (via IQ-TREE 2 -m TESTONLY / -m TESTNEWONLY / -mset).
    Executes substitution model testing independently from tree inference,
    parsing detailed BIC/AIC candidate tables and evolutionary rate parameters.
    """

    def __init__(self):
        self.runner = CommandRunner()

    def cancel(self):
        self.runner.cancel()

    def run_modelfinder(
        self,
        input_alignment: str | Path,
        output_prefix: str | Path,
        search_scope: str = "TESTONLY",  # "TESTONLY", "TESTNEWONLY", "mrbayes", "beast"
        threads: str = "AUTO",
        c_rate: bool = False,
        redo: bool = True,
        log_callback: Callable[[str], None] | None = None,
    ) -> ModelFinderResult:
        iqtree_exe = find_tool("iqtree3") or find_tool("iqtree2") or find_tool("iqtree")
        if not iqtree_exe:
            msg = "IQ-TREE (3/2) 執行檔未找到，無法執行 ModelFinder 模型檢定！"
            if log_callback:
                log_callback(f"[Error] {msg}")
            return ModelFinderResult(success=False, message=msg)

        input_p = Path(input_alignment).resolve()
        if not input_p.exists() or input_p.stat().st_size == 0:
            msg = f"輸入比對檔案不存在或為空 (0 bytes): {input_p}"
            if log_callback:
                log_callback(f"[Error] {msg}")
            return ModelFinderResult(success=False, message=msg)

        prefix_p = Path(output_prefix).resolve()
        prefix_p.parent.mkdir(parents=True, exist_ok=True)

        cmd = [iqtree_exe, "-s", str(input_p), "-pre", str(prefix_p)]

        # Determine ModelFinder search flags
        if search_scope == "TESTNEWONLY":
            cmd.extend(["-m", "TESTNEWONLY"])
        elif search_scope in ("mrbayes", "beast", "raxml"):
            cmd.extend(["-m", "TESTONLY", "-mset", search_scope])
        elif search_scope == "protein":
            cmd.extend(["-m", "TESTONLY"])
        else:
            # Default standard DNA/protein TESTONLY
            cmd.extend(["-m", "TESTONLY"])

        if c_rate:
            cmd.append("-cmax")
            cmd.append("8")

        if threads:
            cmd.extend(["-T", str(threads)])

        if redo:
            cmd.append("-redo")

        # Keep identical sequences in alignment during model testing
        cmd.append("--keep-ident")

        exit_code, full_log = self.runner.run(cmd, cwd=prefix_p.parent, log_callback=log_callback)

        report_file = Path(f"{prefix_p}.iqtree")
        log_file = Path(f"{prefix_p}.log")

        if exit_code != 0 or not report_file.exists():
            return ModelFinderResult(
                success=False,
                message=f"ModelFinder 執行未成功完成 (Exit code: {exit_code})",
                log_file=str(log_file) if log_file.exists() else "",
            )

        # Parse the .iqtree report for ModelFinder results
        return self._parse_report(report_file, log_file)

    def _parse_report(self, report_path: Path, log_path: Path) -> ModelFinderResult:
        try:
            with open(report_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # Input statistics
            taxa = 0
            sites = 0
            m = re.search(r"Input data:\s+(\d+)\s+sequences with\s+(\d+)\s+(nucleotide|amino-acid)", content)
            if m:
                taxa = int(m.group(1))
                sites = int(m.group(2))

            const_sites = 0
            m = re.search(r"Number of constant sites:\s+(\d+)", content)
            if m:
                const_sites = int(m.group(1))

            parsimony_inf = 0
            m = re.search(r"Number of parsimony informative sites:\s+(\d+)", content)
            if m:
                parsimony_inf = int(m.group(1))

            # Best-fit model according to BIC
            best_model = ""
            m = re.search(r"Best-fit model according to BIC:\s+([^\r\n]+)", content)
            if m:
                best_model = m.group(1).strip()
            elif "Best-fit model:" in content:
                m = re.search(r"Best-fit model:\s+([^\r\n]+)", content)
                if m:
                    best_model = m.group(1).strip()
            elif "Model of substitution:" in content:
                m = re.search(r"Model of substitution:\s+([^\r\n]+)", content)
                if m:
                    best_model = m.group(1).strip()

            # Parse candidate models table
            mf_content = content
            if "List of models sorted by BIC scores:" not in mf_content and "List of models sorted by AIC scores:" not in mf_content:
                base_stem = report_path.stem.replace("_tree", "")
                mf_candidates = [
                    report_path.parent / f"{base_stem}_modelfinder.iqtree",
                    report_path.parent / f"{report_path.stem}_modelfinder.iqtree",
                ]
                for cand in mf_candidates:
                    if cand.exists():
                        try:
                            with open(cand, "r", encoding="utf-8", errors="replace") as mf_f:
                                cand_txt = mf_f.read()
                                if "List of models sorted by BIC scores:" in cand_txt or "List of models sorted by AIC scores:" in cand_txt:
                                    mf_content = cand_txt
                                    break
                        except Exception:
                            pass

            candidates = []
            mf_block = re.search(r"List of models sorted by BIC scores:\s*\n+([\s\S]+?)\n\n", mf_content)
            if not mf_block:
                mf_block = re.search(r"List of models sorted by AIC scores:\s*\n+([\s\S]+?)\n\n", mf_content)

            min_bic = None
            if mf_block:
                lines = mf_block.group(1).strip().splitlines()
                # Skip header lines
                rank = 1
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("Model") or line.startswith("---"):
                        continue
                    parts = line.split()
                    # Example line:
                    # Model      LogL        AIC    w-AIC       AICc    w-AICc        BIC    w-BIC
                    # F81+F -1635.674   3295.348 - 0.00458   3295.625 - 0.00493   3355.813 + 0.394
                    if len(parts) >= 8:
                        try:
                            m_name = parts[0]
                            logl = float(parts[1])
                            aic = float(parts[2])
                            
                            # Handle potential confidence set signs (+ or -)
                            idx = 3
                            w_aic = 0.0
                            if parts[idx] in ("+", "-"):
                                idx += 1
                            if idx < len(parts):
                                try:
                                    w_aic = float(parts[idx])
                                except ValueError:
                                    pass
                                idx += 1

                            aicc = 0.0
                            if idx < len(parts):
                                try:
                                    aicc = float(parts[idx])
                                except ValueError:
                                    pass
                                idx += 1

                            w_aicc = 0.0
                            if idx < len(parts) and parts[idx] in ("+", "-"):
                                idx += 1
                            if idx < len(parts):
                                try:
                                    w_aicc = float(parts[idx])
                                except ValueError:
                                    pass
                                idx += 1

                            bic = 0.0
                            if idx < len(parts):
                                try:
                                    bic = float(parts[idx])
                                except ValueError:
                                    pass
                                idx += 1

                            in_conf = False
                            if idx < len(parts) and parts[idx] in ("+", "-"):
                                in_conf = (parts[idx] == "+")
                                idx += 1

                            w_bic = 0.0
                            if idx < len(parts):
                                try:
                                    w_bic = float(parts[idx])
                                except ValueError:
                                    pass

                            if min_bic is None:
                                min_bic = bic

                            delta_bic = max(0.0, bic - min_bic)

                            candidates.append(CandidateModel(
                                rank=rank,
                                model=m_name,
                                logl=logl,
                                aic=aic,
                                w_aic=w_aic,
                                aicc=aicc,
                                w_aicc=w_aicc,
                                bic=bic,
                                w_bic=w_bic,
                                in_conf_set=in_conf,
                                delta_bic=delta_bic,
                            ))
                            rank += 1
                        except (ValueError, IndexError):
                            continue

            if not best_model and candidates:
                best_model = candidates[0].model
            elif best_model and not candidates:
                candidates.append(CandidateModel(
                    rank=1,
                    model=best_model,
                    logl=0.0,
                    aic=0.0,
                    w_aic=1.0,
                    aicc=0.0,
                    w_aicc=1.0,
                    bic=0.0,
                    w_bic=1.0,
                    in_conf_set=True,
                    delta_bic=0.0,
                ))

            # State frequencies
            freqs = {}
            for base in ["A", "C", "G", "T"]:
                m = re.search(rf"pi\({base}\)\s*=\s*([\d\.]+)", content)
                if m:
                    freqs[base] = float(m.group(1))

            # Rate parameters R
            rates = {}
            for pair in ["A-C", "A-G", "A-T", "C-G", "C-T", "G-T"]:
                m = re.search(rf"{pair}:\s*([\d\.]+)", content)
                if m:
                    rates[pair] = float(m.group(1))

            # Rate heterogeneity
            rate_het = ""
            m = re.search(r"Model of rate heterogeneity:\s+([^\r\n]+)", content)
            if m:
                rate_het = m.group(1).strip()

            # Tree length
            tree_len = 0.0
            m = re.search(r"Total tree length \(sum of branch lengths\):\s+([\d\.]+)", content)
            if m:
                tree_len = float(m.group(1))

            return ModelFinderResult(
                success=True,
                best_model=best_model,
                criterion="BIC",
                candidate_models=candidates,
                base_frequencies=freqs,
                rate_parameters=rates,
                rate_heterogeneity=rate_het,
                tree_length=tree_len,
                taxa_count=taxa,
                site_count=sites,
                constant_sites=const_sites,
                parsimony_informative_sites=parsimony_inf,
                iqtree_report=str(report_path),
                log_file=str(log_path) if log_path.exists() else "",
                message=f"ModelFinder 完成: 最佳推薦模式為 {best_model}",
            )

        except Exception as e:
            return ModelFinderResult(
                success=False,
                message=f"解析 ModelFinder 結果報告失敗: {str(e)}",
            )
