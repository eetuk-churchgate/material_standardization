"""Patches Streamlit's static index.html so the browser tab / link-preview title
isn't the literal word 'Streamlit'. Streamlit only sets the real title client-side
via JS after the app loads, so crawlers and share-link previews (which don't run JS)
see the raw HTML title instead.
"""
import os
import streamlit

APP_TITLE = "Material & Asset Standardization Engine"
APP_DESCRIPTION = "AI-powered material and asset standardization for Churchgate Group"

INDEX_PATH = os.path.join(os.path.dirname(streamlit.__file__), "static", "index.html")


def patch():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    if "og:title" in html:
        return  # already patched

    html = html.replace("<title>Streamlit</title>", f"<title>{APP_TITLE}</title>")
    meta_tags = (
        f'<meta name="description" content="{APP_DESCRIPTION}" />\n'
        f'<meta property="og:title" content="{APP_TITLE}" />\n'
        f'<meta property="og:description" content="{APP_DESCRIPTION}" />\n'
        f'<meta property="og:type" content="website" />\n'
    )
    html = html.replace('<meta charset="UTF-8" />', '<meta charset="UTF-8" />\n    ' + meta_tags, 1)

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    patch()
