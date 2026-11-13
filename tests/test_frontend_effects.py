"""Meme pictures/GIFs, sound effects, automatic meme selection, asset health."""
import io

import pytest
from PIL import Image

from conftest import load_video
from helpers import effects, set_segments

COMBO_SOUND = {"laugh": "reveal", "suspicious": "boom", "shocked": "boom", "reveal": "reveal", "confused": "scratch", "awkward": "scratch"}


def run_auto(page, segments):
    set_segments(page, segments)
    page.evaluate("()=>{byId('autoMemes').checked=true;autoInsertMemes();}")
    return effects(page)


def test_generic_everyday_words_do_not_trigger_memes(loaded_page):
    out = run_auto(loaded_page, [{"from": 1 + 3 * i, "to": 2.5 + 3 * i, "text": t} for i, t in enumerate([
        "What time does the meeting start?", "How are you doing today?", "Why is the road closed?",
        "Stop by the shop later.", "I will leave at noon.", "Do you really need that?"])])
    assert out == []


@pytest.mark.parametrize("text,expected", [
    ("That is hilarious, I can't stop laughing!", "laugh"),
    ("You are lying to everyone, that's a lie!", "suspicious"),
    ("Wait, what?! No way, that's unbelievable!", "shocked"),
    ("Plot twist: it turns out the truth was revealed.", "reveal"),
    ("I don't understand, that makes no sense.", "confused"),
    ("This is so awkward, complete silence in the room.", "awkward"),
])
def test_strong_cues_pick_the_matching_reaction_and_sound(loaded_page, text, expected):
    out = run_auto(loaded_page, [{"from": 4, "to": 6, "text": text}])
    assert [(e["id"], e["sound"]) for e in out] == [(expected, COMBO_SOUND[expected])]
    assert out[0]["from"] == 4 and out[0]["auto"]


def test_moments_near_sensitive_topics_get_no_comedic_reaction(loaded_page):
    out = run_auto(loaded_page, [
        {"from": 4, "to": 6, "text": "The shooting left several people dead."},
        {"from": 7, "to": 9, "text": "That is hilarious, lol!"},       # 3 s after: must be skipped
        {"from": 22, "to": 24, "text": "That is hilarious, lol!"}])     # far away: fine
    assert [e["from"] for e in out] == [22]
    assert "sensitive" in loaded_page.inner_text("#autoMemeStatus").lower()


def test_auto_memes_are_capped_spaced_and_idempotent(loaded_page):
    segs = [{"from": 1 + 2 * i, "to": 2.5 + 2 * i, "text": "That is hilarious!"} for i in range(14)]
    out = run_auto(loaded_page, segs)
    assert 1 <= len(out) <= 6
    assert all(b["from"] - a["from"] >= 2.5 for a, b in zip(out, out[1:]))
    again = run_auto(loaded_page, segs)
    assert again == out, "running twice duplicated effects"


def test_auto_insertion_keeps_manual_effects(loaded_page):
    loaded_page.evaluate("reactionEffects.push({text:'MINE',from:20,duration:1,position:'center',sound:'none',emoji:'',image:null,imageName:''})")
    out = run_auto(loaded_page, [{"from": 4, "to": 6, "text": "That is hilarious, lol!"}])
    assert [e["text"] for e in out if not e["auto"]] == ["MINE"]


def test_failed_builtin_graphic_is_reported_and_never_used(make_page, site, media):
    page = make_page(goto=False)
    page.route("**/assets/memes/original/shocked.svg", lambda r: r.fulfill(status=404, body=b""))
    page.goto(site)
    page.wait_for_function("byId('assetStatus') && !byId('assetStatus').hidden", timeout=10000)
    assert "shocked" in page.inner_text("#assetStatus")
    assert page.evaluate("byId('effectCombo').querySelector('[value=shocked]').disabled")
    load_video(page, media["quad"])
    out = run_auto(page, [{"from": 4, "to": 6, "text": "Wait, what?! No way, that's unbelievable!"}])
    assert [e["id"] for e in out] == []


def _png(w, h, fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, fmt)
    return buf.getvalue()


def test_large_meme_pictures_are_downscaled_to_save_memory(loaded_page):
    page = loaded_page
    page.set_input_files("#effectImageFile", {"name": "big.png", "mimeType": "image/png", "buffer": _png(3000, 2000)})
    page.wait_for_function("/^(Ready|Picture failed)/.test(byId('effectImageStatus').textContent)")
    assert page.inner_text("#effectImageStatus").startswith("Ready")
    w, h = page.evaluate("[importedMemeImage.width, importedMemeImage.height]")
    assert max(w, h) <= 1024 and w / h == pytest.approx(1.5, rel=.02)


def test_gif_is_accepted_as_first_frame_with_honest_notice(loaded_page):
    page = loaded_page
    assert "image/gif" in page.get_attribute("#effectImageFile", "accept")
    gif = io.BytesIO()
    frames = [Image.new("RGB", (80, 80), c) for c in ((255, 0, 0), (0, 255, 0))]
    frames[0].save(gif, "GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
    page.set_input_files("#effectImageFile", {"name": "r.gif", "mimeType": "image/gif", "buffer": gif.getvalue()})
    page.wait_for_function("/^(Ready|Picture failed|Choose)/.test(byId('effectImageStatus').textContent)")
    text = page.inner_text("#effectImageStatus")
    assert text.startswith("Ready") and "first frame" in text.lower(), text


def test_audio_import_accepts_files_with_empty_mime_type(loaded_page, media):
    """iOS/Android pickers often give an empty MIME type; the extension fallback regex was broken (matched a literal backslash)."""
    page = loaded_page
    data = list(media["beep"].read_bytes())
    page.evaluate("""bytes=>{const dt=new DataTransfer();dt.items.add(new File([new Uint8Array(bytes)],'beep.mp3',{type:''}));
      const input=byId('effectAudioFile');input.files=dt.files;input.dispatchEvent(new Event('change'));}""", data)
    page.wait_for_function("!byId('effectAudioStatus').textContent.startsWith('Local audio only')")
    assert page.evaluate("byId('effectAudioFile').files[0].type") == ""
    assert page.inner_text("#effectAudioStatus").startswith("Ready"), page.inner_text("#effectAudioStatus")


def test_audio_import_rejects_non_audio(loaded_page):
    page = loaded_page
    page.set_input_files("#effectAudioFile", {"name": "notes.txt", "mimeType": "text/plain", "buffer": b"hello"})
    page.wait_for_function("!byId('effectAudioStatus').textContent.startsWith('Local audio only')")
    assert "audio" in page.inner_text("#effectAudioStatus").lower() and "Ready" not in page.inner_text("#effectAudioStatus")


def add_effect(page, text, start, duration):
    page.evaluate("([t,s,d])=>{byId('effectText').value=t;byId('effectStart').value=s;byId('effectDuration').value=d;byId('addEffect').click();}", [text, start, duration])


def test_overlapping_effects_are_trimmed_so_picture_and_sound_stay_paired(loaded_page):
    page = loaded_page
    add_effect(page, "A", 1.0, 2.0)
    add_effect(page, "B", 2.0, 1.5)
    out = effects(page)
    assert [(e["text"], e["from"]) for e in out] == [("A", 1.0), ("B", 2.0)]
    assert out[0]["duration"] == pytest.approx(1.0), "A still overlaps B, so two sounds would play under one picture"
    add_effect(page, "C", 2.1, 1.0)           # would leave B with 0.1 s: refused
    assert len(effects(page)) == 2
    assert "apart" in page.inner_text("#status").lower()


def test_effect_sounds_still_fire_when_timers_are_slow(make_page, site, media):
    """Phones throttle timers under load; the old 0.15 s trigger window then missed sounds."""
    page = make_page(goto=False)
    page.add_init_script("(()=>{const si=window.setInterval.bind(window);window.setInterval=(f,ms,...a)=>si(f,Math.max(ms||0,250),...a)})()")
    page.goto(site)
    load_video(page, media["quad"])
    page.evaluate("""()=>{byId('start').value=0;byId('end').value=4;window.__sounds=[];
      const orig=playEffectSound;playEffectSound=(k,b)=>{window.__sounds.push(video.currentTime);orig(k,b)};
      for(let i=0;i<8;i++)reactionEffects.push({text:'x',from:.6+.3*i,duration:.3,position:'center',sound:'boom',emoji:'',image:null,imageName:''});}""")
    page.click("#preview")
    page.wait_for_function("byId('status').textContent==='Preview complete.'", timeout=30000)
    assert len(page.evaluate("window.__sounds")) == 8


def test_cutting_into_an_effect_does_not_replay_its_sound_late(loaded_page):
    page = loaded_page
    page.evaluate("""()=>{byId('start').value=2.0;byId('end').value=3.5;window.__sounds=[];
      const orig=playEffectSound;playEffectSound=(k,b)=>{window.__sounds.push(k);orig(k,b)};
      reactionEffects.push({text:'x',from:1.0,duration:2.0,position:'center',sound:'boom',emoji:'',image:null,imageName:''});}""")
    page.click("#preview")
    page.wait_for_function("byId('status').textContent==='Preview complete.'", timeout=30000)
    assert page.evaluate("window.__sounds") == [], "sound started a full second after its picture"