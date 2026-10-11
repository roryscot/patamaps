"""Execute every pinned reference suite, preserving its raw report and hashes.

These are reference results, not a claim that Rust passed the TypeScript tests.
Scientific differential decisions are tested separately in the same checkout.
"""
import argparse, copy, json, os, signal, subprocess, tarfile, tempfile, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ENGINE='399747a4ad05a37cd8db1cedd53048fad2175be4'
p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('--node',type=Path,required=True);p.add_argument('--cli',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--scientific-only',action='store_true');p.add_argument('--reference-report',type=Path,help='Reuse an identified already-run report; does not rerun its tests');a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True);a.cli=a.cli.resolve()
env={**os.environ,'PATH':str(a.node.parent)+':'+os.environ.get('PATH',''),'CI':'true'}
commands=[]
def run(argv,cwd,expected=0):
    child=subprocess.Popen([str(v) for v in argv],cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:stdout,stderr=child.communicate(timeout=900)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);stdout,stderr=child.communicate()
        (a.output/'harness-timeout.json').write_text(json.dumps({'argv':[str(v) for v in argv],'stdout':stdout,'stderr':stderr,'limitSeconds':900},indent=2)+'\n')
        raise
    commands.append({'argv':[str(v) for v in argv],'returncode':child.returncode,'stdout':stdout,'stderr':stderr})
    assert child.returncode==expected,f'{argv}\n{stdout[-3000:]}\n{stderr[-3000:]}'
    return stdout
with tempfile.TemporaryDirectory(prefix='patamaps-full-reference-') as temp:
    work=Path(temp);ref=work/'reference';ref.mkdir();archive=work/'source.tar'
    run(['git','-C',a.reference,'archive',ENGINE,'--output',archive],ROOT)
    with tarfile.open(archive) as t:t.extractall(ref,filter='data')
    (ref/'node_modules').symlink_to(a.reference.resolve()/'node_modules',target_is_directory=True)
    run([a.node,ref/'node_modules/typescript/lib/tsc.js','-p','tsconfig.build.json'],ref)
    raw_report=a.output/'reference-vitest.json'
    suite_manifest=json.loads((ROOT/'fixtures/conformance.json').read_text())['suites']
    for s in suite_manifest:assert hashlib.sha256((ref/s['path']).read_bytes()).hexdigest()==s['sha256'],s['suite']
    raw=None
    if not a.scientific_only:
        if a.reference_report:
            raw_report.write_bytes(a.reference_report.read_bytes())
            commands.append({'action':'reuse-previously-run-reference-report','path':str(a.reference_report),'sha256':hashlib.sha256(raw_report.read_bytes()).hexdigest(),'testsRerun':False})
        else:
            run([a.node,ref/'node_modules/vitest/vitest.mjs','run','--maxWorkers=1','--reporter=default','--reporter=json','--outputFile',raw_report],ref)
        raw=json.loads(raw_report.read_text());assert raw['success'] and raw['numFailedTests']==0
        results=raw['testResults'];assert len(results)==53,len(results)
        paths={Path(r['name']).as_posix().rsplit('/reference/',1)[1] for r in results};assert paths=={s['path'] for s in suite_manifest}
    source=(ROOT/'fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv').read_text()
    options=json.loads((ROOT/'docs/acceptance/scientific-native/crate-options.json').read_text())['source']
    cases=[{'id':'licensed-seven','tsv':source,'sourceOptions':options,'expected':'source-imported'}]
    simple='# mapping_set_id: https://example.org/set\n# license: https://creativecommons.org/licenses/by/4.0/\n# curie_map: {ex: "https://example.org/"}\nsubject_id\tpredicate_id\tobject_id\tmapping_justification\nex:a\tskos:closeMatch\tex:b\tsemapv:ManualMappingCuration\n'
    cases.append({'id':'minimal-close','tsv':simple,'expected':'source-imported'})
    cases.append({'id':'quoted-label','tsv':simple.replace('mapping_justification\n','mapping_justification\tsubject_label\n').replace('semapv:ManualMappingCuration\n','semapv:ManualMappingCuration\t"a\tlabel\nwith ""quote"""\n'),'expected':'source-imported'})
    for name,tsv in [('unknown-prefix',simple.replace('ex:a','unknown:a')),('builtin-collision',simple.replace('{ex:', '{skos: "https://wrong.invalid/", ex:')),('duplicate-yaml',simple.replace('# license:', '# mapping_set_id: https://example.org/other\n# license:')),('negated',simple.replace('mapping_justification\n','mapping_justification\tpredicate_modifier\n').replace('semapv:ManualMappingCuration\n','semapv:ManualMappingCuration\tNot\n')),('no-term',simple.replace('ex:b','sssom:NoTermFound')),('duplicate-header',simple.replace('subject_id\tpredicate_id','subject_id\tsubject_id'))]:cases.append({'id':name,'tsv':tsv,'expected':'rejected'})
    case_file=work/'scientific-cases.json';case_file.write_text(json.dumps(cases));legacy_file=work/'scientific-reference.json'
    run([a.node,ROOT/'scripts/reference/evaluate_scientific.mjs',ref,case_file,legacy_file],ROOT)
    legacy=json.loads(legacy_file.read_text());native=[];comparisons=[]
    def norm(doc):
        d=copy.deepcopy(doc);d['propagation']=sorted(d['propagation'],key=lambda p:p['slot']);return d
    def graph_norm(g):
        # D001 wire envelope and pack content addresses; retain every entity,
        # assertion ID, endpoint, relation, cardinality, field and provenance.
        g=copy.deepcopy(g)
        return {'entities':sorted(g['entities'],key=lambda e:e['id']),'mappings':sorted(g['mappings'],key=lambda m:m['id'])}
    for c,old in zip(cases,legacy,strict=True):
        input_file=work/'case.tsv';input_file.write_text(c['tsv']);config=work/'options.json';config.write_text(json.dumps(c.get('sourceOptions',{'id':'scientific-case','namespace':'scientific-case','sourceRevision':'1'})))
        r=subprocess.run([str(a.cli),'sssom','import',str(input_file),'--source-config',str(config)],cwd=work,capture_output=True,text=True)
        if r.returncode==0:
            new=json.loads(r.stdout);equal=old['status']==new['status']==c['expected'] and old['document']==new['document'] and norm(old['interpretation'])==norm(new['interpretation'])
            if 'graph' in old:equal=equal and graph_norm(old['graph'])==graph_norm(new['graph'])
        else:new={'id':c['id'],'status':'rejected','returncode':r.returncode,'stderr':r.stderr};equal=old['status']==new['status']==c['expected']
        native.append(new);comparisons.append({'id':c['id'],'expected':c['expected'],'pass':equal})
    report={'engineRevision':ENGINE,'referenceSuites':53 if raw else None,'referenceTests':raw['numPassedTests'] if raw else None,'referenceSkipped':raw['numPendingTests'] if raw else None,'referenceStatus':'passed-with-host-skips' if raw and raw['numPendingTests'] else 'passed' if raw else 'not-run','rustParity':'only separately listed differential profiles; full old-wire API parity is not claimed','scientificCases':cases,'scientificReference':legacy,'scientificSuccessor':native,'scientificComparisons':comparisons,'normalization':'D001 removes raw graph envelope and pack addresses only. Compare all entities and assertion records including IDs/provenance. Propagation diagnostic records are keyed by unique slot; order is not semantic. Refusals preserve raw messages, with predeclared status for format-level diagnostics.','commands':commands}
    (a.output/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
    assert all(c['pass'] for c in comparisons),comparisons
    print(f"PASS: {len(cases)} native scientific differential cases with full records." + (f" All 53 pinned reference suite files ran: {raw['numPassedTests']} passed, {raw['numPendingTests']} host skips." if raw else " Reference unit suite was not run in scientific-only mode."))
