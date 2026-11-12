"""Minimal TrueType/OpenType metrics reader (no dependencies).

libass sizes text like old Windows renderers: the requested size is the font's full line height
(win ascent + win descent), not its em size. Design tools size text by the em. To match a design
size S in libass, use S * line_height / units_per_em - that factor comes from here.
"""
import os
import struct


def _tables(data, off):
    num = struct.unpack('>H', data[off + 4:off + 6])[0]
    t = {}
    for i in range(num):
        tag, _, o, ln = struct.unpack('>4sIII', data[off + 12 + 16 * i: off + 28 + 16 * i])
        t[tag.decode('latin-1')] = (o, ln)
    return t


def _names(data, tb):
    o, _ = tb['name']
    _, count, so = struct.unpack('>HHH', data[o:o + 6])
    out = {}
    for i in range(count):
        pid, eid, lid, nid, ln, no = struct.unpack('>HHHHHH', data[o + 6 + 12 * i:o + 18 + 12 * i])
        raw = data[o + so + no:o + so + no + ln]
        try:
            s = raw.decode('utf-16-be') if pid in (0, 3) else raw.decode('mac_roman')
        except Exception:
            continue
        out.setdefault(nid, s)
    return out


def faces(path):
    """All faces in a .ttf/.otf/.ttc with their names and vertical metrics."""
    data = open(path, 'rb').read()
    offs = [0]
    if data[:4] == b'ttcf':
        n = struct.unpack('>I', data[8:12])[0]
        offs = list(struct.unpack('>%dI' % n, data[12:12 + 4 * n]))
    res = []
    for off in offs:
        tb = _tables(data, off)
        upm = struct.unpack('>H', data[tb['head'][0] + 18:tb['head'][0] + 20])[0]
        asc, desc = struct.unpack('>hh', data[tb['hhea'][0] + 4:tb['hhea'][0] + 8])
        o2 = tb.get('OS/2')
        win_a = win_d = cap = None
        weight, italic = 400, False
        if o2:
            b = data[o2[0]:o2[0] + o2[1]]
            weight = struct.unpack('>H', b[4:6])[0]
            italic = bool(struct.unpack('>H', b[62:64])[0] & 1)
            win_a, win_d = struct.unpack('>HH', b[74:78])
            if len(b) >= 90:
                cap = struct.unpack('>h', b[88:90])[0]
        nm = _names(data, tb)
        res.append(dict(family=nm.get(16) or nm.get(1), style=nm.get(17) or nm.get(2), full=nm.get(4), ps=nm.get(6), upm=upm,
                        asc=asc, desc=desc, win_asc=win_a, win_desc=win_d, cap=cap, weight=weight, italic=italic))
    return res


def extract_faces(path, out_dir):
    """Write every face of a .ttc/.ttf as its own .ttf named by PostScript name; returns {ps: file}.

    libass only loads the first face of a font collection given through a fonts folder, so faces like
    Didot-Bold or HelveticaNeue-Medium must be split out to be found by name."""
    data = open(path, 'rb').read()
    offs = [0]
    if data[:4] == b'ttcf':
        n = struct.unpack('>I', data[8:12])[0]
        offs = list(struct.unpack('>%dI' % n, data[12:12 + 4 * n]))
    out = {}
    for off, info in zip(offs, faces(path)):
        ps = info.get('ps')
        if not ps:
            continue
        dst = os.path.join(out_dir, ps + '.ttf')
        out[ps] = dst
        if os.path.exists(dst):
            continue
        num = struct.unpack('>H', data[off + 4:off + 6])[0]
        recs = [struct.unpack('>4sIII', data[off + 12 + 16 * i: off + 28 + 16 * i]) for i in range(num)]
        head = bytearray(data[off:off + 12])
        body, pos = bytearray(), 12 + 16 * num
        dirs = bytearray()
        for tag, chk, o, ln in recs:
            dirs += struct.pack('>4sIII', tag, chk, pos + len(body), ln)
            body += data[o:o + ln] + b'\0' * ((4 - ln % 4) % 4)
        tmp = '%s.%d.part' % (dst, os.getpid())
        with open(tmp, 'wb') as fh:
            fh.write(bytes(head) + bytes(dirs) + bytes(body))
        os.replace(tmp, dst)
    return out


def libass_factor(face):
    """Multiply a design (em) size by this to get the libass font size."""
    if face.get('win_asc') and face.get('win_desc') is not None and (face['win_asc'] + face['win_desc']) > 0:
        h = face['win_asc'] + face['win_desc']
    else:
        h = face['asc'] - face['desc']
    return h / float(face['upm'])


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        for f in faces(p):
            print('%-40s %-30s upm %5d hhea %5d/%5d win %s/%s cap %s  libass factor %.4f' % (
                p.split('/')[-1], (f['ps'] or ''), f['upm'], f['asc'], f['desc'], f['win_asc'], f['win_desc'], f['cap'], libass_factor(f)))
