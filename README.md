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

The image is Alpine Python (multi-stage: compiler only in the build layer). App code is copied in; `config.json` and `scans.csv` stay on the host.

**This machine** (Pi 5, Pi 3B, or an Intel/AMD PC — Docker picks the host arch):

```bash
test -f config.json || cp config.example.json config.json
chmod 600 config.json
touch scans.csv
docker compose up -d --build
docker compose logs -f
```

**One image for all boards** (amd64, arm64 for Pi 5 / 64-bit Pi 3B, arm/v7 for 32-bit Pi 3B):

```bash
docker buildx create --name multi --use 2>/dev/null || docker buildx use multi
docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 \
  -t YOURUSER/barcode-gateway:1.0 --push .
```

On each machine, set `image:` in `docker-compose.yml` to that tag and run `docker compose up -d`.

Python modules load at start. After you edit `.py` files, rebuild or restart. HTML templates are inside the image, so change them and rebuild.

```bash
docker compose logs -f
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
