"""Browser regression: suggestions require explicit selection before editing."""
import json


def test_highlight_choice_sets_cut_only_after_user_approves(loaded_page):
    page = loaded_page
    clips = [{"id": 1, "from": 5, "to": 12,
              "excerpt": "Wait, why did that happen?", "reason": "Speech activity"}]
    page.route("**/api/auto-clips", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
        body=json.dumps({"clips": clips, "selection_method": "transcript_heuristic"})))
    page.evaluate("""() => {
      subtitleSegments.push({from:5,to:8,text:'Wait, why did that happen?'});
      setControls();
    }""")
    initial = page.evaluate("()=>[byId('start').value,byId('end').value]")
    assert page.evaluate("()=>byId('suggestHighlights').disabled") is False
    page.evaluate("()=>byId('suggestHighlights').click()")
    page.wait_for_function("()=>document.querySelectorAll('#highlightSuggestions button').length===1")
    assert page.evaluate("()=>[byId('start').value,byId('end').value]") == initial
    page.evaluate("()=>{byId('hook').checked=true;byId('hook').dispatchEvent(new Event('change'))}")
    page.evaluate("()=>document.querySelector('#highlightSuggestions button').click()")
    selected = page.evaluate("()=>[byId('start').value,byId('end').value,byId('hook').checked,byId('hookTimes').hidden]")
    assert selected == ["5", "12", False, True]
