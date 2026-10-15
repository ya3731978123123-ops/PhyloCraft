import re
from pathlib import Path
from dataclasses import dataclass, field
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq

ILLEGAL_CHARS_PATTERN = re.compile(r"[\s\:\;\,\(\)\[\]\'\"\|\/\\]+")

@dataclass
class SequenceInfo:
    original_id: str
    sanitized_id: str
    original_description: str
    length: int
    gc_content: float
    gap_count: int
    ambiguous_count: int
    preview: str

@dataclass
class SanitizerResult:
    success: bool
    total_taxa: int = 0
    seq_type: str = "Unknown"  # "DNA", "RNA", "Protein"
    min_length: int = 0
    max_length: int = 0
    avg_length: float = 0.0
    is_aligned: bool = False
    sequences: list[SequenceInfo] = field(default_factory=list)
    id_mapping: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    cleaned_records: list[SeqRecord] = field(default_factory=list)


def clean_taxon_name(name: str) -> str:
    """Replaces spaces, punctuation, and illegal characters with single underscores."""
    cleaned = ILLEGAL_CHARS_PATTERN.sub("_", name.strip())
    # Remove leading/trailing underscores
    cleaned = cleaned.strip("_")
    # Avoid empty names
    if not cleaned:
        cleaned = "unnamed_taxon"
    return cleaned


def detect_seq_type(sample_sequences: list[str]) -> str:
    """Guess whether the sequences are DNA, RNA, or Protein based on character frequency."""
    combined = "".join(sample_sequences[:10]).upper()
    if not combined:
        return "Unknown"
    
    clean_chars = [c for c in combined if c not in "-.?~ \r\n"]
    if not clean_chars:
        return "Unknown"
        
    dna_chars = set("ACGTN")
    rna_chars = set("ACGUN")
    
    dna_count = sum(1 for c in clean_chars if c in dna_chars)
    rna_count = sum(1 for c in clean_chars if c in rna_chars)
    total = len(clean_chars)
    
    if dna_count / total > 0.85:
        return "DNA"
    elif rna_count / total > 0.85:
        return "RNA"
    else:
        return "Protein"


def sanitize_fasta_file(input_path: str | Path) -> SanitizerResult:
    """
    Parses a FASTA file, sanitizes sequence IDs, checks for duplicates,
    detects type, and calculates diagnostic stats.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        return SanitizerResult(success=False, warnings=[f"File not found: {input_path}"])

    try:
        with open(input_path, "r", encoding="utf-8", errors="replace") as handle:
            records = list(SeqIO.parse(handle, "fasta"))
    except Exception as e:
        return SanitizerResult(success=False, warnings=[f"Error reading FASTA: {str(e)}"])

    if not records:
        return SanitizerResult(success=False, warnings=["No sequences found in the file."])

    used_ids: set[str] = set()
    cleaned_records: list[SeqRecord] = []
    seq_infos: list[SequenceInfo] = []
    id_mapping: dict[str, str] = {}
    warnings: list[str] = []

    seq_strings = [str(r.seq) for r in records]
    seq_type = detect_seq_type(seq_strings)

    cleaned_lengths = []

    for r in records:
        orig_id = r.id
        orig_desc = r.description

        # Clean ID
        base_clean = clean_taxon_name(orig_id)

        # Handle duplicate names with strict uniqueness guarantee
        cand = base_clean
        suffix = 1
        while cand in used_ids:
            cand = f"{base_clean}_{suffix}"
            suffix += 1
        used_ids.add(cand)
        final_clean = cand

        if final_clean != orig_id:
            id_mapping[orig_id] = final_clean
            if cand != base_clean:
                warnings.append(f"重複物種標頭 '{orig_id}' 已自動重命名為唯一標頭 '{final_clean}'。")

        raw_seq_str = str(r.seq).upper()

        # Sanitize sequence characters (strip whitespace, digits, and illegal characters)
        if seq_type in ("DNA", "RNA"):
            seq_str = re.sub(r"[^ACGTUNRYSWKMBDHV\-\.\?]", "", raw_seq_str)
        else:
            seq_str = re.sub(r"[^ACDEFGHIKLMNPQRSTVWYXBZJUO\*\-\.\?]", "", raw_seq_str)

        if len(seq_str) < len(raw_seq_str):
            removed_chars = len(raw_seq_str) - len(seq_str)
            warnings.append(f"物種 '{orig_id}' 含有 {removed_chars} 個非法非字母字元（如數字或空格），已自動過濾。")

        if len(seq_str) == 0:
            warnings.append(f"警告: 物種 '{orig_id}' 序列長度為 0 bp (空序列)！")

        cleaned_lengths.append(len(seq_str))

        # Count GC for DNA/RNA
        if seq_type in ("DNA", "RNA"):
            gc = sum(1 for c in seq_str if c in "GC")
            valid_bases = sum(1 for c in seq_str if c in "ACGTU")
            gc_pct = (gc / valid_bases * 100) if valid_bases > 0 else 0.0
        else:
            gc_pct = 0.0

        gaps = seq_str.count("-") + seq_str.count(".") + seq_str.count("?")
        ambiguous = sum(1 for c in seq_str if c in "NXRYSWKMBDHV")

        info = SequenceInfo(
            original_id=orig_id,
            sanitized_id=final_clean,
            original_description=orig_desc,
            length=len(seq_str),
            gc_content=round(gc_pct, 2),
            gap_count=gaps,
            ambiguous_count=ambiguous,
            preview=seq_str[:30] + ("..." if len(seq_str) > 30 else ""),
        )
        seq_infos.append(info)

        # Create cleaned record
        clean_rec = SeqRecord(
            Seq(seq_str),
            id=final_clean,
            name=final_clean,
            description="",
        )
        cleaned_records.append(clean_rec)

    is_aligned = len(set(cleaned_lengths)) == 1

    return SanitizerResult(
        success=True,
        total_taxa=len(records),
        seq_type=seq_type,
        min_length=min(cleaned_lengths) if cleaned_lengths else 0,
        max_length=max(cleaned_lengths) if cleaned_lengths else 0,
        avg_length=round(sum(cleaned_lengths) / len(cleaned_lengths), 1) if cleaned_lengths else 0.0,
        is_aligned=is_aligned,
        sequences=seq_infos,
        id_mapping=id_mapping,
        warnings=warnings,
        cleaned_records=cleaned_records,
    )


def save_sanitized_fasta(cleaned_records: list[SeqRecord], output_path: str | Path) -> str:
    """Writes cleaned records to output path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        SeqIO.write(cleaned_records, f, "fasta")
    return str(output_path)
