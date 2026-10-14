"""Local-only snapshot parser and provisional annotation builder; no network/model calls."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def read_snapshot(name):
    value = json.loads((ROOT / name).read_text(encoding='utf-8'))
    assert isinstance(value, str), 'Tool output schema changed; inspect before parsing'
    return value
def lines(block):
    rows = []
    for m in re.finditer(r'^L(\d+)(?:@P([\d-]+))?: (.*)$', block, re.M):
        rows.append({'web_line': int(m[1]), 'pdf_page_zero_based': m[2], 'text': m[3]})
    assert len({r['web_line'] for r in rows}) == len(rows)
    return rows

web = read_snapshot('web-open.json')
linux = lines(web.split('NIST Special Publication XXX')[0])
nist = lines(read_snapshot('web-rights-find.json').split('Source: find(', 1)[1].split('NIST Special Publication XXX')[0])
units = {}
for sid, rows, url, title in [
    ('LCNC-HOME', linux, 'https://linuxcnc.org/docs/2.9/html/config/ini-homing.html', 'Homing Configuration'),
    ('NIST-8091', nist, 'https://nvlpubs.nist.gov/nistpubs/ir/2015/NIST.IR.8091.pdf', 'Predicting Robot System Performance by Measuring and Composing Subsystem Attributes')]:
    text = ''
    for row in rows:
        row['start'] = len(text)
        text += row['text'] + '\n'
        row['end'] = len(text)
    path = ROOT / (sid + '.snapshot.txt')
    path.write_text(text, encoding='utf-8', newline='\n')
    units[sid] = {'source_id': sid, 'title': title, 'url': url, 'role': 'development',
                  'coverage_kind': 'platform_page_text_with_images_missing' if sid == 'LCNC-HOME' else 'partial_excerpt',
                  'observed_web_line_range': [rows[0]['web_line'],rows[-1]['web_line']],
                  'observed_rows':len(rows), 'original_report_total_web_lines':None if sid == 'LCNC-HOME' else 529,
                  'full_scan_eligible':False, 'collected_on':'2026-10-12',
                  'rights_evidence_file':'web-visual-rights.json',
                  'rights_basis':'LinuxCNC Legal Section L9-11, GNU FDL1.1+' if sid == 'LCNC-HOME' else 'NIST technical series policy L175-176; cover/front matter L0-15, third-party figure not used',
                  'artifact_kind': 'PLATFORM_TEXT_EXTRACTION_NOT_ORIGINAL', 'raw_file': None,
                  'raw_sha256': None, 'snapshot_file': path.name, 'snapshot_sha256': sha(path),
                  'version': '2.9 URL branch; exact release unverified' if sid == 'LCNC-HOME' else 'NISTIR 8091, November 2015, DOI 10.6028/NIST.IR.8091',
                  'rows': rows}

def evidence(sid, lo, hi):
    rows = [r for r in units[sid]['rows'] if lo <= r['web_line'] <= hi]
    assert [r['web_line'] for r in rows] == list(range(lo, hi+1)), (sid,lo,hi)
    return {'web_lines_inclusive': [lo, hi], 'snapshot_char_half_open': [rows[0]['start'], rows[-1]['end']],
            'snapshot_sha256': units[sid]['snapshot_sha256']}
def item(name, attrs, lo, hi):
    return {'item': name, 'required_attributes': attrs, 'lines': [lo, hi]}
questions = []
def add(qid, sid, scope, question, items, notes):
    for x in items:
        x['evidence'] = evidence(sid, *x.pop('lines'))
    questions.append({'question_id':qid, 'source_id':sid, 'source_snapshot_sha256':units[sid]['snapshot_sha256'],
                      'status':'PROVISIONAL_GOLD_BLOCKED_RAW_AND_VISUAL_QA', 'role':'development',
                      'question_language':'zh', 'evidence_language':'en', 'scope':evidence(sid,*scope),
                      'question':question, 'gold_items':items, 'expected_item_count':len(items),
                      'scoring_notes':notes, 'human_annotation_verified':False})

add('DEV-L01','LCNC-HOME',(93,104),'按第6节 Configuration 开头的表格，列出全部回零类型，并分别给出 HOME_SEARCH_VEL、HOME_LATCH_VEL、HOME_USE_INDEX 的取值。',[
    item('Immediate',{'HOME_SEARCH_VEL':'0','HOME_LATCH_VEL':'0','HOME_USE_INDEX':'NO'},99,99),
    item('Index-only',{'HOME_SEARCH_VEL':'0','HOME_LATCH_VEL':'nonzero','HOME_USE_INDEX':'YES'},100,100),
    item('Switch-only',{'HOME_SEARCH_VEL':'nonzero','HOME_LATCH_VEL':'nonzero','HOME_USE_INDEX':'NO'},101,101),
    item('Switch and Index',{'HOME_SEARCH_VEL':'nonzero','HOME_LATCH_VEL':'nonzero','HOME_USE_INDEX':'YES'},102,102)],
    ['条目和三个参数属性分开计分；不补入图示中的运动轨迹。'])
add('DEV-L02','LCNC-HOME',(145,156),'在6.10 HOME_ABSOLUTE_ENCODER 中，列出全部设置值及其行为，并列出该节另行说明的两项静默忽略行为。',[
    item('0',{'default':True,'behavior':'不使用绝对编码器'},150,150),
    item('1',{'behavior':'使用绝对编码器，并最终移动到 [JOINT_n]HOME'},151,151),
    item('2',{'behavior':'使用绝对编码器，不执行最终到 [JOINT_n]HOME 的移动'},152,152),
    item('HOME_IS_SHARED',{'behavior':'设置被静默忽略'},154,154),
    item('rehome request',{'behavior':'重新回零请求被静默忽略'},156,156)],
    ['前三项是枚举值，后两项是注意事项；允许分组，不能漏后两项。'])
add('DEV-L03','LCNC-HOME',(105,122),'仅依据6.1–6.3，列出三个速度参数的单位，以及未设置时的默认值或行为；对 HOME_FINAL_VEL 补充允许的取值条件。',[
    item('HOME_SEARCH_VEL',{'units':'machine-units per second','default':'0','behavior':'假定没有回零开关，跳过搜索阶段'},107,109),
    item('HOME_LATCH_VEL',{'units':'machine-units per second','default':'0'},114,117),
    item('HOME_FINAL_VEL',{'units':'machine-units per second','missing_behavior':'使用关节最大速度','value_constraint':'必须为正数'},120,122)],
    ['HOME_FINAL_VEL 未设置的行为不能错误写成数值默认0；不要求补充问题未请求的全部锁存逻辑。'])
add('DEV-L04','LCNC-HOME',(167,195),'列出6.11为三关节系统给出的全部五个示例，按顺序给出三个 HOME_SEQUENCE 值，并说明哪些关节同步最终移动。',[
    item('示例1',{'values':[0,1,1],'synchronized_joints':[]},169,173),
    item('示例2',{'values':[0,-1,-1],'synchronized_joints':[1,2]},174,178),
    item('示例3',{'values':[0,-1,1],'synchronized_joints':[1,2]},180,184),
    item('示例4',{'values':[0,0,0],'synchronized_joints':[]},186,190),
    item('示例5',{'values':[-1,-1,-1],'synchronized_joints':[0,1,2]},191,195)],
    ['同步指最终移动同步；同序号可同时回零不自动等于最终移动同步。'])
add('DEV-L05','LCNC-HOME',(203,212),'列出6.14 Immediate Homing 代码块中的全部五项配置及其给定值或允许替代值，并说明省略 HOME_SEQUENCE 对 HOME ALL 的影响。',[
    item('HOME_SEARCH_VEL',{'value':'0'},207,207),
    item('HOME_LATCH_VEL',{'value':'0'},208,208),
    item('HOME_USE_INDEX',{'value':'NO'},209,209),
    item('HOME_OFFSET',{'value':'0','alternative':'home position offset (HOME)'},210,210),
    item('HOME_SEQUENCE',{'value':'0','alternative':'other valid sequence number','omission_effect':'该关节不参与 HOME ALL'},211,212)],
    ['代码块内容和省略行为均需回答；HOME 仅作解释，不能增加为代码块中的第六项。'])
names = [
 ('Tolerances','机械臂到达位置的变化；传感器输出不确定性',214,215),
 ('Time needed for execution','抓取或定位零件所需时间',216,217),
 ('Variability','时间、位置的变化',218,218),
 ('Weight','负载能力及可达体积不同部位的约束',219,220),
 ('Size','设备占地、传感器视场或可抓取最大物体尺寸',221,222),
 ('Reachability of equipment','机械臂工作体积',223,223),
 ('Accuracy of equipment','装配配合或取件测量是否足够精确',224,226),
 ('Speed of equipment','能否在分配时间内执行',227,227),
 ('Part feeding','是否需精确供料或加传感器定位',228,229),
 ('Required system capacity','系统能否达到必要吞吐量',230,231),
 ('Uptime of equipment','可靠性是否保证产能；子系统失效对系统的影响',232,234),
 ('Tool changes required','是否能调整操作顺序减少换刀',235,236),
 ('Testing and inspection','能否并入其他步骤；是否需独立子系统及数量',237,238),
 ('Constraints','新增子系统对其他子系统的限制，例如定位容差',239,241)]
add('DEV-N01','NIST-8091',(205,241),'在NISTIR 8091第3节、印刷页6（PDF索引7）“An incomplete list”引出的列表中，列出文中全部度量类别，并为每类保留文中的示例或判定含义；说明该列表是否声称穷尽全部度量。',
    [item(n,{'example_or_meaning':a},lo,hi) for n,a,lo,hi in names],
    ['14类为该范围内列举的全部条目，不代表领域全集；必须注明原文称列表不完整，证据web行213。',
     '每类括号内示例/问题的语义逐项检查，不要求逐字翻译；不能将执行时间与变化性等合并。'])

for q in questions:
    q['question'] = q['question'].replace('全部五个示例','全部示例').replace('全部五项配置','全部配置').replace('两项静默忽略行为','静默忽略行为')
    q['task_role'] = 'SCOPE_EXPLICIT_CALIBRATION_PROBE_NOT_DIFFICULTY_OR_NOVELTY_EVIDENCE'
    q['range_condition'] = 'scope_given'
    q['evaluation_input_rule'] = 'Only question and corpus for baseline; gold scope, item count, offsets and answers excluded from model input'
    if q['question_id'] == 'DEV-L01':
        q['attribute_header_evidence'] = evidence('LCNC-HOME',97,98)
    if q['question_id'] == 'DEV-L02':
        q['question'] = '在6.10 HOME_ABSOLUTE_ENCODER 中，列出枚举代码中的设置值及其行为，并列出该节Note说明的静默忽略行为。'
    if q['question_id'] == 'DEV-L03':
        q['question'] = '仅依据6.1–6.3，列出三个速度参数的单位和数值默认值；若没有给出数值默认值，写出未设置时的行为。对 HOME_FINAL_VEL 补充允许的取值条件。'
    if q['question_id'] == 'DEV-N01':
        q['question'] = '在NISTIR 8091第3节中，引出子系统所需度量的列表列出了哪些类别？为每类保留括号中全部示例或判定要点，并说明该列表是否声称穷尽全部度量。'
        q['required_answer_qualifiers'] = [{'claim':'列表不完整；只穷尽文中当前列表，不代表所有可能度量', 'evidence':evidence('NIST-8091',213,213)}]
        components = [
            ['机械臂到达指令位置的变化','传感器输出的不确定性'],
            ['机械臂抓取零件所需时间','传感器定位零件所需时间'],
            ['时间的变化','位置的变化'],
            ['机械臂负载能力','可达体积不同部位的负载能力约束'],
            ['设备占地','传感器视场','机器人可抓取物体的最大尺寸'],
            ['机械臂工作体积'],
            ['机器人能否足够精确地配合零件以完成装配','传感器能否以取件所需精度测量'],
            ['子系统能否在分配时间内执行'],
            ['设备是否需要精确供料','是否需增加传感器定位零件'],
            ['当前配置系统能否达到必要吞吐量'],
            ['设备可靠性是否足以保证所需产能','子系统失效对整体系统的影响'],
            ['是否需要换刀','若需要，能否调整操作顺序以减少换刀'],
            ['测试与检查能否并入其他步骤','是否需要独立子系统','若需要，独立子系统的数量'],
            ['新增子系统是否限制其他子系统的使用','例如机械臂要求传感器在特定容差内定位零件']]
        for x, atoms in zip(q['gold_items'],components, strict=True):
            x['required_attributes'].pop('example_or_meaning')
            x['required_attributes']['example_or_meaning_components'] = atoms
    for x in q['gold_items']:
        x['attribute_scoring_rule'] = 'Score each named field and each list component separately; semantic equivalents accepted; item name alone does not satisfy attributes'
save('units.json',units)
save('questions-gold.draft.json',{'status':'DRAFT_NOT_EXECUTABLE_BENCHMARK','questions':questions,
                               'heldout_H1':[],'heldout_H2':[], 'annotator':'AI source-grounded draft; not independent human Gold'})
checks = {'questions':len(questions),'gold_items':sum(len(q['gold_items']) for q in questions),
          'units':len(units),'original_files_frozen':0,'visual_checks_passed':0,
          'checks':['All scopes and item evidence map to contiguous observed web lines',
                    'All offsets index LF-normalized Unicode code points, half-open',
                    'Snapshot hashes computed from bytes; raw hashes deliberately null'],
          'status':'STRUCTURAL_PASS_ONLY_RAW_AND_VISUAL_GATE_BLOCKED'}
for q in questions:
    lo,hi = q['scope']['snapshot_char_half_open']
    for x in q['gold_items']:
        a,b=x['evidence']['snapshot_char_half_open']
        assert lo <= a < b <= hi
save('verification.json',checks)
print(json.dumps(checks,ensure_ascii=False))
