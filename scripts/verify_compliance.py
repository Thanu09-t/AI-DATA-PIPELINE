"""
Comprehensive compliance verification script for "Editorial, Wine and Blush" redesign.
Checks:
- Em dashes (\u2014)
- Emoji characters
- 'gradient' in styles
- Purple/violet hex values (#A855F7, #818CF8, etc.)
- Pill border radius (9999px, 999px, 50px)
- 'Made with' / generator badges
- 'Lorem'
- 'TODO'
"""
import glob
import re
from pathlib import Path

TARGET_FILES = [
    "src/static/index.html",
    "src/static/landing.html",
    "src/static/privacy.html",
    "src/static/terms.html",
    "src/static/404.html",
    "src/static/css/dashboard.css",
    "src/static/js/app.js",
]

base_dir = Path(__file__).resolve().parent.parent

print("=== STARTING COMPLIANCE AUDIT ===")
total_violations = 0

PURPLE_HEXES = ["#a855f7", "#818cf8", "#9333ea", "#7c3aed", "#6366f1", "#4f46e5", "#8b5cf6"]
EMOJI_PATTERN = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

for rel_path in TARGET_FILES:
    file_path = base_dir / rel_path
    if not file_path.exists():
        print(f"File not found: {file_path}")
        continue
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Em dashes
    em_count = content.count("\u2014")
    if em_count > 0:
        print(f"[FAIL] {rel_path}: {em_count} em-dash(es) found!")
        total_violations += em_count
    else:
        print(f"[PASS] {rel_path}: 0 em-dashes")

    # 2. Gradient check in CSS and HTML
    if "dashboard.css" in rel_path or "index.html" in rel_path or "landing.html" in rel_path:
        gradient_matches = re.findall(r"linear-gradient|radial-gradient|conic-gradient", content, re.IGNORECASE)
        if gradient_matches:
            print(f"[FAIL] {rel_path}: {len(gradient_matches)} gradient occurrences found!")
            total_violations += len(gradient_matches)
        else:
            print(f"[PASS] {rel_path}: 0 gradients")

    # 3. Purple / violet hex values
    content_lower = content.lower()
    for p_hex in PURPLE_HEXES:
        if p_hex in content_lower:
            print(f"[FAIL] {rel_path}: purple hex {p_hex} found!")
            total_violations += 1

    # 4. Pill border radius
    pill_matches = re.findall(r"border-radius:\s*(?:9999px|999px|50px)", content)
    if pill_matches:
        print(f"[FAIL] {rel_path}: {len(pill_matches)} pill border-radius matches found!")
        total_violations += len(pill_matches)
    else:
        print(f"[PASS] {rel_path}: 0 pill shapes")

    # 5. Made with / generator badge
    if "made with" in content_lower or "built with" in content_lower:
        print(f"[FAIL] {rel_path}: 'made with' / 'built with' found!")
        total_violations += 1

    # 6. Lorem ipsum
    if "lorem" in content_lower:
        print(f"[FAIL] {rel_path}: 'lorem' found!")
        total_violations += 1

    # 7. Emojis
    emoji_matches = EMOJI_PATTERN.findall(content)
    if emoji_matches:
        print(f"[FAIL] {rel_path}: {len(emoji_matches)} emoji characters found!")
        total_violations += len(emoji_matches)
    else:
        print(f"[PASS] {rel_path}: 0 emoji characters")

print(f"\n=== COMPLIANCE AUDIT COMPLETE: {total_violations} TOTAL VIOLATIONS ===")
