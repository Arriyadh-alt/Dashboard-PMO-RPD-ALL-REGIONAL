"""Independent source-to-contract reconciliation. Outputs aggregates, not identities.

Inputs and output stay outside the public repository. The optional reference JSON
is an audit assertion, never an input to production calculations.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from backend.analytics import build_analysis, prepare
from backend.browser_api import LocalEvents
from scripts.workbook_intake import header, text, write_private


def reconcile(intake, data, aliases, reference=None):
    prepared = prepare(data)
    analysis = build_analysis(data, prepared, {}, LocalEvents(), 'owner')
    survey, master = intake['survey'], intake['master']
    by_id = {row['pam']: row for row in survey}
    interested = lambda row: bool(row and header(row['minat']) == 'berminat')
    eligible = [row for row in master if header(row['master_flag']) == 'potensi']
    checks = []

    def check(name, expected, actual):
        checks.append({'metric': name, 'excel': expected, 'dashboard': actual,
                       'difference': actual-expected, 'status': 'PASS' if expected==actual else 'FAIL'})

    source_status = Counter(header(row['installation_status']) for row in survey)
    actual_status = Counter(row['status'].casefold() for row in prepared['rows'])
    expected = {'Survey records':len(survey), 'Tercanvassing':len(by_id),
        'Berminat':sum(interested(row) for row in survey),
        'Terpasang':source_status['done'], 'Assign FA':source_status['assign fa'],
        'Outstanding':source_status['outstanding'], 'Cancel':source_status['cancel'],
        'Total Potensi':len(eligible),
        'Sisa Potensi':len(eligible)-sum(interested(by_id.get(row['pam'])) for row in eligible)}
    actual = {'Survey records':len(data['rec']['pam']), 'Tercanvassing':analysis['metrics']['canvassed'],
        'Berminat':analysis['metrics']['interested'], 'Terpasang':analysis['metrics']['installed'],
        'Assign FA':actual_status['assign fa'], 'Outstanding':analysis['outstanding']['survey_rows'],
        'Cancel':actual_status['cancel'], 'Total Potensi':analysis['master']['potential'],
        'Sisa Potensi':analysis['master']['remaining']}
    for key, value in expected.items():
        check(key,value,actual[key])
    for source, field, title in [('result','c1','AO'),('result_detail','c2','AP'),('recommendation','rp','U')]:
        values = Counter(text(row[source]) for row in survey)
        values_actual = Counter(data['dic'][field][code] for code in data['rec'][field])
        for key, value in sorted(values.items()):
            check(title+' · '+key,value,values_actual[key])

    # Direct Update D/E/I + Q + AI groupings; no master inner join.
    def survey_key(row, level):
        values = tuple(header(row[key]) for key in ('region','area','kelurahan'))
        return values[:level]
    def actual_key(row, level):
        return tuple(header(value) for value in (data['reg'][row['ab']],data['abs'][row['ab']],data['kels'][row['kel']]))[:level]
    for level, title in [(1,'Regional'),(2,'Area Bisnis'),(3,'Kelurahan')]:
        groups, observed = defaultdict(lambda:[0,0,0]),defaultdict(lambda:[0,0,0])
        for row in survey:
            value=groups[survey_key(row,level)]
            for i,n in enumerate((1,interested(row),header(row['installation_status'])=='done')):
                value[i]+=n
        for row in prepared['rows']:
            value=observed[actual_key(row,level)]
            for i,n in enumerate((1,row['interest'],row['installed'])):
                value[i]+=n
        keys=groups.keys()|observed.keys()
        check(title+' groups reconciled',len(keys),sum(groups[k]==observed[k] for k in keys))
        for region in sorted(groups) if level==1 else []:
            check('Regional survey records · '+region[0].title(),groups[region][0],observed[region][0])
    # Every G group is checked against raw worksheet geography and master RW/RT.
    master_by_id = {row['pam']:row for row in master}
    source_geo = defaultdict(lambda:[0]*5)
    def neighborhood(row):
        def value(key):
            number=float(row[key] or 0)
            return int(number) if number.is_integer() and 1<=number<=99 else 0
        rw=value('rw')
        return rw,value('rt') if rw else 0
    def master_geo(row):
        return (header(row['region']).removeprefix('regional '),header(row['area']).removeprefix('ab '),header(row['kelurahan']))
    for row in eligible:
        value=source_geo[(*master_geo(row),*neighborhood(row))]
        value[0]+=1;value[4]+=interested(by_id.get(row['pam']))
    for row in survey:
        match=master_by_id.get(row['pam']);geo=survey_key(row,3)
        rwrt=neighborhood(match) if match and geo==master_geo(match) else (0,0)
        value=source_geo[(*geo,*rwrt)]
        for i,n in enumerate((1,interested(row),header(row['installation_status'])=='done'),1):
            value[i]+=n
    observed_geo={(*[header(v) for v in (data['reg'][r[0]],data['abs'][r[0]],data['kels'][r[1]])],r[2],r[3]):r[4:] for r in data['G']}
    keys=source_geo.keys()|observed_geo.keys()
    check('RW/RT groups · all five measures',len(keys),sum(source_geo.get(k)==observed_geo.get(k) for k in keys))
    for i,title in enumerate(('Total Potensi','Tercanvassing','Berminat','Terpasang','Matched eligible Berminat'),4):
        check('Field cube · '+title, (expected.get(title) if title in expected else len(eligible)-expected['Sisa Potensi']),sum(r[i] for r in data['G']))
    # Actual event dates, never survey dates, for FA and installation achievements.
    for source, field, title in [('survey_date','date','Survey'),('fa_date','fa_date','FA'),('meter_date','install_date','Meter')]:
        dates=Counter(row[source] for row in survey if row[source])
        observed=Counter(row[field].isoformat() for row in prepared['rows'] if row[field])
        check(title+' dated records',sum(dates.values()),sum(observed.values()))
        check(title+' daily buckets reconciled',len(dates.keys()|observed.keys()),sum(dates[k]==observed[k] for k in dates.keys()|observed.keys()))
        check(title+' per-PAM dates',len(survey),sum(
            row['pam'] in by_id and (row[field].isoformat() if row[field] else None)==(by_id[row['pam']][source] or None)
            for row in prepared['rows']))
    check('Per-PAM Q/AI membership',len(survey),sum(row['pam'] in by_id
        and row['interest']==interested(by_id[row['pam']])
        and row['status'].casefold()==header(by_id[row['pam']]['installation_status'])
        for row in prepared['rows']))
    events=Counter(row['meter_date'] for row in survey if row['meter_date'] and header(row['installation_status'])=='done')
    observed_events=Counter(row['install_date'].isoformat() for row in prepared['rows'] if row['installed'] and row['install_date'])
    keys=events.keys()|observed_events.keys()
    check('Done meter daily event buckets',len(keys),sum(events[k]==observed_events[k] for k in keys))
    expected_teams, observed_teams=defaultdict(lambda:[0,0,0]),defaultdict(lambda:[0,0,0])
    for row in survey:
        value=expected_teams[aliases.get(text(row['surveyor']),text(row['surveyor']))]
        for i,n in enumerate((1,interested(row),header(row['installation_status'])=='done')):value[i]+=n
    for row in prepared['rows']:
        value=observed_teams[data['svs'][row['sv']]]
        for i,n in enumerate((1,row['interest'],row['installed'])):value[i]+=n
    keys=expected_teams.keys()|observed_teams.keys()
    check('Surveyor groups · survey/interest/Done',len(keys),sum(expected_teams[k]==observed_teams[k] for k in keys))
    for key,title in [('by_obstacle','Outstanding obstacle categories'),('by_file_status','Outstanding file categories'),('by_illegal_flag','Outstanding illegal categories')]:
        check(title,expected['Outstanding'],sum(analysis['outstanding'][key].values()))
    computed = {row['metric']:row['excel'] for row in checks}
    for key, value in (reference or {}).items():
        check('Provided reference: '+key,value,computed[key])
    return {'source_sha256':intake['workbook_sha256'],'reporting_date':intake.get('reporting_date'),
        'survey_through':data['meta']['tmax'],'checks':checks,
        'passed':all(row['status']=='PASS' for row in checks),
        'master_join':intake['summary']['cross_sheet'],
        'unmapped_survey_rows':data['meta']['geographic_survey_unmapped'],
        'definitions':data['meta']['metric_definitions'],
        'active_potential':{'status':'UNVERIFIED','reason':'No separately approved definition; not invented.'}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('intake','contract','aliases','private_output'):parser.add_argument(key,type=Path)
    parser.add_argument('--reference',type=Path)
    args=parser.parse_args()
    read=lambda path:json.loads(path.read_text())
    result=reconcile(read(args.intake),read(args.contract),read(args.aliases),read(args.reference) if args.reference else None)
    write_private(args.private_output,result)
    print('Reconciled',len(result['checks']),'checks; all passed:',result['passed'])
    if not result['passed']:raise SystemExit('Reconciliation failed; retain previous valid release')
