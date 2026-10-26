"""Offline voice cloning with the owner's authorized local reference."""
import os,pathlib,json,time,argparse,hashlib
from config import workspace
ROOT=workspace()/'voice-clone'
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
os.environ['HF_HOME']=str(ROOT/'hf-cache')

def progress(job_path,**data):
    path=pathlib.Path(job_path).with_suffix('.progress.json')
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)

def synthesize(job_path):
    import torch
    import soundfile as sf
    import numpy as np
    from qwen_tts import Qwen3TTSModel
    torch.set_num_threads(4)
    torch.manual_seed(42)
    job=json.loads(pathlib.Path(job_path).read_text(encoding='utf-8-sig'))
    progress(job_path,phase='loading',completed=0,total=len(job['items']))
    reference=ROOT/'private/reference-12s.wav'
    if not reference.is_file(): raise ValueError('Referência local ausente.')
    for item in job['items']:
        output=pathlib.Path(item['output']).resolve()
        allowed=[ROOT/'outputs',ROOT.parent/'cache']
        if not any(output.is_relative_to(p.resolve()) for p in allowed): raise ValueError('Destino fora das pastas autorizadas.')
        if not 1<=len(item['text'])<=1200: raise ValueError('Cada fala deve ter até 1200 caracteres.')
    started=time.monotonic()
    print('Loading local Qwen model on CPU (float32).',flush=True)
    model_path=pathlib.Path(os.environ.get('QWEN_MODEL_DIR',ROOT/'model')).expanduser().resolve()
    model=Qwen3TTSModel.from_pretrained(str(model_path),device_map='cpu',dtype=torch.float32,attn_implementation='sdpa',local_files_only=True)
    original_generate=model.model.generate
    token_counts=[]
    def checked_generate(*args,**kwargs):
        generated=original_generate(*args,**kwargs)
        token_counts.append([len(c) for c in generated[0]])
        return generated
    model.model.generate=checked_generate
    print('Extracting local speaker reference.',flush=True)
    transcript=ROOT/'private/reference.txt'
    ref_text=transcript.read_text(encoding='utf-8').strip() if transcript.exists() else None
    prompt=model.create_voice_clone_prompt(ref_audio=str(reference),ref_text=ref_text,x_vector_only_mode=not bool(ref_text))
    rows=[]
    for index,item in enumerate(job['items']):
        progress(job_path,phase='generating',completed=index,total=len(job['items']),current=index+1)
        print(f'Generating block {index+1}/{len(job["items"])}.',flush=True)
        at=time.monotonic()
        with torch.inference_mode():
            limit=int(job.get('max_new_tokens',384))
            wavs,sr=model.generate_voice_clone(text=item['text'],language='Portuguese',voice_clone_prompt=prompt,max_new_tokens=limit,non_streaming_mode=True)
        output=pathlib.Path(item['output']);output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists(): raise ValueError('Arquivo de áudio existente preservado.')
        if not len(wavs[0]) or not np.isfinite(wavs[0]).all() or np.max(np.abs(wavs[0]))<.001:
            raise RuntimeError('Modelo retornou áudio vazio, silencioso ou inválido.')
        count=token_counts[-1][0]
        if count>=limit-1:
            rejected=output.with_suffix('.rejected.wav')
            sf.write(str(rejected),wavs[0],sr,subtype='PCM_16')
            raise RuntimeError(f'Geração alcançou o limite: {count}/{limit} tokens. Áudio preservado como rejeitado; não foi colocado no cache nem habilitado.')
        sf.write(str(output),wavs[0],sr,subtype='PCM_16')
        rows.append({'output':str(output),'duration_seconds':len(wavs[0])/sr,'sample_rate':sr,'generation_seconds':round(time.monotonic()-at,2),'generated_tokens':count,'token_limit':limit,'hit_token_limit':False,'text':item['text'],'sha256':hashlib.sha256(output.read_bytes()).hexdigest()})
        pathlib.Path(job_path).with_suffix('.partial-result.json').write_text(json.dumps({'items':rows},ensure_ascii=False,indent=2),encoding='utf-8')
        progress(job_path,phase='generating',completed=index+1,total=len(job['items']),last_audio_seconds=rows[-1]['duration_seconds'],last_generation_seconds=rows[-1]['generation_seconds'])
    report={'status':'GENERATED_AWAITING_OWNER_VOICE_REVIEW','model':'Qwen3-TTS-12Hz-0.6B-Base','device':'cpu','mode':'reference audio + transcript' if ref_text else 'x_vector_only (no reference transcript; quality may be lower)','reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),'elapsed_seconds':round(time.monotonic()-started,2),'network':'offline mode for inference; reference never uploaded','items':rows}
    pathlib.Path(job_path).with_suffix('.result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    progress(job_path,phase='complete',completed=len(rows),total=len(job['items']),elapsed_seconds=report['elapsed_seconds'])
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--job',required=True);args=parser.parse_args()
    synthesize(args.job)
