"""Dry-run is a source-only preview: never write, install, or call out.

These tests use synthetic fixtures and temporarily redirected module paths.
No real skill archive, bus, or decision log is changed.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import json
import os
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("skill_evolution_safe_test",ROOT/"evolution_loop.py")
ev=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ev)

class DryRunContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.skills=self.dir/"missing_skills"
        self.bus=self.dir/"missing_bus"
        self.log=self.dir/"previous_decisions.jsonl"
        self.log.write_text('{"prior":"keep"}\n',encoding="utf-8")
        self.original=self.log.read_bytes()
        for name,path in [
            ("SKILLS_DIR",self.skills),
            ("ARCHIVE_DIR",self.dir/"missing_archive"),
            ("BUS_DIR",self.bus),
            ("DECISION_LOG",self.log),
        ]:
            patcher=patch.object(ev,name,path)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_missing_skill_is_readonly_and_reports_unknown_score(self):
        result=ev.run_loop("caveman",60,True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["decision"]["action"],"DRY_RUN_ONLY")
        self.assertEqual(result["steps"]["1_test"]["status"],"READ_ONLY_PROXY")
        self.assertIsNone(result["steps"]["1_test"]["score_proxy"])
        self.assertFalse(self.bus.exists())
        self.assertEqual(self.log.read_bytes(),self.original)

    def test_existing_skill_is_observed_not_misreported_as_tested(self):
        home=self.skills/"caveman"
        home.mkdir(parents=True)
        doc=home/"SKILL.md"
        doc.write_text("# demo\n## Intro\n",encoding="utf-8")
        before=doc.read_bytes()
        result=ev.run_loop("caveman",60,True)
        self.assertTrue(result["steps"]["1_test"]["exists"])
        self.assertEqual(result["decision"]["action"],"DRY_RUN_ONLY")
        self.assertIn("not a real score",result["decision"]["reason"].lower())
        self.assertEqual(before,doc.read_bytes())
        self.assertFalse(self.bus.exists())
        self.assertEqual(self.log.read_bytes(),self.original)

    def test_never_installs_calls_network_writes_bus_or_log(self):
        with patch.object(ev,"step_install",side_effect=AssertionError("install")) as install, \
             patch.object(ev,"step_test",side_effect=AssertionError("writes bus")) as test, \
             patch.object(ev,"step_discover",side_effect=AssertionError("searches")) as discover, \
             patch.object(ev,"_search_openspace",side_effect=AssertionError("network")) as network, \
             patch.object(ev,"log_decision",side_effect=AssertionError("writes log")) as log:
            self.assertEqual(ev.run_loop("caveman",60,True)["decision"]["action"],"DRY_RUN_ONLY")
            for x in (install,test,discover,network,log):x.assert_not_called()

    def test_actual_cli_in_clean_home_never_writes_bus_or_log(self):
        env=dict(os.environ)
        env["HOME"]=str(self.dir)
        env["USERPROFILE"]=str(self.dir)
        original_log=ROOT/"decisions.jsonl"
        previous=original_log.read_bytes()
        proc=subprocess.run(
            [sys.executable,"-B","-X","utf8",str(ROOT/"evolution_loop.py"),
             "--skill","caveman","--dry-run"],
            cwd=ROOT,env=env,capture_output=True,text=True,
            encoding="utf-8",errors="replace",timeout=20,
        )
        self.assertEqual(proc.returncode,0,proc.stderr)
        result=json.loads(proc.stdout)
        self.assertEqual(result["decision"]["action"],"DRY_RUN_ONLY")
        self.assertTrue(result["dry_run"])
        self.assertFalse((self.dir/".claude").exists())
        self.assertEqual(original_log.read_bytes(),previous)

    def test_reject_path_traversal_in_skill_name(self):
        with self.assertRaises(ValueError):
            ev.run_loop("../other",60,True)
        self.assertFalse(self.bus.exists())
        self.assertEqual(self.log.read_bytes(),self.original)

if __name__=="__main__":
    unittest.main()
