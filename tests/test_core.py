"""Tests for GitMoji AI"""

import pytest
from gitmoji_ai.ai_engine import (
    analyze_diff, _fallback_commit_messages, GITMOJI_MAP,
    CONVENTIONAL_TYPES, LANGUAGE_PROMPTS, STYLE_PROMPTS,
    AVAILABLE_STYLES, PRO_ONLY_STYLES, get_system_prompt,
)
from gitmoji_ai.changelog import parse_commit_subject, group_commits_by_type
from gitmoji_ai.team import (
    TeamConfig, validate_commit_against_team,
    TEAM_CONFIG_FILENAME, DEFAULT_TEAM_CONFIG,
)


class TestDiffAnalysis:
    """Test git diff analysis"""

    def test_empty_diff(self):
        result = analyze_diff("")
        assert result.files_changed == 0
        assert result.lines_added == 0
        assert result.lines_removed == 0

    def test_single_file_diff(self):
        diff = """diff --git a/hello.py b/hello.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/hello.py
@@ -0,0 +1,3 @@
+def hello():
+    print("Hello, World!")
+    return True
"""
        result = analyze_diff(diff)
        assert result.files_changed == 1
        assert result.lines_added == 3
        assert result.is_new_feature is True

    def test_bug_fix_diff(self):
        diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -10,5 +10,5 @@
-def calculate(x):
+def calculate(x, y):
-    return x * 2
+    return x + y  # fix: correct calculation
"""
        result = analyze_diff(diff)
        assert result.is_bug_fix is True

    def test_docs_diff(self):
        diff = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,3 +1,5 @@
 # My Project
+
+Documentation update here.
"""
        result = analyze_diff(diff)
        assert result.is_docs is True

    def test_test_diff(self):
        diff = """diff --git a/test_app.py b/test_app.py
new file mode 100644
--- /dev/null
+++ b/test_app.py
@@ -0,0 +1,5 @@
+def test_hello():
+    assert True
"""
        result = analyze_diff(diff)
        assert result.is_test is True


class TestCommitParsing:
    """Test conventional commit parsing"""

    def test_parse_feat(self):
        entry = parse_commit_subject("feat(auth): add login functionality")
        assert entry.type == "feat"
        assert entry.scope == "auth"
        assert "login" in entry.description

    def test_parse_fix(self):
        entry = parse_commit_subject("fix: resolve crash on startup")
        assert entry.type == "fix"
        assert entry.scope == ""

    def test_parse_no_type(self):
        entry = parse_commit_subject("update something")
        assert entry.type == "chore"

    def test_parse_complex_scope(self):
        entry = parse_commit_subject("feat(api/v2): add new endpoint")
        assert entry.type == "feat"


class TestFallbackCommits:
    """Test fallback commit generation (without AI)"""

    def test_feature_commit(self):
        diff = """diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,3 @@
+# New feature
+def new_feature():
+    pass
"""
        suggestions = _fallback_commit_messages(diff, "conventional")
        assert len(suggestions) >= 1
        assert suggestions[0].type == "feat"

    def test_emoji_style(self):
        suggestions = _fallback_commit_messages("new file mode\n+feature", "emoji")
        assert any(e in suggestions[0].message for e in GITMOJI_MAP.values())

    def test_plain_style(self):
        suggestions = _fallback_commit_messages("new file mode\n+feature", "plain")
        assert suggestions[0].message[0].isupper()

    def test_semantic_release_style(self):
        suggestions = _fallback_commit_messages("new file mode\n+feature", "semantic-release")
        assert len(suggestions) >= 1

    def test_gitmoji_dict_style(self):
        suggestions = _fallback_commit_messages("new file mode\n+feature", "gitmoji-dict")
        assert len(suggestions) >= 1

    def test_empty_diff_fallback(self):
        suggestions = _fallback_commit_messages("", "conventional")
        assert len(suggestions) >= 1


class TestChangelogGrouping:
    """Test changelog grouping by type"""

    def test_group_mixed_commits(self):
        commits = [
            {"subject": "feat: add feature", "hash": "abc1234", "author": "Dev", "date": "2024-01-01", "body": ""},
            {"subject": "fix: fix bug", "hash": "def5678", "author": "Dev", "date": "2024-01-01", "body": ""},
            {"subject": "docs: update readme", "hash": "ghi9012", "author": "Dev", "date": "2024-01-01", "body": ""},
        ]
        grouped = group_commits_by_type(commits)
        assert "Features" in grouped
        assert "Bug Fixes" in grouped
        assert "Documentation" in grouped

    def test_empty_commits(self):
        grouped = group_commits_by_type([])
        assert len(grouped) == 0


class TestGitmojiMap:
    """Test GitMoji emoji mapping"""

    def test_all_conventional_types_have_emoji(self):
        for t in CONVENTIONAL_TYPES:
            assert t in GITMOJI_MAP, f"Missing emoji for type: {t}"

    def test_emoji_are_unicode(self):
        for key, emoji in GITMOJI_MAP.items():
            assert len(emoji) >= 1, f"Empty emoji for {key}"


class TestLanguagePrompts:
    """Test all 7 language prompts exist"""

    def test_all_languages_have_prompts(self):
        for lang in ["en", "ru", "es", "de", "fr", "ja", "zh"]:
            assert lang in LANGUAGE_PROMPTS, f"Missing prompt for language: {lang}"

    def test_prompts_are_nonempty(self):
        for lang, prompt in LANGUAGE_PROMPTS.items():
            assert len(prompt) > 100, f"Prompt too short for language: {lang}"

    def test_get_system_prompt_default(self):
        prompt = get_system_prompt("en", "conventional")
        assert "Conventional Commits" in prompt

    def test_get_system_prompt_unknown_language(self):
        prompt = get_system_prompt("xx", "conventional")
        # Should fall back to English
        assert "Conventional Commits" in prompt

    def test_get_system_prompt_with_style(self):
        prompt = get_system_prompt("en", "emoji")
        assert "Emoji style" in prompt

    def test_get_system_prompt_semantic_release(self):
        prompt = get_system_prompt("en", "semantic-release")
        assert "Semantic Release" in prompt

    def test_get_system_prompt_gitmoji_dict(self):
        prompt = get_system_prompt("en", "gitmoji-dict")
        assert "GitMoji Dictionary" in prompt


class TestCommitStyles:
    """Test commit style profiles"""

    def test_all_styles_have_prompts(self):
        for style in AVAILABLE_STYLES:
            assert style in STYLE_PROMPTS, f"Missing style prompt for: {style}"

    def test_pro_only_styles(self):
        assert "semantic-release" in PRO_ONLY_STYLES
        assert "gitmoji-dict" in PRO_ONLY_STYLES
        assert "conventional" not in PRO_ONLY_STYLES
        assert "emoji" not in PRO_ONLY_STYLES
        assert "plain" not in PRO_ONLY_STYLES

    def test_available_styles_list(self):
        assert "conventional" in AVAILABLE_STYLES
        assert "emoji" in AVAILABLE_STYLES
        assert "plain" in AVAILABLE_STYLES
        assert "semantic-release" in AVAILABLE_STYLES
        assert "gitmoji-dict" in AVAILABLE_STYLES


class TestTeamConfig:
    """Test team configuration"""

    def test_default_team_config(self):
        config = TeamConfig()
        assert config.commit_style == "conventional"
        assert config.language == "en"
        assert config.max_subject_length == 72
        assert config.require_scope is False
        assert config.required_types == []
        assert config.required_scopes == []
        assert config.disallowed_types == []

    def test_validate_commit_no_rules(self):
        config = TeamConfig()
        violations = validate_commit_against_team("feat(auth): add login", config)
        assert len(violations) == 0

    def test_validate_commit_required_types(self):
        config = TeamConfig(required_types=["feat", "fix"])
        violations = validate_commit_against_team("chore: update config", config)
        assert len(violations) == 1
        assert "not allowed" in violations[0]

    def test_validate_commit_required_types_valid(self):
        config = TeamConfig(required_types=["feat", "fix"])
        violations = validate_commit_against_team("feat: add login", config)
        assert len(violations) == 0

    def test_validate_commit_disallowed_types(self):
        config = TeamConfig(disallowed_types=["poo"])
        violations = validate_commit_against_team("poo: bad code", config)
        assert len(violations) == 1
        assert "disallowed" in violations[0]

    def test_validate_commit_require_scope(self):
        config = TeamConfig(require_scope=True)
        violations = validate_commit_against_team("feat: add login", config)
        assert len(violations) == 1
        assert "Scope is required" in violations[0]

    def test_validate_commit_require_scope_with_scope(self):
        config = TeamConfig(require_scope=True)
        violations = validate_commit_against_team("feat(auth): add login", config)
        assert len(violations) == 0

    def test_validate_commit_required_scopes(self):
        config = TeamConfig(required_scopes=["api", "ui"])
        violations = validate_commit_against_team("feat(auth): add login", config)
        assert len(violations) == 1
        assert "not allowed" in violations[0]

    def test_validate_commit_required_scopes_valid(self):
        config = TeamConfig(required_scopes=["api", "ui"])
        violations = validate_commit_against_team("feat(api): add endpoint", config)
        assert len(violations) == 0

    def test_validate_commit_subject_too_long(self):
        config = TeamConfig(max_subject_length=20)
        violations = validate_commit_against_team("feat(auth): this is a very long description that exceeds the limit", config)
        assert len(violations) == 1
        assert "too long" in violations[0]

    def test_validate_commit_custom_type_alias(self):
        config = TeamConfig(required_types=["feat"], custom_types={"feature": "feat"})
        violations = validate_commit_against_team("feature: add login", config)
        assert len(violations) == 0

    def test_team_config_filename(self):
        assert TEAM_CONFIG_FILENAME == ".gitmoji-ai-team.yml"

    def test_default_team_config_has_yaml(self):
        assert "required_types:" in DEFAULT_TEAM_CONFIG
        assert "required_scopes:" in DEFAULT_TEAM_CONFIG
        assert "commit_style:" in DEFAULT_TEAM_CONFIG


class TestConfigSecurity:
    """Test that is_pro property was removed from Settings"""

    def test_settings_has_no_is_pro_property(self):
        from gitmoji_ai.config import Settings
        s = Settings()
        assert not hasattr(s, 'is_pro'), "Settings should NOT have is_pro property — use is_pro() from usage.py"

    def test_is_pro_is_function(self):
        from gitmoji_ai.usage import is_pro
        assert callable(is_pro), "is_pro should be a function, not a property"
