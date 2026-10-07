"""Stress test in WebKit: one inspection with 15 rooms x (8 move-in + 8 move-out) = 240 photos.
Shows that saving stays instant no matter how many photos, and measures PDF/backup at that size."""
import sys, os, time, json, base64
sys.path.insert(0, os.path.dirname(__file__))
import wk_test as T
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8765/'
T.OUT = sys.argv[2] if len(sys.argv) > 2 else '/tmp/pa_stress'; os.makedirs(T.OUT, exist_ok=True)
FILES = ['p1.jpg', 'p2.jpg', 'p3.jpg', 'p4.jpg', 'p5.jpg', 'p6.jpg', 'noexif.jpg', 'land_exif.jpg']
def save_latency(d):
    return d.execute_async_script("""const done=arguments[0]; const t0=performance.now(); const x=window.__pa.cur;
      x.details.gennotes='latency '+Date.now(); const el=document.getElementById('f_gennotes'); el.value=x.details.gennotes; el.dispatchEvent(new Event('input',{bubbles:true}));
      window.__pa.flushSave().then(()=>window.__pa.dbGet('inspections',x.id)).then(y=>done({ms:performance.now()-t0, ok:y.details.gennotes===x.details.gennotes, recordKB:Math.round(JSON.stringify(y).length/1024)}));""")
wd, d = T.start_driver(4460)
try:
    d.get(BASE + 'index.html'); T.ready(d)
    T.click(d, '#newInspBtn'); T.wait(d, "!document.getElementById('inspView').hidden", 10)
    T.J(d, "const a=document.getElementById('f_address'); a.value='500 Stress Test Way, Monterey, CA'; a.dispatchEvent(new Event('input',{bubbles:true})); const dp=document.getElementById('f_deposit'); dp.value='$4,000'; dp.dispatchEvent(new Event('input',{bubbles:true}));")
    T.click(d, '#stdRoomsBtn')
    l0 = save_latency(d); T.log(l0['ok'], 'save with 0 photos: %.0f ms (record %d KB)' % (l0['ms'], l0['recordKB']))
    t0 = time.time()
    for stage in ['movein', 'moveout']:
        if stage == 'moveout': T.click(d, '.st[data-stage=moveout]')
        for i in range(15):
            rid = T.J(d, "return window.__pa.cur.areas[%d].id" % i)
            if T.J(d, "return window.__pa.openRid") != rid: T.click(d, '#room_%s .room-h' % rid)
            T.add_files(d, '#room_%s input[data-act=file-lib]' % rid, FILES)
            T.wait(d, "window.__pa.cur.areas[%d].%s.photos.length===8 && !document.querySelector('.thumb.pending')" % (i, stage), 60, 'room %d %s' % (i, stage))
            if stage == 'moveout' and i % 3 == 0:
                T.J(d, "const r=window.__pa.cur.areas[%d]; r.tag='damage'; r.charge='%d'; r.moveout.note='Wall gouge and carpet stain, needs patch and paint.'; window.__pa.flushSave();" % (i, 50 + i * 10))
    el = time.time() - t0
    n = T.J(d, "return window.__pa.cur.areas.reduce((s,r)=>s+r.movein.photos.length+r.moveout.photos.length,0)")
    T.log(n == 240, 'added %d photos in %.0fs (%.2fs per photo incl. resize, stamp, thumbnail, save)' % (n, el, el / max(1, n)))
    l1 = save_latency(d); T.log(l1['ok'] and l1['ms'] < max(250, l0['ms'] * 6), 'save with 240 photos: %.0f ms (record %d KB) — stays instant' % (l1['ms'], l1['recordKB']))
    t1 = time.time(); d.refresh(); T.ready(d); T.wait(d, "window.__pa.cur && window.__pa.cur.areas.length===15", 10)
    T.log(True, 'relaunch into the 240-photo inspection: %.1fs' % (time.time() - t1))
    T.J(d, "return window.__pa.showLibrary()")
    T.capture_hook(d)
    for size in ['email', 'full']:
        r = d.execute_async_script("""const [size,done]=arguments; const t0=performance.now(); window.__pa.dbGet('inspections', window.__pa.lib[0].id).then(x=>window.__pa.buildPDF(x,'moveout',size,null)).then(res=>done({ms:performance.now()-t0,pages:res.pages,kb:Math.round(res.blob.size/1024)})).catch(e=>done({err:String(e)}));""", size)
        T.log('err' not in r, 'Move-Out PDF (%s) for 240 photos: %s pages, %.1f MB, built in %.1fs' % (size, r.get('pages'), r.get('kb', 0) / 1024, r.get('ms', 0) / 1000))
    r = d.execute_async_script("""const done=arguments[0]; const t0=performance.now(); window.__pa.buildBackupBlob(window.__pa.lib,null).then(b=>done({ms:performance.now()-t0,mb:b.size/1048576})).catch(e=>done({err:String(e)}));""")
    T.log('err' not in r, 'backup of 240 photos: %.1f MB in %.1fs' % (r.get('mb', 0), r.get('ms', 0) / 1000))
    est = T.J(d, "return window.__pa.dbGetAll('full').then(a=>a.reduce((s,x)=>s+x.byteLength,0)/1048576)")
    T.log(True, 'storage used by 240 photos: %.0f MB' % est)
finally:
    d.quit(); wd.terminate()
fails = [m for ok, m in T.RESULTS if not ok]
print('\n%d checks, %d failed' % (len(T.RESULTS), len(fails)))
