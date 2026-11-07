# Session start in one shot: Rack on dj-set.vcv, wait for the My lil MCP server, (re)start pads.py at a section.
# usage: py -3 start.py [section=0]
import os, subprocess, sys, time
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
RACK = r'C:\Program Files\VCV\Rack2Free\Rack.exe'
PATCH = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')
PYW = r'C:\Users\Arikl\AppData\Local\Programs\Python\Python311\pythonw.exe'      # 3.11 has mido + rtmidi; bare pythonw (3.14) does not
STOP, LOG = os.path.join(here, 'pads.stop'), os.path.join(here, 'pads.log')
ps = lambda cmd: subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, text=True).stdout.split()
rack_up = lambda: bool(ps("(Get-Process Rack -ErrorAction SilentlyContinue).Id"))
pads_pids = lambda: ps("Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object CommandLine -match 'pads[.]py' | ForEach-Object ProcessId")
if rack_up(): print('Rack already running (plain launch restores the autosave; fine if it was dj-set.vcv)')
else: subprocess.Popen([RACK, PATCH]); print('Rack launched on', os.path.basename(PATCH))
for i in range(120):                                          # the MCP answers only once the audio engine runs (interface present)
    try: rpc('tools/list', timeout=2); break
    except Exception: time.sleep(1); print('.', end='', flush=True)
else: sys.exit('\nMCP never answered in 120 s: Yamaha off? (no audio device = idle engine = no MCP; `audio_swap.py laptop` for laptop speakers)')
print(f'\nMCP up after {i} s')
if pads_pids():
    open(STOP, 'w').close()
    for _ in range(40):
        if not pads_pids(): break
        time.sleep(0.25)
    print('old pads.py stopped')
if os.path.exists(STOP): os.remove(STOP)
n = len(open(LOG, encoding='utf-8', errors='replace').readlines()) if os.path.exists(LOG) else 0
subprocess.Popen([PYW, 'pads.py', sys.argv[1] if len(sys.argv) > 1 else '0'], cwd=here); time.sleep(5)
new = open(LOG, encoding='utf-8', errors='replace').readlines()[n:]
print(''.join(new[-3:]).rstrip() or 'pads.py wrote nothing yet')
if any('StopIteration' in l for l in new): print('Launchpad not found: plug it in (Programmer mode), then `py -3 start.py` again')
elif not any(' start ' in l for l in new): print('pads.py did not report a start: see pads.log')
else: print('ready: row 1 = vocals, row 2 = keys')
ML, MLSTOP = os.path.join(here, 'minilab.log'), os.path.join(here, 'minilab.stop')   # MiniLab 3: faders = volumes, knobs = filters
ml_pids = lambda: ps("Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object CommandLine -match 'minilab[.]py' | ForEach-Object ProcessId")
if ml_pids():
    open(MLSTOP, 'w').close()
    for _ in range(40):
        if not ml_pids(): break
        time.sleep(0.25)
if os.path.exists(MLSTOP): os.remove(MLSTOP)
# the MiniLab program for the saved mode (minilab.mode: mix = drums + mix map, acid = Synths, env = Acid Env); pads.py does the
# swap (acid / env -> acid.py <mode>), the same as its Drums / Keys / User buttons. Switch later with those buttons or on the page.
import json, urllib.request
MF = os.path.join(here, 'minilab.mode'); m = open(MF).read().strip() if os.path.exists(MF) else 'mix'
logf = os.path.join(here, 'acid.log' if m in ('acid', 'env') else 'minilab.log')
n = len(open(logf, encoding='utf-8', errors='replace').readlines()) if os.path.exists(logf) else 0
try: urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:2700/mode', data=json.dumps({'mode': m}).encode(),
                                                  headers={'Content-Type': 'application/json'}), timeout=10)
except Exception as e: print('minilab: page server not answering', e)
time.sleep(6)
new = open(logf, encoding='utf-8', errors='replace').readlines()[n:] if os.path.exists(logf) else []
print(f'minilab ({m}): ' + ('ready' if any(' start' in l for l in new) else 'not started (plugged in?) see ' + os.path.basename(logf)))
