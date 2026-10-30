"""Scans store: in-memory list (last KEEP), scans.csv log, SSE subscriber fan-out."""
import os, csv, json, queue, threading, datetime, itertools
BASE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(BASE, 'scans.csv')
scans, subs, lock = [], [], threading.Lock()
ids = itertools.count(1)
KEEP = 5000     # scans kept in memory (and reloaded from scans.csv) for paging
PER_PAGE = 100  # rows per page on the scans page / API

# --- Publish the scan ------------------------------------
def publish(s):
    """Publish the scan to the subscribers."""
    with lock:
        for q in subs: q.put(s)

# --- New scan ------------------------------------
def new_scan(code, reader_name):
    """Create a new scan."""
    s = {'id': next(ids), 'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'code': code,
         'reader': reader_name, 'fwd': 'queued', 'ok': None}
    with lock: scans.insert(0, s); del scans[KEEP:]
    publish(s)
    return s

# --- Set the result ------------------------------------
def set_result(s, ok, txt):
    """Set the result of the scan."""
    s['ok'], s['fwd'] = ok, txt
    with lock:
        with open(LOG, 'a', newline='') as f: csv.writer(f).writerow([s['time'], s['code'], s['reader'], txt])
    publish(s)

# --- Load the log ------------------------------------
def load_log():
    """Load the log from the file."""
    if os.path.exists(LOG):
        with open(LOG) as f:
            for row in csv.reader(f):
                if len(row) >= 2:
                    fwd = row[3] if len(row) > 3 else ''
                    scans.insert(0, {'id': next(ids), 'time': row[0], 'code': row[1], 'reader': row[2] if len(row) > 2 else '',
                                     'fwd': fwd, 'ok': fwd.startswith('HTTP 2') if fwd else None})
        del scans[KEEP:]

# --- SSE generator ------------------------------------
def sse():
    """Generator of SSE text for one subscriber."""
    q = queue.Queue()
    with lock: subs.append(q)
    try:
        yield ': connected\n\n'
        while True:
            try: yield 'data: ' + json.dumps(q.get(timeout=20)) + '\n\n'
            except queue.Empty: yield ': ping\n\n'
    finally:
        with lock: subs.remove(q)

# --- Page ------------------------------------
def page(reader='', page=1, per=PER_PAGE):
    """One page of scans (newest first), optionally only one reader's. Returns dict for template/API."""
    with lock: rows = [s for s in scans if not reader or s['reader'] == reader]
    pages = max(1, -(-len(rows) // per))
    page = min(max(1, page), pages)
    return {'items': rows[(page - 1) * per: page * per], 'page': page, 'pages': pages,
            'total': len(rows), 'per_page': per, 'reader': reader}

# --- Latest scan ------------------------------------
def latest(reader=''):
    """Newest scan (optionally for one reader) for the 'Latest' card."""
    with lock: return next((s for s in scans if not reader or s['reader'] == reader), None)
