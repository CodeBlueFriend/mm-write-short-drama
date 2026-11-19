"""Behavioral regressions for formal delivery and expression review."""
from __future__ import annotations
import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'mm-write-short-drama/scripts'
sys.path.insert(0,str(SCRIPTS))
import polish_guard
import render_screenplay
try:
 import export_screenplay_docx as exporter
except SystemExit:
 exporter=None


def front(title='新故事',total=2,start=1,end=2):
 return f'''## 剧本名\n{title}\n## 来源\n自主创意，原创合成测试项目。\n## 短剧类型\n家庭剧情\n## 集数\n全剧共{total}集，本稿为第{start}—{end}集正式剧本。\n## 剧名寓意\n一件旧物改变两人的选择。\n## 热门元素\n母女共同做决定。\n## 创作理由\n写出共同承担损失的过程。\n## 故事梗概\n两人决定一起承担损失并交付旧物。\n## 主要角色\n甲，母亲，想保住旧物；她学会让女儿决定。\n乙，女儿，想修复旧物；她最终承担修复失败的费用。\n'''


class PolishGuardTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.work=Path(self.tmp.name)
  self.before=self.work/'before.md';self.after=self.work/'after.md'
  self.before.write_text('甲：这三万元是我收的，十九号开席。\n',encoding='utf-8')
  self.after.write_text('甲：这两万元是你收的，二十一号开席。\n',encoding='utf-8')
 def review(self,changes):
  report=polish_guard.inspect_changes(self.before,self.after)
  value={k:report[k] for k in ('beforeHash','afterHash')}
  value.update(mode='local',reviewer='test reviewer',evidence='Read current before and after.',semanticVerified=True,checked=list({'characters','subject_object','negation','conditions','time','amounts','promises','voice','continuity'}),callChain=['test editor'],changes=changes)
  p=self.work/'review.json';p.write_text(json.dumps(value),encoding='utf-8');return p
 def test_amount_responsibility_and_date_drift_is_located_and_rejected(self):
  report=polish_guard.inspect_changes(self.before,self.after)
  self.assertEqual(len(report['changes']),1)
  change=report['changes'][0]
  self.assertIn('amount_or_date',change['flags']);self.assertIn('subject_or_responsibility',change['flags'])
  self.assertEqual(change['afterLines'],[1,1])
  p=self.review([{'id':change['id'],'meaningPreserved':True,'reason':'Review without exact editor approval cannot clear protected changes.'}])
  with self.assertRaisesRegex(ValueError,'restore it or record exact editor approval'):
   polish_guard.record_review(self.before,self.after,p,self.work/'record.json')
 def test_no_edit_passes_without_forced_rewording(self):
  self.after.write_bytes(self.before.read_bytes());p=self.review([])
  v=json.loads(p.read_text());v.update(mode='off',callChain=[]);p.write_text(json.dumps(v))
  record=polish_guard.record_review(self.before,self.after,p,self.work/'record.json')
  self.assertEqual(record['status'],'passed');self.assertEqual(record['changes'],[])
 def test_stale_review_cannot_approve_a_new_text(self):
  p=self.review([]);self.after.write_text('甲：我不答应。\n')
  with self.assertRaisesRegex(ValueError,'hashes do not match'):
   polish_guard.record_review(self.before,self.after,p,self.work/'record.json')
 def test_saved_record_revalidates_preserved_baseline_and_cannot_omit_checks(self):
  self.after.write_bytes(self.before.read_bytes());p=self.review([])
  v=json.loads(p.read_text());v.update(mode='off',callChain=[]);p.write_text(json.dumps(v))
  out=self.work/'record.json';polish_guard.record_review(self.before,self.after,p,out)
  self.assertEqual(polish_guard.validate_record(self.after,out),[])
  record=json.loads(out.read_text());record['review']['checked'].remove('promises');out.write_text(json.dumps(record))
  self.assertTrue(any('nine required checks' in e for e in polish_guard.validate_record(self.after,out)))
 def test_saved_record_cannot_invent_a_difference_free_baseline(self):
  self.after.write_bytes(self.before.read_bytes());p=self.review([])
  v=json.loads(p.read_text());v.update(mode='off',callChain=[]);p.write_text(json.dumps(v))
  out=self.work/'record.json';polish_guard.record_review(self.before,self.after,p,out)
  self.before.write_text('甲：我没收到钱。\n')
  self.assertTrue(any('preserved baseline' in e for e in polish_guard.validate_record(self.after,out)))
 def test_unflagged_edit_still_requires_reading(self):
  self.before.write_text('甲：门开着。\n');self.after.write_text('甲：窗开着。\n');p=self.review([])
  with self.assertRaisesRegex(ValueError,'semantic decision'):
   polish_guard.record_review(self.before,self.after,p,self.work/'record.json')


@unittest.skipUnless(exporter,'python-docx unavailable')
class FormalWordGateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.work=Path(self.tmp.name)
  (self.work/'episodes').mkdir();(self.work/'.drama').mkdir()
  (self.work/'.drama/project-state.json').write_text(json.dumps({'totalEpisodes':2}))
  self.episodes=[]
  for n in (1,2):
   p=self.work/f'episodes/EP{n:03d}.md';p.write_text(f'# 第{n}集\n## {n}-1 日 内 工作间\n人物：甲\n▲甲把盒子放下。\n甲：留下吧。\n',encoding='utf-8')
   self.episodes.append(exporter.parse_episode(p))
  self.front=self.work/'front-matter.md';self.front.write_text(front(),encoding='utf-8')
  self.output=self.work/'deliverables/新故事_第01-02集.docx'
 def test_formal_cli_requires_project_and_nine_modules(self):
  r=subprocess.run([sys.executable,str(SCRIPTS/'export_screenplay_docx.py'),str(self.episodes[0].source),'--output',str(self.output)],text=True,capture_output=True)
  self.assertNotEqual(r.returncode,0);self.assertIn('--project-dir',r.stderr);self.assertFalse(self.output.exists())
 def test_episode_directory_ignores_plans_and_review_notes(self):
  (self.work/'episodes/EP001-plan.md').write_text('# 分集计划，不是演员正文\n')
  (self.work/'episodes/EP002-review.md').write_text('# 审稿笔记，不是演员正文\n')
  files=exporter.collect_inputs([self.work/'episodes'])
  self.assertEqual([p.name for p in files],['EP001.md','EP002.md'])
  r=subprocess.run([sys.executable,str(SCRIPTS/'export_screenplay_docx.py'),str(self.work/'episodes'),'--output',str(self.work/'preview.docx'),'--preview'],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr)
 def test_force_preview_cannot_replace_a_published_delivery(self):
  self.output.parent.mkdir(parents=True)
  exporter.build_docx(self.episodes,self.output,'新故事',False)
  original=exporter.file_hash(self.output)
  self.output.with_suffix('.delivery.json').write_text(json.dumps({'status':'published','outputHash':original}))
  r=subprocess.run([sys.executable,str(SCRIPTS/'export_screenplay_docx.py'),str(self.work/'episodes'),'--output',str(self.output),'--preview','--force'],capture_output=True,text=True)
  self.assertNotEqual(r.returncode,0)
  self.assertEqual(exporter.file_hash(self.output),original)
 def test_force_can_replace_only_a_labeled_preview(self):
  from docx import Document
  self.output.parent.mkdir(parents=True)
  d=Document();d.add_paragraph('existing external document');d.save(self.output)
  original=exporter.file_hash(self.output)
  with self.assertRaisesRegex(FileExistsError,'only a labeled preview'):
   exporter.build_docx(self.episodes,self.output,'新故事',True)
  self.assertEqual(exporter.file_hash(self.output),original)
 def test_front_matter_checks_order_nonempty_title_and_range(self):
  self.assertEqual(exporter.validate_front_matter(self.front,'新故事',[1,2],2),[])
  self.front.write_text(front(start=1,end=1))
  self.assertTrue(any('total/range' in e for e in exporter.validate_front_matter(self.front,'新故事',[1,2],2)))
  self.front.write_text(front().replace('## 来源','## 类型'))
  self.assertTrue(any('nine modules' in e for e in exporter.validate_front_matter(self.front,'新故事',[1,2],2)))
 def test_front_matter_prose_starting_with_module_words_is_not_a_new_module(self):
  body=front().replace('两人决定一起承担损失并交付旧物。','来源不明的旧物让两人决定先核对归属。\n剧名寓意来自她们最终共同承担损失的选择。')
  self.front.write_text(body,encoding='utf-8')
  self.assertEqual(exporter.validate_front_matter(self.front,'新故事',[1,2],2),[])
  modules=dict(exporter.read_front_modules(self.front))
  self.assertIn('来源不明的旧物',modules['故事梗概'])
  self.assertIn('剧名寓意来自',modules['故事梗概'])
  self.assertEqual(modules['来源'],'自主创意，原创合成测试项目。')
 def test_legacy_low_level_call_is_a_visible_preview(self):
  from docx import Document
  exporter.build_docx(self.episodes,self.work/'legacy.docx','新故事',False)
  d=Document(self.work/'legacy.docx')
  self.assertEqual(d.core_properties.category,'PREVIEW');self.assertIn('版式预览','\n'.join(p.text for p in d.paragraphs))
 def test_formal_low_level_api_cannot_bypass_staging(self):
  with self.assertRaisesRegex(ValueError,'must be staged'):
   exporter.build_docx(self.episodes,self.output,'新故事',False,self.front,preview=False,project_dir=self.work)
 def stage(self):
  with patch.object(exporter,'release_errors',return_value=[]):
   return exporter.stage_release(self.work,self.episodes,self.output,'新故事',self.front)
 def test_staging_preserves_formal_directory_and_checks_exact_text(self):
  staged=self.stage();self.assertTrue(staged.exists());self.assertFalse(self.output.exists())
  self.assertTrue(exporter.verify_visible_text(staged,self.episodes,'新故事',self.front))
 def test_staged_content_mutation_blocks_publish(self):
  from docx import Document
  staged=self.stage();d=Document(staged);d.paragraphs[-1].text='甲：已经答应。';d.save(staged)
  with self.assertRaisesRegex(ValueError,'changed after content verification'):
   exporter.publish_release(staged,self.work/'missing-qa.json')
 def test_changed_episode_blocks_old_staged_release(self):
  staged=self.stage();self.episodes[0].source.write_text(self.episodes[0].source.read_text().replace('留下吧','拿走吧'))
  with self.assertRaisesRegex(ValueError,'changed after staging'):
   exporter.publish_release(staged,self.work/'missing-qa.json')
 def test_missing_visual_review_cannot_publish(self):
  staged=self.stage();qa=self.work/'qa.json';qa.write_text(json.dumps({'docxHash':exporter.file_hash(staged),'passed':True,'reviewer':'test','notes':'fixture'}))
  with patch.object(exporter,'release_errors',return_value=[]):
   with self.assertRaisesRegex(ValueError,'manifest from an actual fresh render'):
    exporter.publish_release(staged,qa)
  self.assertFalse(self.output.exists())
 def test_exact_reviewed_source_is_required(self):
  wrong=self.work/'EP001.md';wrong.write_text(self.episodes[0].source.read_text().replace('留下吧','拿走吧'))
  # release_errors must detect file substitution before consulting the review ledger.
  import types
  stub=types.ModuleType('workflow_lib');stub.validate_release=lambda *a,**kw:[]
  with patch.dict(sys.modules,{'workflow_lib':stub}):
   self.assertTrue(any('differs' in e for e in exporter.release_errors(self.work,[exporter.parse_episode(wrong)],self.front)))




HAS_RENDER_DEPS=importlib.util.find_spec('PIL') is not None and (importlib.util.find_spec('fitz') is not None or importlib.util.find_spec('pypdf') is not None)


def write_fixture_renderer(directory):
 """A declared test double, not a real DOCX layout renderer or visual approval."""
 path=directory/'render_docx.py'
 path.write_text("""import argparse
from pathlib import Path
from pypdf import PdfWriter
from PIL import Image,ImageDraw
p=argparse.ArgumentParser();p.add_argument('docx');p.add_argument('--output_dir');p.add_argument('--emit_pdf',action='store_true');a=p.parse_args()
out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
d=PdfWriter()
for n in (1,2):
 d.add_blank_page(width=420,height=594)
 im=Image.new('RGB',(1050,1485),'white');ImageDraw.Draw(im).text((40,50),'Synthetic renderer fixture '+str(n),fill='black');im.save(out/f'page-{n}.png')
with (out/(Path(a.docx).stem+'.pdf')).open('wb') as f:d.write(f)
""",encoding='utf-8')
 return path


@unittest.skipUnless(exporter and HAS_RENDER_DEPS,'render checks require python-docx, PyMuPDF and Pillow')
class RenderManifestTests(unittest.TestCase):
 def setUp(self):
  from docx import Document
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.work=Path(self.tmp.name)
  self.docx=self.work/'source.docx';d=Document();d.add_paragraph('Declared synthetic test input');d.save(self.docx)
  self.renderer=write_fixture_renderer(self.work)
 def render(self):
  return render_screenplay.render(self.docx,self.renderer,self.work/'new-render')
 def test_wrapper_runs_renderer_and_binds_pdf_true_page_count_and_dimensions(self):
  manifest=self.render();value=json.loads(manifest.read_text())
  self.assertEqual(render_screenplay.verify_render_manifest(self.docx,manifest),[])
  self.assertEqual(value['pdf']['pageCount'],2);self.assertEqual(len(value['pages']),2)
  self.assertGreaterEqual(value['pages'][0]['width'],600)
  self.assertEqual(value['command'][0],str(Path(sys.executable).resolve()))
 def test_cannot_certify_a_preexisting_directory(self):
  output=self.work/'old';output.mkdir()
  with self.assertRaisesRegex(FileExistsError,'fresh actual render'):
   render_screenplay.render(self.docx,self.renderer,output)
 def test_old_manifest_rejects_a_new_docx(self):
  from docx import Document
  manifest=self.render();d=Document(self.docx);d.add_paragraph('A changed input');d.save(self.docx)
  self.assertTrue(any('different or changed DOCX' in e for e in render_screenplay.verify_render_manifest(self.docx,manifest)))
 def test_one_pixel_images_are_rejected_even_if_manifest_is_rewritten_to_claim_them(self):
  from PIL import Image
  manifest=self.render();value=json.loads(manifest.read_text());page=manifest.parent/'page-1.png'
  Image.new('RGB',(1,1),'white').save(page)
  value['pages'][0].update(sha256=exporter.file_hash(page),width=1,height=1);manifest.write_text(json.dumps(value))
  self.assertTrue(any('too small' in e for e in render_screenplay.verify_render_manifest(self.docx,manifest)))
 def test_missing_page_is_checked_against_the_pdf_not_qa_claims(self):
  manifest=self.render();(manifest.parent/'page-2.png').unlink()
  value=json.loads(manifest.read_text());value['pages']=value['pages'][:1];manifest.write_text(json.dumps(value))
  self.assertTrue(any("PDF's true page count" in e for e in render_screenplay.verify_render_manifest(self.docx,manifest)))
 def test_manifest_cannot_be_used_for_another_qa_directory(self):
  manifest=self.render();other=self.work/'unrelated';other.mkdir()
  self.assertTrue(any('directory differs' in e for e in render_screenplay.verify_render_manifest(self.docx,manifest,other)))
 def test_corrupt_pdf_returns_a_gate_error_without_accepting_metadata(self):
  manifest=self.render();value=json.loads(manifest.read_text());pdf=manifest.parent/value['pdf']['path']
  pdf.write_bytes(b'broken PDF')
  self.assertTrue(render_screenplay.verify_render_manifest(self.docx,manifest))
 def test_renderer_changes_invalidate_its_record(self):
  manifest=self.render();self.renderer.write_text(self.renderer.read_text()+'\n# changed\n')
  self.assertTrue(any('renderer is missing or has changed' in e for e in render_screenplay.verify_render_manifest(self.docx,manifest)))


@unittest.skipUnless(exporter and HAS_RENDER_DEPS,'render checks require python-docx, PyMuPDF and Pillow')
class PublishRenderBindingTests(unittest.TestCase):
 setUp=FormalWordGateTests.setUp
 stage=FormalWordGateTests.stage
 def fixture_qa(self,staged,manifest):
  value=json.loads(manifest.read_text());directory=manifest.parent
  qa={'docxHash':exporter.file_hash(staged),'passed':True,'reviewer':'declared adversarial fixture, no actual visual approval','notes':'Negative regression injection only','renderManifest':str(manifest),'renderDirectory':str(directory),'pages':[{'path':str(directory/p['path']),'sha256':p['sha256'],'inspected':True} for p in value['pages']]}
  path=self.work/'negative-qa.json';path.write_text(json.dumps(qa));return path
 def test_publish_rejects_one_pixel_forged_qa(self):
  from PIL import Image
  staged=self.stage();renderer=write_fixture_renderer(self.work)
  manifest=render_screenplay.render(staged,renderer,self.work/'render')
  value=json.loads(manifest.read_text());page=manifest.parent/'page-1.png';Image.new('RGB',(1,1),'white').save(page)
  value['pages'][0].update(sha256=exporter.file_hash(page),width=1,height=1);manifest.write_text(json.dumps(value))
  qa=self.fixture_qa(staged,manifest)
  with patch.object(exporter,'release_errors',return_value=[]):
   with self.assertRaisesRegex(ValueError,'too small'):
    exporter.publish_release(staged,qa)
  self.assertFalse(self.output.exists())
 def test_publish_rejects_an_old_render_despite_qa_self_reporting_the_new_docx_hash(self):
  from docx import Document
  staged=self.stage();old=self.work/'old.docx';d=Document();d.add_paragraph('Unrelated old document');d.save(old)
  manifest=render_screenplay.render(old,write_fixture_renderer(self.work),self.work/'old-render')
  qa=self.fixture_qa(staged,manifest)
  with patch.object(exporter,'release_errors',return_value=[]):
   with self.assertRaisesRegex(ValueError,'different or changed DOCX'):
    exporter.publish_release(staged,qa)
  self.assertFalse(self.output.exists())


if __name__=='__main__': unittest.main()
