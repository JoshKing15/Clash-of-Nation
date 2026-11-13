"""Preview/export parity: crop framing, masks, effect timing, memory and CPU use."""
import io

import pytest
from PIL import Image

from conftest import load_video
from helpers import audio_onset, export_to_file, pixel_class, quadrant_color, video_onset

CROP_CASES = [(1.0, .5, .5), (2.0, 0, 0), (2.0, 1, 1), (2.0, .5, .5), (3.0, 0, 1)]
POINTS = [(.1, .1), (.9, .1), (.1, .9), (.9, .9)]


def expected(zoom, x, y, u, v):
    w = 1 / zoom
    return quadrant_color((1 - w) * x + w * u, (1 - w) * y + w * v)


def seek(page, t):
    page.evaluate("t=>new Promise(r=>{video.addEventListener('seeked',r,{once:true});video.currentTime=t})", t)


@pytest.mark.parametrize("zoom,x,y", CROP_CASES)
def test_export_frame_applies_the_crop(loaded_page, zoom, x, y):
    page = loaded_page
    seek(page, 1)
    got = page.evaluate("""([z,x,y])=>{canvas.width=640;canvas.height=360;
      watermarkSettings={brand:false,crop:{enabled:z>1,zoom:z,x:x,y:y},mask:null};draw(false);
      return [[.1,.1],[.9,.1],[.1,.9],[.9,.9]].map(([u,v])=>[...ctx.getImageData(Math.round(u*640),Math.round(v*360),1,1).data]);}""", [zoom, x, y])
    assert [pixel_class(p) for p in got] == [expected(zoom, x, y, u, v) for u, v in POINTS]


def test_pixelated_mask_samples_the_cropped_region_not_the_raw_frame(loaded_page):
    page = loaded_page
    seek(page, 1)
    px = page.evaluate("""()=>{canvas.width=640;canvas.height=360;
      const mask={x:1,y:1,width:.2,height:.2,pixelate:true};
      watermarkSettings={brand:false,crop:{enabled:true,zoom:2,x:0,y:0},mask};   // crop shows only the red quadrant
      maskCanvas.width=Math.max(1,Math.round(canvas.width*mask.width/14));maskCanvas.height=Math.max(1,Math.round(canvas.height*mask.height/14));
      draw(false);return [...ctx.getImageData(Math.round(.9*640),Math.round(.9*360),1,1).data];}""")
    assert pixel_class(px) == "red", "mask patch came from the uncropped frame: %s" % pixel_class(px)


@pytest.mark.parametrize("zoom,x,y", CROP_CASES)
def test_live_crop_preview_matches_export_framing(loaded_page, zoom, x, y):
    page = loaded_page
    page.evaluate("openEditorTool('brand')")
    seek(page, 1)
    page.evaluate("([z,x,y])=>{const set=(id,v)=>{byId(id).value=v;byId(id).dispatchEvent(new Event('input'))};"
                  "byId('cropEnabled').checked=z>1;byId('cropEnabled').dispatchEvent(new Event('input'));"
                  "set('cropZoom',z*100);set('cropX',x*100);set('cropY',y*100);}", [zoom, x, y])
    page.locator(".screen").scroll_into_view_if_needed()
    page.wait_for_timeout(150)
    rect = page.evaluate("""()=>{const s=document.querySelector('.screen').getBoundingClientRect();
      const r=Math.min(s.width/video.videoWidth,s.height/video.videoHeight),w=video.videoWidth*r,h=video.videoHeight*r;
      return {x:s.left+(s.width-w)/2,y:s.top+(s.height-h)/2,w,h}}""")
    png = page.screenshot(clip={"x": rect["x"], "y": rect["y"], "width": rect["w"], "height": rect["h"]})
    img = Image.open(io.BytesIO(png)).convert("RGB")
    got = [pixel_class(img.getpixel((int(u * img.width), int(v * img.height)))) for u, v in POINTS]
    assert got == [expected(zoom, x, y, u, v) for u, v in POINTS]


def test_crop_preview_never_stretches_the_picture(loaded_page):
    page = loaded_page
    page.evaluate("openEditorTool('brand')")
    page.evaluate("()=>{byId('cropEnabled').checked=true;byId('cropEnabled').dispatchEvent(new Event('input'))}")
    assert page.evaluate("getComputedStyle(video).objectFit") in ("contain", "scale-down")


def test_preview_draws_each_video_frame_about_once(loaded_page):
    page = loaded_page
    page.evaluate("""()=>{byId('start').value=0;byId('end').value=2;window.__draws=0;
      const o=CanvasRenderingContext2D.prototype.drawImage;
      CanvasRenderingContext2D.prototype.drawImage=function(i,...a){if(i instanceof HTMLVideoElement)window.__draws++;return o.call(this,i,...a)}}""")
    page.click("#preview")
    page.wait_for_function("byId('status').textContent==='Preview complete.'", timeout=30000)
    draws = page.evaluate("window.__draws")
    assert draws <= 30 * 2 * 1.4 + 3, "%d draws for 60 source frames: wasted CPU/heat on phones" % draws


def test_export_planner_keeps_long_clips_within_phone_memory(loaded_page):
    page = loaded_page
    short = page.evaluate("planExport(60,1920,1080)")
    assert short["ok"] and short["bitsPerSecond"] <= 6_500_000
    mid = page.evaluate("planExport(600,1920,1080)")
    assert mid["ok"] and mid["estimatedBytes"] <= 160e6
    long_ = page.evaluate("planExport(3600,1920,1080)")
    assert not long_["ok"] and "shorter" in long_["message"].lower()


def test_export_sound_lands_on_the_meme_frame(loaded_page, tmp_path):
    page = loaded_page
    page.evaluate("""()=>{byId('start').value=0;byId('end').value=4;byId('brand').checked=false;
      reactionEffects.push({text:'WHAT?!',from:1.5,duration:1.0,position:'center',sound:'boom',emoji:'',image:builtInMemes.shocked,imageName:'shocked',imageSize:.5});}""")
    out = export_to_file(page, tmp_path / "out.mp4")
    a, v = audio_onset(out), video_onset(out)
    assert a is not None and v is not None
    assert abs(a - 1.5) < .2 and abs(v - 1.5) < .2 and abs(a - v) < .15, (a, v)


def test_export_trimmed_into_an_effect_keeps_sound_aligned(loaded_page, tmp_path):
    """Cut starts 0.1 s after the effect begins: picture is on screen at once, sound must be too."""
    page = loaded_page
    page.evaluate("""()=>{byId('start').value=1.6;byId('end').value=3.6;byId('brand').checked=false;
      reactionEffects.push({text:'WHAT?!',from:1.5,duration:1.0,position:'center',sound:'boom',emoji:'',image:builtInMemes.shocked,imageName:'shocked',imageSize:.5});}""")
    out = export_to_file(page, tmp_path / "late.mp4")
    a = audio_onset(out)
    assert a is not None and a < .35, a


def _duration(path):
    import subprocess
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True).stdout.strip())


def test_export_with_teaser_crop_mask_subtitles_and_watermark_completes(loaded_page, tmp_path):
    page = loaded_page
    page.evaluate("""()=>{byId('start').value=2;byId('end').value=4;
      byId('hook').checked=true;byId('hookStart').value=6;byId('hookEnd').value=7;
      byId('brand').checked=true;byId('mask').checked=true;byId('maskMode').value='pixelate';
      byId('cropEnabled').checked=true;byId('cropZoom').value=150;
      byId('showSubtitles').checked=true;subtitleSegments.push({from:2.2,to:3.5,text:'Hello there'});}""")
    out = export_to_file(page, tmp_path / "full.mp4")
    assert 2.7 <= _duration(out) <= 3.8, _duration(out)
    assert "Export ready" in page.inner_text("#status")


def test_bleep_lands_at_the_right_moment_in_the_exported_audio(loaded_page, tmp_path):
    page = loaded_page
    page.evaluate("()=>{byId('start').value=2;byId('end').value=4;byId('brand').checked=false;ranges.push({from:2.5,to:3.0,mode:'bleep'});}")
    out = export_to_file(page, tmp_path / "bleep.mp4")
    onset = audio_onset(out)
    assert onset is not None and 0.3 <= onset <= 0.7, onset      # source 2.5 s, cut starts at 2.0 s