# Virtual controller page: http://127.0.0.1:2700 . Started from inside pads.py (start(press, state)) so a click and a real press
# share pads.py's memory (rows playing, toggled moves, the DnB snapshot). MiniLab side: labels from maps.py for the mode in
# minilab.mode (written by acid.py / minilab.py); a drag sets the Rack param exactly like that CC would.
import json, os, sys, time, threading, importlib, http.server
import sections as S, fx, maps
PORT, ORIGIN = 2700, 'http://127.0.0.1:2700'
cache, lock = {'t': 0.0, 'p': {}}, threading.Lock()
PRESS, ST, TURN, MODE, FLIP, MACHINE = None, None, None, None, None, None

def params(mods):                                       # Rack params per module, cached 0.5 s (the page polls every 0.5 s)
    with lock:
        if time.time() - cache['t'] > 0.5 or not mods <= set(cache['p']):
            cache['p'] = {}
            for m in mods:                                  # a module that fails reads as {}: its controls show unavailable, the page stays up
                try: cache['p'][m] = {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': m}))}
                except Exception: cache['p'][m] = {}
            if not any(cache['p'].values()): raise RuntimeError('Rack not answering')   # every module failed: /state says rack:false (cache['t'] stays stale)
            cache['t'] = time.time()
        return cache['p']
def mode():
    try: m = open(os.path.join(S.here, 'minilab.mode')).read().strip()
    except OSError: m = ''
    return m if m in maps.MODES else 'acid'
def launchpad():
    pg = ST['page']; on = ST['on'][pg]
    if S.PAGES[pg].get('synth'):                                    # Synths page: action pads, several lit per row
        import synths; P = synths.pads(ST['song']); lit = ST['slit'] | ST['held']
        rows = [dict(name=n, base=b, color=c, labels=[P[b + i][0] if b + i in P else '' for i in range(8)], on=None,
                     lit=[i for i in range(8) if b + i in lit]) for b, (n, c) in sorted(synths.ROWS.items(), reverse=True)]
    else:
        rows = [dict(name=r['name'], base=b, color=r['color'], labels=maps.pad_labels(r['samples']), on=on.get(b))
                for b, r in sorted(S.PAGES[pg]['rows'].items(), reverse=True)]
    bank = ST['bank']
    return dict(rows=rows, page=pg, pages=[p['name'] for p in S.PAGES], bank=bank, banks=len(fx.BANKS), machine=ST['machine'],
                fx=[dict(note=n, name=nm, on=nm in ST['fx']) for n, nm in sorted(fx.BANKS[bank].items())],
                color=fx.COLOR, busy=ST['busy'], hw=ST['hw'])
def minilab():
    importlib.reload(maps); m = mode(); M = maps.MODES[m]; pm, pp, off, n = M['pads']; CC = ccmap(m)
    p = params({mod for mod, *_ in CC.values()} | {pm})
    def ctl(cc):
        if cc not in CC: return dict(cc=cc, label='', pos=None, value=None)
        mod, pid, f, label = CC[cc]
        if pid not in p[mod]: return dict(cc=cc, label=label, pos=None, value=None)
        v = p[mod][pid]
        return dict(cc=cc, label=label, pos=maps.to_cc(f, v), value=round(v, 2))
    cur = round(p[pm][pp]) if pp in p[pm] else None; live = m != 'mix' or p[pm].get(5, 0) > 0.001          # mix: beat pads dark while the drum beat is off
    return dict(mode=m, title=M['title'], knobs=[ctl(c) for c in maps.KNOBS], faders=[ctl(c) for c in maps.FADERS],
                pads=[dict(i=i, label=M['pad_label'](off + i), on=live and cur == off + i) for i in range(n)], keys=M['keys'])
ccmap = lambda m: maps.mix_map() if m == 'mix' else maps.MODES[m]['cc']   # mix follows the song on show
def set_cc(cc, v):
    mod, pid, f, _ = ccmap(mode())[cc]
    S.call('vcvrack_set_params', {'moduleId': mod, 'params': [{'id': pid, 'value': f(max(0, min(127, v)))}]}); cache['t'] = 0
def set_pad(i):
    pm, pp, off, n = maps.MODES[mode()]['pads']
    if not 0 <= i < n: return
    if mode() == 'mix': maps.drum_pad(i)                                  # beat on / off / switch, as the MiniLab pads
    else: S.call('vcvrack_set_params', {'moduleId': pm, 'params': [{'id': pp, 'value': off + i}]})
    cache['t'] = 0

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype='application/json'):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Cache-Control', 'no-store')
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == '/': return self.send(200, open(os.path.join(S.here, 'board.html'), 'rb').read(), 'text/html; charset=utf-8')
        if self.path == '/state':
            out = dict(rack=True, launchpad=launchpad(), v=os.path.getmtime(os.path.join(S.here, 'board.html')))   # v: page reloads when board.html changes
            try: out['minilab'] = minilab()
            except Exception as e: out.update(rack=False, error=str(e)[:200])
            return self.send(200, out)
        self.send(404, {})
    def do_POST(self):
        if self.headers.get('Origin', ORIGIN) != ORIGIN: return self.send(403, {'ok': False})   # only this page may press
        try:
            d = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            if self.path == '/press': return self.send(200, {'ok': PRESS(int(d['note']))})
            if self.path == '/page': return self.send(200, {'ok': TURN(int(d['dir']))})
            if self.path == '/mode': return self.send(200, {'ok': MODE(str(d['mode']))})
            if self.path == '/bank': return self.send(200, {'ok': FLIP()})
            if self.path == '/machine': return self.send(200, {'ok': True, 'on': MACHINE()})
            if self.path == '/set':
                set_pad(int(d['pad'])) if 'pad' in d else set_cc(int(d['cc']), int(d['value']))
                if 'pad' in d or d.get('log', True): sys.stderr.write(time.ctime() + f' page set {mode()} {d}\n')   # pads.log: what the page moved
                return self.send(200, {'ok': True})
        except Exception as e: return self.send(500, {'ok': False, 'error': str(e)[:200]})
        self.send(404, {})

def start(press, state, turn, mode, flip, machine):
    global PRESS, ST, TURN, MODE, FLIP, MACHINE
    PRESS, ST, TURN, MODE, FLIP, MACHINE = press, state, turn, mode, flip, machine
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
