# Tiny JSON-RPC client for the My lil MCP server (session's MCP connection failed at startup).
# usage: py -3 rack.py list | py -3 rack.py call <tool> '<json args>'
import json, sys, urllib.request

URL = 'http://127.0.0.1:2600/mcp'

def rpc(method, params=None, timeout=30):
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}).encode()
    req = urllib.request.Request(URL, body, {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'})
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
    if raw.startswith('event:') or raw.startswith('data:'):   # SSE framing
        raw = next(l[5:] for l in raw.splitlines() if l.startswith('data:'))
    return json.loads(raw)

if sys.argv[1] == 'list':
    for t in rpc('tools/list')['result']['tools']:
        print(t['name'], '-', t.get('description', '')[:110])
else:
    args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    r = rpc('tools/call', {'name': sys.argv[2], 'arguments': args}, timeout=float(sys.argv[4]) if len(sys.argv) > 4 else 30)
    if 'error' in r: print('ERROR', r['error']); sys.exit(1)
    for c in r['result'].get('content', []): print(c.get('text', c))
