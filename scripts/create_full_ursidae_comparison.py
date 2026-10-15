"""
Create Side-by-Side Visual Comparison for 100% Complete Family Ursidae (All 8 Extant Bear Species)
"""

import sys
import io
from pathlib import Path
from PIL import Image, ImageDraw

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE_DIR = Path(r"C:\Users\Alan\.gemini\antigravity\brain\b252e923-3bcb-4e1f-b6b5-41ade74e0f9b\screens\paper_trees")

def build_full_ursidae_comparison():
    img_left = Image.open(BASE_DIR / "krause2008_fig1.jpg")
    img_right = Image.open(BASE_DIR / "ursidae_all_8_species_full_publication_tree.png")

    target_h = 800
    w_l = int(img_left.width * target_h / img_left.height)
    left_resized = img_left.resize((w_l, target_h), Image.Resampling.LANCZOS)

    w_r = int(img_right.width * target_h / img_right.height)
    right_resized = img_right.resize((w_r, target_h), Image.Resampling.LANCZOS)

    header_h = 110
    banner_w = w_l + w_r + 40
    total_h = target_h + header_h + 40

    canvas = Image.new("RGB", (banner_w, total_h), "#ffffff")
    draw = ImageDraw.Draw(canvas)

    # Header bar
    draw.rectangle([(0, 0), (banner_w, 65)], fill="#0f172a")
    # Subheaders
    draw.rectangle([(10, 70), (w_l + 10, 105)], fill="#f1f5f9", outline="#cbd5e1")
    draw.rectangle([(w_l + 30, 70), (banner_w - 10, 105)], fill="#eff6ff", outline="#93c5fd")

    # Paste
    canvas.paste(left_resized, (10, header_h))
    canvas.paste(right_resized, (w_l + 30, header_h))

    # Borders
    draw.rectangle([(10, header_h), (w_l + 10, header_h + target_h)], outline="#cbd5e1", width=2)
    draw.rectangle([(w_l + 30, header_h), (banner_w - 10, header_h + target_h)], outline="#93c5fd", width=2)

    # Texts
    draw.text((20, 20), "FULL-TAXON AUDIT: Complete Family Ursidae (100% of All 8 Extant Bear Species on Earth)", fill="#ffffff")
    draw.text((20, 78), "Published Literature: Krause et al. (2008) BMC Evol Biol 8:220 Fig 1", fill="#334155")
    draw.text((w_l + 40, 78), "PhyloCraft Reconstructed Pipeline: NCBI Real CDS (MAFFT -> trimAl -> ModelFinder -> IQ-TREE)", fill="#1d4ed8")

    out_path = BASE_DIR / "comparison_krause2008_all_8_bears.png"
    canvas.save(out_path)
    print(f"Saved full Ursidae side-by-side comparison to {out_path} ({out_path.stat().st_size} bytes)")

if __name__ == "__main__":
    build_full_ursidae_comparison()
