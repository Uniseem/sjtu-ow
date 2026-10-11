"""真实浏览器延迟加载字体：look 必须等字体，删除等待后必须失败。"""
from pathlib import Path
import http.server
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root))
spec=importlib.util.spec_from_file_location('parity_probe',root/'e2e/parity/parity.py')
parity=importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)
screens=parity.screens
font=Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
assert font.exists(), 'fixture font unavailable'
font_data=font.read_bytes()
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self):
  if self.path.startswith('/font.ttf'):
   time.sleep(2)
   body=font_data;kind='font/ttf'
  else:
   body=b'''<!doctype html><style>#main{width:500px;font-size:40px}</style><main id="main">MMMMWWWWiiii</main><script>setTimeout(()=>{const style=document.createElement('style');style.textContent='@font-face{font-family:Delayed;src:url(/font.ttf)} #main{font-family:Delayed}';document.head.append(style)},200)</script>'''
   kind='text/html'
  self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

def check(wait):
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 with tempfile.TemporaryDirectory(prefix='ow-font-probe-') as tmp:
  port=screens.free_port()
  proc=subprocess.Popen(['chromium','--headless=new','--no-sandbox',f'--remote-debugging-port={port}',f'--user-data-dir={tmp}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   screens.wait_for(f'http://127.0.0.1:{port}/json/version')
   targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
   tools=screens.DevTools(next(t for t in targets if t.get('type')=='page')['webSocketDebuggerUrl'])
   tools.send('Page.enable');tools.send('Network.enable')
   original=parity.evaluate
   def evaluate(tools,expression):
    if not wait and expression.startswith('document.fonts.ready.then'):
     return None
    return original(tools,expression)
   parity.evaluate=evaluate
   parity.look(tools,f'http://127.0.0.1:{server.server_port}/',None,1280,'dark',Path(tmp)/'shot.png')
   loaded=original(tools,"document.fonts.check('40px Delayed') && document.fonts.status === 'loaded'")
   assert loaded, 'capture completed before delayed font loaded'
   return True
  finally:
   parity.evaluate=original
   proc.terminate();proc.wait(timeout=10)
 server.shutdown();server.server_close()

assert check(True)
print('FONT-CAPTURE-OK',flush=True)
try:
 check(False)
except AssertionError as err:
 print(f'CAUGHT removed font wait: {err}',flush=True)
else:
 raise SystemExit('SURVIVED removed font wait')
print('FONT-MUTATION-OK',flush=True)
