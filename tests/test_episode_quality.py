import json
import sys
import unittest
import tempfile
import subprocess
import shutil
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import render_episode as render
import make_intro as intro
import write_episode as writer
from episode_quality import validate_lines, validate_duration


class QualityTests(unittest.TestCase):
    def test_editorial_policy_replaces_old_audience(self):
        self.assertIn('broad audience', writer.SYSTEM)
        self.assertNotIn('المستمعة وحدة', writer.SYSTEM)
        from datetime import date
        prompt = writer.build_prompt(7, date(2026, 8, 31), 'Wise')
        self.assertNotIn('المصادر الجادة كلها إنجليزية', prompt)
        self.assertNotIn('أنصاف جمل', prompt)
        self.assertIn('Fintech Pulse', prompt)

    def test_weekend_news_window(self):
        from datetime import date
        self.assertEqual(writer.previous_publishing_day(date(2026, 8, 30)), date(2026, 8, 27))
        self.assertEqual(writer.previous_publishing_day(date(2026, 8, 31)), date(2026, 8, 30))

    def test_brand_is_english_and_faisal(self):
        self.assertEqual(intro.IDENT_TEXT, 'Fintech Pulse.')
        self.assertEqual(intro.IDENT_VOICE, render.VOICES['فيصل'])

    def test_formal_numbers_accepted(self):
        validate_lines([{'speaker': 'سلطان', 'text': 'خمسة عشر مليون ريال.'}])

    def test_bad_speech_rejected_before_spend(self):
        for text in ['خمستعشر مليون.', 'فنتك بلس.', 'القيمة 15 ريال.', 'عايز أفهم.']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_lines([{'speaker': 'سلطان', 'text': text}])

    def test_unknown_speaker_is_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            render.chunk_lines([{'speaker': 'Dana', 'text': 'hello'}], render.VOICES)

    def test_blocks_are_bounded_and_keep_order(self):
        lines = [{'speaker': 'سلطان' if i % 2 else 'فيصل',
                  'text': f'هذا مثال للتجربة فقط. ' * 12} for i in range(20)]
        blocks = render.chunk_lines(lines, render.VOICES)
        self.assertEqual(sum(map(len, blocks)), len(lines))
        self.assertTrue(all(sum(len(i['text']) for i in b) <= 2000 for b in blocks))

    def test_long_turn_is_rejected(self):
        with self.assertRaises(ValueError):
            render.chunk_lines([{'speaker': 'سلطان', 'text': 'أ' * 2100}], render.VOICES)

    def test_payload_is_stable_arabic_v3(self):
        p = render.dialogue_payload([{'text': 'طيب، وش الفرق؟', 'voice_id': 'test'}], 'eleven_v3')
        self.assertEqual(p['language_code'], 'ar')
        self.assertEqual(p['settings']['stability'], 0.5)
        with self.assertRaises(ValueError):
            render.dialogue_payload([], 'eleven_turbo_v2_5')

    def test_cache_changes_with_settings_or_script(self):
        self.assertNotEqual(render.request_digest({'text': 'أ'}), render.request_digest({'text': 'ب'}))
        self.assertEqual(render.request_digest({'b': 2, 'a': 1}), render.request_digest({'a': 1, 'b': 2}))

    def test_each_block_reanchors_each_voice_once(self):
        lines = [{'speaker': 'سلطان' if i % 2 else 'فيصل',
                  'text': 'هذا مثال للتجربة فقط. ' * 12} for i in range(20)]
        for block in render.chunk_lines(lines, render.VOICES):
            seen = set()
            for line in block:
                self.assertEqual(line['text'].startswith(render.ACCENT_CUE), line['voice_id'] not in seen)
                seen.add(line['voice_id'])

    def test_preview_script_is_valid(self):
        path = Path(__file__).resolve().parents[1] / 'docs/drafts/quality-preview.json'
        draft = json.loads(path.read_text())
        validate_lines(draft['lines'])
        with patch.object(render, 'DIALOGUE_CHARS', 900):
            self.assertGreater(len(render.chunk_lines(draft['lines'], render.VOICES)), 1)

    def test_ident_reuses_unchanged_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'intro-music.mp3').touch()
            def fake_build(key):
                (root / 'intro.mp3').touch()
            with patch.object(intro, 'ASSETS', root), patch.object(intro, 'build_ident', side_effect=fake_build) as build:
                intro.ensure_ident('not-a-real-key')
                intro.ensure_ident('not-a-real-key')
                self.assertEqual(build.call_count, 1)
                intro.ensure_ident('not-a-real-key', force=True)
                self.assertEqual(build.call_count, 2)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
    def test_music_mix_preserves_full_body_duration(self):
        # Synthetic test tones only: no API call, credit spend, or existing media edits.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, duration in [('intro', 3), ('body', 4), ('outro', 2)]:
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi',
                                '-i', f'sine=frequency=440:duration={duration}',
                                str(root / f'{name}.mp3')], check=True)
            with patch.object(render, 'ASSETS', root):
                render.dress(root / 'body.mp3', root / 'out.mp3')
            self.assertGreaterEqual(render.audio_seconds(root / 'out.mp3'), 9)
            self.assertLess(render.audio_seconds(root / 'out.mp3'), 10)

    def test_ten_minute_gate(self):
        validate_duration(600)
        for duration in (0, 480, 850, float('nan')):
            with self.assertRaises(ValueError):
                validate_duration(duration)


if __name__ == '__main__':
    unittest.main()
