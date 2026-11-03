import json
import subprocess
import sys
import threading
import time
from pathlib import Path

LOG_FILE = Path("proxy_traffic.jsonl")
SERVER_CMD = [sys.executable, "server.py"]
log_lock = threading.Lock()   # iki işçi aynı anda dosyaya yazmasın


def log(direction, line):
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        msg = {"_raw": line.rstrip("\n")}   # bozuk satırı da kaybetme
    entry = {"ts": time.time(), "dir": direction, "msg": msg}
    with log_lock, LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def pump(src, dst, direction):
    """Bir yönün işçisi: satır oku → logla → karşıya ilet."""
    for line in src:
        log(direction, line)
        dst.write(line)
        dst.flush()
    try:
        dst.close()   # kaynak kapandıysa karşı tarafa da haber ver
    except Exception:
        pass


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")

    server = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )

    t_up = threading.Thread(target=pump, args=(sys.stdin, server.stdin, "client->server"), daemon=True)
    t_down = threading.Thread(target=pump, args=(server.stdout, sys.stdout, "server->client"), daemon=True)
    t_up.start()
    t_down.start()

    t_down.join()   # server kapanınca proxy de biter
    server.wait()


if __name__ == "__main__":
    main()
