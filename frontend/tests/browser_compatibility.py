"""Real Chromium UI/CSS checks; API route fixtures are not provider integration tests."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT = Path('../docs/testing/frontend-browser-20261013')
OUT.mkdir(exist_ok=True)
NODE = {'id': 'n', 'node_id': 'n', 'label': '收入', 'entity_type': 'metric', 'properties': {'value': 10}, 'page_idx': 0, 'bbox_norm': [1,2,3,4], 'grounding_status': 'grounded'}
GRAPH = {'nodes': [NODE], 'edges': [], 'stats': {'total_nodes': 1, 'total_edges': 0, 'grounded_nodes': 1, 'entity_types': {'metric': 1}}, 'documents': ['d']}
RECEIPTS = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def route_handler(route):
        path = route.request.url.split('/api/v1/')[-1]
        if path == 'health':
            data = {'stats': {'total_kg_nodes': 1, 'total_kg_edges': 0}, 'components': {}, 'status': 'healthy'}
        elif path == 'documents':
            data = {'documents': [{'document_id': 'd', 'filename': 'report.pdf', 'status': 'indexed', 'kg_nodes': 1, 'kg_edges': 0, 'pages': 1, 'file_size_mb': 1, 'indexed_at': '2026-01-01'}], 'total': 1}
        elif path.startswith('graph/'):
            data = GRAPH
        elif path == 'rag/query':
            data = {'query': 'q', 'answer': '**答案**\n\n|字段|值|\n|---|---|\n|收入|10|', 'sources': [NODE], 'metadata': {'duration_ms': 20}}
        else:
            data = {}
        route.fulfill(json=data)
    page.route('**/api/v1/**', route_handler)
    page.goto('http://127.0.0.1:4175/upload')
    page.wait_for_load_state('networkidle')
    expect(page.get_by_text('上传文档，构建知识图谱')).to_be_visible()
    upload = page.locator('main > div')
    style = upload.evaluate('(el) => ({padding:getComputedStyle(el).paddingTop, maxWidth:getComputedStyle(el).maxWidth})')
    assert style == {'padding': '32px', 'maxWidth': '900px'}, style
    assert page.locator('aside').evaluate('(el)=>getComputedStyle(el).backgroundColor') == 'rgb(17, 24, 39)'
    assert page.locator('body').evaluate('(el)=>getComputedStyle(el).backgroundColor') == 'rgb(11, 17, 32)'
    assert 'Inter' in page.locator('body').evaluate('(el)=>getComputedStyle(el).fontFamily')
    assert page.locator('#urlInput').evaluate('(el)=>getComputedStyle(el).borderRadius') == '3.40282e+38px' or page.locator('#urlInput').evaluate('(el)=>parseFloat(getComputedStyle(el).borderRadius)') >= 9999
    page.locator('#fileInput').set_input_files({'name': 'fixture.pdf', 'mimeType': 'application/pdf', 'buffer': b'%PDF-fixture'})
    expect(page.get_by_text('fixture.pdf')).to_be_visible()
    expect(page.get_by_role('button', name='🚀 开始解析文档')).to_be_enabled()
    page.screenshot(path=str(OUT/'upload-desktop.png'))
    RECEIPTS.append({'scenario': 'upload-desktop', 'style': style})
    page.goto('http://127.0.0.1:4175/documents')
    page.wait_for_load_state('networkidle')
    expect(page.get_by_text('report.pdf')).to_be_visible()
    assert page.get_by_role('table').evaluate('(el)=>getComputedStyle(el).width') != '0px'
    assert page.get_by_title('问答').get_attribute('href') == '/query/d'
    RECEIPTS.append({'scenario': 'document-table'})
    page.goto('http://127.0.0.1:4175/query/d')
    page.wait_for_load_state('networkidle')
    page.get_by_placeholder('输入你的问题，Enter 发送...').fill('问题')
    page.get_by_placeholder('输入你的问题，Enter 发送...').press('Enter')
    expect(page.get_by_text('答案', exact=True)).to_be_visible()
    expect(page.get_by_role('table')).to_be_visible()
    page.get_by_role('button', name='n', exact=True).click()
    expect(page.get_by_text('答案溯源', exact=True)).to_be_visible()
    expect(page.get_by_text('[1, 2, 3, 4]')).to_be_visible()
    assert page.get_by_role('table').locator('td').first.evaluate('(el)=>getComputedStyle(el).color') == 'rgb(241, 245, 249)'
    page.screenshot(path=str(OUT/'query-details-desktop.png'))
    RECEIPTS.append({'scenario': 'query-markdown-source-detail'})
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto('http://127.0.0.1:4175/upload')
    page.wait_for_load_state('networkidle')
    expect(page.locator('aside')).not_to_be_visible()
    assert page.locator('main > div').evaluate('(el)=>getComputedStyle(el).paddingTop') == '16px'
    expect(page.locator('nav').last).to_be_visible()
    page.screenshot(path=str(OUT/'upload-mobile.png'))
    RECEIPTS.append({'scenario': 'mobile-breakpoint'})
    assert not errors, errors
    (OUT/'receipt.json').write_text(json.dumps({'browser': browser.version, 'scenarios': RECEIPTS, 'page_errors': errors, 'api_boundary': 'local fixtures, no backend/provider calls'}, ensure_ascii=False, indent=2), encoding='utf-8')
    browser.close()
