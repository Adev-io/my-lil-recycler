# usage: audio_swap.py laptop | restore [patch.vcv]   (Rack must be closed; default patch: dj-set.vcv)
# Finds every Core AudioInterface block in the patch (no fixed module ids), so it follows the patch as it changes.
# laptop:  the first audio interface -> WASAPI "Speakers (Realtek(R) Audio)" 48 kHz. All original blocks are saved to
#          audio_orig.json first (never overwritten while it exists).
# restore: put the saved blocks back. No audio_orig.json: take them from the newest dj-set.bak-pre-audiolaptop-*.vcv
#          beside the patch. A saved block whose module is not in the patch is skipped and reported.
import glob, json, os, subprocess, sys, tempfile, time
here = os.path.dirname(os.path.abspath(__file__)); TAR = r'C:\Windows\System32\tar.exe'
mode = sys.argv[1] if len(sys.argv) > 1 else ''
LAPTOP = 'Speakers (Realtek(R) Audio)'
if mode not in ('laptop', 'restore'): sys.exit('usage: audio_swap.py laptop | restore [patch.vcv]')
explicit = len(sys.argv) > 2
PATCH = sys.argv[2] if explicit else os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')
if not explicit and 'Rack.exe' in subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Rack.exe'], capture_output=True, text=True).stdout:
    sys.exit('Rack is running: close it first (it would overwrite the patch on exit)')
orig = os.path.join(here, 'audio_orig.json')

def unpack(path, d):
    subprocess.run([TAR, '-xf', path, '-C', d], check=True)
    return json.load(open(os.path.join(d, 'patch.json'), encoding='utf-8'))
def blocks(p): return {str(m['id']): m for m in p['modules'] if m['plugin'] == 'Core' and m['model'].startswith('AudioInterface')}

with tempfile.TemporaryDirectory() as w:
    p = unpack(PATCH, w); A = blocks(p)
    if not A: sys.exit('no Core AudioInterface module in ' + PATCH)
    if mode == 'laptop':
        if not os.path.exists(orig): json.dump({k: m['data']['audio'] for k, m in A.items()}, open(orig, 'w'), indent=1)
        A[next(iter(A))]['data']['audio'].update(driver=6, deviceName=LAPTOP, sampleRate=48000.0, blockSize=512)
    else:
        if os.path.exists(orig): o = json.load(open(orig))
        else:
            o = None
            for bk in reversed(sorted(glob.glob(PATCH.replace('.vcv', '.bak-pre-audiolaptop-*.vcv')))):   # newest first; a backup already on the laptop speakers is not the original
                with tempfile.TemporaryDirectory() as b: o = {k: m['data']['audio'] for k, m in blocks(unpack(bk, b)).items()}
                if any(a['deviceName'] != LAPTOP for a in o.values()): print('restoring from', os.path.basename(bk)); break
                o = None
            if not o: sys.exit('no audio_orig.json and no .bak-pre-audiolaptop-* beside the patch with a non-laptop device: nothing to restore from')
        hit = [k for k in A if k in o]
        for k in o:
            if k not in A: print('skipped (module not in this patch):', k)
        if not hit: sys.exit('none of the saved audio blocks match a module in this patch')
        for k in hit: A[k]['data']['audio'] = o[k]
    ts = time.strftime('%Y%m%d-%H%M%S'); bak = PATCH.replace('.vcv', f'.bak-pre-audio{mode}-{ts}.vcv')
    with open(PATCH, 'rb') as s, open(bak, 'wb') as d: d.write(s.read())
    json.dump(p, open(os.path.join(w, 'patch.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    new = PATCH + '.new'; subprocess.run([TAR, '--zstd', '-cf', new, '-C', w, 'patch.json', 'modules'], check=True)
    with tempfile.TemporaryDirectory() as c: chk = unpack(new, c); q, n = blocks(chk), len(chk['modules'])   # read the repacked file back before it replaces the patch
    os.replace(new, PATCH)
print('audio now:', [(k, m['data']['audio']['driver'], m['data']['audio']['deviceName']) for k, m in q.items()], '| modules', n, '| backup', os.path.basename(bak))
