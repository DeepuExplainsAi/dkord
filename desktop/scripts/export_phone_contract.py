"""Export the PHONE product contract; no second hand-maintained desktop theme/catalogue.

Run from any directory. CI --check rejects drift when Android resources change.
Only presentation/navigation metadata is exported, never Android code or user data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'desktop/assets/phone-contract.json'
SOURCES = (
    'app/src/main/res/values/strings.xml',
    'app/src/main/res/values-hi/strings.xml',
    'app/src/main/java/app/dkord/ui/theme/Theme.kt',
    'app/src/main/java/app/dkord/ui/screens/Home.kt',
    'app/src/main/java/app/dkord/ui/App.kt',
)


def strings(path):
    values = {}
    for node in ET.parse(path).getroot():
        if node.tag == 'string':
            value = ''.join(node.itertext())
            for old, new in ((r'\n', '\n'), (r"\'", "'"), (r'\"', '"')):
                value = value.replace(old, new)
            values[node.attrib['name']] = value
    return values


def build():
    theme = (ROOT / SOURCES[2]).read_text(encoding='utf-8')
    palettes = {}
    for name in ('Dark', 'Light'):
        block = re.search(r'private val Yt' + name + r' = \w+ColorScheme\((.*?)\n\)', theme, re.S).group(1)
        palette = {}
        for key, value in re.findall(r'(\w+)\s*=\s*(Color\(0xFF[0-9A-Fa-f]{6}\)|Color\.White|Color\.Black|Red)', block):
            palette[key] = {'Red': '#FF2D2D', 'Color.White': '#FFFFFF', 'Color.Black': '#000000'}.get(value, '#' + value[10:16])
        palettes[name.lower()] = palette
    # These overrides are explicit in DkordTheme, not a desktop reinterpretation.
    amoled = re.search(r'if \(mode == ThemeMode.AMOLED\).*?scheme.copy\((.*?)\n\s*\)', theme, re.S).group(1)
    palettes['amoled'] = dict(palettes['dark'])
    for key, value in re.findall(r'(\w+)\s*=\s*(Color\(0xFF[0-9A-Fa-f]{6}\)|Color\.Black)', amoled):
        palettes['amoled'][key] = '#000000' if value == 'Color.Black' else '#' + value[10:16]
    home = (ROOT / SOURCES[3]).read_text(encoding='utf-8')
    curated = re.search(r'private val CURATED = listOf\((.*?)\n\)', home, re.S).group(1)
    navigation = re.findall(r'TabSpec\(Tab\.(\w+), Icons\.Default\.\w+, R\.string\.(\w+)\)', (ROOT / SOURCES[4]).read_text(encoding='utf-8'))
    return {
        'schema': 1,
        'sources': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES},
        'navigation': [{'id': name, 'label': key} for name, key in navigation],
        'palettes': palettes,
        'curated': [{'title': name, 'query': query} for name, query in re.findall(r'"([^"]+)" to "([^"]+)"', curated)],
        'strings': {'en': strings(ROOT / SOURCES[0]), 'hi': strings(ROOT / SOURCES[1])},
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding='utf-8') != text:
            raise SystemExit('Phone/PC contract drift: run python desktop/scripts/export_phone_contract.py')
        print('Phone/PC theme, EN/HI strings, navigation and 14 curated shelves: exact source contract PASS')
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(text, encoding='utf-8')
