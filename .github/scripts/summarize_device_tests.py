#!/usr/bin/env python3
"""Fail-closed device summary, including AGP's nested/namespaced JUnit suites."""
import argparse
import os
from pathlib import Path
import xml.etree.ElementTree as ET


def tag(element):
    return element.tag.rsplit('}', 1)[-1]


def testcases(element, suite=''):
    if tag(element) == 'testsuite':
        suite = element.get('name', suite)
    if tag(element) == 'testcase':
        yield element, element.get('classname') or element.get('className') or element.get('class') or suite
    for child in element:
        yield from testcases(child, suite)


def summarize(root, required):
    reports = sorted(Path(root).rglob('TEST-*.xml'))
    totals = dict.fromkeys(('tests', 'failures', 'errors', 'skipped'), 0)
    classes, failures, inconsistent = set(), [], False
    for report in reports:
        suite = ET.parse(report).getroot()
        cases = list(testcases(suite))
        counted = dict.fromkeys(totals, 0)
        counted['tests'] = len(cases)
        for case, classname in cases:
            classes.add(classname)
            children = list(case.iter())
            for category, marker in (('failures', 'failure'), ('errors', 'error'), ('skipped', 'skipped')):
                errors = [child for child in children if tag(child) == marker]
                if errors:
                    counted[category] += 1
                    if marker != 'skipped':
                        error = errors[0]
                        # AGP often sets message to only java.lang.AssertionError; the XML
                        # body holds the assertion and source line. Keep both, bounded, so
                        # read-only Checks can diagnose a failure without Azure log access.
                        detail = '\n'.join(filter(None, (error.get('message'), '\n'.join((error.text or '').splitlines()[:15]))))
                        failures.append(f"{classname}.{case.get('name')}: {detail[:2400]}")
        for key in totals:
            reported = int(suite.get(key, counted[key]))
            if reported != counted[key]:
                inconsistent = True
                failures.append(f'{report.name}: {key} aggregate {reported} disagrees with actual testcase nodes {counted[key]}')
            totals[key] += max(reported, counted[key])
    passed = totals['tests'] - totals['failures'] - totals['errors'] - totals['skipped']
    message = (f"{totals['tests']} Android device cases: {passed} passed, {totals['failures']} failed, "
               f"{totals['errors']} errors, {totals['skipped']} skipped ({len(reports)} XML reports).")
    missing = set(required) - classes
    return message, failures, missing, bool(reports and passed > 0 and not inconsistent and not missing and not any(totals[k] for k in ('failures', 'errors', 'skipped')))


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
