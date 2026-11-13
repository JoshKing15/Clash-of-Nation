"""Mobile layout: six tabs, two independent scroll panes with visible draggable scrollbars."""
import re

import pytest
import tinycss2

from conftest import load_video

TABS = ["Trim", "Censor", "Brand", "Subtitles", "AI Caption", "Effects"]


@pytest.mark.parametrize("width,height", [(430, 932), (390, 844), (375, 667)])
def test_six_editing_tabs_fit_on_one_row(make_page, width, height):
    page = make_page(viewport={"width": width, "height": height})
    buttons = page.locator(".tool-nav button[data-tool]")
    assert buttons.count() == 6
    assert [t.strip() for t in page.locator(".tool-nav button span").all_inner_texts()] == TABS
    boxes = page.eval_on_selector_all(".tool-nav button", "els=>els.map(e=>{const r=e.getBoundingClientRect();"
                                      "return {x:r.x,y:r.y,w:r.width,sw:e.scrollWidth,cw:e.clientWidth}})")
    assert len({round(b["y"]) for b in boxes}) == 1, "tabs wrap onto two rows: %s" % boxes
    assert all(b["x"] >= 0 and b["x"] + b["w"] <= width + 0.5 for b in boxes)
    assert all(b["sw"] <= b["cw"] + 1 for b in boxes), "a tab label overflows its button"
    page.close()


def test_every_tab_opens_its_own_panel(page):
    ids = {"edit": "edit", "censor": "censor", "brand": "brandPanel", "subtitles": "subtitles", "captionTools": "captionTools", "effects": "effects"}
    for tool, panel in ids.items():
        page.click(f'.tool-nav [data-tool="{tool}"]')
        visible = page.evaluate("ids=>Object.fromEntries(ids.map(i=>[i,!document.getElementById(i).classList.contains('tool-hidden')]))", list(ids.values()))
        assert [k for k, v in visible.items() if v] == [panel]


def test_two_panes_scroll_independently_and_page_does_not_scroll(loaded_page):
    page = loaded_page
    panes = page.evaluate("""()=>[...document.querySelectorAll('.scroll-pane>.viewer,.scroll-pane>.controls')].map(e=>({
        cls:e.classList.contains('viewer')?'viewer':'controls',client:e.clientHeight,scroll:e.scrollHeight,
        overflowY:getComputedStyle(e).overflowY}))""")
    assert {p["cls"] for p in panes} == {"viewer", "controls"}
    assert all(p["scroll"] > p["client"] and p["overflowY"] in ("scroll", "auto") for p in panes), panes
    page.evaluate("document.querySelector('.scroll-pane>.controls').scrollTop = 200")
    assert page.evaluate("document.querySelector('.scroll-pane>.viewer').scrollTop") == 0
    page.evaluate("document.querySelector('.scroll-pane>.viewer').scrollTop = 80")
    assert page.evaluate("document.querySelector('.scroll-pane>.controls').scrollTop") == 200
    assert page.evaluate("document.documentElement.scrollHeight <= innerHeight + 1 && scrollY === 0")


@pytest.mark.parametrize("pane", [".viewer", ".controls"])
def test_scrollbar_rail_is_visible_and_draggable(loaded_page, pane):
    page = loaded_page
    rail = page.locator(f".scroll-pane:has(> {pane}) > .scroll-rail")
    thumb = rail.locator(".scroll-thumb")
    box = rail.bounding_box()
    assert box and box["width"] >= 6 and box["height"] > 40
    assert float(rail.evaluate("e=>getComputedStyle(e).opacity")) >= .9
    tb = thumb.bounding_box()
    assert tb["height"] >= 26
    page.mouse.move(tb["x"] + tb["width"] / 2, tb["y"] + tb["height"] / 2)
    page.mouse.down()
    page.mouse.move(tb["x"] + tb["width"] / 2, box["y"] + box["height"] - 4, steps=5)
    page.mouse.up()
    top = page.evaluate(f"document.querySelector('.scroll-pane > {pane}').scrollTop")
    assert top > 20, "dragging the rail did not scroll the pane"


def test_stylesheet_has_no_orphan_closing_brace_swallowing_rules(root):
    html = (root / "index.html").read_text()
    css = html[html.index("<style>") + 7:html.index("</style>")]
    for rule in tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True):
        if rule.type == "qualified-rule":
            prelude = tinycss2.serialize(rule.prelude).strip()
            assert not prelude.startswith("}") and "@media" not in prelude, "stray } swallowed a rule: %r" % prelude[:60]
        assert rule.type != "error", rule.message


def test_old_browsers_get_a_clear_message_instead_of_a_blank_page(make_page, site):
    page = make_page(goto=False)
    page.add_init_script("delete AbortSignal.prototype.throwIfAborted;")
    page.goto(site)
    banner = page.locator("#compatBanner")
    assert banner.is_visible()
    assert "15.4" in banner.inner_text()