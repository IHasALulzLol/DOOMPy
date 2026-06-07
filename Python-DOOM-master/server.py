"""
DOOMPy Matchmaking Server — Flask HTTP edition
Deploy on Render (free tier) or run locally with:  python server.py

Endpoints:
  GET  /list                         → all public lobbies
  POST /create  {name, private, host, port}
  POST /join    {code}               → join by code
  POST /join_any                     → random public lobby
  POST /heartbeat {code}             → keep lobby alive
  GET  /ping                         → health check
"""

import os
import random
import string
import time
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

LOBBY_TIMEOUT = 300   # seconds of silence before a lobby is purged

lobbies = {}          # code -> dict
lock = threading.Lock()


# ── helpers ──────────────────────────────────────────────────────────────────

def make_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if code not in lobbies:
            return code


def purge_loop():
    while True:
        time.sleep(30)
        now = time.time()
        with lock:
            stale = [c for c, l in lobbies.items() if now - l['ts'] > LOBBY_TIMEOUT]
            for c in stale:
                print(f'[server] purged idle lobby {c}')
                del lobbies[c]


threading.Thread(target=purge_loop, daemon=True).start()


# ── routes ───────────────────────────────────────────────────────────────────

@app.get('/ping')
def ping():
    return jsonify(ok=True)


@app.get('/list')
def list_lobbies():
    with lock:
        public = [
            {'code': c, 'name': l['name'],
             'players': l['players'], 'host': l['host']}
            for c, l in lobbies.items() if not l['private']
        ]
    return jsonify(ok=True, lobbies=public)


@app.post('/create')
def create():
    data    = request.get_json(force=True) or {}
    name    = str(data.get('name', 'Unnamed'))[:32]
    private = bool(data.get('private', False))
    host    = str(data.get('host', ''))
    port    = int(data.get('port', 9998))
    with lock:
        code = make_code()
        lobbies[code] = {
            'name': name, 'private': private,
            'host': host, 'port': port,
            'players': 1, 'ts': time.time()
        }
    print(f'[server] created lobby {code} "{name}" private={private} host={host}')
    return jsonify(ok=True, code=code)


@app.post('/join')
def join():
    data = request.get_json(force=True) or {}
    code = str(data.get('code', '')).upper()
    with lock:
        lobby = lobbies.get(code)
        if not lobby:
            return jsonify(ok=False, error='lobby not found'), 404
        lobby['players'] += 1
        lobby['ts'] = time.time()
        return jsonify(ok=True, code=code, host=lobby['host'], port=lobby['port'])


@app.post('/join_any')
def join_any():
    with lock:
        public = [(c, l) for c, l in lobbies.items() if not l['private']]
    if not public:
        return jsonify(ok=False, error='no public lobbies'), 404
    code, lobby = random.choice(public)
    with lock:
        if code in lobbies:
            lobbies[code]['players'] += 1
            lobbies[code]['ts'] = time.time()
    return jsonify(ok=True, code=code, host=lobby['host'], port=lobby['port'])


@app.post('/heartbeat')
def heartbeat():
    data = request.get_json(force=True) or {}
    code = str(data.get('code', '')).upper()
    with lock:
        if code in lobbies:
            lobbies[code]['ts'] = time.time()
            return jsonify(ok=True)
    return jsonify(ok=False, error='lobby not found'), 404


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9999))
    print(f'[server] DOOMPy matchmaking listening on port {port}')
    app.run(host='0.0.0.0', port=port)
