# Barcode Gateway

A small Flask app that turns USB HID barcode scanners into a live log and forwards each scan to another service (for example a grocery/Shelf API).

## What it does

- Watches plugged-in **HID keyboard** scanners (typical USB “wedge” guns).
- Shows each code **immediately** on Arriving scans (no refresh).
- If the payload is a web address (`http://` or `https://`, usual 2D / QR), it is **clickable**.
- Forwards in the background: `{ "slug": "<reader>", "barcode": "<code>" }` with `Authorization: Bearer <key>`.
- Supports **more than one** scanner. Each has a name and a slug so the far end knows which gun it was.

## Pages

| Path | Access | What |
| --- | --- | --- |
| `/` | No login | Latest scan, filter by reader, history, live updates |
| `/config` | HTTP basic auth (`admin`) | Endpoint, API key, add/edit/enable scanners, send a test |
| `/api/scans` | No login | Same history as JSON |

Saving on Config reloads listener threads at once. You do not need a process restart for that.

Do not put this site on the public internet without your own auth in front: scans and the JSON API are open to anyone who can reach the port.

## Setup

Copy the example config and keep the real file **off git**:

```bash
cp config.example.json config.json
chmod 600 config.json
```

Fill in `endpoint` and `api_key`. Set `admin_hash` with Werkzeug (`generate_password_hash`) or use Config after you bootstrap an admin hash once.

`config.json` and `scans.csv` are gitignored. They hold the API key, password hash, LAN URLs, and every barcode you have scanned.

## Everyday files

- `config.json` — endpoint, API key, admin hash, scanner list (mode 600).
- `scans.csv` — time, code, reader, forward result.

## Docker

Typical run: bind-mount this directory at `/app`, publish a port, and give the container `/dev` and `/sys` so hot-plugged hidraw scanners appear. Rebuild the image only when Python dependencies change:

```bash
docker build -t barcode-gateway:1.0 .
docker restart barcode-gateway
```

Python modules load at start. After you edit `.py` files, restart the container. HTML templates are reread on the next request.

```bash
docker logs -f barcode-gateway
```

## Code map

| File | Job |
| --- | --- |
| `app.py` | Web pages and startup |
| `config.py` | Load/save `config.json`, admin login, config form actions |
| `reader.py` | Find hidraw keyboards, decode scans, one thread per gun |
| `sender.py` | Queue and POST to the endpoint (retries, test button) |
| `store.py` | Live list, CSV log, streaming updates to the browser |
| `templates/` | Arriving scans and Config HTML |
