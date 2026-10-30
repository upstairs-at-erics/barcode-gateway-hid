#!/usr/bin/env python3

"""Barcode Gateway: Flask routes + startup. 

Logic lives in config/reader/sender/store modules:
- config.py: configuration
- reader.py: reader management
- sender.py: barcode forwarding
- store.py: scan logging and storage
"""

import os
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for
import config as cfg, reader, sender, store

app = Flask(__name__)

# --- on_scan callback ---------------------------------------------------
# reader.py calls this for every complete barcode (Enter received).
# We log it in the store (shown live on the page) and queue it for forwarding.

def on_scan(code, rid):
    """Log the scan on the live page and queue it for forwarding."""
    
    # get the reader from the config
    reader = cfg.reader_by_id(rid) or {}

    # log the scan on the live page 
    scan  = store.new_scan(code, reader.get('name', '?'))
    
    # queue the scan for forwarding
    sender.enqueue(scan, reader.get('slug', '')) 


def readers_view():
    """Each saved reader plus the hidraw path its thread is on, or None if it isn't listening."""
    rows = []
    # get all readers from the config
    for saved in cfg.readers():
        # create a row for the reader
        row = dict(saved)
        # add the hidraw path the reader is on, or None if it isn't listening
        row['device_path'] = reader.status.get(saved['id'])
        rows.append(row)
    return rows

# Ask the browser for the admin username/password (HTTP basic auth).
def need_auth(): 
    """Return a 401 response with a basic auth prompt."""
    # return a 401 response with a basic auth prompt
    headers = {'WWW-Authenticate': 'Basic realm="Barcode Gateway config"'}
    return Response('Login required', 401, headers)

# --- Public pages (no login) -----------------------------------------------
# Scans page: recent scans plus a badge per reader.
# ?reader=<name> filters by reader, ?page=N pages (100 per page, newest first).
def page_args(): 
    """Return the reader and page arguments from the query string."""
    return request.args.get('reader', ''), request.args.get('page', 1, type=int)

@app.route('/')
def index():
    rname, pg = page_args()
    return render_template(
        'index.html',
        p=store.page(rname, pg),
        latest=store.latest(rname),
        readers=readers_view(),
        highlight_seconds=cfg.highlight_seconds(),
    )

# Recent scans as JSON: plain list as before; with ?reader= and/or ?page= a page object {items,page,pages,total,...}.
@app.route('/api/scans')
def api():
    if 'reader' in request.args or 'page' in request.args: return jsonify(store.page(*page_args()))
    return jsonify(store.scans)

# Live feed (server-sent events): the scans page listens here for new scans.
@app.route('/stream')
def stream(): return Response(store.sse(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache'})

# --- Config page (admin login) ----------------------------------------------
# GET shows the form; POST saves one change, then reloads the reader threads.
@app.route('/config', methods=['GET', 'POST'])
def config():
    """Endpoint, readers, and plugged-in dongles. A POST saves then reloads the listener threads."""
    
    # check if the admin is authenticated
    if not cfg.check_admin(request.authorization):
        return need_auth()

    # if the request method is POST, apply the form
    if request.method == 'POST':
        # apply the form
        msg = cfg.apply_form(request.form)
        if request.form.get('action') != 'display':
            reader.apply()
        return redirect(url_for('config', msg=msg))

    # get the plugged in dongles
    plugged_in = reader.detect()
    # get the assigned dongles
    assigned = {saved.get('device') for saved in cfg.readers()}
    # get the spare dongles
    spare = [dongle for key, dongle in plugged_in.items() if key not in assigned]

    # Add or edit a reader form
    edit = cfg.reader_by_id(request.args.get('edit', ''))
    # get the message
    msg = request.args.get('msg')

    context = {
        'conf'          : cfg.conf,
        'key_set'       : bool(cfg.conf.get('api_key')),
        'readers'       : readers_view(),
        'detected'      : plugged_in,
        'unconfigured'  : spare,
        'edit'          : edit,
        'msg'           : msg,
    }

    return render_template('config.html', **context)

# 'Send test' button: posts a test barcode for this reader to the real endpoint.
@app.route('/config/test/<rid>', methods=['POST'])
def config_test(rid):
    # check if the admin is authenticated
    if not cfg.check_admin(request.authorization): return need_auth()
    # get the reader
    r = cfg.reader_by_id(rid)
    # if the reader is not found, return a 404 error
    if not r: return jsonify(ok=False, result='unknown reader'), 404
    # send the test barcode
    ok, txt = sender.send_test(r, request.json.get('barcode', 'TEST') if request.is_json else 'TEST')
    # return the result as JSON
    return jsonify(ok=ok, result=txt)

# --- Startup ----------------------------------------------------------------
if __name__ == '__main__':

    
    store.load_log()            # reload recent scans from scans.csv
    sender.start()              # start the background forwarding worker
    reader.on_scan = on_scan    # tell the readers where to hand each scan
    reader.apply()              # start one thread per enabled reader
    
    # Serve on the Tailscale IP set by the systemd unit (BIND / PORT).
    # Default to 127.0.0.1:8095 if not set.
    address = os.environ.get('BIND', '127.0.0.1')
    port    = int(os.environ.get('PORT', 8095))    
    print(f"Serving on {address}:{port}")
    app.run(host=address, port=port, threaded=True)
