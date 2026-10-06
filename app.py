from flask import Flask, render_template, request, jsonify, send_file
import csv, io, os, threading, time, uuid
from urllib.parse import urlparse
import requests

BASE=os.path.dirname(os.path.abspath(__file__))
app=Flask(__name__,template_folder=os.path.join(BASE,'templates'),static_folder=os.path.join(BASE,'static'))
JOBS={}

def valid_url(u):
    try:
        p=urlparse(u.strip()); return p.scheme in ('http','https') and bool(p.netloc)
    except: return False

def parse_csv(f):
    text=f.read().decode('utf-8-sig','replace')
    r=csv.DictReader(io.StringIO(text))
    if not r.fieldnames: raise ValueError('CSV has no headers')
    h={x.strip().lower():x for x in r.fieldnames if x}
    if 'brand' not in h or 'signup_url' not in h: raise ValueError('CSV headers must be brand,signup_url')
    out=[]; seen=set()
    for row in r:
        brand=(row.get(h['brand']) or '').strip(); url=(row.get(h['signup_url']) or '').strip()
        if not brand and not url: continue
        if not valid_url(url): out.append({'brand':brand or '(unnamed)','signup_url':url,'status':'Invalid URL'}); continue
        key=url.lower().rstrip('/')
        if key in seen: out.append({'brand':brand or '(unnamed)','signup_url':url,'status':'Duplicate skipped'}); continue
        seen.add(key); out.append({'brand':brand or '(unnamed)','signup_url':url,'status':'Queued'})
    return out

def worker(jid):
    j=JOBS[jid]; s=requests.Session(); s.headers['User-Agent']='Mozilla/5.0 NewsletterSignupAssistant/1.0'
    for x in j['rows']:
        if j['stop']: x['status']='Stopped'; continue
        if x['status']!='Queued': continue
        x['status']='Checking page...'; j['current']=x['brand']
        try:
            r=s.get(x['signup_url'],timeout=15,allow_redirects=True); x['final_url']=r.url
            if r.status_code>=400: x['status']=f'Page unavailable (HTTP {r.status_code})'
            elif 'text/html' not in r.headers.get('content-type','').lower(): x['status']='Not an HTML signup page'
            else: x['status']='Manual signup required'
        except requests.RequestException as e: x['status']='Connection failed'; x['error']=str(e)[:180]
        time.sleep(.15)
    j['current']=''; j['done']=True

@app.get('/')
def home(): return render_template('index.html')
@app.get('/health')
def health(): return jsonify(status='ok')
@app.post('/api/start')
def start():
    try:
        email=(request.form.get('email') or '').strip(); f=request.files.get('csv')
        if not email or '@' not in email: return jsonify(error='Enter a valid email address.'),400
        if not f: return jsonify(error='Upload a CSV file.'),400
        rows=parse_csv(f)
        if not rows: return jsonify(error='CSV contains no rows.'),400
        jid=uuid.uuid4().hex; JOBS[jid]={'email':email,'rows':rows,'stop':False,'done':False,'current':''}
        threading.Thread(target=worker,args=(jid,),daemon=True).start()
        return jsonify(job_id=jid,count=len(rows))
    except Exception as e:
        app.logger.exception('start failed'); return jsonify(error=f'{type(e).__name__}: {e}'),500
@app.get('/api/status/<jid>')
def status(jid):
    j=JOBS.get(jid)
    if not j:return jsonify(error='Job not found'),404
    return jsonify(done=j['done'],current=j['current'],rows=j['rows'])
@app.post('/api/stop/<jid>')
def stop(jid):
    j=JOBS.get(jid)
    if not j:return jsonify(error='Job not found'),404
    j['stop']=True; return jsonify(ok=True)
@app.get('/api/export/<jid>')
def export(jid):
    j=JOBS.get(jid)
    if not j:return jsonify(error='Job not found'),404
    out=io.StringIO(); w=csv.DictWriter(out,fieldnames=['brand','signup_url','status','final_url','error'],extrasaction='ignore'); w.writeheader(); w.writerows(j['rows'])
    return send_file(io.BytesIO(out.getvalue().encode()),mimetype='text/csv',as_attachment=True,download_name='subscription_results.csv')

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')))
