"""
DOOMPy Matchmaking Server
Run this independently:  python server.py
Listens on TCP port 9999.  Clients connect to discover / create / join lobbies.

Protocol (newline-delimited JSON):
  Client → Server:
    {"cmd": "list"}                             → get all public lobbies
    {"cmd": "create", "name": "...", "private": false, "host": "1.2.3.4"}
    {"cmd": "join",   "code": "ABCD"}           → join by 4-letter code
    {"cmd": "join_any"}                         → join a random public lobby
    {"cmd": "ping"}                             → keep-alive

  Server → Client:
    {"ok": true,  "lobbies": [...]}             → response to "list"
    {"ok": true,  "code": "ABCD", "host": "1.2.3.4", "port": 9998}
    {"ok": false, "error": "..."}
"""

import socket
import threading
import json
import random
import string
import time

import os

HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', 9999))
LOBBY_TIMEOUT = 300   # seconds before an idle lobby is purged

lobbies = {}   # code -> dict
lobbies_lock = threading.Lock()


def make_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if code not in lobbies:
            return code


def purge_old():
    while True:
        time.sleep(30)
        now = time.time()
        with lobbies_lock:
            stale = [c for c, l in lobbies.items() if now - l['ts'] > LOBBY_TIMEOUT]
            for c in stale:
                print(f'[server] purged idle lobby {c}')
                del lobbies[c]


def handle_client(conn, addr):
    print(f'[server] connection from {addr}')
    buf = ''
    try:
        while True:
            data = conn.recv(4096).decode('utf-8', errors='ignore')
            if not data:
                break
            buf += data
            while '\n' in buf:
                line, buf = buf.split('\n', 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    send(conn, {'ok': False, 'error': 'bad json'})
                    continue
                handle_msg(conn, msg)
    except Exception as e:
        print(f'[server] client {addr} error: {e}')
    finally:
        conn.close()


def handle_msg(conn, msg):
    cmd = msg.get('cmd')

    if cmd == 'ping':
        send(conn, {'ok': True})

    elif cmd == 'list':
        with lobbies_lock:
            public = [
                {'code': c, 'name': l['name'], 'players': l['players'], 'host': l['host']}
                for c, l in lobbies.items() if not l['private']
            ]
        send(conn, {'ok': True, 'lobbies': public})

    elif cmd == 'create':
        name    = msg.get('name', 'Unnamed')[:32]
        private = bool(msg.get('private', False))
        host    = msg.get('host', '')
        port    = int(msg.get('port', 9998))
        with lobbies_lock:
            code = make_code()
            lobbies[code] = {
                'name': name, 'private': private,
                'host': host, 'port': port,
                'players': 1, 'ts': time.time()
            }
        print(f'[server] lobby created: {code} "{name}" private={private}')
        send(conn, {'ok': True, 'code': code})

    elif cmd == 'join':
        code = msg.get('code', '').upper()
        with lobbies_lock:
            lobby = lobbies.get(code)
            if lobby:
                lobby['players'] += 1
                lobby['ts'] = time.time()
                send(conn, {'ok': True, 'code': code,
                            'host': lobby['host'], 'port': lobby['port']})
            else:
                send(conn, {'ok': False, 'error': 'lobby not found'})

    elif cmd == 'join_any':
        with lobbies_lock:
            public = [(c, l) for c, l in lobbies.items() if not l['private']]
        if public:
            code, lobby = random.choice(public)
            with lobbies_lock:
                if code in lobbies:
                    lobbies[code]['players'] += 1
                    lobbies[code]['ts'] = time.time()
            send(conn, {'ok': True, 'code': code,
                        'host': lobby['host'], 'port': lobby['port']})
        else:
            send(conn, {'ok': False, 'error': 'no public lobbies'})

    else:
        send(conn, {'ok': False, 'error': f'unknown cmd: {cmd}'})


def send(conn, data):
    try:
        conn.sendall((json.dumps(data) + '\n').encode('utf-8'))
    except Exception:
        pass


if __name__ == '__main__':
    threading.Thread(target=purge_old, daemon=True).start()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen()
        print(f'[server] DOOMPy matchmaking server listening on {HOST}:{PORT}')
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
