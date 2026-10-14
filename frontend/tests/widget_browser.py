"""Exercise the shipped public widget in Chromium with local API fixtures."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

payload = '<img src=x onerror="window.pwn=1">'
output = Path('../docs/testing/frontend-widget-browser-20261013')
output.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    calls = []
    def route_handler(route):
        if route.request.method == 'POST':
            calls.append(route.request.post_data_json)
        route.fulfill(json={'answer': payload, 'sources': [{'label': payload, 'entity_type': payload}], 'metadata': {'query_id': 'fixture-query'}})
    page.route('**/api/v1/**', route_handler)
    page.goto('http://127.0.0.1:4175/')
    page.wait_for_load_state('networkidle')
    page.evaluate('document.body.replaceChildren()')
    page.add_script_tag(url='http://127.0.0.1:4175/chat-widget.js')
    page.evaluate('window.GraphRAGChat.ask("恶意文档来源回归")')
    expect(page.locator('.source-label')).to_have_text('[1] ' + payload)
    expect(page.locator('.source-type')).to_have_text(' • ' + payload)
    expect(page.locator('.message.assistant')).to_contain_text(payload)
    assert page.locator('img').count() == 0
    assert page.evaluate('window.pwn === undefined')
    page.locator('.sources-toggle').click()
    expect(page.locator('.sources-list')).to_be_visible()
    with page.expect_request('**/api/v1/feedback'):
        page.locator('.fb-btn').first.click()
    page.wait_for_function('document.querySelector("#graphrag-chat-widget-root").shadowRoot.querySelector(".fb-btn").classList.contains("active")')
    assert any(call.get('rating') == 'positive' for call in calls)
    assert not errors, errors
    page.screenshot(path=str(output / 'widget-source-safety.png'))
    (output / 'receipt.json').write_text(json.dumps({'browser': browser.version, 'scenarios': ['shipped-public-script', 'inert-answer-label-type', 'source-expand', 'feedback'], 'page_errors': errors, 'api_boundary': 'local fixtures, no backend/provider calls'}, ensure_ascii=False, indent=2), encoding='utf-8')
    browser.close()
