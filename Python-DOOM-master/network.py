"""
DOOMPy Network Client
Handles:
  - Matchmaking (talking to server.py)
  - Peer game socket (UDP, talking to the host's game port)
"""

import socket
import threading
import json
import time

MATCHMAKING_HOST = '127.0.0.1'   # change to your server's IP / domain
MATCHMAKING_PORT = 9999
GAME_PORT = 9998                  # local UDP port for game data


class MatchmakingClient:
    """Synchronous TCP client for the matchmaking server."""

    def __init__(self, host=MATCHMAKING_HOST, port=MATCHMAKING_PORT):
        self.host = host
        self.port = port
        self._sock = None
        self._buf = ''

    def connect(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(5)
        self._sock.connect((self.host, self.port))
        self._buf = ''

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _send(self, data: dict) -> dict:
        payload = json.dumps(data) + '\n'
        self._sock.sendall(payload.encode('utf-8'))
        # read until newline
        while '\n' not in self._buf:
            chunk = self._sock.recv(4096).decode('utf-8', errors='ignore')
            if not chunk:
                raise ConnectionError('server closed connection')
            self._buf += chunk
        line, self._buf = self._buf.split('\n', 1)
        return json.loads(line.strip())

    def list_lobbies(self):
        """Returns list of public lobbies or raises on error."""
        r = self._send({'cmd': 'list'})
        if r.get('ok'):
            return r.get('lobbies', [])
        raise RuntimeError(r.get('error', 'unknown error'))

    def create_lobby(self, name: str, private: bool, local_ip: str, port: int = GAME_PORT):
        r = self._send({'cmd': 'create', 'name': name,
                        'private': private, 'host': local_ip, 'port': port})
        if r.get('ok'):
            return r['code']
        raise RuntimeError(r.get('error', 'unknown error'))

    def join_by_code(self, code: str):
        """Returns (host_ip, port) tuple."""
        r = self._send({'cmd': 'join', 'code': code.upper()})
        if r.get('ok'):
            return r['host'], r['port']
        raise RuntimeError(r.get('error', 'lobby not found'))

    def join_any(self):
        """Returns (code, host_ip, port) for a random public lobby."""
        r = self._send({'cmd': 'join_any'})
        if r.get('ok'):
            return r['code'], r['host'], r['port']
        raise RuntimeError(r.get('error', 'no public lobbies'))


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


# ---------------------------------------------------------------------------
# Lightweight UDP game-state layer (placeholder for actual multiplayer loop)
# ---------------------------------------------------------------------------

class GameNetwork:
    """
    UDP socket for sending/receiving player state each frame.
    Format: JSON line → {"id": str, "x": float, "y": float, "angle": float, "hp": int}
    """

    def __init__(self, port=GAME_PORT):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', port))
        self.sock.setblocking(False)
        self.peers = {}       # addr -> latest state dict
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
