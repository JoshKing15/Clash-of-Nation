"""Meme / sound library integrity. Catalogue links must never be mistaken for media files."""
import json
import pathlib
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import pytest

MEDIA_EXT = {".gif", ".mp4", ".webm", ".mov", ".m4v", ".mp3", ".wav", ".m4a", ".ogg", ".png", ".jpg", ".jpeg", ".webp"}
BUILTIN = ["suspicious", "shocked", "laugh", "awkward", "confused", "reveal"]
BUILTIN_SOUNDS = {"boom", "scratch", "reveal"}


def read(root, rel):
    return json.loads((root / rel).read_text())


@pytest.fixture
def catalogs(root):
    return {
        "pixabay": read(root, "assets/memes/pixabay-reaction-catalog.json"),
        "video": read(root, "assets/memes/reaction-video-catalog.json"),
        "sfx": read(root, "assets/sfx/phoenix-connection-catalog.json"),
    }


def entries(c):
    return c["pixabay"]["items"] + c["video"]["clips"] + c["video"].get("famous_meme_references", []) + c["sfx"]["items"]


def test_catalogue_links_are_never_recorded_as_downloaded_files(root, catalogs):
    for item in entries(catalogs):
        for key in ("file", "local_file"):
            value = item.get(key)
            if value:
                assert not re.match(r"^https?://", value), "%s: a URL is not a file" % item
                assert (root / value).is_file(), "%s points at a file that is not in the repo: %s" % (item.get("id") or item.get("title"), value)


def test_entries_marked_bundled_have_files_and_rights_records(root, catalogs):
    for item in catalogs["sfx"]["items"]:
        if item.get("approved_for_bundling"):
            assert item.get("file") and (root / item["file"]).is_file()
        else:
            assert not item.get("file"), "unapproved sound must not have a bundled file: %s" % item["id"]
    for clip in catalogs["video"]["clips"]:
        if clip.get("local_file"):
            assert clip.get("rights_status") == "cleared", clip["id"]


def test_no_third_party_media_is_bundled(root):
    """Only the six original graphics and the project's own watermark may ship as media files."""
    allowed_dirs = [root / "assets" / "memes" / "original"]
    allowed_files = {root / "assets" / "clash-of-nations-watermark.png"}
    for path in (root / "assets").rglob("*"):
        if path.suffix.lower() in MEDIA_EXT:
            ok = path in allowed_files or any(d in path.parents for d in allowed_dirs)
            assert ok, "unreviewed media file bundled: %s" % path.relative_to(root)
    for path in root.rglob("*"):
        if ".git" in path.parts or "assets" in path.parts or "tests" in path.parts or "node_modules" in path.parts:
            continue
        assert path.suffix.lower() not in {".gif", ".mp4", ".webm", ".mov", ".mp3", ".wav", ".m4a", ".ogg"}, path


def test_source_links_are_https_and_from_expected_hosts(catalogs):
    hosts = {"pixabay.com", "www.pexels.com", "pexels.com"}
    for item in entries(catalogs):
        url = item.get("source_url")
        if not url:
            continue
        parsed = urlparse(url)
        assert parsed.scheme == "https" and parsed.hostname in hosts, url


def test_ids_are_unique_and_titles_present(catalogs):
    for name, items in (("pixabay", catalogs["pixabay"]["items"]), ("video", catalogs["video"]["clips"]), ("sfx", catalogs["sfx"]["items"])):
        ids = [i["id"] for i in items]
        assert len(ids) == len(set(ids)), name
        assert all(i.get("title", "").strip() for i in items), name


def test_suggested_sounds_exist_in_the_app(catalogs):
    for item in catalogs["pixabay"]["items"] + catalogs["video"]["clips"] + catalogs["video"].get("famous_meme_references", []):
        assert item["suggested_sound"] in BUILTIN_SOUNDS, item


def test_reaction_vocabulary_matches_the_builtin_reaction_ids(catalogs):
    """The catalogues said 'shock', 'confusion', 'surprise', 'sad'; the app only knows its own ids."""
    # "sad" is a reference-only category: no built-in graphic exists for it yet, so nothing can be inserted for it.
    allowed = set(BUILTIN) | {"sad"}
    for item in catalogs["pixabay"]["items"]:
        assert item["category"] in {"impact", "shock", "laugh", "surprise"}, item
    for item in catalogs["video"]["clips"] + catalogs["video"].get("famous_meme_references", []):
        assert item["reaction"] in allowed, "%s uses reaction '%s' which the app cannot map" % (item.get("id") or item["title"], item["reaction"])


def test_every_builtin_graphic_exists_and_is_wellformed_svg_with_intrinsic_size(root):
    for name in BUILTIN:
        path = root / "assets" / "memes" / "original" / (name + ".svg")
        assert path.is_file(), path
        svg = ET.parse(path).getroot()
        assert svg.tag.endswith("svg")
        assert svg.get("width") and svg.get("height"), "%s has no width/height: Firefox/Safari cannot draw it to a canvas reliably" % name
    wm = ET.parse(root / "assets" / "clash-of-nations-watermark-v2.svg").getroot()
    assert wm.get("width") and wm.get("height")


def test_ui_counts_match_catalogues(root, catalogs):
    html = (root / "index.html").read_text()
    m = re.search(r"Browse (\d+) Pixabay", html)
    assert m and int(m.group(1)) == len(catalogs["pixabay"]["items"])