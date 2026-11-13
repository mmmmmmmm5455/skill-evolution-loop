"""Contract for a repo whose default branch is master, not main."""
import re
from pathlib import Path
import unittest

WF = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"


class WorkflowBranchContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WF.read_text(encoding="utf-8-sig")

    def test_push_master_and_feature_branches(self):
        self.assertRegex(
            self.source,
            r"(?m)^  push:\n    branches: \[master, 'feature/\*\*'\]"
        )

    def test_pull_requests_to_master(self):
        self.assertRegex(
            self.source,
            r"(?m)^  pull_request:\n    branches: \[master\]"
        )

    def test_permissions_remain_read_only(self):
        self.assertRegex(self.source, r"(?m)^permissions:\n  contents: read")

    def test_real_branch_contract_is_run_in_ci(self):
        self.assertIn("test_master_workflow_trigger.py", self.source)
        self.assertIn("unittest discover", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
