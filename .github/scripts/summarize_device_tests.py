#!/usr/bin/env python3
"""Fail-closed device test summary, visible through Checks even if artifact hosts are blocked."""
import argparse
import os
from pathlib import Path
import xml.etree.ElementTree as ET


def summarize(root, required):
    reports = sorted(Path(root).rglob('TEST-*.xml'))
    totals = dict.fromkeys(('tests', 'failures', 'errors', 'skipped'), 0)
    classes, failures = set(), []
    for report in reports:
        suite = ET.parse(report).getroot()
        for key in totals:
            totals[key] += int(suite.get(key, 0))
        for case in suite.findall('testcase'):
            classes.add(case.get('classname', ''))
            error = case.find('failure')
            if error is None:
                error = case.find('error')
            if error is not None:
                detail = (error.get('message') or error.text or '').splitlines()[:1]
                failures.append(f"{case.get('classname')}.{case.get('name')}: {' '.join(detail)[:600]}")
    passed = totals['tests'] - totals['failures'] - totals['errors'] - totals['skipped']
    message = (f"{totals['tests']} Android device cases: {passed} passed, {totals['failures']} failed, "
               f"{totals['errors']} errors, {totals['skipped']} skipped ({len(reports)} XML reports).")
    missing = set(required) - classes
    return message, failures, missing, bool(reports and passed > 0 and not missing and not any(totals[k] for k in ('failures', 'errors', 'skipped')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='app/build/outputs/androidTest-results/connected')
    parser.add_argument('--required-class', action='append', default=[])
    args = parser.parse_args()
    message, failures, missing, passed = summarize(args.root, args.required_class)
    print('::notice title=Android device tests::' + message)
    for failure in failures:
        print('::error title=Android device failure::' + failure.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A'))
    if missing:
        print('::error title=Missing device regressions::' + ', '.join(sorted(missing)))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as output:
            output.write('## Real Android device validation\n\n' + message + '\n\n')
            output.write('Required classes: ' + ', '.join(args.required_class) + '\n')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
