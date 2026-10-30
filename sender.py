"""Sender: background forward queue/worker, POST with retries, send_test."""
import json, time, queue, threading, urllib.request, urllib.error
import config, store
fwdq = queue.Queue()

# --- Forward the barcode to the endpoint ------------------------------------
def forward(slug, code, tries=3, endpoint=None, api_key=None):
    """POST {slug, barcode} to the endpoint with Bearer key. Returns (ok, text)."""
    # get the endpoint from the config
    ep = config.conf.get('endpoint', '') if endpoint is None else endpoint
    # get the api key from the config
    key = config.conf.get('api_key', '') if api_key is None else api_key
    if not ep: return False, 'no endpoint'
    # create the body
    body = json.dumps({'slug': slug, 'barcode': code}).encode()
    # initialize the last error
    last = ''
    # loop through the tries
    for i in range(tries):
        req = urllib.request.Request(ep, data=body, method='POST', headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp: return True, 'HTTP %d' % resp.status
        except urllib.error.HTTPError as e:
            last = 'HTTP %d' % e.code
            if e.code < 500: return False, last  # client error: don't retry
        except Exception as e: last = type(e).__name__ + ': ' + str(getattr(e, 'reason', e))[:80]
        if i < tries - 1: time.sleep(1 + i)
    return False, last

def send_test(reader, barcode='TEST'): 
    return forward(reader.get('slug', ''), barcode, tries=1)

def enqueue(scan, slug): 
    fwdq.put((scan, slug))

def worker():
    while True:
        s, slug = fwdq.get()
        ok, txt = forward(slug, s['code'])
        store.set_result(s, ok, txt)

def start(): threading.Thread(target=worker, daemon=True).start()
