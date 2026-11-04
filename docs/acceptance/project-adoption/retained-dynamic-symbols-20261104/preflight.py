from pathlib import Path
import ast,hashlib,json,os,shutil,subprocess,sys,time,unittest
ROOT=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
BASE=Path(__file__).resolve().parent
assert os.environ.get('WARGAME_STORAGE_RUN_TOKEN')
names=['scripts/test_public_pnpm_bootstrap.py','scripts/chatbot_dynamic_profile.py','scripts/qualify_chatbot_next.py','scripts/qualify_chatbot_runtime.py','scripts/next_retained_runtime.py','scripts/qualify_next_standalone.py','scripts/qualify_installed_next.py','scripts/test_installed_retained_dynamic_next.py','.github/workflows/next-server-actions.yml','.github/workflows/native-capabilities.yml']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
saved=BASE/'source';saved.mkdir(mode=0o700);bindings={}
for name in names:
 p=ROOT/name;shutil.copy2(p,saved/p.name);bindings[name]=digest(p)
 if name.endswith('.py'):ast.parse(p.read_text(),filename=name)
fixture=BASE/'fixtures';fixture.mkdir(mode=0o700);os.environ['PATAMAPS_TEST_RETAIN_ROOT']=str(fixture)
sys.path.insert(0,str(ROOT/'scripts'))
patterns=['test_public_pnpm_bootstrap.py','test_installed_retained_dynamic_next.py','test_installed_dynamic_next.py','test_installed_retained_next.py','test_chatbot_dynamic_profile.py','test_next_retained_runtime.py','test_chatbot_rewrite_profile.py','test_next_standalone.py','test_next_output_inventory.py','test_installed_source_identity.py','test_exact_archive_install.py','test_next_source_acquisition.py']
suite=unittest.TestSuite()
for pattern in patterns:suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'scripts'),pattern=pattern))
with(BASE/'tests.log').open('x')as stream:
 result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
yaml_result=subprocess.run(['/usr/bin/ruby','-e','require "yaml"; ARGV.each { |p| YAML.parse_file(p) }; puts "workflow YAML parsed"',*[str(ROOT/name)for name in names if name.endswith('.yml')]],capture_output=True,text=True,timeout=30)
(BASE/'yaml.stdout').write_text(yaml_result.stdout);(BASE/'yaml.stderr').write_text(yaml_result.stderr)
unchanged=all(digest(ROOT/name)==sha for name,sha in bindings.items())
value=dict(status='passed'if result.wasSuccessful()and yaml_result.returncode==0 and unchanged else'failed',testsRun=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),yamlParsed=yaml_result.returncode==0,sourceBindings=bindings,sourcesUnchanged=unchanged,actualApplicationRun=False,retainedDynamicProfileAccepted=False,nativeI3eRetryRun=False)
(BASE/'result.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value),flush=True)
sys.exit(0 if value['status']=='passed'else 1)
