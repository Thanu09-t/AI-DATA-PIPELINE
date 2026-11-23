"""
Download Cormorant Garamond and Inter fonts for self-hosting.
Ensures zero third-party font network requests in production.
"""
import urllib.request
from pathlib import Path

FONTS_DIR = Path("src/static/fonts")
FONTS_DIR.mkdir(parents=True, exist_ok=True)

FONT_URLS = {
    "CormorantGaramond-Light.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/cormorantgaramond/CormorantGaramond-Light.ttf",
    "CormorantGaramond-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/cormorantgaramond/CormorantGaramond-Regular.ttf",
    "Inter-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
}

for name, url in FONT_URLS.items():
    dest = FONTS_DIR / name
    if not dest.exists() or dest.stat().st_size < 1000:
        print(f"Downloading {name}...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                with open(dest, "wb") as f:
                    f.write(data)
            print(f"Saved {name} ({len(data):,} bytes)")
        except Exception as exc:
            print(f"Failed to download {name}: {exc}")
    else:
        print(f"Already exists: {name} ({dest.stat().st_size:,} bytes)")
