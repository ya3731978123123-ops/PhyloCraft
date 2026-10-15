"""
PhyloCraft Core Evolutionary Biology & Computational Engine.
"""

from src.core.sanitizer import (
    sanitize_fasta_file,
    clean_taxon_name,
    detect_seq_type,
    SanitizerResult,
    SequenceInfo,
)
from src.core.converter import convert_alignment
from src.core.concatenator import (
    concatenate_alignments,
    ConcatResult,
    PartitionInfo,
)
from src.core.gene_extractor import (
    GeneExtractor,
    GeneExtractionResult,
    ExtractedGeneRecord,
)
from src.core.eln_generator import ELNGenerator
from src.core.iqtree_parser import (
    parse_iqtree_report,
    IQTreeReportData,
    TopModelInfo,
)
from src.core.project_manager import (
    ProjectManager,
    PhyloProject,
    STEP_KEYS,
    STEP_TITLES,
    StepRecord,
)
from src.core.tools_installer import TOOL_METADATA

__all__ = [
    "sanitize_fasta_file",
    "clean_taxon_name",
    "detect_seq_type",
    "SanitizerResult",
    "SequenceInfo",
    "convert_alignment",
    "concatenate_alignments",
    "ConcatResult",
    "PartitionInfo",
    "GeneExtractor",
    "GeneExtractionResult",
    "ExtractedGeneRecord",
    "ELNGenerator",
    "parse_iqtree_report",
    "IQTreeReportData",
    "TopModelInfo",
    "ProjectManager",
    "PhyloProject",
    "STEP_KEYS",
    "STEP_TITLES",
    "StepRecord",
    "TOOL_METADATA",
]
