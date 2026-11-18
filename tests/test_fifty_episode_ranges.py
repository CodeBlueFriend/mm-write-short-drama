"""50-episode software-fixture regression, not fifty episodes of authored drama.

All review/confirmation records are explicitly synthetic software fixtures.
The test stages and inspects DOCX structure; it neither claims literary review
nor visual QA and does not publish through a fake render manifest.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'mm-write-short-drama/scripts'
sys.path.insert(0,str(SCRIPTS))
import workflow_lib as w
import init_project
import update_episode_state
try:
 import export_screenplay_docx as ex
 from docx import Document
except SystemExit:
 ex=None
sys.path.insert(0,str(SCRIPTS.parent/'evals/fixtures'))
from workflow_fixture import fixture_polish

TAG='software-fixture'
IDS=[f'{n:03d}' for n in range(1,51)]
PROMISE='SOFTWARE-FUTURE-035'


def run_main(module,*args):
 with patch.object(sys,'argv',[str(Path(module.__file__)),*map(str,args)]),contextlib.redirect_stdout(io.StringIO()):
  return module.main()


def write_front(root,end):
 body={
  '剧本名':'范围软件夹具','来源':'software-fixture 合成软件验收；不是五十集真实故事，不是真人创作批准。',
  '类型':'software-fixture 范围与版式回归','集数':f'全剧共50集，本稿为第1—{end}集正式剧本。',
  '剧名寓意':'software-fixture 用编号标记检查范围。','热门元素':'software-fixture 无市场或热度主张。',
  '创作理由':'software-fixture 仅测试范围、版本及承诺到期规则。','故事梗概':f'software-fixture 本稿含第1—{end}号合成检查项，不作为叙事成品。',
  '主要角色':'夹具甲：software-fixture 编号检查角色，不作为文学人物评价。'}
 path=root/'front-matter.md';path.write_text('\n\n'.join(f'## {k}\n{v}' for k,v in body.items())+'\n',encoding='utf-8')
 return path


def seed(root):
 run_main(init_project,root,'--mode','original','--total-episodes','50','--review-mode','automatic')
 source=w.read_json(root/w.SOURCE);source['originalIdea']='software-fixture: fifty numbered legal episode/scene records, not an authored story.';w.save_json(root/w.SOURCE,source)
 for name in [w.TREATMENT,'04-story-bible.md',w.OUTLINE]:
  (root/name).write_text('# software-fixture\n\nsoftware-fixture：夹具甲逐项检查编号；标记一在第35项到期。仅为确定性软件回归，不声称创作或文学审核。\n',encoding='utf-8')
 for n in range(1,51):
  extra='▲夹具甲放下一号夹具。\n' if n==1 else ''
  (root/f'episodes/EP{n:03d}.md').write_text(f'# 第{n}集\n\n## {n}-1 日 内 软件夹具检查室\n人物：夹具甲\n▲夹具甲查看第{n}号文件。\n{extra}夹具甲：software-fixture，第{n}号收到。\n',encoding='utf-8')
 path=root/'06-episode-matrix.csv'
 with path.open(newline='',encoding='utf-8') as f: fields=next(csv.reader(f))
 with path.open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
  for n in range(1,51): writer.writerow({k:str(n) if k=='episode' else TAG for k in fields})
 path=root/'continuity/foreshadowing.csv'
 with path.open(newline='',encoding='utf-8') as f: fields=next(csv.reader(f))
 row={k:'' for k in fields};row.update(foreshadow_id=PROMISE,setup='software-fixture 一号夹具',setup_episode='1',setup_scene='1-1',payoff_by='35',status='planned',evidence='software-fixture EP001/1-1')
 with path.open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerow(row)
 write_front(root,30)


def promise(state):
 data={'id':PROMISE,'status':state,'setupEvidence':[{'path':'episodes/EP001.md','quote':'放下一号夹具'}]}
 if state=='future': data.update(owner=TAG,plannedRange='35')
 if state=='resolved': data['payoffEvidence']=[{'path':'episodes/EP035.md','quote':'归还一号夹具'}]
 return data


def issue(fixed=False):
 refs=[{'path':'episodes/EP001.md','quote':'放下一号夹具'}]
 if fixed: refs.append({'path':'episodes/EP035.md','quote':'归还一号夹具'})
 result={'issueId':'SOFTWARE-OVERDUE-035','severity':'P1','category':'foreshadowing','promiseId':PROMISE,'location':'software-fixture EP035/35-1','evidence':refs,'reason':'software-fixture: due-at-35 marker absent in full-season scope.' if not fixed else 'software-fixture: actual marker now present in EP035.','returnTo':'scene','impactScope':['EP035'],'regressionCheck':['software-fixture compare setup at 1-1 with payoff at 35-1'],'status':'fixed' if fixed else 'open'}
 if fixed: result['retest']={'passed':True,'evidence':refs}
 return result


def review(root,stage,ids=None,promise_state=None,issues=None):
 ids=ids or [];session=w.review_pack(root,stage,ids,'front-matter.md' if stage=='final' else None)
 first={'reviewer':TAG,'knowledgeOfExpectations':'informed','readChunks':[c['id'] for c in session['chunks']],
        'causalRetelling':'software-fixture metadata and coverage exercise; no model literary reading or real user approval is claimed.',
        'observations':[{'chunkId':c['id'],'protagonistIntent':TAG,'concern':TAG,'forcedChange':TAG,'understanding':'software-fixture only','evidence':[{'path':c['source'],'quote':'夹具甲'}]} for c in session['chunks']]}
 work=root/'work/software-fixture'/session['sessionId'];w.save_json(work/'first.json',first);w.submit_first_read(root,session['sessionId'],work/'first.json');w.reveal_context(root,session['sessionId'])
 refs=[{'path':session['coverage'][0]['path'],'quote':'夹具甲'}]
 report={'sessionId':session['sessionId'],'stage':stage,'reviewer':TAG,'purpose':'software-fixture, not a literary evaluation','complete':True,'coverage':session['coverage'],
         'checks':[{'domain':domain,'result':'fail' if domain=='payoff' and issues and issues[0]['status']=='open' else 'pass','reason':'software-fixture deterministic contract exercise only','evidence':refs,'issueIds':[issues[0]['issueId']] if domain=='payoff' and issues and issues[0]['status']=='open' else []} for domain in sorted(w.DOMAINS[stage])],
         'issues':issues or [],'methods':[{'status':'skipped','reason':'software-fixture only; not testing literary methods.'}],'promiseAudit':[promise(promise_state)] if promise_state else []}
 w.save_json(work/'second.json',report)
 return w.record_review(root,session['sessionId'],work/'second.json')


def approve(root,ids):
 state=w.read_json(root/'.drama/project-state.json');bible=state['artifacts']['storyBible']['revision'];matrix=state['artifacts']['episodeMatrix']['revision']
 for number in ids:
  for target in ('planned','draft','in_review','approved'):
   run_main(update_episode_state,root,'--episode',number,'--to',target,'--story-bible-revision',bible,'--matrix-revision',matrix)


@unittest.skipUnless(ex,'python-docx unavailable')
class FiftyEpisodeRangeTests(unittest.TestCase):
 def test_partial_full_ranges_future_due_marker_and_visible_word(self):
  result={'purpose':'software-fixture only','totalEpisodes':50,'literaryReview':False,'realUserApproval':False,'visualQaOrPublication':False,'renderManifestBypass':False}
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'software-fixture';seed(root)
   review(root,'treatment');review(root,'outline');w.confirm_outline(root,'confirm','software-fixture synthetic confirmation only; not creator approval',TAG,'software-fixture total50')
   partial=IDS[:30];review(root,'batch',partial,'future');fixture_polish(root,partial);approve(root,partial);review(root,'final',partial,'future')
   front=root/'front-matter.md';self.assertEqual(w.validate_release(root,partial,front),[])
   episodes=[ex.parse_episode(root/f'episodes/EP{n}.md') for n in reversed(partial)];episodes.sort(key=lambda e:e.number)
   target=root/'deliverables/范围软件夹具_第01-30集.docx';staged=ex.stage_release(root,episodes,target,'范围软件夹具',front)
   visible=[p.text for p in Document(staged).paragraphs if p.text.strip()];labels=[int(m[1]) for text in visible if (m:=re.fullmatch(r'第\s*(\d+)\s*集',text))]
   self.assertEqual(labels,list(range(1,31)));self.assertIn('集数：全剧共50集，本稿为第1—30集正式剧本。',visible);partial_hash=ex.verify_visible_text(staged,episodes,'范围软件夹具',front);self.assertFalse(target.exists())
   result['partial']={'episodeCount':len(labels),'episodeOrder':labels,'frontTotal':50,'frontRange':[1,30],'allVisibleParagraphsMatchReviewedInput':True,'visibleTextHash':partial_hash,'promiseDueAt35':'future accepted with owner software-fixture and plannedRange35','formalFileCreated':False}
   # Parser checks run before a content gate and must not silently drop/merge IDs.
   for values,message in [([episodes[0].source,episodes[0].source],'duplicate episode input paths')]:
    with self.assertRaisesRegex(ValueError,message): ex.collect_inputs(values)
   alias=root/'EP002-copy.md';alias.write_bytes((root/'episodes/EP002.md').read_bytes())
   cli_results={}
   for label,inputs in [('duplicate-number',[root/'episodes/EP002.md',alias]),('gap',[root/'episodes/EP001.md',root/'episodes/EP003.md'])]:
    with self.assertRaises(SystemExit) as stopped,contextlib.redirect_stderr(io.StringIO()) as stderr:
     run_main(ex,*inputs,'--preview','--output',root/f'{label}.docx')
    self.assertEqual(stopped.exception.code,2);self.assertFalse((root/f'{label}.docx').exists());cli_results[label]=stderr.getvalue().strip().splitlines()[-1]
   self.assertTrue(ex.validate_front_matter(front,'范围软件夹具',list(range(1,51)),50))
   result['rangeRejections']={**cli_results,'duplicatePathRejected':True,'wrongFrontRangeRejected':True}
   # At season end the same due-at-35 row can no longer be labeled future.
   write_front(root,50)
   with self.assertRaisesRegex(ValueError,'overdue promise cannot be future'):
    review(root,'batch',IDS,'future')
   blocked_batch=review(root,'batch',IDS,'overdue',[issue()]);blocked_final=review(root,'final',IDS,'overdue',[issue()])
   self.assertEqual(blocked_batch['status'],'blocked');self.assertEqual(blocked_final['status'],'blocked')
   full_episodes=[ex.parse_episode(root/f'episodes/EP{n}.md') for n in IDS];full_target=root/'deliverables/范围软件夹具_第01-50集.docx'
   with self.assertRaisesRegex(ValueError,'blocking issues|unresolved issues'):
    ex.stage_release(root,full_episodes,full_target,'范围软件夹具',front)
   self.assertFalse(full_target.exists());result['unresolvedFullSeason']={'futureRejected':True,'batchStatus':blocked_batch['status'],'finalStatus':blocked_final['status'],'formalExportBlocked':True,'dueEpisode':35}
   # Repair the synthetic missing marker and re-review, preserving the issue ID.
   path=root/'episodes/EP035.md';path.write_text(path.read_text()+'▲夹具甲归还一号夹具。\n',encoding='utf-8')
   ledger=root/'continuity/foreshadowing.csv'
   with ledger.open(newline='',encoding='utf-8') as f: reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
   rows[0].update(actual_payoff='software-fixture EP035/35-1',status='resolved')
   with ledger.open('w',newline='',encoding='utf-8') as f: writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
   stale=w.synchronize(root);self.assertTrue(all(stale['episodes'][n]=='stale' for n in partial))
   review(root,'batch',IDS,'resolved',[issue(True)]);fixture_polish(root,IDS);approve(root,IDS);review(root,'final',IDS,'resolved',[issue(True)])
   self.assertEqual(w.validate_release(root,IDS,front),[])
   full_episodes=[ex.parse_episode(root/f'episodes/EP{n}.md') for n in IDS];full_stage=ex.stage_release(root,full_episodes,full_target,'范围软件夹具',front)
   visible=[p.text for p in Document(full_stage).paragraphs if p.text.strip()];labels=[int(m[1]) for text in visible if (m:=re.fullmatch(r'第\s*(\d+)\s*集',text))]
   self.assertEqual(labels,list(range(1,51)));self.assertIn('集数：全剧共50集，本稿为第1—50集正式剧本。',visible);full_hash=ex.verify_visible_text(full_stage,full_episodes,'范围软件夹具',front);self.assertFalse(full_target.exists())
   result['repairedFullSeason']={'episodeCount':len(labels),'episodeOrder':labels,'frontTotal':50,'frontRange':[1,50],'allVisibleParagraphsMatchReviewedInput':True,'visibleTextHash':full_hash,'sameIssueIdRetested':'SOFTWARE-OVERDUE-035','payoffEpisode':35,'allEpisodeStatesApprovedAsSoftwareFixtures':True,'formalFileCreated':False}
   result['status']='passed';result['scope']='temporary isolated fixture; staged Word structure and gate behavior only; no literary or visual quality claim, no formal publication'
  output=os.environ.get('WORKFLOW_FIFTY_REPORT')
  if output:
   path=Path(output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__': unittest.main()
