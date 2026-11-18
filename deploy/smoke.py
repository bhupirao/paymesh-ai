"""Container metadata smoke only. Run via compose exec python; never host endpoints.
No login, inference or financial mutation. Functional disposable E2E is separate.
"""
import urllib.request,urllib.error,json

def main():
    client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for name,url in [('java','http://127.0.0.1:18080/actuator/health/readiness'),('python','http://127.0.0.1:8000/health'),('llama','http://127.0.0.1:8082/health')]:
        with client.open(url,timeout=5) as response:
            value=json.load(response)
            if value.get('status') not in ('UP','ok'):raise SystemExit(name+' health failed')
        print(name+': PASS')
    for role in ('merchant','admin'):
        with client.open('http://127.0.0.1:15500/'+role+'/ai',timeout=5) as response:
            if response.status!=200:raise SystemExit('HTML route failed')
        try:client.open('http://127.0.0.1:15500/api/v1/'+role+'/ai/conversations?page=0&size=5',timeout=5)
        except urllib.error.HTTPError as error:
            if error.code not in (401,403):raise SystemExit('Authorization boundary failed')
        else:raise SystemExit('Authorization boundary open')
    print('CONTAINER_METADATA_PASS_NO_INFERENCE')
if __name__=='__main__':main()
