#!/usr/bin/env python3
"""
Erzeugt app/streifenhelfer-offline.html: die komplette App in EINER Datei
(Oberfläche + Regelwerk + Rechtsdaten eingebettet), z. B. zum Kopieren aufs Gerät.
Wird beim Veröffentlichen automatisch erzeugt (.github/workflows/pages.yml), nicht eingecheckt.

Aufruf:  python tools/build_offline_html.py
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
OUT = APP / "streifenhelfer-offline.html"


def inline_script(path):
    code = (APP / path).read_text("utf-8")
    # "</script" darf im eingebetteten Code nicht vorkommen
    code = re.sub(r"</(script)", r"<\\/\1", code, flags=re.I)
    return f"<script>\n{code}\n</script>"


def main():
    html = (APP / "index.html").read_text("utf-8")
    for name in ("rechtsdaten.js", "regelwerk.js"):
        tag = f'<script src="{name}"></script>'
        if tag not in html:
            raise SystemExit(f"Script-Tag für {name} nicht gefunden – index.html geändert?")
        html = html.replace(tag, inline_script(name))
    # In der Einzeldatei weder Manifest/Icons (relative Pfade) noch Service Worker
    html = re.sub(r'\s*<link rel="(manifest|icon|apple-touch-icon)"[^>]*>', "", html)
    html = html.replace('if("serviceWorker" in navigator', 'if(!window.STREIFENHELFER_EINZELDATEI && "serviceWorker" in navigator')
    html = html.replace("<head>", "<head>\n<script>window.STREIFENHELFER_EINZELDATEI=true;</script>", 1)
    OUT.write_text(html, "utf-8")
    print(f"{OUT.name}: {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
