import importlib.util
from pathlib import Path
import unittest
from dkord_desktop.experience import contract, palette, text, branding


class PhoneContractTest(unittest.TestCase):
    def test_packaged_contract_is_generated_from_actual_phone_sources_not_a_redesign(self):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location('exporter', root/'desktop/scripts/export_phone_contract.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertEqual(module.build(), contract())
        self.assertEqual(['HOME','SEARCH','LISTEN','LIBRARY','DOWNLOADS'], [item['id'] for item in contract()['navigation']])
        self.assertEqual(14, len(contract()['curated']))

    def test_phone_palette_english_hindi_and_android_positional_formats_are_shared(self):
        self.assertEqual('#0B0B0B', palette()['background']); self.assertEqual('#FF2D2D', palette()['primary'])
        self.assertEqual('#D50000', palette('light')['primary']); self.assertEqual('#000000', palette('amoled')['surface'])
        self.assertEqual('होम', text('tab_home', 'hi'))
        self.assertIn('ABCDEFGHJK', text('room_invitation', 'hi', 'ABCDEFGHJK'))
        self.assertEqual(text('tab_home'), text('tab_home', 'unknown-language'))

    def test_display_only_choliwood_branding_never_rewrites_song_or_query(self):
        self.assertEqual('Choliwood hits', branding('Bhojpuri hits'))
        self.assertEqual('Choliwood', branding('भोजपुरी'))
        self.assertEqual('popular bhojpuri songs', contract()['curated'][1]['query'])

    def test_professional_about_and_diagnostics_have_no_visible_repository_or_links(self):
        for language in ('en', 'hi'):
            about = text('about_text', language)
            self.assertIn('© 2026 dKORD', about); self.assertLess(len(about), 200)
            for key in ('about_text', 'report_broken', 'report_broken_hint', 'report_copied'):
                value = text(key, language).lower()
                self.assertNotIn('github', value); self.assertNotIn('http', value)
