"""Export the current shortlist and only its referenced photos for GitHub Pages."""
from pathlib import Path
import shutil

from latest_dashboard import ROOT, load_listings
from palo_alto_server import render_archive_redirect, render_body


def build(output):
    output = Path(output)
    output.mkdir(parents=True)
    (output / "index.html").write_text(render_body(), encoding="utf-8")
    (output / "summer.html").write_text(render_archive_redirect(), encoding="utf-8")
    (output / "maps").mkdir()
    for listing in load_listings()["listings"]:
        for photo in listing.get("photos", []):
            filename = photo["file"]
            shutil.copyfile(ROOT / "maps" / filename, output / "maps" / filename)
    (output / ".nojekyll").touch()


if __name__ == "__main__":
    build(ROOT / "site")
    print("Built the current dashboard and its listing photos.")
