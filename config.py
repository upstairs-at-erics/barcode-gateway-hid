"""Config: load/save config.json (chmod 600), defaults, reader lookup, admin auth."""
import json, os
from werkzeug.security import check_password_hash

# --- Config file location and defaults ------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
CONF = os.environ.get('CONFIG', os.path.join(BASE, 'config.json'))
DEFAULTS = {'endpoint': '', 'api_key': '', 'readers': []}

# --- Load the config file ------------------------------------
def load():
    """Load the config file."""
    try:
        with open(CONF) as f: return json.load(f)
    except (OSError, ValueError): return dict(DEFAULTS, readers=[])

# --- Save the config file ------------------------------------
def save(c):
    """Atomically write config (mode 600) and make it current."""
    global conf
    tmp = CONF + '.tmp'
    # open the temporary file for writing
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f: json.dump(c, f, indent=2)
    os.chmod(tmp, 0o600); os.replace(tmp, CONF)
    conf = c

conf = load()

# --- Copy the config ------------------------------------
def copy(): return json.loads(json.dumps(conf))

# --- Get the readers ------------------------------------
def readers(): return conf.get('readers', [])

# --- Get the reader by id ------------------------------------
def reader_by_id(rid): return next((r for r in readers() if r['id'] == rid), None)

# --- Check the admin authentication ------------------------------------
def check_admin(auth):
    """auth = flask request.authorization; user 'admin' + password matching admin_hash."""
    
    # get the admin hash from the config
    h = conf.get('admin_hash')

    # check if the admin authentication is valid
    if h and auth and auth.username == 'admin' and check_password_hash(h, auth.password or ''):
        return True
    else:
        return False

# --- Config changes from the config page ------------------------------------
# Each takes the submitted form, changes a copy of the config, saves it and
# returns a message for the page. Callers restart the readers afterwards.

# --- Set the endpoint ------------------------------------
def set_endpoint(form):
    """Endpoint URL and API key (a blank key box keeps the current key)."""
    c = copy()
    c['endpoint'] = form.get('endpoint', '').strip()
    key = form.get('api_key', '').strip()
    if key: c['api_key'] = key
    save(c); return 'Endpoint saved.'

# --- Build a reader dict from the add/edit form ------------------------------------
def reader_from_form(form, rid):
    """Build a reader dict from the add/edit form."""
    return {'id': rid,
            'name': form.get('name', '').strip() or 'Reader',
            'slug': form.get('slug', '').strip(),
            'device': form.get('device', ''),
            'enabled': form.get('enabled') == 'on'}

# --- Save the reader ------------------------------------
def save_reader(form):
    """Add a new reader, or update it if the form carries an existing id."""
    import secrets
    c = copy(); rid = form.get('id') or secrets.token_hex(4)
    new = reader_from_form(form, rid)
    if form.get('id') and reader_by_id(rid):
        c['readers'] = [new if r['id'] == rid else r for r in c['readers']]
    else:
        c['readers'].append(new)
    save(c); return 'Reader saved.'

# --- Delete the reader ------------------------------------
def delete_reader(form):
    """Remove a reader."""
    c = copy(); c['readers'] = [r for r in c['readers'] if r['id'] != form.get('id')]
    save(c); return 'Reader deleted.'

# --- Toggle the reader ------------------------------------
def toggle_reader(form):
    """Enable / disable a reader."""
    c = copy()
    for r in c['readers']:
        if r['id'] == form.get('id'): r['enabled'] = not r.get('enabled')
    save(c); return 'Reader updated.'

ACTIONS = {'endpoint': set_endpoint, 'reader': save_reader,
           'delete': delete_reader, 'toggle': toggle_reader}

# --- Apply the form ------------------------------------
def apply_form(form):
    """Run the action named in the form; returns the message to show."""
    fn = ACTIONS.get(form.get('action'))
    return fn(form) if fn else None
