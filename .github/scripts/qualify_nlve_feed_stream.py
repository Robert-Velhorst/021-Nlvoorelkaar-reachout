"""Owned hosted source/real-HTTP/current-package evidence, with fatal audit gates."""
import collections,concurrent.futures,datetime,hashlib,json,os,pathlib,re,subprocess,sys,urllib.parse,urllib.request,venv
assert os.environ.get('GITHUB_REPOSITORY')=='Robert-Velhorst/021-Nlvoorelkaar-reachout'
root=pathlib.Path.cwd();output=root/'nlve-feed-evidence';output.mkdir(exist_ok=True)
descriptor=json.loads((root/'.github/qualification/nlve-feed-stream.json').read_bytes())
def save(name,data):(output/name).write_bytes((json.dumps(data,indent=2)+'\n').encode())
def snapshot():
    entries={}
    for entry in subprocess.check_output(['git','ls-files','-s','-z']).split(b'\0'):
        if not entry:continue
        left,name=entry.split(b'\t');mode,blob,stage=left.decode().split();assert stage=='0'
        path=root/name.decode();payload=os.readlink(path).encode() if mode=='120000' else path.read_bytes()
        canonical=payload;eol=None
        if hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest()!=blob:
            attributes=subprocess.check_output(['git','check-attr','-z','eol','--',name.decode()]).split(b'\0')
            assert attributes==[name,b'eol',b'crlf',b''],name
            canonical=subprocess.check_output(['git','cat-file','blob',blob])
            assert b'\r\n' not in canonical and payload==canonical.replace(b'\n',b'\r\n'),name
            eol='crlf'
        entries[name.decode()]={'mode':mode,'blob':blob,'sha256':hashlib.sha256(canonical).hexdigest(),'checkout_sha256':hashlib.sha256(payload).hexdigest(),'declared_checkout_eol':eol}
    return {'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'payloads':entries}
before=snapshot();save('source-before.json',before)
assert sys.version_info[:3]==(3,15,2)
envroot=pathlib.Path(os.environ['RUNNER_TEMP'])/'owned-nlve-stream'
commands=[]
def run(label,argv):
    with (output/(label+'.log')).open('wb') as stream:result=subprocess.run([str(a) for a in argv],stdout=stream,stderr=subprocess.STDOUT)
    commands.append({'label':label,'argv':[str(a) for a in argv],'exit_code':result.returncode});save('commands.json',commands)
    return result.returncode
sdk=envroot/'sdk';audit_env=envroot/'audit'
venv.create(sdk,with_pip=True);venv.create(audit_env,with_pip=True)
python=sdk/'bin/python';auditor=audit_env/'bin/python'
assert run('current-SDK-installer',[python,'-m','pip','install','--report',output/'pip-upgrade-report.json','pip=='+descriptor['targets']['pip']])==0
assert run('normal-Requests-install',[python,'-m','pip','install','--report',output/'Requests-install-report.json','requests=='+descriptor['targets']['requests']])==0
assert run('normal-SDK-package-consistency',[python,'-m','pip','check'])==0
run('original-real-HTTP',[python,'.github/scripts/review_nlve_feed_stream.py','original'])
run('candidate-real-HTTP',[python,'.github/scripts/review_nlve_feed_stream.py','candidate'])
distribution_code="import importlib.metadata,json,platform,ssl,sys;print(json.dumps({'python':sys.version,'openssl':ssl.OPENSSL_VERSION,'platform':platform.platform(),'distributions':sorted([{'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions()],key=lambda r:r['name'].lower())}))"
actual=json.loads(subprocess.check_output([str(python),'-c',distribution_code]));save('actual-SDK-distributions.json',actual)
bootstrap_code="import ensurepip,hashlib,json,pathlib;files=list((pathlib.Path(ensurepip.__file__).parent/'_bundled').glob('pip-*.whl'));assert len(files)==1;p=files[0];print(json.dumps({'filename':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))"
bootstrap=json.loads(subprocess.check_output([str(python),'-c',bootstrap_code]));save('actual-CPython-bundled-pip-wheel.json',bootstrap)
requirements=''.join(r['name']+'=='+r['version']+'\n' for r in actual['distributions']);(output/'observed-SDK-requirements.txt').write_bytes(requirements.encode())
def public(row):
    url='https://pypi.org/pypi/'+urllib.parse.quote(row['name'])+'/json'
    try:
        with urllib.request.urlopen(url,timeout=45) as response:raw=response.read(32*1024*1024+1)
        assert len(raw)<=32*1024*1024
        data=json.loads(raw);stable=[v for v,files in data['releases'].items() if re.fullmatch(r'\d+(?:\.\d+){1,3}',v) and files and any(not f.get('yanked') for f in files)]
        highest=max(stable,key=lambda v:tuple(map(int,v.split('.'))))
        return {**row,'source':url,'highest_public_stable':highest,'highest_stable_met':row['version']==highest,'query':'ok','metadata_sha256':hashlib.sha256(raw).hexdigest()}
    except Exception as error:return {**row,'query':'unavailable','highest_stable_met':False,'error':str(error)}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:versions=list(pool.map(public,actual['distributions']))
save('complete-installed-SDK-public-version-comparison.json',versions)
assert run('normal-auditor-installer',[auditor,'-m','pip','install','pip=='+descriptor['targets']['pip'],'pip-audit=='+descriptor['targets']['pip-audit']])==0
site_paths=json.loads(subprocess.check_output([str(python),'-c','import site,json;print(json.dumps(site.getsitepackages()))']))
assert len(site_paths)==1 and pathlib.Path(site_paths[0]).resolve().is_relative_to(sdk.resolve())
audit_exit=run('complete-unfiltered-SDK-audit',[auditor,'-m','pip_audit','--path',site_paths[0],'--format','json','--output',output/'raw-SDK-audit.json'])
after=snapshot();save('source-after.json',after);assert before==after
old=json.loads((output/'original-real-HTTP-results.json').read_bytes());new=json.loads((output/'candidate-real-HTTP-results.json').read_bytes())
assert [r['name'] for r in old['cases']]==[r['name'] for r in new['cases']] and len(new['cases'])==19
audit=json.loads((output/'raw-SDK-audit.json').read_bytes())
normalize=lambda name:re.sub(r'[-_.]+','-',name.lower())
assert {normalize(r['name']):r['version'] for r in audit['dependencies']}=={normalize(r['name']):r['version'] for r in actual['distributions']},'Audit package identity must match every installed SDK distribution, including the installer.'
summary={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_payloads_unchanged':len(before['payloads']),'original_passed':old['passed'],'original_failed':old['failed'],'candidate_passed':new['passed'],'candidate_failed':new['failed'],'skipped':0,'SDK_distributions':actual['distributions'],'highest_public_stable_gaps':[r for r in versions if not r['highest_stable_met']],'audit_exit':audit_exit,'raw_audit_findings':sum(len(r.get('vulns',[])) for r in audit['dependencies']),'whole_Requests_original_SDK_or_native_runtime_application_deployment_or_data_acceptance':False,'existing_inactivity_timeouts_preserved_and_whole_wall_clock_deadline_not_claimed':True}
save('qualification-summary.json',summary)
assert old['failed']>0 and new['failed']==0 and new['passed']==19 and new['skipped']==0
assert audit_exit==0 and summary['raw_audit_findings']==0 and not summary['highest_public_stable_gaps']
assert all(r['exit_code']==0 for r in commands if r['label']!='original-real-HTTP')
