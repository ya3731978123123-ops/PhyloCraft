from pathlib import Path
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord


def convert_alignment(
    input_path: str | Path,
    output_path: str | Path,
    in_format: str = "fasta",
    out_format: str = "phylip-relaxed",
) -> tuple[bool, str]:
    """
    Converts alignment files between formats:
    - fasta
    - phylip (strict, 10 chars)
    - phylip-relaxed (standard modern phylip)
    - nexus
    - clustal
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        return False, f"Input file not found: {input_path}"

    try:
        with open(input_path, "r", encoding="utf-8", errors="replace") as handle:
            records = list(SeqIO.parse(handle, in_format))
        if not records:
            return False, f"No sequences found in {input_path} using format '{in_format}'"

        lengths = [len(r.seq) for r in records]
        if len(set(lengths)) > 1 and out_format in ("phylip", "phylip-relaxed", "nexus", "clustal"):
            return False, (
                "Sequences are not aligned (lengths differ: "
                f"min={min(lengths)}, max={max(lengths)}). "
                "PHYLIP/NEXUS require an aligned matrix. Please run Alignment first."
            )

        # Biopython format mapping
        bio_format = out_format
        if out_format == "phylip-relaxed":
            bio_format = "phylip-relaxed"
        elif out_format == "phylip-strict":
            bio_format = "phylip"

        # BioPython Nexus requires molecule_type annotation
        for r in records:
            r.description = ""
            if "molecule_type" not in r.annotations:
                # Guess DNA vs Protein
                seq_sample = str(r.seq[:100]).upper()
                clean_sample = [c for c in seq_sample if c not in "-.?~ \r\n"]
                if clean_sample and (sum(1 for c in clean_sample if c in "ACGTUN") / len(clean_sample)) > 0.85:
                    r.annotations["molecule_type"] = "DNA"
                else:
                    r.annotations["molecule_type"] = "protein"

        with open(output_path, "w", encoding="utf-8") as out_f:
            SeqIO.write(records, out_f, bio_format)

        return True, f"Successfully converted to {out_format}: {output_path.name}"
    except Exception as e:
        return False, f"Conversion error: {str(e)}"
