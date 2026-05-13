"""Unit tests for src/rfc.py."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
import rfc as m


class TestSlugify(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(m.slugify('Hello World'), 'hello-world')

    def test_strips_special_chars(self):
        self.assertEqual(m.slugify('Hello, World!'), 'hello-world')

    def test_collapses_spaces(self):
        self.assertEqual(m.slugify('Hello  World'), 'hello-world')

    def test_replaces_underscores(self):
        self.assertEqual(m.slugify('hello_world'), 'hello-world')

    def test_strips_leading_trailing_hyphens(self):
        self.assertEqual(m.slugify('  -hello-  '), 'hello')

    def test_preserves_numbers(self):
        self.assertEqual(m.slugify('RFC 2119'), 'rfc-2119')


class TestNextRfcNumber(unittest.TestCase):
    def test_empty_directory_returns_one(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(m.next_rfc_number(d), 1)

    def test_increments_past_existing(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, '0001-foo.md').touch()
            self.assertEqual(m.next_rfc_number(d), 2)

    def test_uses_highest_number(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ('0001-a.md', '0003-b.md', '0002-c.md'):
                Path(d, name).touch()
            self.assertEqual(m.next_rfc_number(d), 4)

    def test_ignores_non_matching_files(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ('README.md', 'notes.txt', 'foo-bar.md'):
                Path(d, name).touch()
            self.assertEqual(m.next_rfc_number(d), 1)


class TestGitUser(unittest.TestCase):
    def test_returns_git_name(self):
        result = MagicMock()
        result.stdout = 'Jane Doe\n'
        with patch('subprocess.run', return_value=result):
            self.assertEqual(m.git_user(), 'Jane Doe')

    def test_strips_whitespace_from_git_output(self):
        result = MagicMock()
        result.stdout = '  Jane Doe  \n'
        with patch('subprocess.run', return_value=result):
            self.assertEqual(m.git_user(), 'Jane Doe')

    def test_falls_back_to_user_env_when_git_missing(self):
        with patch('subprocess.run', side_effect=FileNotFoundError):
            with patch.dict(os.environ, {'USER': 'jdoe'}):
                self.assertEqual(m.git_user(), 'jdoe')

    def test_falls_back_to_unknown_when_no_user_env(self):
        with patch('subprocess.run', side_effect=FileNotFoundError):
            env = {k: v for k, v in os.environ.items() if k != 'USER'}
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(m.git_user(), 'Unknown')

    def test_falls_back_when_git_returns_empty_name(self):
        result = MagicMock()
        result.stdout = '   \n'
        with patch('subprocess.run', return_value=result):
            with patch.dict(os.environ, {'USER': 'fallback'}):
                self.assertEqual(m.git_user(), 'fallback')


class TestWriteIfAbsent(unittest.TestCase):
    def test_creates_file_and_returns_true(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'new.txt')
            self.assertTrue(m.write_if_absent(str(path), 'hello'))
            self.assertEqual(path.read_text(), 'hello')

    def test_skips_existing_file_and_returns_false(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'existing.txt')
            path.write_text('original')
            self.assertFalse(m.write_if_absent(str(path), 'new content'))
            self.assertEqual(path.read_text(), 'original')

    def test_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'a', 'b', 'c.txt')
            m.write_if_absent(str(path), 'hello')
            self.assertTrue(path.exists())


class TestAppendIfMarkerAbsent(unittest.TestCase):
    MARKER = '<!-- test-marker -->'

    def test_creates_file_when_absent_and_returns_true(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'out.md')
            self.assertTrue(m.append_if_marker_absent(str(path), self.MARKER, '# Content\n'))
            self.assertIn('# Content', path.read_text())

    def test_appends_when_marker_absent(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'out.md')
            path.write_text('# Existing\n')
            m.append_if_marker_absent(str(path), self.MARKER, '\n# New\n')
            content = path.read_text()
            self.assertIn('# Existing', content)
            self.assertIn('# New', content)

    def test_skips_when_marker_present_and_returns_false(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'out.md')
            path.write_text(f'existing\n{self.MARKER}\n')
            self.assertFalse(m.append_if_marker_absent(str(path), self.MARKER, 'extra'))
            self.assertNotIn('extra', path.read_text())

    def test_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'sub', 'out.md')
            m.append_if_marker_absent(str(path), self.MARKER, 'content')
            self.assertTrue(path.exists())


class TestScaffoldAgentFiles(unittest.TestCase):
    def _claude_path(self, d):
        return os.path.join(d, '.claude', 'skills', 'rfc', 'SKILL.md')

    def _copilot_path(self, d):
        return os.path.join(d, '.github', 'copilot-instructions.md')

    def test_creates_both_files(self):
        with tempfile.TemporaryDirectory() as d:
            results = dict(m.scaffold_agent_files(d))
            self.assertEqual(results[self._claude_path(d)], 'created')
            self.assertEqual(results[self._copilot_path(d)], 'created')

    def test_claude_skill_contains_required_content(self):
        with tempfile.TemporaryDirectory() as d:
            m.scaffold_agent_files(d)
            content = Path(self._claude_path(d)).read_text()
            for keyword in ('description:', 'RFC 2119', 'MUST', 'SHOULD', 'Abstract', 'Security'):
                self.assertIn(keyword, content, f'SKILL.md missing: {keyword!r}')

    def test_copilot_instructions_contain_required_content(self):
        with tempfile.TemporaryDirectory() as d:
            m.scaffold_agent_files(d)
            content = Path(self._copilot_path(d)).read_text()
            for keyword in ('RFC 2119', m.COPILOT_MARKER, 'MUST', 'SHOULD'):
                self.assertIn(keyword, content, f'copilot-instructions.md missing: {keyword!r}')

    def test_skips_existing_claude_skill(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(self._claude_path(d))
            path.parent.mkdir(parents=True)
            path.write_text('custom')
            results = dict(m.scaffold_agent_files(d))
            self.assertEqual(results[str(path)], 'skipped')
            self.assertEqual(path.read_text(), 'custom')

    def test_skips_copilot_when_marker_present(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(self._copilot_path(d))
            path.parent.mkdir(parents=True)
            path.write_text(f'existing\n{m.COPILOT_MARKER}\n')
            results = dict(m.scaffold_agent_files(d))
            self.assertEqual(results[str(path)], 'skipped')

    def test_appends_to_existing_copilot_without_marker(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(self._copilot_path(d))
            path.parent.mkdir(parents=True)
            path.write_text('# Existing\n')
            results = dict(m.scaffold_agent_files(d))
            self.assertEqual(results[str(path)], 'created')
            content = path.read_text()
            self.assertIn('# Existing', content)
            self.assertIn(m.COPILOT_MARKER, content)


class TestCmdBootstrap(unittest.TestCase):
    def _run(self, *args):
        parser = m.build_parser()
        parsed = parser.parse_args(['bootstrap'] + list(args))
        parsed.func(parsed)

    @patch('rfc.git_user', return_value='Test Author')
    @patch('rfc.datetime')
    def test_rfc_file_content(self, mock_dt, _):
        mock_dt.date.today.return_value.isoformat.return_value = '2026-01-01'
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'out.md')
            self._run('My RFC', '-o', out)
            content = Path(out).read_text()
            self.assertIn('Title: My RFC', content)
            self.assertIn('Author: Test Author', content)
            self.assertIn('Date: 2026-01-01', content)
            self.assertIn('RFC: 0001', content)
            for section in ('Abstract', 'Motivation', 'Proposal',
                            'Drawbacks', 'Alternatives', 'Security Considerations'):
                self.assertIn(f'## {section}', content)
            self.assertIn('RFC 2119', content)

    @patch('rfc.git_user', return_value='Author')
    def test_auto_names_with_slug(self, _):
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            self._run('My Great RFC')
            self.assertTrue(Path('0001-my-great-rfc.md').exists())

    @patch('rfc.git_user', return_value='Author')
    def test_auto_numbering_increments(self, _):
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            self._run('First')
            self._run('Second')
            self.assertTrue(Path('0001-first.md').exists())
            self.assertTrue(Path('0002-second.md').exists())

    @patch('rfc.git_user', return_value='Author')
    def test_refuses_to_overwrite_without_force(self, _):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'out.md')
            self._run('RFC', '-o', out)
            with self.assertRaises(SystemExit):
                self._run('RFC', '-o', out)

    @patch('rfc.git_user', return_value='Author')
    def test_force_overwrites(self, _):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'out.md')
            self._run('RFC v1', '-o', out)
            self._run('RFC v2', '-o', out, '--force')
            self.assertIn('RFC v2', Path(out).read_text())

    @patch('rfc.git_user', return_value='Author')
    def test_creates_agent_files(self, _):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'out.md')
            self._run('RFC', '-o', out)
            self.assertTrue(Path(d, '.claude', 'skills', 'rfc', 'SKILL.md').exists())
            self.assertTrue(Path(d, '.github', 'copilot-instructions.md').exists())

    @patch('rfc.git_user', return_value='Author')
    def test_agent_files_not_duplicated_on_repeat_bootstrap(self, _):
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            self._run('First RFC')
            skill = Path(d, '.claude', 'skills', 'rfc', 'SKILL.md')
            skill.write_text('custom skill')
            self._run('Second RFC')
            self.assertEqual(skill.read_text(), 'custom skill')


if __name__ == '__main__':
    unittest.main(verbosity=2)
