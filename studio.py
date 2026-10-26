"""Portable narration assembly with optional local voice cloning."""
import argparse, datetime, hashlib, http.server, json, pathlib, re, secrets
import subprocess, threading, urllib.parse, wave, shutil, sys, os

from config import CODE, workspace, ffmpeg, safe_child
ROOT=workspace()
PROD=ROOT
FF=ffmpeg()
PLAN=ROOT/'plan.json'
CLONE=ROOT/'voice-clone'
CLONE_VOICE='Minha voz (clone local)'
TOKEN=''
ORIGIN=''
STATE={'running':False,'message':'Pronto. Edite o roteiro e os tempos antes de gerar.','outputs':[]}
LOCK=threading.Lock()

def clone_ready():
    model=pathlib.Path(os.environ.get('QWEN_MODEL_DIR',CLONE/'model')).expanduser()
    return all(p.is_file() for p in [CLONE/'ready.json', CLONE/'private/reference-12s.wav', model/'config.json'])

def load(): return json.loads(PLAN.read_text(encoding='utf-8')) if PLAN.exists() else {'voice':'Microsoft Maria Desktop','rate':0,'scenes':[],'note':'Adicione seus vídeos com python project.py --video CAMINHO.'}
def save(data,path): path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def run(args,log=None):
    p=subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if log: log.write_text(p.stderr,encoding='utf-8')
    if p.returncode: raise RuntimeError('Processo falhou: '+p.stderr[-1200:])
    return p

def validate(plan):
    if plan['voice'] not in ['Microsoft Daniel','Microsoft Maria','Microsoft Maria Desktop',CLONE_VOICE]: raise ValueError('Voz PT-BR não suportada por este projeto.')
    if plan['voice']==CLONE_VOICE and not clone_ready(): raise ValueError('Clonagem ainda não validada neste computador.')
    if plan['voice']==CLONE_VOICE and int(plan.get('rate',0))!=0: raise ValueError('Para clonagem, use ritmo 0 e ajuste o texto ou o início. O ritmo Windows não se aplica ao clone.')
    if not -3 <= int(plan.get('rate',0)) <= 3: raise ValueError('Velocidade deve ficar entre -3 e 3.')
    if not isinstance(plan.get('scenes'),list) or len(plan['scenes'])>100: raise ValueError('Use uma lista de até 100 cenas.')
    ids=set()
    for s in plan['scenes']:
        if s['scene'] in ids: raise ValueError('Cena duplicada.')
        ids.add(s['scene'])
        if not 1<=int(s['scene'])<=999: raise ValueError('Cena inválida.')
        if pathlib.Path(s['file']).name != s['file'] or not safe_child(PROD/'raw',s['file']).is_file(): raise ValueError('Vídeo inválido.')
        if not 0<float(s['duration'])<=7200: raise ValueError('Duração deve ficar entre 0 e 7200 segundos.')
        if not s['cues']: raise ValueError('Cada cena precisa de ao menos uma fala.')
        last=-1
        for c in s['cues']:
            start=float(c['start'])
            if not 0<=start<float(s['duration']) or start<=last: raise ValueError('Tempos devem crescer dentro da cena.')
            if not isinstance(c['text'],str) or not 1<=len(c['text'].strip())<=1200: raise ValueError('Fala vazia.')
            last=start
            if c.get('audio'):
                path=safe_child(ROOT/'imports',c['audio'])
                if not path.is_relative_to((ROOT/'imports').resolve()) or not path.is_file(): raise ValueError('Áudio externo deve existir em imports/.')

def render(selected=None):
    plan=load(); validate(plan)
    if not plan['scenes']: raise ValueError('Adicione vídeos e roteiro antes de gerar.')
    out=ROOT/'output'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True)
    scenes=[s for s in plan['scenes'] if selected is None or int(s['scene'])==selected]
    if not scenes: raise ValueError('Cena inexistente.')
    jobs=[]; sources={}; manifest=[]
    cache=ROOT/'cache';cache.mkdir(exist_ok=True)
    for s in scenes:
        for i,c in enumerate(s['cues']):
            if c.get('audio'): path=ROOT/'imports'/c['audio']
            else:
                fingerprint=(CLONE/'ready.json').read_text(encoding='utf-8') if plan['voice']==CLONE_VOICE else ''
                key=hashlib.sha256((plan['voice']+str(plan['rate'])+fingerprint+c['text']).encode()).hexdigest()
                path=cache/(key+'.wav')
                if not path.exists(): jobs.append({'text':c['text'],'output':str(path)})
            sources[s['scene'],i]=path
    save({'voice':plan['voice'],'rate':plan['rate'],'items':jobs},out/'speech-job.json')
    STATE['progress_file']=str(out/'speech-job.progress.json')
    STATE['active_output']=str(out.relative_to(ROOT))
    if jobs:
        STATE['message']='Gerando falas com a voz local…'
        if plan['voice']==CLONE_VOICE:
            STATE['message']='Clonando voz em CPU. A geração pode levar vários minutos…'
            run([sys.executable,CODE/'voice_clone.py','--job',out/'speech-job.json'],out/'speech.log')
        else:
            run([shutil.which('powershell.exe') or shutil.which('pwsh.exe') or 'powershell.exe','-NoProfile','-File',CODE/'synthesize.ps1','-JobFile',out/'speech-job.json'],out/'speech.log')
    for s in scenes:
        STATE['message']=f'Montando cena {s["scene"]:02d}…'
        total=round(float(s['duration'])*48000)
        pcm=bytearray(total*2); cues=[]
        for i,c in enumerate(s['cues']):
            src=sources[s['scene'],i]
            normalized=out/f'{s["scene"]:02d}-cue-{i:02d}.wav'
            run([FF,'-hide_banner','-loglevel','error','-i',src,'-ar','48000','-ac','1','-c:a','pcm_s16le',normalized])
            with wave.open(str(normalized),'rb') as w: samples=w.readframes(w.getnframes()); seconds=w.getnframes()/48000
            start=float(c['start']); limit=float(s['cues'][i+1]['start']) if i+1<len(s['cues']) else float(s['duration'])
            if start+seconds>limit-.15: raise ValueError(f'Cena {s["scene"]}, fala {i+1}: termina em {start+seconds:.2f}s, próxima janela em {limit:.2f}s. Reduza o texto, ajuste o início ou a velocidade no plano. Nenhum áudio foi cortado.')
            offset=round(start*48000)*2
            pcm[offset:offset+len(samples)]=samples
            cues.append({'start':start,'end':round(start+seconds,3),'text':c['text'],'source':str(src)})
        audio=out/(pathlib.Path(s['file']).stem+'-voz.wav')
        with wave.open(str(audio),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(pcm)
        video=out/(pathlib.Path(s['file']).stem+'-narrado.mp4')
        run([FF,'-hide_banner','-nostdin','-i',PROD/'raw'/s['file'],'-i',audio,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','160k','-af','loudnorm=I=-16:TP=-1.5:LRA=11','-t',str(s['duration']),'-movflags','+faststart',video],out/(video.stem+'-mux.log'))
        run([FF,'-hide_banner','-nostdin','-v','error','-xerror','-i',video,'-f','null','-'],out/(video.stem+'-decode.log'))
        # Actual audio sample peak; metadata alone is not evidence of speech.
        peak=max(abs(int.from_bytes(pcm[j:j+2],'little',signed=True)) for j in range(0,len(pcm),2))
        if peak==0: raise ValueError('Áudio gerado silencioso.')
        manifest.append({'scene':s['scene'],'video':str(video),'audio':str(audio),'duration':s['duration'],'cues':cues,'audio_peak_pcm16':peak,'decode':'PASS','raw_sha256':hashlib.sha256((PROD/'raw'/s['file']).read_bytes()).hexdigest()})
        # Real frame from the newly muxed video, useful for editorial inspection.
        run([FF,'-hide_banner','-loglevel','error','-ss',str(s['cues'][0]['start']+2),'-i',video,'-frames:v','1',out/(video.stem+'.png')])
    if selected is None:
        concat=out/'concat.txt'
        concat.write_text('\n'.join("file '"+pathlib.Path(v['video']).name+"'" for v in manifest),encoding='utf-8')
        final=out/'video-completo.mp4'
        run([FF,'-hide_banner','-nostdin','-f','concat','-safe','0','-i',concat,'-c','copy','-movflags','+faststart',final],out/'concat.log')
        run([FF,'-hide_banner','-v','error','-xerror','-i',final,'-f','null','-'],out/'final-decode.log')
    save({'status':'DRAFT_FOR_VOICE_AND_SYNC_REVIEW','engine':'Qwen3-TTS local CPU' if plan['voice']==CLONE_VOICE else 'Windows System.Speech','voice':plan['voice'],'semantic_sync':'manually scheduled blocks; owner review required','scenes':manifest,'full_video':'video-completo.mp4' if selected is None else None},out/'manifest.json')
    save(plan,out/'plan-used.json')
    STATE.update(message='Rascunho gerado e decodificado. Ouça a voz e revise os tempos.',outputs=[str(out.relative_to(ROOT))])
    save({**STATE,'running':False},ROOT/'latest.json')
    return out

def worker(scene):
    try: render(scene)
    except Exception as e: STATE['message']='Falha: '+str(e)
    finally: STATE['running']=False

def clone_preview(text):
    try:
        if not clone_ready(): raise ValueError('Ambiente de clonagem ainda não validado.')
        stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        dest=CLONE/'outputs'/stamp;dest.mkdir(parents=True)
        save({'items':[{'text':text,'output':str(dest/'preview.wav')}],'max_new_tokens':384},dest/'job.json')
        STATE['message']='Gerando teste com sua voz em CPU; aguarde alguns minutos…'
        run([sys.executable,CODE/'voice_clone.py','--job',dest/'job.json'],dest/'generation.log')
        public=ROOT/'cloned-previews';public.mkdir(exist_ok=True)
        shutil.copy2(dest/'preview.wav',public/(stamp+'.wav'))
        STATE['clone_preview']='cloned-previews/'+stamp+'.wav'
        STATE['clone_preview_text']=text
        save({'path':STATE['clone_preview'],'text':text},ROOT/'clone-preview.json')
        STATE['message']='Teste de voz gerado. Ouça e compare antes de narrar as cenas.'
    except Exception as e: STATE['message']='Falha na clonagem: '+str(e)
    finally: STATE['running']=False

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def log_message(self,*a): pass
    def reply(self,data,code=200):
        b=json.dumps(data,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.end_headers();self.wfile.write(b)
    def do_GET(self):
        if self.headers.get('Host')!=urllib.parse.urlparse(ORIGIN).netloc: return self.send_error(403)
        if self.path=='/api/state':
            if STATE['running'] and STATE.get('progress_file'):
                progress_path=pathlib.Path(STATE['progress_file'])
                if progress_path.is_file():
                    details=json.loads(progress_path.read_text(encoding='utf-8'))
                    STATE['progress']=details
                    if details['phase']=='generating': STATE['message']=f"Gerando sua voz: {details['completed']}/{details['total']} blocos concluídos."
            STATE['clone_ready']=clone_ready()
            if (ROOT/'clone-preview.json').is_file() and not STATE.get('clone_preview'):
                preview=json.loads((ROOT/'clone-preview.json').read_text(encoding='utf-8'))
                STATE['clone_preview']=preview['path']
                STATE['clone_preview_text']=preview.get('text','')
            if not STATE['running'] and (ROOT/'latest.json').exists():
                latest=json.loads((ROOT/'latest.json').read_text(encoding='utf-8'))
                STATE['outputs']=latest.get('outputs',[])
            return self.reply(STATE)
        if self.path=='/api/plan': return self.reply(load())
        if self.path in ('/','/index.html'):
            body=(CODE/'web/index.html').read_text(encoding='utf-8').replace('__TOKEN__',TOKEN).encode()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body);return
        relative=urllib.parse.unquote(urllib.parse.urlparse(self.path).path).lstrip('/')
        first=relative.split('/')[0]
        if first not in {'output','imports','cloned-previews'}: return self.send_error(403)
        try: safe_child(ROOT,relative)
        except ValueError: return self.send_error(403)
        return super().do_GET()
    def do_POST(self):
        if self.headers.get('X-Studio-Token')!=TOKEN: return self.reply({'error':'Token inválido'},403)
        if self.headers.get('Origin') not in (None,ORIGIN): return self.reply({'error':'Origem inválida'},403)
        if self.headers.get('Host')!=urllib.parse.urlparse(ORIGIN).netloc: return self.reply({'error':'Host inválido'},403)
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=200000: return self.reply({'error':'Tamanho de pedido inválido'},413)
            data=json.loads(self.rfile.read(n))
            with LOCK:
                if STATE['running']: return self.reply({'error':'Aguarde a tarefa atual'},409)
                if self.path=='/api/save': validate(data);save(data,PLAN);return self.reply({'ok':True})
                if self.path=='/api/render':
                    scene=int(data['scene']) if data.get('scene') else None
                    STATE.update(running=True,message='Preparando…')
                    threading.Thread(target=worker,args=(scene,),daemon=True).start();return self.reply({'ok':True})
                if self.path=='/api/clone':
                    text=data.get('text','').strip()
                    if not 1<=len(text)<=500: raise ValueError('Teste deve ter de 1 a 500 caracteres.')
                    if not clone_ready(): raise ValueError('Clonagem ainda não validada.')
                    STATE.update(running=True,message='Preparando teste de voz…')
                    threading.Thread(target=clone_preview,args=(text,),daemon=True).start();return self.reply({'ok':True})
                return self.reply({'error':'Rota inválida'},404)
        except Exception as e: return self.reply({'error':str(e)},400)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--render',action='store_true');parser.add_argument('--scene',type=int);parser.add_argument('--serve',action='store_true');parser.add_argument('--open',action='store_true');parser.add_argument('--port',type=int,default=0);args=parser.parse_args()
    if args.render: print(render(args.scene))
    elif args.serve:
        TOKEN=secrets.token_urlsafe(24)
        ROOT.mkdir(parents=True,exist_ok=True)
        if (ROOT/'latest.json').exists():
            STATE.update(json.loads((ROOT/'latest.json').read_text(encoding='utf-8')))
            STATE['running']=False
        server=http.server.ThreadingHTTPServer(('127.0.0.1',args.port),Handler);ORIGIN=f'http://127.0.0.1:{server.server_port}'
        (ROOT/'server.json').write_text(json.dumps({'url':ORIGIN,'pid':__import__('os').getpid()}))
        print(ORIGIN,flush=True)
        if args.open:
            import webbrowser
            webbrowser.open(ORIGIN)
        server.serve_forever()
    else: parser.print_help()
