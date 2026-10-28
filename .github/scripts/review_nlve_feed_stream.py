"""Owned real-HTTP counterfactuals; no live provider, credentials or data used."""
import argparse,gzip,hashlib,http.server,importlib.util,json,pathlib,socket,subprocess,tempfile,threading
import requests

parser=argparse.ArgumentParser();parser.add_argument('variant',choices=['original','candidate']);args=parser.parse_args()
root=pathlib.Path.cwd();descriptor=json.loads((root/'.github/qualification/nlve-feed-stream.json').read_bytes())
assert descriptor['baseline']=='1821a254f46d893e413aaf3719ed7a444d966267'
source=subprocess.check_output(['git','show','1821a254f46d893e413aaf3719ed7a444d966267:connectors/hai_bridge.py']) if args.variant=='original' else (root/'connectors/hai_bridge.py').read_bytes()
assert hashlib.sha256(source).hexdigest()==descriptor['baseline_bridge_sha256' if args.variant=='original' else 'candidate_bridge_sha256']
limit=5*1024*1024;chunk=64*1024;token='owned-synthetic-feed-token-only-0123456789';records=[];responses=[]
normal=json.dumps({'cursor':'owned-unicode-\u20ac','items':[]},ensure_ascii=False).encode()
def sized_json(size):
    prefix=b'{"items":[],"cursor":"';suffix=b'"}'
    return prefix+b'x'*(size-len(prefix)-len(suffix))+suffix
class Server(http.server.ThreadingHTTPServer):
    daemon_threads=True
    block_on_close=False
    def handle_error(self,request,client_address):
        self.fixture_peer_closures+=1
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*unused):pass
    def do_GET(self):
        self.server.observed.append({'path':self.path,'authorization_exact':self.headers.get('Authorization')=='Bearer '+token})
        mode=self.server.mode
        body=normal;status=200;headers={};chunked=False;disconnect=False
        if mode=='item':body=json.dumps({'cursor':'one','items':[{'externalId':'owned-1','provider':'generic_json_feed','itemType':'owned'}]}).encode()
        elif mode=='utf16':body=normal.decode().encode('utf-16')
        elif mode=='exact':body=sized_json(limit)
        elif mode in ['oversize','chunked_oversize','gzip_oversize']:body=sized_json(limit+3*chunk)
        elif mode=='status':status=503;body=b'owned-private-upstream-body-'*40000
        elif mode=='invalid_json':body=b'{owned-private-feed-invalid-json'
        elif mode=='invalid_envelope':body=b'{}'
        elif mode=='too_many':body=json.dumps({'items':[{'externalId':str(i),'provider':'generic_json_feed','itemType':'owned'} for i in range(501)]}).encode()
        elif mode=='missing_key':body=b'{"items":[{"provider":"generic_json_feed"}]}'
        elif mode=='redirect':status=302;body=b'';headers['Location']=self.server.sink
        elif mode=='disconnect':body=b'{"items":';disconnect=True
        if mode in ['gzip','gzip_oversize']:body=gzip.compress(body);headers['Content-Encoding']='gzip'
        if mode in ['chunked','chunked_oversize']:chunked=True
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-16' if mode=='utf16' else 'application/json')
        for name,value in headers.items():self.send_header(name,value)
        self.send_header('Connection','close')
        if chunked:self.send_header('Transfer-Encoding','chunked')
        else:self.send_header('Content-Length',str(len(body)+(100 if disconnect else 0)))
        self.end_headers()
        try:
            for start in range(0,len(body),chunk):
                data=body[start:start+chunk]
                if chunked:self.wfile.write(f'{len(data):X}\r\n'.encode()+data+b'\r\n')
                else:self.wfile.write(data)
                self.wfile.flush()
            if chunked:self.wfile.write(b'0\r\n\r\n');self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError):self.server.fixture_peer_closures+=1
        self.close_connection=True

real_send=requests.Session.send
def observe_send(session,request,**kwargs):
    def observe(response,**unused):
        row={'status':response.status_code,'decoded_bytes':0,'stream_requested':kwargs.get('stream',False),'closed':False};responses.append((response,row))
        original=response.iter_content
        def iter_content(*pos,**kw):
            for data in original(*pos,**kw):row['decoded_bytes']+=len(data);yield data
        response.iter_content=iter_content
        return response
    request.register_hook('response',observe)
    return real_send(session,request,**kwargs)
requests.Session.send=observe_send
server=Server(('127.0.0.1',0),Handler);server.mode='normal';server.observed=[];server.fixture_peer_closures=0
sink=Server(('127.0.0.1',0),Handler);sink.mode='normal';sink.observed=[];sink.fixture_peer_closures=0
server.sink=f'http://127.0.0.1:{sink.server_port}/owned-redirect-sink'
for s in [server,sink]:threading.Thread(target=s.serve_forever,kwargs={'poll_interval':0.01},daemon=True).start()
cases=[('normal','valid_empty'),('item','valid_item'),('utf16','valid_UTF16'),('chunked','valid_chunked'),('gzip','valid_gzip'),('exact','valid_exact_5MiB'),('oversize','bounded_declared_oversize'),('chunked_oversize','bounded_chunked_oversize'),('gzip_oversize','bounded_decoded_gzip_oversize'),('status','reject_status_before_body'),('invalid_json','private_JSON_error'),('disconnect','private_transport_error'),('invalid_envelope','preserve_invalid_envelope'),('too_many','preserve_501_item_guard'),('missing_key','preserve_required_item_fields'),('redirect','preserve_redirect_denial')]
cases += [('bad_header_'+control,'private_token_'+control) for control in ['LF','CR','CRLF']]
try:
    with tempfile.TemporaryDirectory(prefix='owned-nlve-feed-') as temp:
        module_path=pathlib.Path(temp)/'owned_bridge.py';module_path.write_bytes(source)
        spec=importlib.util.spec_from_file_location('owned_bridge',module_path);bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
        for index,(mode,name) in enumerate(cases):
            destination=pathlib.Path(temp)/str(index)/'feed.json';destination.parent.mkdir();destination.write_bytes(b'owned-existing-feed-preserved')
            server.mode=mode;server.observed=[];sink.observed=[];responses.clear();failure=None;error=None;result=None
            used_token=token
            if mode.startswith('bad_header_'):
                control={'LF':'\n','CR':'\r','CRLF':'\r\n'}[mode.removeprefix('bad_header_')]
                used_token='owned-private-token-canary'+control+'owned-private-token-tail'
            try:result=bridge.sync_feed(f'http://127.0.0.1:{server.server_port}',used_token,str(destination),17)
            except Exception as caught:error=caught
            try:
                valid=mode in ['normal','item','utf16','chunked','gzip','exact']
                if valid:
                    assert error is None,f'unexpected {type(error).__name__}'
                    saved=json.loads(destination.read_bytes());assert isinstance(saved['items'],list)
                    assert result['items']==(1 if mode=='item' else 0)
                else:
                    assert error is not None,'rejected input was accepted'
                    assert destination.read_bytes()==b'owned-existing-feed-preserved'
                assert not list(destination.parent.glob('.feed.json.*.tmp'))
                if mode.startswith('bad_header_'):
                    assert 'owned-private-token' not in str(error),'private token appears in exception'
                    assert isinstance(error,RuntimeError),'transport errors must have stable public classification'
                    assert not server.observed
                else:
                    assert len(server.observed)==1 and server.observed[0]=={'path':'/api/v1/hai/feed?limit=17','authorization_exact':True}
                if mode in ['oversize','chunked_oversize','gzip_oversize']:
                    assert sum(row['decoded_bytes'] for _,row in responses)<=limit+chunk,'decoded body read exceeded bounded streaming allowance'
                if mode=='status':assert sum(row['decoded_bytes'] for _,row in responses)==0,'error status body was eagerly buffered'
                if mode in ['invalid_json','disconnect']:
                    assert isinstance(error,RuntimeError),'provider errors must have stable public classification'
                    assert 'owned-private' not in str(error),'provider details appear in public error'
                assert not sink.observed,'redirect reached the second origin'
            except Exception as caught:failure=str(caught)
            records.append({'name':name,'mode':mode,'pass':failure is None,'assertion_failure':failure,'exception_type':type(error).__name__ if error else None,'decoded_bytes_read':sum(row['decoded_bytes'] for _,row in responses),'actual_HTTP_requests':len(server.observed),'redirect_sink_requests':len(sink.observed),'destination_preserved_on_failure':destination.read_bytes()==b'owned-existing-feed-preserved' if error else None})
finally:
    requests.Session.send=real_send
    for s in [server,sink]:s.shutdown();s.server_close()
output=root/'nlve-feed-evidence';output.mkdir(exist_ok=True)
record={'variant':args.variant,'source_sha256':hashlib.sha256(source).hexdigest(),'cases':records,'passed':sum(r['pass'] for r in records),'failed':sum(not r['pass'] for r in records),'skipped':0,'owned_fixture_peer_closures':server.fixture_peer_closures,'real_HTTP_and_real_Requests_used':True,'no_live_provider_credentials_or_data_used':True,'whole_wall_clock_deadline_not_claimed':True}
(output/(args.variant+'-real-HTTP-results.json')).write_bytes((json.dumps(record,indent=2)+'\n').encode())
print(json.dumps({'variant':args.variant,'passed':record['passed'],'failed':record['failed'],'skipped':0}))
raise SystemExit(1 if record['failed'] else 0)
