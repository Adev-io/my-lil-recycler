# Relaunch pads.py whenever it dies, until pads.stop exists (a deliberate stop from start.py). usage: pythonw pads_keep.py [section]
# After a crash the relaunch gets PADS_RESPAWN=1: pads.py then leaves the mixer strips alone (sections.base(strips=False)).
import os, subprocess, sys, time
here = os.path.dirname(os.path.abspath(__file__)); STOP = os.path.join(here, 'pads.stop')
sec = sys.argv[1] if len(sys.argv) > 1 else '0'
env = dict(os.environ)
while not os.path.exists(STOP):
    t = time.time(); rc = subprocess.run([sys.executable, 'pads.py', sec], cwd=here, env=env).returncode
    if os.path.exists(STOP): break
    with open(os.path.join(here, 'pads.log'), 'a') as f: f.write(time.ctime() + f' pads.py died, exit {rc} (0x{rc & 0xFFFFFFFF:X}): restarting\n')
    env['PADS_RESPAWN'] = '1'
    if time.time() - t < 5: time.sleep(5)
