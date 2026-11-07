# Relaunch pads.py whenever it dies, until pads.stop exists (a deliberate stop from start.py). usage: pythonw pads_keep.py [section]
# After a crash the relaunch gets PADS_RESPAWN=1: pads.py then leaves the mixer strips alone (sections.base(strips=False)).
# 5 deaths within 60 s = crash loop: log 'giving up' and stop (a loop would flash the Launchpad and hammer Rack).
import os, subprocess, sys, time
here = os.path.dirname(os.path.abspath(__file__)); STOP = os.path.join(here, 'pads.stop')
sec = sys.argv[1] if len(sys.argv) > 1 else '0'
env = dict(os.environ); deaths = []
def log(s):
    with open(os.path.join(here, 'pads.log'), 'a') as f: f.write(time.ctime() + ' ' + s + '\n')
while not os.path.exists(STOP):
    t = time.time(); ran = True
    try: rc = subprocess.run([sys.executable, 'pads.py', sec], cwd=here, env=env).returncode; what = f'exit {rc} (0x{rc & 0xFFFFFFFF:X})'
    except Exception as e: ran = False; what = f'launch failed: {e!r}'            # pads.py never started: not a crash respawn, always wait 5 s
    if os.path.exists(STOP): break
    now = time.time(); deaths = [d for d in deaths if now - d < 60] + [now]
    if len(deaths) >= 5: log(f'pads.py died, {what}: 5 deaths in 60 s, giving up'); break
    log(f'pads.py died, {what}: restarting')
    if ran: env['PADS_RESPAWN'] = '1'
    if not ran or now - t < 5: time.sleep(5)
