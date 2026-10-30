"""Readers: hidraw device detection, HID keyboard decode, one thread per enabled reader, reload."""
import glob, os, select, threading
import config

# --- HID keyboard decode table ------------------------------------

# add the letters a-z
U = {i: chr(ord('a') + i - 4) for i in range(4, 30)}

# add the numbers 0-9
U.update({30+i: '1234567890'[i] for i in range(10)})

# add the special characters
U.update({0x2c:' ',0x2d:'-',0x2e:'=',0x2f:'[',0x30:']',0x31:'\\',0x33:';',0x34:"'",0x35:'`',0x36:',',0x37:'.',0x38:'/'})

# --- Shifted keyboard decode table ------------------------------------
S = {0x1e:'!',0x1f:'@',0x20:'#',0x21:'$',0x22:'%',0x23:'^',0x24:'&',0x25:'*',0x26:'(',0x27:')',0x2d:'_',0x2e:'+',0x2f:'{',0x30:'}',0x31:'|',0x33:':',0x34:'"',0x35:'~',0x36:'<',0x37:'>',0x38:'?'}

# --- Status dictionary ------------------------------------
status = {}   # reader id -> device path or None

# --- Threads dictionary ------------------------------------
threads = {}  # reader id -> (thread, stop event, device key)

# --- On scan callback ------------------------------------
on_scan = lambda code, rid: None  # set by app

# --- Detect devices ------------------------------------
def detect():
    """Keyboard-interface (input0) hidraw devices, keyed stably by vendor:product:serial."""
    found = {}
    # loop through the hidraw devices
    for sysfs in sorted(glob.glob('/sys/class/hidraw/hidraw*')):
        try:
            with open(sysfs + '/device/uevent') as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        # create a dictionary of the uevent lines
        uevent = {}
        for line in lines:
            if '=' not in line:
                continue
            name, value = line.split('=', 1)
            uevent[name] = value

        # if the device is not an input0, continue
        if not uevent.get('HID_PHYS', '').endswith('input0'):
            continue

        # get the hid id
        hid_id = uevent.get('HID_ID', '0:0:0').split(':') + ['0', '0']
        
        # get the vendor and product from the hid id
        vendor, product = hid_id[1][-4:].lower(), hid_id[2][-4:].lower()
        
        # get the serial from the uevent
        serial = uevent.get('HID_UNIQ') or uevent.get('HID_PHYS', '')
        
        # create the key from the vendor, product and serial
        key = '%s:%s:%s' % (vendor, product, serial)

        # add the key to the found dictionary
        key_dict = {
            'key'  : key,
            'name' : uevent.get('HID_NAME', '?'),
            'dev'  : '/dev/' + os.path.basename(sysfs),
            'phys' : uevent.get('HID_PHYS', ''),
        }
        found.setdefault(key, key_dict)
    return found

# --- Decode HID report ------------------------------------
def decode(r, prev, buf, emit):
    """Process one 8-byte HID report. Returns (prev, buf); calls emit(code) on Enter."""
    # check if the shift key is pressed
    shift = bool(r[0] & 0x22)
    # loop through the report, skipping the first two bytes
    for k in [k for k in r[2:8] if k and k not in prev]:
        # if the key is the enter key or the shift key, emit the buffer
        if k in (0x28, 0x58):
            if buf: emit(buf)
            buf = ''
        # if the key is in the decode table, add the character to the buffer
        elif k in U:
            # if the shift key is pressed, use the shifted decode table
            buf += (S.get(k) or U[k].upper()) if shift else U[k]
    # return the set of keys and the buffer
    return set(k for k in r[2:8] if k), buf

# --- Loop through the devices ------------------------------------
def loop(rid, devkey, stop):
    """Loop through the devices."""
    while not stop.is_set():
        d = detect().get(devkey); status[rid] = d['dev'] if d else None
        if not d: stop.wait(3); continue
        try:
            fd = os.open(d['dev'], os.O_RDONLY)
            try:
                buf, prev = '', set()
                while not stop.is_set():
                    if not select.select([fd], [], [], 1)[0]: continue
                    r = os.read(fd, 64)
                    if not r: raise OSError('eof')
                    if len(r) < 8: continue
                    prev, buf = decode(r, prev, buf, lambda c: on_scan(c, rid))
            finally: os.close(fd)
        except OSError:
            status[rid] = None; stop.wait(3)
    # Only clear the status if a newer thread for this reader hasn't taken over.
    if rid not in threads or threads[rid][1] is stop: status.pop(rid, None)

# --- Apply the config ------------------------------------
def apply():
    """Start or stop listener threads so they match the enabled readers in config."""
    wanted = {}

    # loop through the saved readers
    for saved in config.readers():
        if saved.get('enabled') and saved.get('device'):
            wanted[saved['id']] = saved['device']

    # loop through the threads
    for rid, (_thread, stop, device_key) in list(threads.items()):
        # get the still wanted device key
        still_wanted = wanted.get(rid)
        if still_wanted != device_key:
            stop.set()
            del threads[rid]

    # loop through the wanted readers
    for rid, device_key in wanted.items():
        if rid in threads:
            continue
        stop = threading.Event()
        thread = threading.Thread(
            target=loop,
            args=(rid, device_key, stop),
            daemon=True,
        )
        threads[rid] = (thread, stop, device_key)
        thread.start()
