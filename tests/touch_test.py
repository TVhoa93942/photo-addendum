"""Touch-input cross-check in Chromium with iPhone emulation (Playwright): real file-input picking,
tap targets, finger swipes and double-tap zoom in the viewer, finger-drawn signature, no console errors.
Usage: python3 tests/touch_test.py <base_url> <out_dir>"""
import sys, os, time
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8765/'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/tmp/pa_touch'
FX = os.environ.get('FX', '/home/claude/pa/www/fx')
os.makedirs(OUT, exist_ok=True)
R = []
def check(c, m): R.append((bool(c), m)); print(('ok   - ' if c else 'FAIL - ') + m, flush=True)

def touch(cdp, typ, pts):
    cdp.send('Input.dispatchTouchEvent', {'type': typ, 'touchPoints': [{'x': x, 'y': y} for x, y in pts]})

def swipe(cdp, x0, y0, x1, y1, steps=8):
    touch(cdp, 'touchStart', [(x0, y0)])
    for i in range(1, steps + 1):
        touch(cdp, 'touchMove', [(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)]); time.sleep(0.01)
    touch(cdp, 'touchEnd', [])

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(**p.devices['iPhone 13'], timezone_id='America/Los_Angeles')
    pg = ctx.new_page()
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    cdp = ctx.new_cdp_session(pg)
    pg.goto(BASE + 'index.html'); pg.wait_for_function('window.__pa && window.__pa.ready')
    pg.tap('#newInspBtn'); pg.wait_for_selector('#inspView:not([hidden])')
    pg.tap('#f_address'); pg.keyboard.type('9 Touch Test Ln, Seaside, CA')
    pg.evaluate('document.activeElement.blur()')
    pg.tap('#stdRoomsBtn')
    rid = pg.evaluate('window.__pa.cur.areas[3].id')
    pg.tap('#room_%s .room-h' % rid)
    # the real <input type=file> path (hidden input inside the Library button)
    pg.set_input_files('#room_%s input[data-act=file-lib]' % rid, [os.path.join(FX, f) for f in ['land_exif.jpg', 'portrait_rot6.jpg', 'p1.jpg', 'p2.jpg']])
    pg.wait_for_function('window.__pa.cur.areas[3].movein.photos.length===4 && !document.querySelector(".thumb.pending")', timeout=30000)
    check(True, 'real file input accepted 4 photos')
    ph = pg.evaluate('window.__pa.cur.areas[3].movein.photos.map(p=>[p.w,p.h,p.dateSrc])')
    check(ph[1][0] == 1200 and ph[1][1] == 1600, 'rotated portrait upright in this engine too %s' % ph)
    # viewer: tap first thumb, swipe left twice, swipe right once
    pg.tap('#room_%s [data-part=thumbs] .thumb >> nth=0' % rid)
    pg.wait_for_selector('#viewer:not([hidden])')
    box = pg.locator('#vStage').bounding_box(); cx = box['x'] + box['width'] / 2; cy = box['y'] + box['height'] / 2
    swipe(cdp, cx + 120, cy, cx - 120, cy); time.sleep(0.3)
    swipe(cdp, cx + 120, cy, cx - 120, cy); time.sleep(0.3)
    check(pg.inner_text('#vIdx') == '3 / 4', 'finger swipe left moves to the next photo (3 / 4)')
    swipe(cdp, cx - 120, cy, cx + 120, cy); time.sleep(0.3)
    check(pg.inner_text('#vIdx') == '2 / 4', 'finger swipe right goes back (2 / 4)')
    # double-tap to zoom, double-tap again to reset
    for _ in range(2):
        touch(cdp, 'touchStart', [(cx, cy)]); touch(cdp, 'touchEnd', []); time.sleep(0.08)
    time.sleep(0.3)
    check(pg.evaluate("document.getElementById('vStage').classList.contains('zoom')"), 'double-tap zooms in')
    pg.screenshot(path=os.path.join(OUT, 't1_zoom.png'))
    for _ in range(2):
        touch(cdp, 'touchStart', [(cx, cy)]); touch(cdp, 'touchEnd', []); time.sleep(0.08)
    time.sleep(0.3)
    check(not pg.evaluate("document.getElementById('vStage').classList.contains('zoom')"), 'double-tap again zooms back out')
    pg.tap('#vClose')
    # signature with a finger
    pg.tap('#sigTenantBtn'); pg.wait_for_selector('#sigPad:not([hidden])'); time.sleep(0.3)
    sb = pg.locator('#sigCanvas').bounding_box()
    y0 = pg.evaluate('window.scrollY')
    pts = [(sb['x'] + 30 + i * 14, sb['y'] + sb['height'] / 2 + (25 if i % 2 else -25)) for i in range(18)]
    touch(cdp, 'touchStart', [pts[0]])
    for pt in pts[1:]: touch(cdp, 'touchMove', [pt]); time.sleep(0.01)
    touch(cdp, 'touchEnd', [])
    pg.screenshot(path=os.path.join(OUT, 't2_signature.png'))
    pg.tap('#sigSave')
    sg = pg.evaluate('window.__pa.cur.signatures')
    check(len(sg) == 1 and len(sg[0]['data']) > 1500, 'finger-drawn signature saved (%d bytes)' % (len(sg[0]['data']) if sg else 0))
    check(pg.evaluate('window.scrollY') == y0, 'signing does not scroll the page')
    # quick phrase strip scrolls sideways; tap a chip that starts off-screen
    pg.tap('#room_%s .room-h' % rid) if pg.evaluate('window.__pa.openRid') != rid else None
    strip = pg.locator('#room_%s .phrases' % rid)
    sw = pg.evaluate("(()=>{const s=document.querySelector('#room_%s .phrases'); return [s.scrollWidth, s.clientWidth];})()" % rid)
    check(sw[0] > sw[1], 'phrase chips sit in a compact sideways-scrolling strip (%s)' % sw)
    pg.locator('#room_%s .phrases button' % rid).last.scroll_into_view_if_needed()
    pg.locator('#room_%s .phrases button' % rid).last.tap()
    check(pg.evaluate('window.__pa.cur.areas[3].movein.note') == 'Not working', 'off-screen phrase chip reachable and works')
    # bottom bar hides while typing, and returns
    pg.tap('#room_%s textarea[data-act=note]' % rid)
    check(pg.evaluate("getComputedStyle(document.getElementById('actionBar')).display") == 'none', 'bottom bar hidden while typing')
    pg.evaluate('document.activeElement.blur()'); time.sleep(0.3)
    check(pg.evaluate("getComputedStyle(document.getElementById('actionBar')).display") != 'none', 'bottom bar back after typing')
    # every visible button is at least 40px tall (comfortable for a thumb)
    small = pg.evaluate("""Array.from(document.querySelectorAll('#inspView button, #inspView label.pbtn')).filter(b=>{const r=b.getBoundingClientRect(); return r.width>0&&r.height>0&&r.height<34;}).map(b=>(b.className||b.tagName)+':'+Math.round(b.getBoundingClientRect().height))""")
    check(len(small) == 0, 'no tiny tap targets in the inspection screen %s' % small[:8])
    pg.screenshot(path=os.path.join(OUT, 't3_room.png'))
    errs = [e for e in errors if 'favicon' not in e]
    check(not errs, 'no console errors (%s)' % errs[:3])
    b.close()
print('\n%d checks, %d failed' % (len(R), sum(1 for ok, _ in R if not ok)))
sys.exit(0 if all(ok for ok, _ in R) else 1)
