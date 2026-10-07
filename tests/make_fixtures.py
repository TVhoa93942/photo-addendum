"""Create test fixtures for the Photo Addendum test suite.
- iPhone-like JPEGs with EXIF DateTimeOriginal (one landscape, one portrait stored rotated with Orientation=6)
- a JPEG with no EXIF, a broken "jpg"
- a v3-format project (.json) and a seed page that writes a v3 save into the old IndexedDB
Usage: python3 make_fixtures.py <out_dir>"""
import sys, os, io, json, base64, random
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else 'fixtures'
os.makedirs(OUT, exist_ok=True)

def font(sz):
    for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

def scene(w, h, label, hue=(70, 120, 170), arrow=True):
    img = Image.new('RGB', (w, h), hue)
    d = ImageDraw.Draw(img)
    for i in range(0, w, max(1, w // 24)):  # stripes so downscaling artifacts are visible
        d.line([(i, 0), (i + h // 3, h)], fill=(hue[0] + 25, hue[1] + 25, min(255, hue[2] + 25)), width=max(2, w // 300))
    d.rectangle([w * 0.06, h * 0.06, w * 0.94, h * 0.94], outline=(255, 255, 255), width=max(4, w // 200))
    f = font(max(24, w // 12))
    d.text((w * 0.1, h * 0.12), label, fill=(255, 255, 255), font=f)
    if arrow:  # arrow pointing UP in the intended viewing orientation
        cx, top, bot = w * 0.5, h * 0.35, h * 0.85
        d.line([(cx, bot), (cx, top)], fill=(255, 220, 60), width=max(8, w // 60))
        d.polygon([(cx, top - h * 0.08), (cx - w * 0.08, top + h * 0.02), (cx + w * 0.08, top + h * 0.02)], fill=(255, 220, 60))
        d.text((cx + w * 0.05, top), 'UP', fill=(255, 220, 60), font=f)
    return img

def exif_bytes(dt, orientation=1, offset=None):
    ex = Image.Exif()
    ex[0x0112] = orientation
    ex[0x0132] = dt
    ifd = ex.get_ifd(0x8769)
    ifd[0x9003] = dt
    if offset:
        ifd[0x9011] = offset
    return ex.tobytes()

# 1) landscape with DateTimeOriginal + offset
scene(4032, 3024, 'KITCHEN 1').save(os.path.join(OUT, 'land_exif.jpg'), 'JPEG', quality=88,
                                     exif=exif_bytes('2026:03:14 10:22:33', 1, '-07:00'))
# 2) portrait stored rotated (pixels landscape, Orientation=6) — must display upright
portrait = scene(3024, 4032, 'BEDROOM P', hue=(120, 80, 140))
portrait.transpose(Image.ROTATE_90).save(os.path.join(OUT, 'portrait_rot6.jpg'), 'JPEG', quality=88,
                                         exif=exif_bytes('2025:07:01 09:15:00', 6))
# 3) no EXIF at all
scene(1200, 900, 'NO EXIF', hue=(60, 140, 90)).save(os.path.join(OUT, 'noexif.jpg'), 'JPEG', quality=85)
# 4) several small photos for bulk/stress tests
for i in range(6):
    scene(1600, 1200, 'ROOM %d' % (i + 1), hue=(40 + i * 25, 90 + i * 10, 150 - i * 12)).save(
        os.path.join(OUT, 'p%d.jpg' % (i + 1)), 'JPEG', quality=82, exif=exif_bytes('2026:10:0%d 1%d:0%d:00' % (1 + i % 5, i, i)))
# 5) not an image
open(os.path.join(OUT, 'broken.jpg'), 'wb').write(b'this is not a jpeg at all')

# 6) a v3 project (photos inline as data URLs at 1400px like v3 stored them)
def v3photo(label, hue, ts, pid):
    b = io.BytesIO(); scene(1400, 1050, label, hue=hue).save(b, 'JPEG', quality=72)
    return {'id': pid, 'data': 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode(), 'ts': ts, 'w': 1400, 'h': 1050}

sig = Image.new('RGBA', (640, 160), (255, 255, 255, 0)); sd = ImageDraw.Draw(sig)
sd.line([(40, 120), (120, 40), (200, 120), (300, 50), (420, 110), (600, 60)], fill=(28, 39, 51, 255), width=5)
sb = io.BytesIO(); sig.save(sb, 'PNG')
v3 = {
    'details': {'address': '742 Evergreen Ter, Pacific Grove, CA', 'unit': '3', 'inspector': 'Bill Phillips', 'tenant': 'Pat Example',
                'movein': '2026-07-01', 'moveout': '', 'rent': '$2,950', 'deposit': '$3,500', 'gennotes': 'Two keys and one garage remote given.'},
    'stage': 'movein',
    'areas': [
        {'id': 'a1', 'area': 'Kitchen', 'custom': '', 'tag': '',
         'movein': {'photos': [v3photo('V3 KITCHEN A', (90, 60, 40), 1751385600000, 'v3p1'), v3photo('V3 KITCHEN B', (95, 65, 45), 1751385660000, 'v3p2')], 'note': 'Counters clean, new range.'},
         'moveout': {'photos': [], 'note': ''}, 'afterrepairs': {'photos': [], 'note': ''}},
        {'id': 'a2', 'area': 'Bathroom', 'custom': 'Hall bath', 'tag': '',
         'movein': {'photos': [v3photo('V3 BATH', (40, 90, 110), 1751385720000, 'v3p3')], 'note': 'Grout stained near tub.'},
         'moveout': {'photos': [], 'note': ''}, 'afterrepairs': {'photos': [], 'note': ''}},
        {'id': 'a3', 'area': 'Bedroom', 'custom': '', 'tag': '',
         'movein': {'photos': [], 'note': ''}, 'moveout': {'photos': [], 'note': ''}, 'afterrepairs': {'photos': [], 'note': ''}},
    ],
    'signatures': {'tenantMovein': {'data': 'data:image/png;base64,' + base64.b64encode(sb.getvalue()).decode(), 'ts': 1751386000000}},
}
json.dump(v3, open(os.path.join(OUT, 'v3_project.json'), 'w'))
# v1-style (no afterrepairs / tag / signatures) to test old migrations
v1 = {'details': {'address': '12 Old Format Way'}, 'stage': 'movein', 'areas': [
    {'id': 'x1', 'area': 'Kitchen', 'custom': '', 'movein': {'photos': [v3photo('V1 OLD', (60, 60, 60), 1700000000000, 'v1p1')], 'note': 'old note'}, 'moveout': {'photos': [], 'note': ''}}]}
json.dump(v1, open(os.path.join(OUT, 'v1_project.json'), 'w'))

seed = """<!doctype html><meta charset=utf-8><body><script>
window.seedDone=false;
fetch('v3_project.json').then(r=>r.text()).then(txt=>{
  const rq=indexedDB.open('phillips_photo_addendum_db',1);
  rq.onupgradeneeded=()=>rq.result.createObjectStore('project');
  rq.onsuccess=()=>{ const db=rq.result; const t=db.transaction('project','readwrite'); t.objectStore('project').put(txt,'current');
    t.oncomplete=()=>{ db.close(); window.seedDone=true; document.body.textContent='seeded '+txt.length; }; };
  rq.onerror=()=>{ document.body.textContent='seed error'; };
});
</script></body>"""
open(os.path.join(OUT, 'seed_v3.html'), 'w').write(seed)

check = """<!doctype html><meta charset=utf-8><body><script>
window.v3check=null;
const rq=indexedDB.open('phillips_photo_addendum_db');
rq.onsuccess=()=>{ const db=rq.result; if(!db.objectStoreNames.contains('project')){ window.v3check='nostore'; return; }
  const g=db.transaction('project').objectStore('project').get('current'); g.onsuccess=()=>{ window.v3check=g.result?('present:'+g.result.length):'missing'; db.close(); }; };
</script></body>"""
open(os.path.join(OUT, 'check_v3.html'), 'w').write(check)
print('fixtures in', OUT, sorted(os.listdir(OUT)))
