"""Tests for .githooks/pre-push: every push the hook must refuse, and the ones it must let through.

Each case builds a throwaway bare remote plus a clone, pushes a known-clean base,
then feeds the hook the same arguments and stdin git would. Terms are made up.
Every refusal asserts WHY it refused, so a hit can never pass for an error.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HOOK = os.environ.get("PRE_PUSH_HOOK") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "pre-push")
ZERO = "0" * 40
TERM = "zzclientzz"
HIT = "private term in"


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
        for key, value in (("user.email", "dev@example.com"), ("user.name", "Dev"),
                           ("commit.gpgsign", "false"), ("tag.gpgsign", "false")):
            self.git("config", key, value)
        self.git("remote", "add", "origin", self.remote)
        self.commit({"README.md": "clean\n"}, "base")
        self.git("push", "-q", "origin", "HEAD:refs/heads/main")
        self.git("fetch", "-q", "origin")
        self.base = self.git("rev-parse", "HEAD")

    # helpers
    def git(self, *args, env=None, stdin=None):
        return subprocess.run(["git", "-C", self.repo] + list(args), check=True, capture_output=True,
                              text=True, env=env, input=stdin).stdout.strip()

    def write_terms(self, text, raw=False):
        with open(self.terms, "wb" if raw else "w") as fh:
            fh.write(text)

    def commit(self, files, msg, remove=(), author=None, committer=None):
        for rel, text in files.items():
            path = os.path.join(self.repo, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(text)
        for rel in remove:
            os.remove(os.path.join(self.repo, rel))
        self.git("add", "-A")
        env = dict(os.environ)
        if committer:
            env.update(GIT_COMMITTER_NAME=committer, GIT_COMMITTER_EMAIL="c@example.com")
        extra = ["--author", author] if author else []
        self.git("commit", "-q", "-m", msg, *extra, env=env)
        return self.git("rev-parse", "HEAD")

    def run_hook(self, lines, env_extra=None):
        env = dict(os.environ, TOWNSEND_PRIVATE_TERMS=self.terms)
        env.pop("TOWNSEND_ALLOW_NO_TERMS", None)
        env.update(env_extra or {})
        stdin = "".join("%s %s %s %s\n" % line for line in lines)
        r = subprocess.run(["sh", HOOK, "origin", self.remote], cwd=self.repo, input=stdin,
                           env=env, capture_output=True, text=True)
        return r.returncode, r.stderr

    def push(self, local_sha, remote_sha=None, ref="refs/heads/main", **kw):
        remote_sha = self.base if remote_sha is None else remote_sha
        return self.run_hook([(ref, local_sha, ref, remote_sha)], **kw)

    def assertRefused(self, result, why=HIT):
        self.assertEqual(result[0], 1, result[1])
        self.assertIn(why, result[1])

    def assertAllowed(self, result):
        self.assertEqual(result[0], 0, result[1])

    # content, names, metadata
    def test_term_in_file_content(self):
        self.assertRefused(self.push(self.commit({"a.md": "hi ZZClientZZ\n"}, "add a")))

    def test_term_only_in_an_intermediate_commit(self):
        self.commit({"a.md": TERM + "\n"}, "add")
        self.assertRefused(self.push(self.commit({}, "remove", remove=["a.md"])))

    def test_term_only_in_an_intermediate_commit_on_a_new_branch(self):
        self.commit({"a.md": TERM + "\n"}, "add")
        sha = self.commit({}, "remove", remove=["a.md"])
        self.assertRefused(self.push(sha, ZERO, ref="refs/heads/feature"))

    def test_term_in_file_name(self):
        self.assertRefused(self.push(self.commit({TERM + ".md": "clean\n"}, "add file")))

    def test_term_in_symlink_target(self):
        os.symlink("/x/" + TERM, os.path.join(self.repo, "lnk"))
        self.assertRefused(self.push(self.commit({}, "add link")))

    def test_term_in_commit_message(self):
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "fix for " + TERM)))

    def test_term_in_author(self):
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "add", author="%s Staff <s@example.com>" % TERM)))

    def test_term_in_committer(self):
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "add", committer=TERM + " Bot")))

    def test_term_in_a_mergetag_header(self):
        tree = self.git("rev-parse", "HEAD^{tree}")
        raw = ("tree %s\nparent %s\nauthor Dev <d@example.com> 0 +0000\ncommitter Dev <d@example.com> 0 +0000\n"
               "mergetag object %s\n type commit\n tag v0\n tagger Dev <d@example.com> 0 +0000\n \n release for %s\n"
               "\nmerge\n") % (tree, self.base, self.base, TERM)
        sha = self.git("hash-object", "-t", "commit", "-w", "--stdin", stdin=raw)
        self.assertRefused(self.push(sha))

    # refs and tags
    def test_term_in_branch_name(self):
        sha = self.commit({"a.md": "clean\n"}, "add")
        self.assertRefused(self.push(sha, ZERO, ref="refs/heads/" + TERM))

    def test_term_in_lightweight_tag_name(self):
        self.assertRefused(self.push(self.base, ZERO, ref="refs/tags/" + TERM))

    def test_term_in_annotated_tag_message(self):
        self.git("tag", "-a", "v1", "-m", "release for " + TERM)
        self.assertRefused(self.push(self.git("rev-parse", "v1"), ZERO, ref="refs/tags/v1"))

    def test_term_in_nested_tag_message(self):
        self.git("tag", "-a", "inner", "-m", "for " + TERM)
        self.git("tag", "-a", "outer", "-m", "clean", "inner")
        self.assertRefused(self.push(self.git("rev-parse", "outer"), ZERO, ref="refs/tags/outer"))

    def test_lightweight_tag_on_a_dirty_blob(self):
        blob = self.git("hash-object", "-w", "--stdin", stdin="hello " + TERM + "\n")
        self.assertRefused(self.push(blob, ZERO, ref="refs/tags/b"))

    def test_lightweight_tag_on_a_dirty_tree(self):
        blob = self.git("hash-object", "-w", "--stdin", stdin="hello " + TERM + "\n")
        tree = self.git("mktree", stdin="100644 blob %s\tf\n" % blob)
        self.assertRefused(self.push(tree, ZERO, ref="refs/tags/t"))

    def test_clean_annotated_tag_on_a_dirty_blob(self):
        blob = self.git("hash-object", "-w", "--stdin", stdin="hello " + TERM + "\n")
        self.git("tag", "-a", "bt", "-m", "clean", blob)
        self.assertRefused(self.push(self.git("rev-parse", "bt"), ZERO, ref="refs/tags/bt"))

    # what counts as "already on the remote"
    def test_stale_remote_tracking_ref_is_not_trusted(self):
        sha = self.commit({"a.md": TERM + "\n"}, "add")
        self.git("update-ref", "refs/remotes/origin/leak", sha)
        self.assertRefused(self.push(sha, ZERO, ref="refs/heads/feature"))

    def test_term_already_on_the_remote_is_not_rechecked(self):
        self.commit({"old.md": TERM + "\n"}, "old")
        self.git("push", "-q", "--no-verify", "origin", "HEAD:refs/heads/main")
        dirty = self.git("rev-parse", "HEAD")
        self.assertAllowed(self.push(self.commit({}, "clean up", remove=["old.md"]), dirty))

    def test_clean_push_with_a_remote_tip_we_do_not_have_passes(self):
        sha = self.commit({"a.md": "clean\n"}, "add")
        self.assertAllowed(self.push(sha, "1234567" + "0" * 33))

    def _two_refs(self):
        dirty = self.commit({"a.md": TERM + "\n"}, "dirty")
        self.git("checkout", "-q", "-b", "other", self.base)
        clean = self.commit({"b.md": "clean\n"}, "clean")
        return ("refs/heads/d", dirty, "refs/heads/d", ZERO), ("refs/heads/c", clean, "refs/heads/c", ZERO)

    def test_dirty_ref_after_a_clean_one_is_checked(self):
        dirty, clean = self._two_refs()
        self.assertRefused(self.run_hook([clean, dirty]))

    def test_clean_ref_after_a_dirty_one_does_not_reset_the_refusal(self):
        dirty, clean = self._two_refs()
        self.assertRefused(self.run_hook([dirty, clean]))

    def test_grep_error_refuses(self):
        shim = os.path.join(self.tmp, "shim")
        os.mkdir(shim)
        real = shutil.which("grep")
        with open(os.path.join(shim, "grep"), "w") as fh:  # fail only the content search, not the list parsing
            fh.write('#!/bin/sh\ncase "$1" in -a) exit 2;; esac\nexec %s "$@"\n' % real)
        os.chmod(os.path.join(shim, "grep"), 0o755)
        path = shim + os.pathsep + os.environ.get("PATH", "")
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "add"), env_extra={"PATH": path}), "could not check")

    # files CI must spell, and the list itself
    def test_ci_yml_is_not_exempt(self):
        self.assertRefused(self.push(self.commit({".github/workflows/ci.yml": TERM + "\n"}, "ci")))

    def test_license_is_not_exempt(self):
        self.assertRefused(self.push(self.commit({"LICENSE": "Copyright " + TERM + "\n"}, "license")))

    def test_list_with_crlf_bom_and_padding_still_matches(self):
        self.write_terms(b"\xef\xbb\xbf  " + TERM.encode() + b" \r\n# note\r\n", raw=True)
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "fix for " + TERM)))

    def test_hash_prefixed_term_is_a_term_not_a_comment(self):
        self.write_terms("# a comment\n#hashco\n")
        self.assertRefused(self.push(self.commit({"a.md": "tag #hashco\n"}, "add")))

    def test_non_ascii_term_refuses(self):
        self.write_terms("café zürich\n")
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "add")), "non-ASCII")

    def test_missing_list_refuses(self):
        os.remove(self.terms)
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "add")), "no private-terms list")

    def test_comments_only_list_refuses(self):
        self.write_terms("# nothing here\n\n")
        self.assertRefused(self.push(self.commit({"a.md": "clean\n"}, "add")), "has no terms")

    def test_unknown_local_object_refuses(self):
        self.assertRefused(self.push("1234567" + "0" * 33), "could not list")

    # allowed
    def test_clean_push_passes(self):
        self.assertAllowed(self.push(self.commit({"a.md": "clean\n"}, "add")))

    def test_deleted_ref_passes(self):
        self.assertAllowed(self.push(ZERO, self.base, ref="refs/heads/old"))

    def test_missing_list_with_explicit_opt_out_passes(self):
        os.remove(self.terms)
        self.assertAllowed(self.push(self.commit({"a.md": TERM + "\n"}, "add"), env_extra={"TOWNSEND_ALLOW_NO_TERMS": "1"}))


if __name__ == "__main__":
    unittest.main()
