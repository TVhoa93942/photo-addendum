"""End-to-end test of Photo Addendum v4 in WebKit (Safari's engine, via WebKitGTK MiniBrowser),
at iPhone width with an iPhone user agent and a mock camera. Drives the real UI with real clicks/typing
and verifies storage, photos, viewer, Quick Shoot, signatures, relaunch/resume, PDF, backup/restore,
and the automatic upgrade from v3.

Usage: python3 tests/wk_test.py <base_url> <out_dir>
Requires: Xvfb on :99, WebKitWebDriver, selenium. Fixtures at <base_url>/fx/ (tests/make_fixtures.py)."""
import os, sys, time, json, base64, subprocess, datetime, traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.options import ArgOptions
from selenium.webdriver.common.action_chains import ActionChains

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8765/'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/tmp/pa_test'
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault('DISPLAY', ':99')
os.environ['TZ'] = 'America/Los_Angeles'
UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 '
      '(KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1')
RESULTS = []

def log(ok, msg):
    RESULTS.append((ok, msg)); print(('ok   - ' if ok else 'FAIL - ') + msg, flush=True)

def check(cond, msg):
    log(bool(cond), msg)
    return bool(cond)

IPAD_UA = ('Mozilla/5.0 (iPad; CPU OS 18_6 like Mac OS X) AppleWebKit/605.1.15 '
           '(KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1')
def start_driver(port, ua=None, size=(400, 860)):
    wd = subprocess.Popen(['WebKitWebDriver', '--port=%d' % port], stdout=open(os.path.join(OUT, 'wkwd_%d.log' % port), 'w'), stderr=subprocess.STDOUT)
    time.sleep(1.5)
    o = ArgOptions(); o.set_capability('browserName', 'MiniBrowser')
    o.set_capability('webkitgtk:browserOptions', {'binary': '/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1/MiniBrowser',
        'args': ['--automation', '--enable-media-stream=true', '--enable-mock-capture-devices=true', '--enable-webrtc=true',
                 '--media-playback-requires-user-gesture=false', '--user-agent=' + (ua or UA)]})
    d = webdriver.Remote(command_executor='http://127.0.0.1:%d' % port, options=o)
    d.set_window_size(*size)
    d.set_script_timeout(120)
    return wd, d

def J(d, s, *a): return d.execute_script(s, *a)
def wait(d, js, timeout=25, msg=None, interval=0.15):
    t0 = time.time(); last = None
    while time.time() - t0 < timeout:
        try:
            last = d.execute_script('return (' + js + ')')
            if last: return last
        except Exception as e:
            last = 'ERR ' + str(e)[:200]
        time.sleep(interval)
    if msg: log(False, 'timeout: %s (last=%r)' % (msg, last))
    return None
def shot(d, name):
    try: d.save_screenshot(os.path.join(OUT, name + '.png'))
    except Exception as e: print('screenshot failed', name, e)
def click(d, css, idx=0):
    els = d.find_elements(By.CSS_SELECTOR, css)
    if len(els) <= idx: raise AssertionError('no element for ' + css)
    el = els[idx]
    d.execute_script("arguments[0].scrollIntoView({block:'center'})", el); time.sleep(0.25)
    el.click(); time.sleep(0.25)
    return el
def tap(d, el):
    d.execute_script("arguments[0].scrollIntoView({block:'center'})", el); time.sleep(0.25); el.click(); time.sleep(0.15); return el
def click_text(d, css, text):
    for el in d.find_elements(By.CSS_SELECTOR, css):
        if text in (el.text or ''):
            d.execute_script("arguments[0].scrollIntoView({block:'center'})", el); time.sleep(0.25); el.click(); time.sleep(0.3); return el
    raise AssertionError('no %s with text %r' % (css, text))
def add_files(d, input_css, names, last_modified=None):
    """Simulate picking files (exactly what the iPhone hands the page): build File objects, set input.files, fire change."""
    return d.execute_async_script("""
      const [css, names, lm, done] = arguments;
      (async () => {
        const inp = document.querySelector(css); if (!inp) return done('no input ' + css);
        const dt = new DataTransfer();
        for (const n of names) { const b = await (await fetch('fx/' + n)).blob();
          dt.items.add(new File([b], n, {type: n.endsWith('.jpg') ? 'image/jpeg' : 'application/octet-stream', lastModified: lm || Date.now()})); }
        inp.files = dt.files; inp.dispatchEvent(new Event('change', {bubbles: true})); done('ok');
      })().catch(e => done('ERR ' + e));""", input_css, names, last_modified)
def capture_hook(d):
    J(d, "window.__cap=[]; window.__pa.deliverHook=(blob,name,type)=>{ window.__cap.push({blob:blob,name:name,type:type}); return 'shared'; };")
def read_capture(d, i=-1):
    return d.execute_async_script("""
      const [i, done] = arguments; const c = window.__cap[i < 0 ? window.__cap.length + i : i]; if (!c) return done(null);
      const r = new FileReader(); r.onload = () => done({name: c.name, type: c.type, size: c.blob.size, b64: r.result.split(',')[1]}); r.readAsDataURL(c.blob);""", i)
def state(d): return J(d, "return JSON.parse(JSON.stringify(window.__pa.cur))")
def ms_local(y, mo, da, h, mi, s):
    import zoneinfo
    return int(datetime.datetime(y, mo, da, h, mi, s, tzinfo=zoneinfo.ZoneInfo('America/Los_Angeles')).timestamp() * 1000)

def ready(d):
    return wait(d, "window.__pa && window.__pa.ready", 30, 'app ready')

# ------------------------------------------------------------------ main scenario
def scenario_main(d):
    d.get(BASE + 'index.html'); ready(d)
    check(J(d, "return !document.getElementById('libView').hidden && document.getElementById('splash').hidden"), 'opens to the inspections library')
    check('No inspections yet' in J(d, "return document.getElementById('libList').innerText"), 'empty library message shown')
    shot(d, '01_library_empty')
    check(wait(d, "navigator.serviceWorker && navigator.serviceWorker.getRegistration().then(r=>!!r)", 10), 'service worker registered (offline support)')

    # --- new inspection + details typed with the keyboard
    click(d, '#newInspBtn')
    check(wait(d, "!document.getElementById('inspView').hidden", 10, 'inspection view'), 'New Inspection opens a blank inspection')
    insp_id = J(d, "return window.__pa.cur.id")
    check(J(d, "return window.__pa.cur.details.inspector") == 'Bill Phillips', 'inspector defaults to Bill Phillips')
    check(J(d, "return window.__pa.cur.details.movein").count('-') == 2, 'move-in date defaults to today')
    for fid, txt in [('f_address', '1450 Ocean View Blvd, Pacific Grove, CA'), ('f_unit', '7'), ('f_tenant', 'Jordan & Casey Rivera'), ('f_rent', '$3,200'), ('f_deposit', '$3,500')]:
        el = d.find_element(By.ID, fid); d.execute_script("arguments[0].scrollIntoView({block:'center'})", el); el.click(); el.send_keys(txt)
    check(J(d, "return document.body.classList.contains('typing')"), 'bottom bar hides while typing (keyboard can’t cover fields)')
    check(J(d, "return getComputedStyle(document.getElementById('actionBar')).display") == 'none', 'action bar actually hidden during typing')
    J(d, "document.activeElement.blur()"); time.sleep(0.6)
    check(not J(d, "return document.body.classList.contains('typing')"), 'bottom bar returns after typing')
    check(wait(d, "document.getElementById('savePill').textContent.indexOf('Saved')>=0", 5), 'header shows ✓ Saved')
    saved = J(d, "return window.__pa.dbGet('inspections', arguments[0]).then(x=>x.details)", insp_id)
    check(saved and saved['address'].startswith('1450 Ocean View') and saved['deposit'] == '$3,500', 'typed details are in storage within a second')
    check(J(d, "return document.getElementById('inspTitle').textContent") == '1450 Ocean View Blvd, Pacific Grove, CA · Unit 7', 'header title shows address + unit')
    shot(d, '02_details')

    # --- standard rooms
    click(d, '#stdRoomsBtn')
    check(J(d, "return window.__pa.cur.areas.length") == 15, 'Standard list adds 15 rooms in one tap')
    check(J(d, "return document.getElementById('stp_movein').textContent") == '0/15 rooms', 'stage bar shows 0/15 progress')
    shot(d, '03_rooms')

    # --- room 1: add photos through the Library picker (EXIF dates + rotated portrait)
    rid1 = J(d, "return window.__pa.cur.areas[3].id")  # Kitchen
    click(d, '#room_%s .room-h' % rid1)
    check(J(d, "return window.__pa.openRid") == rid1, 'tapping a room opens it')
    r = add_files(d, '#room_%s input[data-act=file-lib]' % rid1, ['land_exif.jpg', 'portrait_rot6.jpg', 'noexif.jpg'], last_modified=ms_local(2026, 10, 6, 15, 0, 0))
    check(r == 'ok', 'library picker accepted 3 files')
    check(wait(d, "window.__pa.cur.areas[3].movein.photos.length===3 && !document.querySelector('#room_%s .thumb.pending')" % rid1, 30, 'photos processed'), '3 photos processed and saved')
    ph = J(d, "return window.__pa.cur.areas[3].movein.photos")
    exp1 = ms_local(2026, 3, 14, 10, 22, 33)  # offset -07:00 == PT DST
    check(ph[0]['ts'] == int(datetime.datetime(2026, 3, 14, 17, 22, 33, tzinfo=datetime.timezone.utc).timestamp() * 1000) and ph[0]['dateSrc'] == 'exif', 'camera-roll photo keeps the date it was TAKEN (EXIF), not today')
    check(ph[1]['ts'] == ms_local(2025, 7, 1, 9, 15, 0), 'EXIF date without timezone read as local time')
    check(ph[2]['ts'] == ms_local(2026, 10, 6, 15, 0, 0) and ph[2]['dateSrc'] == 'file', 'photo without EXIF falls back to file date')
    check(ph[0]['w'] == 1600 and ph[0]['h'] == 1200, 'landscape photo stored at 1600x1200 (from 4032x3024)')
    check(ph[1]['w'] == 1200 and ph[1]['h'] == 1600, 'rotated iPhone portrait is stored upright (1200x1600)')
    check(all(p['stamped'] for p in ph), 'date/address/stage stamp burned into each photo')
    sizes = J(d, "return Promise.all(window.__pa.cur.areas[3].movein.photos.map(p=>Promise.all([window.__pa.dbGet('full',p.id),window.__pa.dbGet('thumb',p.id)]))).then(a=>a.map(x=>[x[0]&&x[0].byteLength,x[1]&&x[1].byteLength]))")
    check(all(s[0] and s[0] > 50000 and s[1] and s[1] < 60000 for s in sizes), 'full photo + small thumbnail stored per photo %s' % sizes)
    check(wait(d, "Array.from(document.querySelectorAll('#room_%s .room-b [data-part=thumbs] img')).filter(i=>i.complete&&i.naturalWidth>0).length===3" % rid1, 10), 'thumbnails render in the room')
    # broken file -> friendly error, nothing added
    add_files(d, '#room_%s input[data-act=file-lib]' % rid1, ['broken.jpg'])
    check(wait(d, "document.getElementById('toast').classList.contains('show') && document.getElementById('toast').innerText.indexOf('couldn')>=0", 10), 'unreadable file gives a clear message')
    check(J(d, "return window.__pa.cur.areas[3].movein.photos.length") == 3, 'unreadable file adds nothing')

    # --- condition + quick phrases + typed comment
    click(d, '#room_%s .seg[data-part=cond] button.good' % rid1)
    check(J(d, "return window.__pa.cur.areas[3].movein.cond") == 'good', 'condition chip sets Good')
    click_text(d, '#room_%s .phrases button' % rid1, 'Clean')
    click_text(d, '#room_%s .phrases button' % rid1, 'Minor wear')
    ta = d.find_element(By.CSS_SELECTOR, '#room_%s textarea[data-act=note]' % rid1)
    check(ta.get_attribute('value') == 'Clean, minor wear', 'one-tap phrases build the comment ("Clean, minor wear")')
    d.execute_script("arguments[0].scrollIntoView({block:'center'})", ta); tap(d, ta); ta.send_keys('. Small chip on counter edge by sink')
    J(d, "document.activeElement.blur()"); time.sleep(0.7)
    check(J(d, "return window.__pa.cur.areas[3].movein.note").endswith('chip on counter edge by sink'), 'typed comment saved to the room')
    shot(d, '04_room_open')

    # --- viewer: open 2nd photo, caption, make main, delete + undo
    click(d, '#room_%s [data-part=thumbs] .thumb' % rid1, 1)
    check(wait(d, "!document.getElementById('viewer').hidden", 5), 'tapping a thumbnail opens the full-screen viewer')
    check(wait(d, "document.getElementById('vImg').naturalWidth===1200", 8), 'viewer loads the full-resolution photo')
    check(J(d, "return document.getElementById('vIdx').textContent") == '2 / 3', 'viewer shows position 2 / 3')
    shot(d, '05_viewer')
    cap = d.find_element(By.ID, 'vCap'); tap(d, cap); cap.send_keys('Upright portrait check')
    check(J(d, "const s=getComputedStyle(document.getElementById('vCap')); return s.backgroundColor!=='rgb(255, 255, 255)' && s.color==='rgb(255, 255, 255)'"), 'caption box is readable (light text on dark field)')
    J(d, "document.activeElement.blur()")
    click(d, '#vMain')
    p0 = J(d, "return window.__pa.cur.areas[3].movein.photos[0]")
    check(p0['w'] == 1200 and p0['cap'] == 'Upright portrait check', '“Make main” moves the photo first; caption saved')
    click(d, '#vNext'); check(J(d, "return document.getElementById('vIdx').textContent") == '2 / 3', 'next arrow moves through photos')
    click(d, '#vDel')
    check(J(d, "return window.__pa.cur.areas[3].movein.photos.length") == 2, 'delete removes the photo')
    click(d, '#toast button')
    check(J(d, "return window.__pa.cur.areas[3].movein.photos.length") == 3, 'Undo brings the deleted photo back')
    click(d, '#vClose')
    check(J(d, "return document.getElementById('viewer').hidden"), 'viewer closes')

    # --- next room button
    click(d, '#room_%s [data-act=next]' % rid1)
    rid2 = J(d, "return window.__pa.cur.areas[4].id")
    check(J(d, "return window.__pa.openRid") == rid2, '“Next room” opens the following room')

    # --- Quick Shoot rapid camera
    click(d, '#room_%s [data-act=quick]' % rid2)
    check(wait(d, "!document.getElementById('cam').hidden", 5), 'Quick Shoot opens the in-app camera')
    ok_stream = wait(d, "document.getElementById('camVideo').videoWidth>0", 15, 'camera stream')
    check(ok_stream, 'camera stream running (mock camera)')
    time.sleep(0.5); shot(d, '06_quickshoot')
    for _ in range(3):
        click(d, '#camShutter'); time.sleep(0.15)
    click(d, '#camNext')
    click(d, '#camShutter')
    check(wait(d, "window.__pa.cur.areas[4].movein.photos.length===3 && window.__pa.cur.areas[5].movein.photos.length===1", 20, 'quick shots saved'), '3 rapid shots in room 5, then ›, 1 shot in room 6')
    qp = J(d, "return window.__pa.cur.areas[4].movein.photos[0]")
    check(qp['src'] == 'quick' and qp['stamped'] and abs(qp['ts'] / 1000 - time.time()) < 120, 'Quick Shoot photos are time-stamped now and stamped')
    bright = d.execute_async_script("""const done=arguments[0]; (async()=>{ const ids=window.__pa.cur.areas[4].movein.photos.concat(window.__pa.cur.areas[5].movein.photos).map(p=>p.id); const out=[];
      for(const id of ids){ const ab=await window.__pa.dbGet('thumb',id); const bm=await createImageBitmap(new Blob([ab],{type:'image/jpeg'})); const c=document.createElement('canvas'); c.width=32;c.height=24; const g=c.getContext('2d'); g.drawImage(bm,0,0,32,24); const d=g.getImageData(0,0,32,24).data; let mx=0; for(let i=0;i<d.length;i+=4) mx=Math.max(mx,d[i],d[i+1],d[i+2]); out.push(mx); }
      done(out); })().catch(e=>done('ERR '+e));""")
    check(isinstance(bright, list) and all(b > 40 for b in bright), 'no black Quick Shoot frames saved (max brightness per photo %s)' % bright)
    click(d, '#camDone')
    check(J(d, "return document.getElementById('cam').hidden"), 'Done closes the camera')
    check(J(d, "return (document.getElementById('camVideo').srcObject===null)"), 'camera released when closed')
    check(J(d, "return document.getElementById('stp_movein').textContent") == '3/15 rooms', 'progress updates to 3/15 rooms')

    # --- signatures (draw with a real pointer)
    click(d, '#sigTenantBtn')
    check(wait(d, "!document.getElementById('sigPad').hidden", 5), 'tenant signature pad opens full screen')
    check(J(d, "return document.getElementById('sigName').value") == 'Jordan & Casey Rivera', 'signer name pre-filled from tenant')
    cv = d.find_element(By.ID, 'sigCanvas')
    w = cv.size['width']; h = cv.size['height']
    a = ActionChains(d)
    a.move_to_element_with_offset(cv, -w // 3, 10).click_and_hold()
    for i in range(12):
        a.move_by_offset(w // 20, (-1) ** i * 18)
    a.release().perform()
    time.sleep(0.3); shot(d, '07_signature')
    click(d, '#sigSave')
    sg = J(d, "return window.__pa.cur.signatures")
    check(len(sg) == 1 and sg[0]['data'].startswith('data:image/png') and sg[0]['role'] == 'tenant' and sg[0]['stage'] == 'movein', 'signature saved (tenant, move-in)')
    click(d, '#sigAgentBtn'); time.sleep(0.4)
    click(d, '#sigSave')
    check(len(J(d, "return window.__pa.cur.signatures")) == 1, 'empty signature is refused')
    a = ActionChains(d); cv = d.find_element(By.ID, 'sigCanvas')
    a.move_to_element_with_offset(cv, -60, 0).click_and_hold().move_by_offset(40, -20).move_by_offset(40, 25).move_by_offset(40, -15).release().perform()
    click(d, '#sigSave')
    check(len(J(d, "return window.__pa.cur.signatures")) == 2, 'agent signature saved')

    # --- relaunch (what happens when iOS kills the app in the background)
    J(d, "return window.__pa.flushSave()"); time.sleep(0.5)
    before = state(d); open_before = J(d, "return window.__pa.openRid")
    d.refresh(); ready(d)
    check(wait(d, "!document.getElementById('inspView').hidden && window.__pa.cur && window.__pa.cur.id===arguments[0]".replace('arguments[0]', json.dumps(insp_id)), 10), 'after relaunch the app resumes in the same inspection')
    after = state(d)
    check(after['areas'][3]['movein']['photos'] == before['areas'][3]['movein']['photos'] and after['areas'][3]['movein']['note'] == before['areas'][3]['movein']['note'], 'photos + notes identical after relaunch')
    check(len(after['signatures']) == 2 and after['details'] == before['details'], 'signatures + details identical after relaunch')
    check(J(d, "return window.__pa.openRid") == open_before and open_before, 'relaunch reopens the room you were in')
    shot(d, '08_after_relaunch')
    # what's new sheet appears once on first run with data — close if open
    if J(d, "return !document.getElementById('sheet').hidden"): click(d, '#sheetClose')

    # --- move-out
    click(d, '.st[data-stage=moveout]')
    check(J(d, "return window.__pa.cur.stage") == 'moveout', 'switched to Move-Out')
    check(not J(d, "return document.getElementById('dedCard').hidden"), 'Deposit Worksheet appears at move-out')
    if J(d, "return window.__pa.openRid") != rid1:
        click(d, '#room_%s .room-h' % rid1)
    check(J(d, "return !!document.querySelector('#room_%s details.cmp.movein[open]')" % rid1), 'move-in photos shown under the room while shooting move-out')
    add_files(d, '#room_%s input[data-act=file-lib]' % rid1, ['p1.jpg', 'p2.jpg'])
    wait(d, "window.__pa.cur.areas[3].moveout.photos.length===2", 20, 'move-out photos')
    click(d, '#room_%s .seg[data-part=cond] button.fair' % rid1)
    click(d, '#room_%s .seg[data-part=tag] button.damage' % rid1)
    ci = d.find_element(By.CSS_SELECTOR, '#room_%s input[data-act=charge]' % rid1)
    check(ci.is_displayed(), 'charge field appears for Damage')
    tap(d, ci); ci.send_keys('150'); J(d, "document.activeElement.blur()")
    ta = d.find_element(By.CSS_SELECTOR, '#room_%s textarea[data-act=note]' % rid1); tap(d, ta); ta.send_keys('Burn mark on counter; chip enlarged.'); J(d, "document.activeElement.blur()")
    shot(d, '09_moveout_room')
    click(d, '#room_%s [data-act=next]' % rid1)
    add_files(d, '#room_%s input[data-act=file-lib]' % rid2, ['p3.jpg', 'p4.jpg', 'p5.jpg'])
    wait(d, "window.__pa.cur.areas[4].moveout.photos.length===3", 20, 'room2 move-out photos')
    click(d, '#room_%s .seg[data-part=tag] button.cleaning' % rid2)
    ci = d.find_element(By.CSS_SELECTOR, '#room_%s input[data-act=charge]' % rid2); tap(d, ci); ci.send_keys('85.50'); J(d, "document.activeElement.blur()")
    click(d, '#room_%s [data-act=next]' % rid2)
    rid3 = J(d, "return window.__pa.cur.areas[5].id")
    click(d, '#room_%s .seg[data-part=tag] button.wear' % rid3)
    time.sleep(0.6)
    check(abs(J(d, "return window.__pa.cur.areas.reduce((s,r)=>s+((r.tag==='damage'||r.tag==='cleaning')?parseFloat(String(r.charge).replace(/[^0-9.]/g,''))||0:0),0)") - 235.5) < 0.01, 'charges total $235.50')
    ded = J(d, "return document.getElementById('dedBody').innerText")
    check('$235.50' in ded and '$3,264.50' in ded, 'worksheet shows total and balance to return ($3,264.50)')
    shot(d, '10_worksheet')
    # after repairs
    click(d, '.st[data-stage=afterrepairs]')
    if J(d, "return window.__pa.openRid") != rid1: click(d, '#room_%s .room-h' % rid1)
    add_files(d, '#room_%s input[data-act=file-lib]' % rid1, ['p6.jpg'])
    wait(d, "window.__pa.cur.areas[3].afterrepairs.photos.length===1", 20, 'after-repairs photo')
    ta = d.find_element(By.CSS_SELECTOR, '#room_%s textarea[data-act=note]' % rid1); tap(d, ta); ta.send_keys('Counter resurfaced 10/20.'); J(d, "document.activeElement.blur()")
    click(d, '.st[data-stage=moveout]')
    # move-out tenant signature
    click(d, '#sigTenantBtn'); time.sleep(0.3)
    check(J(d, "return document.querySelector('#sigStageSeg button.on').dataset.v") == 'moveout', 'signature defaults to Move-Out stage at move-out')
    a = ActionChains(d); cv = d.find_element(By.ID, 'sigCanvas')
    a.move_to_element_with_offset(cv, -80, 10).click_and_hold().move_by_offset(50, -30).move_by_offset(50, 40).move_by_offset(50, -20).release().perform()
    click(d, '#sigSave')

    # --- PDFs
    capture_hook(d)
    pdfs = {}
    for rtype, size in [('moveout', 'email'), ('movein', 'email'), ('moveout', 'full')]:
        click(d, '#pdfBtn')
        check(wait(d, "!document.getElementById('sheet').hidden && document.getElementById('pdfGo')", 5), 'PDF sheet opens')
        click(d, 'input[name=rtype][value=%s]' % rtype); click(d, 'input[name=psize][value=%s]' % size)
        t0 = time.time(); click(d, '#pdfGo')
        ok = wait(d, "document.getElementById('pdfShare')", 90, 'pdf build %s %s' % (rtype, size))
        el = time.time() - t0
        if rtype == 'moveout' and size == 'email': shot(d, '11_pdf_ready')
        click(d, '#pdfShare'); time.sleep(0.4)
        cap = read_capture(d)
        fn = os.path.join(OUT, 'report_%s_%s.pdf' % (rtype, size))
        open(fn, 'wb').write(base64.b64decode(cap['b64']))
        pdfs[(rtype, size)] = fn
        check(cap['type'] == 'application/pdf' and cap['size'] > 20000, 'PDF %s/%s built in %.1fs: %s (%d KB, %s pages)' % (rtype, size, el, cap['name'], cap['size'] // 1024, J(d, "return window.__lastPdf.pages")))
        if J(d, "return !document.getElementById('sheet').hidden"): click(d, '#sheetClose')
    e_sz = os.path.getsize(pdfs[('moveout', 'email')]); f_sz = os.path.getsize(pdfs[('moveout', 'full')])
    check(e_sz < f_sz, 'email-friendly PDF is smaller than full resolution (%d KB vs %d KB)' % (e_sz // 1024, f_sz // 1024))

    # --- backup this inspection
    click(d, '#inspMenuBtn'); click_text(d, '.menu-item', 'Back up this inspection')
    click(d, '#bkGo')
    wait(d, "document.getElementById('bkShare')", 60, 'backup built')
    shot(d, '12_backup_ready')
    click(d, '#bkShare'); time.sleep(0.6)
    bk = read_capture(d)
    bk_path = os.path.join(OUT, bk['name']); open(bk_path, 'wb').write(base64.b64decode(bk['b64']))
    check(bk['name'].endswith('.json') and bk['size'] > 300000, 'backup file created: %s (%d KB)' % (bk['name'], bk['size'] // 1024))
    check(wait(d, "window.__pa.cur.backupTs>=window.__pa.cur.updated", 5), 'inspection marked as backed up')
    n_photos = J(d, "return window.__pa.cur.areas.reduce((s,r)=>s+r.movein.photos.length+r.moveout.photos.length+r.afterrepairs.photos.length,0)")

    # --- library card
    click(d, '#backBtn')
    check(wait(d, "!document.getElementById('libView').hidden", 5), 'back to the library')
    card = J(d, "return document.querySelector('.icard').innerText")
    check('1450 Ocean View' in card and 'Backed up' in card, 'library card shows the inspection and “Backed up”')
    shot(d, '13_library')

    # --- delete + restore from the backup
    click(d, '.icard .ic-more'); click_text(d, '.menu-item', 'Delete inspection')
    click_text(d, '#sheetBody button', 'Delete permanently')
    check(wait(d, "window.__pa.lib.length===0", 5), 'inspection deleted')
    left = J(d, "return window.__pa.dbGetAll('full').then(a=>a.length)")
    check(left == 0, 'deleting an inspection frees its photos (no orphans left: %s)' % left)
    J(d, "return 1")
    # inject the captured backup file into the Restore picker
    d.execute_async_script("""
      const [b64, name, done] = arguments; const bin = atob(b64); const u = new Uint8Array(bin.length); for (let i=0;i<bin.length;i++) u[i]=bin.charCodeAt(i);
      const dt = new DataTransfer(); dt.items.add(new File([u], name, {type:'application/json'}));
      const inp = document.getElementById('importFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); done('ok');""", bk['b64'], bk['name'])
    check(wait(d, "window.__pa.cur && !document.getElementById('inspView').hidden && document.getElementById('busy').hidden", 60, 'restore'), 'restore opens the restored inspection')
    rs = state(d)
    n2 = sum(len(r_[st]['photos']) for r_ in rs['areas'] for st in ('movein', 'moveout', 'afterrepairs'))
    check(n2 == n_photos and len(rs['signatures']) == 3 and rs['areas'][3]['charge'] == '150', 'restored inspection has all %d photos, 3 signatures, charges' % n_photos)
    thumbs_ok = wait(d, "(()=>{ const ids=window.__pa.cur.areas[3].movein.photos.map(p=>p.id); return window.__pa.dbGet('full',ids[0]).then(x=>!!x&&x.byteLength>50000); })()", 10)
    check(thumbs_ok, 'restored photo bytes are readable')
    # restore again -> duplicate prompt -> keep both
    click(d, '#backBtn'); wait(d, "!document.getElementById('libView').hidden", 5)
    d.execute_async_script("""
      const [b64, name, done] = arguments; const bin = atob(b64); const u = new Uint8Array(bin.length); for (let i=0;i<bin.length;i++) u[i]=bin.charCodeAt(i);
      const dt = new DataTransfer(); dt.items.add(new File([u], name, {type:'application/json'}));
      const inp = document.getElementById('importFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); done('ok');""", bk['b64'], bk['name'])
    check(wait(d, "!document.getElementById('sheet').hidden && document.getElementById('sheetTitle').textContent==='Already on this iPhone'", 20), 'restoring a duplicate asks what to do')
    click_text(d, '#sheetBody button', 'Keep both')
    check(wait(d, "window.__pa.cur && window.__pa.cur.id!==arguments_id".replace('arguments_id', json.dumps(rs['id'])), 40, 'copy import'), 'Keep both imports a separate copy')
    click(d, '#backBtn'); wait(d, "!document.getElementById('libView').hidden", 5)
    check(J(d, "return window.__pa.lib.length") == 2, 'library now has both copies')
    allf = J(d, "return window.__pa.dbGetAll('full').then(a=>a.length)")
    check(allf == 2 * n_photos, 'each copy has its own photos (%s stored)' % allf)
    shot(d, '14_library_two')
    # restore once more and choose Replace: count stays the same, old photo bytes are released
    d.execute_async_script("""
      const [b64, name, done] = arguments; const bin = atob(b64); const u = new Uint8Array(bin.length); for (let i=0;i<bin.length;i++) u[i]=bin.charCodeAt(i);
      const dt = new DataTransfer(); dt.items.add(new File([u], name, {type:'application/json'}));
      const inp = document.getElementById('importFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); done('ok');""", bk['b64'], bk['name'])
    check(wait(d, "!document.getElementById('sheet').hidden && document.getElementById('sheetTitle').textContent==='Already on this iPhone'", 20), 'duplicate prompt shown again')
    click_text(d, '#sheetBody button', 'Replace')
    check(wait(d, "window.__pa.cur && window.__pa.cur.id===" + json.dumps(rs['id']) + " && document.getElementById('busy').hidden", 40, 'replace import'), 'Replace restores over the existing inspection')
    click(d, '#backBtn'); wait(d, "!document.getElementById('libView').hidden", 5)
    allf2 = J(d, "return window.__pa.dbGetAll('full').then(a=>a.length)")
    check(J(d, "return window.__pa.lib.length") == 2 and allf2 == 2 * n_photos, 'Replace keeps 2 inspections and releases the replaced photos (%s stored)' % allf2)
    check(J(d, "return document.documentElement.scrollWidth<=window.innerWidth+1"), 'no sideways scrolling at phone width')
    # regression: leave the page right after an edit, then launch again — must not freeze on "Opening…"
    click(d, '.icard .ic-main'); wait(d, "window.__pa.cur", 5)
    J(d, "const el=document.getElementById('f_gennotes'); el.value='left in a hurry'; el.dispatchEvent(new Event('input',{bubbles:true}));")
    d.get(BASE + 'fx/check_v3.html'); time.sleep(0.5)
    d.get(BASE + 'index.html')
    check(wait(d, "window.__pa && window.__pa.ready", 15), 'leaving mid-edit and relaunching does not freeze the app')
    errs = J(d, "return window.__pa.errLog.slice()")
    check(all('broken' in e or 'readable' in e or 'addFiles' in e for e in errs), 'no unexpected errors logged: %s' % errs)
    return pdfs

# ------------------------------------------------------------------ migration from v3
def scenario_migration(d):
    d.get(BASE + 'fx/seed_v3.html')
    check(wait(d, "window.seedDone", 15), 'seeded a v3 saved inspection into the old storage')
    d.get(BASE + 'index.html'); ready(d)
    lib = J(d, "return window.__pa.lib.map(x=>({id:x.id,t:x.details.address,n:x.areas.length,p:x.areas.reduce((s,r)=>s+r.movein.photos.length,0),sg:x.signatures.length}))")
    check(len(lib) == 1 and lib[0]['id'] == 'v3-migrated' and lib[0]['p'] == 3 and lib[0]['sg'] == 1, 'v3 inspection moved into v4 automatically: %s' % lib)
    check(wait(d, "!document.getElementById('sheet').hidden && document.getElementById('sheetBody').innerText.indexOf('moved in automatically')>=0", 5), 'What’s New explains the move')
    time.sleep(0.8); shot(d, '20_migrated_whatsnew')
    click(d, '#wnOk')
    click(d, '.icard .ic-main')
    wait(d, "window.__pa.cur", 5)
    x = state(d)
    check(x['details']['tenant'] == 'Pat Example' and x['areas'][0]['movein']['note'] == 'Counters clean, new range.', 'migrated details + notes intact')
    p = x['areas'][0]['movein']['photos'][0]
    check(p['src'] == 'v3' and not p['stamped'] and p['w'] == 1400, 'migrated photos keep their dates (overlay stamp in PDF)')
    check(wait(d, "Array.from(document.querySelectorAll('.room img.rmini')).filter(i=>i.naturalWidth>0).length>=2", 8), 'migrated thumbnails display')
    shot(d, '21_migrated_inspection')
    # old storage untouched
    d.get(BASE + 'fx/check_v3.html')
    v = wait(d, "window.v3check", 10)
    check(v and v.startswith('present'), 'old v3 save left untouched as a safety net (%s)' % v)
    # relaunch must not migrate twice
    d.get(BASE + 'index.html'); ready(d)
    check(J(d, "return window.__pa.lib.length") == 1, 'migration runs only once')
    # importing the old .json export of the same project -> duplicate prompt -> keep both
    J(d, "if(window.__pa.cur) return window.__pa.showLibrary();")
    wait(d, "!document.getElementById('libView').hidden", 5)
    d.execute_async_script("""const [done]=arguments; (async()=>{ const b=await (await fetch('fx/v3_project.json')).blob();
      const dt=new DataTransfer(); dt.items.add(new File([b],'PhotoAddendum_742_Evergreen.json',{type:'application/json'}));
      const inp=document.getElementById('importFile'); inp.files=dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); done('ok'); })();""")
    check(wait(d, "!document.getElementById('sheet').hidden && document.getElementById('sheetTitle').textContent==='Already on this iPhone'", 20), 'old .json for an inspection already here is recognized')
    click_text(d, '#sheetBody button', 'Keep both')
    check(wait(d, "window.__pa.cur && window.__pa.cur.id!=='v3-migrated'", 30), 'old .json imported as a copy')
    # v1 file
    J(d, "return window.__pa.showLibrary()"); wait(d, "!document.getElementById('libView').hidden", 5)
    d.execute_async_script("""const [done]=arguments; (async()=>{ const b=await (await fetch('fx/v1_project.json')).blob();
      const dt=new DataTransfer(); dt.items.add(new File([b],'old.json',{type:'application/json'}));
      const inp=document.getElementById('importFile'); inp.files=dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); done('ok'); })();""")
    check(wait(d, "window.__pa.cur && window.__pa.cur.details.address==='12 Old Format Way'", 30), 'very old (v1) project file imports')
    y = state(d)
    check(y['areas'][0]['afterrepairs']['photos'] == [] and y['areas'][0]['movein']['photos'][0]['w'] == 1400, 'v1 project upgraded cleanly')
    # not-a-backup file
    J(d, "return window.__pa.showLibrary()"); wait(d, "!document.getElementById('libView').hidden", 5)
    d.execute_async_script("""const [done]=arguments; const dt=new DataTransfer(); dt.items.add(new File(['{"hello":1}'],'x.json',{type:'application/json'}));
      const inp=document.getElementById('importFile'); inp.files=dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); done('ok');""")
    check(wait(d, "document.getElementById('toast').innerText.indexOf('isn’t a Photo Addendum')>=0", 10), 'wrong file type gives a clear message')

# ------------------------------------------------------------------ iPad
def scenario_ipad(d):
    d.get(BASE + 'index.html'); ready(d)
    check(J(d, "return window.innerWidth") >= 1000, 'iPad landscape viewport (%s px)' % J(d, "return window.innerWidth"))
    click(d, '#newInspBtn'); wait(d, "!document.getElementById('inspView').hidden", 10)
    J(d, "const a=document.getElementById('f_address'); a.value='88 Lighthouse Ave, Monterey, CA'; a.dispatchEvent(new Event('input',{bubbles:true}));")
    click(d, '#stdRoomsBtn')
    rid = J(d, "return window.__pa.cur.areas[3].id")
    click(d, '#room_%s .room-h' % rid)
    add_files(d, '#room_%s input[data-act=file-lib]' % rid, ['land_exif.jpg', 'p1.jpg', 'p2.jpg'])
    wait(d, "window.__pa.cur.areas[3].movein.photos.length===3", 30, 'ipad photos')
    check('this iPad' in J(d, "return document.querySelector('.devname').parentNode.innerText"), 'wording says “this iPad” on iPad')
    click(d, '.st[data-stage=moveout]')
    if J(d, "return window.__pa.openRid") != rid: click(d, '#room_%s .room-h' % rid)
    add_files(d, '#room_%s input[data-act=file-lib]' % rid, ['p3.jpg'])
    wait(d, "window.__pa.cur.areas[3].moveout.photos.length===1", 20, 'ipad mo photo')
    cols = J(d, "return getComputedStyle(document.querySelector('#room_%s .rb-grid')).gridTemplateColumns" % rid)
    check(len(cols.split()) == 2, 'iPad: move-out shooting area and move-in reference side by side (%s)' % cols)
    J(d, "document.querySelector('#room_%s').scrollIntoView({block:'start'}); window.scrollBy(0,-150)" % rid); time.sleep(0.6)
    shot(d, '40_ipad_moveout_room')
    click(d, '#backBtn'); wait(d, "!document.getElementById('libView').hidden", 5)
    # second inspection so the library shows the 2-column grid
    click(d, '#newInspBtn'); wait(d, "!document.getElementById('inspView').hidden", 10)
    J(d, "const a=document.getElementById('f_address'); a.value='2 Ocean Ave, Carmel, CA'; a.dispatchEvent(new Event('input',{bubbles:true}));"); time.sleep(0.6)
    click(d, '#backBtn'); wait(d, "!document.getElementById('libView').hidden && window.__pa.lib.length===2", 5)
    if J(d, "return !document.getElementById('sheet').hidden"): click(d, '#sheetClose')
    lc = J(d, "return getComputedStyle(document.getElementById('libList')).gridTemplateColumns")
    check(len(lc.split()) == 2, 'iPad: inspections list in two columns (%s)' % lc)
    shot(d, '41_ipad_library')
    ix = J(d, "return Array.from(document.querySelectorAll('.icard .ic-main')).findIndex(b=>b.textContent.indexOf('Lighthouse')>=0)")
    click(d, '.icard .ic-main', ix); wait(d, "window.__pa.cur && window.__pa.cur.areas.length", 5)
    click(d, '#pdfBtn'); time.sleep(0.4)
    rc = J(d, "const r=document.querySelector('.sheet').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2, innerWidth/2, innerHeight/2]")
    check(abs(rc[0] - rc[2]) < 4 and abs(rc[1] - rc[3]) < 30, 'iPad: panels open centered on screen')
    shot(d, '42_ipad_pdf_sheet')
    click(d, '#sheetClose')
    click(d, '#sigTenantBtn'); time.sleep(0.5)
    hh = J(d, "return document.getElementById('sigCanvas').getBoundingClientRect().height")
    check(hh >= 300, 'iPad: bigger signature area (%d px tall)' % hh)
    shot(d, '43_ipad_signature')
    click(d, '#sigCancel')
    check(J(d, "return document.documentElement.scrollWidth<=window.innerWidth+1"), 'no sideways scrolling at iPad width')

# ------------------------------------------------------------------ offline
def scenario_offline(d, stop_server, start_server):
    d.get(BASE + 'index.html'); ready(d)
    ok = wait(d, "navigator.serviceWorker.ready.then(r=>!!r.active)", 15)
    d.refresh(); ready(d)
    ctl = wait(d, "!!navigator.serviceWorker.controller", 10)
    check(ctl, 'service worker controls the page after first launch')
    stop_server(); time.sleep(1)
    try:
        d.refresh()
        okk = wait(d, "window.__pa && window.__pa.ready", 25)
        check(okk, 'app opens with NO network (from the offline cache)')
        shot(d, '30_offline')
    finally:
        start_server()

if __name__ == '__main__':
    import signal
    def start_server():
        global SRV
        SRV = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '--bind', '127.0.0.1', '--directory', os.environ.get('WWW', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.8)
    def stop_server():
        SRV.terminate(); SRV.wait()
    start_server()
    which = sys.argv[3] if len(sys.argv) > 3 else 'all'
    try:
        if which in ('all', 'main'):
            wd, d = start_driver(4444)
            try: scenario_main(d)
            except Exception as e: log(False, 'main scenario crashed: %s\n%s' % (e, traceback.format_exc()[-2500:])); shot(d, 'crash_main')
            finally: d.quit(); wd.terminate()
        if which in ('all', 'migration'):
            wd, d = start_driver(4445)
            try: scenario_migration(d)
            except Exception as e: log(False, 'migration scenario crashed: %s\n%s' % (e, traceback.format_exc()[-2500:])); shot(d, 'crash_migration')
            finally: d.quit(); wd.terminate()
        if which in ('all', 'ipad'):
            wd, d = start_driver(4447, ua=IPAD_UA, size=(1180, 900))
            try: scenario_ipad(d)
            except Exception as e: log(False, 'ipad scenario crashed: %s\n%s' % (e, traceback.format_exc()[-2500:])); shot(d, 'crash_ipad')
            finally: d.quit(); wd.terminate()
        if which in ('all', 'offline'):
            wd, d = start_driver(4446)
            try: scenario_offline(d, stop_server, start_server)
            except Exception as e: log(False, 'offline scenario crashed: %s\n%s' % (e, traceback.format_exc()[-2500:]))
            finally: d.quit(); wd.terminate()
    finally:
        try: stop_server()
        except Exception: pass
    fails = [m for ok, m in RESULTS if not ok]
    print('\n%d checks, %d failed' % (len(RESULTS), len(fails)))
    for m in fails: print('  FAIL:', m.split('\n')[0])
    sys.exit(1 if fails else 0)
