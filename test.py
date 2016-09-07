#!/usr/bin/env python3

import glob
import json
import locale
from os.path import basename

from schema2reql import validate
import rethinkdb as r
import click

TESTFILES = './JSON-Schema-Test-Suite/tests/draft4/'

# Keep click from complaining about stuff
locale.setlocale(locale.LC_ALL, 'en_US.utf-8')


@click.command()
@click.option('--match', default='', help='glob to match filenames')
def main(match):
    conn = r.connect()
    results = {}
    for testfilename in glob.glob(TESTFILES + match + '*.json'):
        name = basename(testfilename).rsplit('.', 1)[0]
        results[name] = {"passed": 0, "failed": 0}
        click.secho(name, bold=True)
        with open(testfilename) as testfile:
            test_definitions = json.load(testfile)
        for td in test_definitions:
            click.secho(' ' + td['description'], bold=True, fg='yellow')
            try:
                schema_filter = r.expr(validate(td['schema']))
            except NotImplementedError as nie:
                num_failed = len(td['tests'])
                click.secho('  schema had unimplemented keyword "%s" '
                            'autofailed %s tests' % (
                                nie.args[0], num_failed),
                            fg='red', bold=True)
                results[name]['failed'] += num_failed
                continue
            for test in td['tests']:
                passed = False
                try:
                    result = r.do(test['data'], schema_filter).run(conn)
                    passed = result is test['valid']
                except r.ReqlError as re:
                    passed = test['valid'] is False
                click.echo('  ' + test['description'] + ': ', nl=False)
                if passed:
                    click.secho('passed', fg='green')
                    results[name]['passed'] += 1
                else:
                    click.secho('failed', fg='red', bold=True)
                    results[name]['failed'] += 1
                    click.echo('    Data: ' + json.dumps(test['data']))
                    click.echo('    Schema: ' + json.dumps(td['schema']))
                    click.echo('    ReQL: ' + str(r.expr(schema_filter)))
    summary(results)


def summary(results):
    total_overall = 0
    total_passed = 0
    click.secho('\n\nFinal Results', fg='white', bold=True)
    for test, result in sorted(results.items()):
        passed = result['passed']
        total_passed += passed
        total = result['passed'] + result['failed']
        total_overall += total
        color = pass_color(passed, total)
        click.secho(' %s : passed %s/%s' % (test, passed, total),
                    fg=color, bold=True)

    color = pass_color(total_passed, total_overall)
    click.secho('\nTotal:', nl=False, fg='white', bold=True)
    click.secho(' passed %s/%s' % (total_passed, total_overall),
                fg=color, bold=True)


def pass_color(passed, total):
    if passed == total:
        return 'green'
    elif passed > total // 2:
        return 'yellow'
    else:
        return 'red'


if __name__ == '__main__':
    main()
