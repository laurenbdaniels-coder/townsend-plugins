"""Tests for .githooks/pre-push: every push the hook must refuse, and the ones it must let through.

Each case builds a throwaway bare remote plus a clone, pushes a known-clean base,
then feeds the hook the same stdin git would. Terms are made up.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pre-push")
ZERO = "0" * 40
TERM = "zzclientzz"


@unittest.skipIf(sys.platform == "win32" or not shutil.which("git") or not shutil.which("sh"), "posix sh + git")
class PrePushHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.remote = os.path.join(self.tmp, "remote.git")
        self.repo = os.path.join(self.tmp, "repo")
        self.terms = os.path.join(self.tmp, "terms.txt")
        self.write_terms(TERM + "\n")
        subprocess.run(["git", "init", "-q", "--bare", self.remote], check=True)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.git("config", "user.email", "dev@example.com")
        self.git("config", "user.name", "Dev")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")
        self.git("remote", "add", "origin", self.remote)
        self.commit({"README.md": "clean\n"}, "base")
        self.git("push", "-q", "origin", "HEAD:refs/heads/main")
        self.git("fetch", "-q", "origin")
        self.base = self.git("rev-parse", "HEAD")

    def git(self, *args, **kw):
        return subprocess.run(["git", "-C", self.repo] + list(args), check=True,
                              capture_output=True, text=True, **kw).stdout.strip()

    def write_terms(self, text, raw=False):
        with open(self.terms, "wb" if raw else "w") as fh:
            fh.write(text)

    def commit(self, files, msg, remove=(), author=None):
        for rel, text in files.items():
            path = os.path.join(self.repo, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(text)
        for rel in remove:
            os.remove(os.path.join(self.repo, rel))
        self.git("add", "-A")
        extra = ["--author", author] if author else []
        self.git("commit", "-q", "-m", msg, *extra)
        return self.git("rev-parse", "HEAD")

    def push(self, local_sha, remote_sha=None, ref="refs/heads/main", env_extra=None):
        remote_sha = self.base if remote_sha is None else remote_sha
        env = dict(os.environ, TOWNSEND_PRIVATE_TERMS=self.terms)
        env.pop("TOWNSEND_ALLOW_NO_TERMS", None)
        env.update(env_extra or {})
        line = "%s %s %s %s\n" % (ref, local_sha, ref, remote_sha)
        r = subprocess.run(["sh", HOOK, "origin", self.remote], cwd=self.repo, input=line,
                           env=env, capture_output=True, text=True)
        return r.returncode, r.stderr

    def assertRefused(self, result):
        self.assertEqual(result[0], 1, result[1])

    def assertAllowed(self, result):
        self.assertEqual(result[0], 0, result[1])

    # refusals
    def test_term_in_file_content(self):
        self.assertRefused(self.push(self.commit({"a.md": "hi ZZClientZZ\n"}, "add a")))

    def test_term_only_in_an_intermediate_commit(self):
        self.commit({"a.md": TERM + "\n"}, "add")
        self.assertRefused(self.push(self.commit({}, "remove", remove=["a.md"])))

    def test_term_in_file_name(self):
        self.assertRefused(self.push(self.commit({TERM + ".md": "clean\n"}, "add file")))

    def test_term_in_commit_message(self):
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "fix for " + TERM)))

    def test_term_in_author(self):
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "add", author="%s Staff <s@example.com>" % TERM)))

    def test_term_in_annotated_tag_message(self):
        self.git("tag", "-a", "v1", "-m", "release for " + TERM)
        tag = self.git("rev-parse", "v1")
        self.assertRefused(self.push(tag, ZERO, ref="refs/tags/v1"))

    def test_new_branch_is_checked(self):
        sha = self.commit({"a.md": TERM + "\n"}, "add")
        self.assertRefused(self.push(sha, ZERO, ref="refs/heads/feature"))

    def test_remote_tip_unknown_locally_falls_back_to_unseen_commits(self):
        sha = self.commit({"a.md": "clean\n"}, "fix for " + TERM)
        self.assertRefused(self.push(sha, "1234567" + "0" * 33))

    def test_list_with_crlf_bom_and_padding_still_matches(self):
        self.write_terms(b"\xef\xbb\xbf  " + TERM.encode() + b" \r\n# note\r\n", raw=True)
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "fix for " + TERM)))

    def test_missing_list_refuses(self):
        os.remove(self.terms)
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "add")))

    def test_comments_only_list_refuses(self):
        self.write_terms("# nothing here\n\n")
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "add")))

    def test_ci_and_license_are_not_exempt(self):
        self.assertRefused(self.push(self.commit({".github/workflows/ci.yml": TERM + "\n", "LICENSE": "x\n"}, "ci")))

    # allowed
    def test_clean_push_passes(self):
        self.assertAllowed(self.push(self.commit({"a.md": "clean\n"}, "add")))

    def test_term_already_on_the_remote_is_not_rechecked(self):
        dirty = self.commit({"old.md": TERM + "\n"}, "old")
        self.git("push", "-q", "--no-verify", "origin", "HEAD:refs/heads/main")
        self.assertAllowed(self.push(self.commit({}, "clean up", remove=["old.md"]), dirty))

    def test_deleted_ref_passes(self):
        self.assertAllowed(self.push(ZERO, self.base, ref="refs/heads/old"))

    def test_missing_list_with_explicit_opt_out_passes(self):
        os.remove(self.terms)
        self.assertAllowed(self.push(self.commit({"a.md": TERM + "\n"}, "add"), env_extra={"TOWNSEND_ALLOW_NO_TERMS": "1"}))


if __name__ == "__main__":
    unittest.main()
