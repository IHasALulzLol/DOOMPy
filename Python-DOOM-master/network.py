"""
DOOMPy Network Client — HTTP edition
Talks to the Flask matchmaking server via plain HTTP requests.
"""

import socket
import threading
import json
import time
import requests   # pip install requests

# ── change this to your Render URL after deploying ───────────────────────────
MATCHMAKING_URL = 'https://doombetter.onrender.com'
# For local testing use: 'http://127.0.0.1:9999'

GAME_PORT = 9998   # UDP port for in-game peer data


# ── matchmaking ───────────────────────────────────────────────────────────────

class MatchmakingClient:

    def __init__(self, base_url=MATCHMAKING_URL):
        self.base = base_url.rstrip('/')
        self._session = requests.Session()
        self._session.timeout = 6

    def connect(self):
        """Test connection — raises on failure."""
        r = self._session.get(f'{self.base}/ping')
        r.raise_for_status()

    def close(self):
        self._session.close()

    def list_lobbies(self):
        r = self._session.get(f'{self.base}/list')
        data = r.json()
        if data.get('ok'):
            return data.get('lobbies', [])
        raise RuntimeError(data.get('error', 'unknown error'))

    def create_lobby(self, name: str, private: bool, local_ip: str, port: int = GAME_PORT):
        r = self._session.post(f'{self.base}/create', json={
            'name': name, 'private': private, 'host': local_ip, 'port': port
        })
        data = r.json()
        if data.get('ok'):
            return data['code']
        raise RuntimeError(data.get('error', 'unknown error'))

    def join_by_code(self, code: str):
        """Returns (host_ip, port)."""
        r = self._session.post(f'{self.base}/join', json={'code': code.upper()})
        data = r.json()
        if data.get('ok'):
            return data['host'], data['port']
        raise RuntimeError(data.get('error', 'lobby not found'))

    def join_any(self):
        """Returns (code, host_ip, port)."""
        r = self._session.post(f'{self.base}/join_any')
        data = r.json()
        if data.get('ok'):
            return data['code'], data['host'], data['port']
        raise RuntimeError(data.get('error', 'no public lobbies'))

    def heartbeat(self, code: str):
        try:
            self._session.post(f'{self.base}/heartbeat', json={'code': code})
        except Exception:
            pass


def get_local_ip():
    """Best-effort local LAN IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


# ── UDP game-state layer ──────────────────────────────────────────────────────

class GameNetwork:
    """
    UDP socket for sending/receiving player state each frame.
    Packet format: JSON  {"id": str, "x": float, "y": float, "angle": float, "hp": int}
    """

    def __init__(self, port=GAME_PORT):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', port))
        self.sock.setblocking(False)
        self.peers = {}    # addr -> latest state dict
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

    def send_state(self, peer_addr, state: dict):
        payload = (json.dumps(state) + '\n').encode('utf-8')
        try:
            self.sock.sendto(payload, peer_addr)
        except Exception:
            pass

    def _recv_loop(self):
        while self._running:
            try:
                data, addr = self.sock.recvfrom(4096)
                state = json.loads(data.decode('utf-8').strip())
                self.peers[addr] = state
            except BlockingIOError:
                time.sleep(0.005)
            except Exception:
                pass

    def stop(self):
        self._running = False
        self.sock.close()
