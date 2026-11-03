# zt-mcp-lab

ZT-MCP bitirme projesinin (**A Zero-Trust Policy Proxy and Anomaly Detection Gateway for MCP**) laboratuvar deposu.

Amaç: Bir MCP istemcisi ile MCP sunucusu arasındaki trafiği **ham JSON-RPC seviyesinde** görmek ve araya **ayrı bir proxy** koymak. Gateway'in güvenlik kontrolleri ileride bu proxy'nin içine eklenecek.

---

## Mimari

```
raw_client.py  ──stdin──▶  proxy.py  ──stdin──▶  server.py
     ▲         ◀──stdout──     │     ◀──stdout──
     │                         │
traffic.jsonl          proxy_traffic.jsonl       server_stderr.log
(client'ın gördüğü)    (proxy'nin gördüğü)       (server hataları)
```

| Dosya | Görevi |
|---|---|
| `server.py` | Demo MCP sunucusu. İki tool içerir: `add(a, b)` ve `read_note(name)`. `read_note` veri sızıntısı testi için **bilerek** sahte bir API anahtarı döndürür. |
| `proxy.py` | Şeffaf stdio proxy. `server.py`'yi başlatır, iki thread ile iki yönü dinler, her mesajı `proxy_traffic.jsonl` dosyasına loglar ve **hiçbir şeyi değiştirmeden** iletir. |
| `raw_client.py` | Ajanın yerini tutan istemci. SDK kullanmadan ham JSON-RPC mesajları gönderir. `proxy.py`'yi başlatır ve tüm akışı sırayla dener. |

Neden proxy? Güvenlik kontrolü server'ın koduna yazılırsa sadece o server korunur. Proxy ise herhangi bir MCP server'ın önüne kod değiştirmeden konabilir. Zero-trust yaklaşımında server'a güvenilmez, denetimi dış katman yapar.

---

## Kurulum

Gereksinimler: Python 3.12, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/berrayckts/zt-mcp-lab.git
cd zt-mcp-lab
uv sync          # .venv oluşturur, mcp[cli] paketini kurar
```

> Not: Proje **MCP Python SDK 2.x** kullanır (`from mcp.server import MCPServer`). `mcp<2` sürümünde bu import çalışmaz.

VS Code kullanıyorsanız:
1. Klasörü açın ve **Trust** deyin (Restricted Mode'dan çıkın).
2. Microsoft'un **Python** eklentisini kurun.
3. `Ctrl+Shift+P` → **Python: Select Interpreter** → `./.venv/bin/python` seçin.

---

## Çalıştırma

```bash
uv run python raw_client.py
```

Tek komut yeterli. `raw_client.py` proxy'yi, proxy de server'ı kendisi başlatır. **`server.py` ve `proxy.py`'yi ayrıca çalıştırmayın.** Onlar stdin'den mesaj bekler ve terminalde boş duruyormuş gibi görünürler.

Server'ı görsel arayüzle denemek için (opsiyonel):

```bash
npx @modelcontextprotocol/inspector uv run python server.py
```

---

## Akış ve beklenen çıktı

`raw_client.py` sırasıyla şunları gönderir:

| # | Mesaj | Ne test ediliyor | Beklenen sonuç |
|---|---|---|---|
| 1 | `initialize` | El sıkışma, sürüm anlaşması | `protocolVersion: 2025-11-25`, server yetenekleri |
| 2 | `notifications/initialized` | Bildirim (id yok, cevap beklenmez) | Cevap gelmez |
| 3 | `tools/list` | Tool adları, açıklamaları, şemaları | `add` ve `read_note` |
| 4 | `tools/call add(2, 3)` | Normal çağrı | `"5"`, `isError: false` |
| 5 | `tools/call add("merhaba", 3)` | Yanlış veri tipi | Pydantic doğrulama hatası, `isError: true` |
| 6 | `tools/call read_note("test")` | Hassas veri sızıntısı | Cevapta `gizli_api_key=sk-test-123` görünür |

Her istek bir `id` taşır. Cevap aynı `id` ile döner, istemci cevabı bu sayede eşleştirir.

---

## Bulgular

- **`tools/list` açıklamaları modele olduğu gibi gider.** Tool poisoning saldırısı bu `description` alanına gizli talimat yazmaktır. Gateway'in ilk denetleyeceği yer burası.
- **`listChanged: false`** tool listesinin oturum boyunca değişmeyeceğini söyler. `true` olursa server listeyi sonradan değiştirebilir (rug pull). Gateway ilk listeyi saklayıp karşılaştırmalı.
- **Tool hataları JSON-RPC `error` olarak değil, `result` içinde `isError: true` olarak döner.** Gateway bu iki hata türünü ayrı ele almalı.
- **İstemci tarafı kontrol güvenlik değildir.** Inspector `add("merhaba", 3)` çağrısını formda engelliyor, ama ham JSON ile bu kontrol atlatılabiliyor.
- **Secret iki alanda birden sızıyor:** `content[].text` ve `structuredContent`. Yanıt filtresi JSON'un tamamını taramalı.
- **Loglar da sızıntı noktası.** Proxy şu an her şeyi açık metin olarak logluyor. Bu yüzden `*.jsonl` ve `*.log` dosyaları `.gitignore` içinde, repoya gönderilmiyor.

### Proxy gecikmesi (referans ölçüm)

Aynı mesajın `traffic.jsonl` ve `proxy_traffic.jsonl` dosyalarındaki zaman damgaları farkından hesaplandı (2 çalıştırma × 4 istek).

| Ölçüm | Değer |
|---|---|
| Proxy ek gecikmesi (gidiş + dönüş, ortalama) | **~0.235 ms** (0.18 – 0.34 ms) |
| Server işlem süresi, normal çağrı | 1.0 – 1.8 ms |
| Server işlem süresi, tip hatası | 5.9 – 7.8 ms |
| Proxy + server açılışı | ~0.5 sn |

Şeffaf proxy'nin maliyeti ihmal edilebilir. Güvenlik katmanları (regex, embedding, yerel LLM) eklendikçe bu değer referans olarak kullanılacak. Ölçüm sayısı az, kesin sonuç için daha çok tekrar gerekiyor.

---

## Log formatı

`traffic.jsonl` ve `proxy_traffic.jsonl` dosyalarında her satır bir JSON nesnesidir:

```json
{"ts": 1792847586.755, "dir": "client->server", "msg": {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "add", "arguments": {"a": 2, "b": 3}}}}
```

- `ts`: Unix zaman damgası (saniye)
- `dir`: Mesajın yönü (`client->server` veya `server->client`)
- `msg`: Ham JSON-RPC mesajı

Loglar **append-only**. Her çalıştırma dosyanın sonuna eklenir, eski kayıtlar silinmez.

---

## Sonraki adımlar

- [ ] Proxy loglarında regex ile hassas veri maskeleme (`[REDACTED]`)
- [ ] Proxy'de ilk engelleme kuralı: izinli tool listesi, argüman şema kontrolü, `ALLOWED` / `BLOCKED` audit kaydı
- [ ] Engellenen çağrıya `isError: true` veya JSON-RPC `error` döndürme
- [ ] Eksik test senaryoları: eksik parametre, olmayan tool, bağlantının kopması
- [ ] Tool listesi değişim kontrolü (rug pull)
- [ ] Dockerfile

---

## Kaynaklar

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
