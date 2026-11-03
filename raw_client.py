import json
import subprocess
import time
from pathlib import Path

LOG_FILE = Path("traffic.jsonl")
SERVER_CMD = ["uv", "run", "python", "proxy.py"]


def log(direction, msg):
    """Her fişi dosyanın sonuna bir satır olarak ekler (append-only)."""
    entry = {"ts": time.time(), "dir": direction, "msg": msg}
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def send(proc, msg):
    log("client->server", msg)
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def wait_response(proc, req_id):
    """Doğru id'li cevap gelene kadar satır okur; aradaki her şeyi loglar."""
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("Server kapandı, server_stderr.log dosyasına bak")
        msg = json.loads(line)
        log("server->client", msg)
        if msg.get("id") == req_id:
            return msg


def request(proc, req_id, method, params=None):
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    send(proc, msg)
    return wait_response(proc, req_id)


def show(title, obj):
    print(f"\n=== {title} ===")
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main():
    proc = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=open("server_stderr.log", "a"),
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    try:
        # 1) Tanışma
        r = request(proc, 1, "initialize", {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "raw-client", "version": "0.1"},
        })
        show("initialize", r)

        # 2) "Hazırım" bildirimi (id yok, cevap beklenmez)
        send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        # 3) Aletleri listele
        r = request(proc, 2, "tools/list")
        show("tools/list", r)

        # 4) Normal çağrı
        r = request(proc, 3, "tools/call",
                    {"name": "add", "arguments": {"a": 2, "b": 3}})
        show("add(2, 3)", r)

        # 5) Inspector'ın engellediği çağrı: formu atlatıp ham JSON gönderiyoruz
        r = request(proc, 4, "tools/call",
                    {"name": "add", "arguments": {"a": "merhaba", "b": 3}})
        show("add('merhaba', 3)", r)

        # 6) Sızıntı yapan alet
        r = request(proc, 5, "tools/call",
                    {"name": "read_note", "arguments": {"name": "test"}})
        show("read_note('test')", r)
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
