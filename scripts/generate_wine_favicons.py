"""
Generate editorial Wine and Blush favicons for AI Intelligence.
Brand: Monogram 'AI' in serif lettering on deep wine background with blush text.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "src" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Colors
WINE_BG = (30, 11, 16)      # #1E0B10
BLUSH_FG = (243, 213, 202)  # #F3D5CA
BORDER_COL = (201, 163, 143) # #C9A38F

def make_monogram(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Square background
    draw.rectangle([0, 0, size - 1, size - 1], fill=WINE_BG, outline=BORDER_COL, width=max(1, size // 32))
    
    # Try serif font, fallback to default
    font = None
    font_path = STATIC_DIR / "fonts" / "CormorantGaramond-Variable.ttf"
    if font_path.exists():
        try:
            font = ImageFont.truetype(str(font_path), int(size * 0.58))
        except Exception:
            pass
    if not font:
        font = ImageFont.load_default()
        
    text = "AI"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) / 2 - bbox[0]
    y = (size - text_h) / 2 - bbox[1]
    
    draw.text((x, y), text, fill=BLUSH_FG, font=font)
    return img

# Generate apple-touch-icon (180x180)
icon_180 = make_monogram(180)
icon_180.save(STATIC_DIR / "apple-touch-icon.png", format="PNG")

# Generate 32x32 PNG
icon_32 = make_monogram(32)
icon_32.save(STATIC_DIR / "favicon-32x32.png", format="PNG")

# Generate 16x16 PNG
icon_16 = make_monogram(16)
icon_16.save(STATIC_DIR / "favicon-16x16.png", format="PNG")

# Generate multi-size favicon.ico
icon_48 = make_monogram(48)
icon_48.save(
    STATIC_DIR / "favicon.ico",
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48)]
)

# Web manifest
manifest = """{
  "name": "AI Intelligence Platform",
  "short_name": "AI Intelligence",
  "description": "Editorial index and analytics across AI products, research, startups, jobs, and news.",
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
  "theme_color": "#1E0B10",
  "background_color": "#1E0B10",
  "display": "standalone"
}"""
with open(STATIC_DIR / "site.webmanifest", "w", encoding="utf-8") as f:
    f.write(manifest)

print("Generated Wine & Blush favicons and web manifest successfully.")
