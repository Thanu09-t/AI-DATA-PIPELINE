"""
Generate clean, brand-compliant favicon set for AI Intelligence.
Uses a professional geometric "AI" wordmark monogram glyph on dark slate.
No robots, no sparkles, meets strict design rules.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import json

STATIC_DIR = Path("src/static")
STATIC_DIR.mkdir(parents=True, exist_ok=True)

def create_icon(size: int) -> Image.Image:
    # 0B1120 background, subtle border, cyan/white geometric AI monogram
    img = Image.new("RGBA", (size, size), (11, 17, 32, 255))
    draw = ImageDraw.Draw(img)
    
    # Outer border
    border_color = (51, 65, 85, 255)
    r = int(size * 0.18)
    draw.rounded_rectangle([1, 1, size - 2, size - 2], radius=r, outline=border_color, width=max(1, int(size * 0.04)))
    
    # Draw stylized geometric "A" and "I"
    # A (cyan): apex and legs
    pad = int(size * 0.22)
    h = size - pad * 2
    w = size - pad * 2
    
    cyan = (34, 211, 238, 255)
    white = (248, 250, 252, 255)
    
    # 'A' left leg & right leg
    stroke = max(2, int(size * 0.08))
    left_x = pad
    mid_x = pad + int(w * 0.42)
    top_y = pad
    bot_y = pad + h
    
    draw.line([(left_x, bot_y), (mid_x, top_y)], fill=cyan, width=stroke)
    draw.line([(mid_x, top_y), (mid_x + int(w * 0.28), bot_y)], fill=cyan, width=stroke)
    # A crossbar
    cross_y = pad + int(h * 0.6)
    draw.line([(left_x + int(w * 0.12), cross_y), (mid_x + int(w * 0.18), cross_y)], fill=cyan, width=stroke)
    
    # 'I' (white)
    ix = pad + int(w * 0.82)
    draw.line([(ix, top_y), (ix, bot_y)], fill=white, width=stroke)
    
    return img

def main():
    icon_180 = create_icon(180)
    icon_180.save(STATIC_DIR / "apple-touch-icon.png", format="PNG")
    
    icon_32 = create_icon(32)
    icon_32.save(STATIC_DIR / "favicon-32x32.png", format="PNG")
    
    icon_16 = create_icon(16)
    icon_48 = create_icon(48)
    icon_48.save(
        STATIC_DIR / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=[icon_16, icon_32]
    )
    
    # Web manifest
    manifest = {
        "name": "AI Intelligence Platform",
        "short_name": "AI Intelligence",
        "icons": [
            {
                "src": "/static/favicon-32x32.png",
                "sizes": "32x32",
                "type": "image/png"
            },
            {
                "src": "/static/apple-touch-icon.png",
                "sizes": "180x180",
                "type": "image/png"
            }
        ],
        "theme_color": "#0B1120",
        "background_color": "#0B1120",
        "display": "standalone"
    }
    with open(STATIC_DIR / "site.webmanifest", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print("Favicon set generated successfully in src/static/")

if __name__ == "__main__":
    main()
