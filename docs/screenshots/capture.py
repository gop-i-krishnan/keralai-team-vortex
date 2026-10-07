"""
docs/screenshots/capture.py
Takes the README/SUBMISSION screenshots from the RUNNING app using headless Chrome (DevTools protocol).
Dev tooling only: needs `pip install websockets` and Chrome or Edge. Not used by the app or the tests.

Usage (backend on :8000 and `npm run dev` on :5173 already running):
    python docs/screenshots/capture.py
"""
import json
import os
import pathlib
import subprocess
import tempfile
import time
import urllib.request

from websockets.sync.client import connect

HERE = pathlib.Path(__file__).parent
API = "http://localhost:8000/api"
UI = "http://localhost:5173/"
PORT = 9333
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def api(method, path, body=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"null")


class Page:
    def __init__(self):
        exe = next(p for p in BROWSERS if os.path.exists(p))
        self.proc = subprocess.Popen([
            exe, "--headless=new", f"--remote-debugging-port={PORT}", "--window-size=1280,1000",
            f"--user-data-dir={tempfile.mkdtemp()}", "--hide-scrollbars", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
                ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        self.ws = connect(ws_url, max_size=64 * 1024 * 1024)
        self.n = 0

    def cmd(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    def js(self, expr):
        r = self.cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    def go(self, url):
        self.cmd("Page.navigate", url=url)
        time.sleep(1.8)

    def click(self, text, sel="button,a,summary"):
        ok = self.js(f"""(()=>{{const el=[...document.querySelectorAll({json.dumps(sel)})]
            .find(b=>b.textContent.trim().includes({json.dumps(text)}));
            if(!el) return false; el.click(); return true;}})()""")
        if not ok:
            raise RuntimeError(f"nothing to click: {text!r}")
        time.sleep(0.7)

    def set(self, sel, value, idx=0):
        self.js(f"""(()=>{{const el=document.querySelectorAll({json.dumps(sel)})[{idx}];
            const proto=el.tagName==='SELECT'?HTMLSelectElement.prototype:(el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype);
            Object.getOwnPropertyDescriptor(proto,'value').set.call(el,{json.dumps(str(value))});
            el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{{bubbles:true}}));}})()""")
        time.sleep(0.9)

    def shot(self, name):
        h = int(self.js("document.documentElement.scrollHeight"))
        self.cmd("Emulation.setDeviceMetricsOverride", width=1280, height=min(max(h, 700), 2600),
                 deviceScaleFactor=1, mobile=False)
        time.sleep(0.4)
        data = self.cmd("Page.captureScreenshot", format="png")["data"]
        import base64
        (HERE / name).write_bytes(base64.b64decode(data))
        print("saved", name)

    def close(self):
        self.proc.terminate()


def main():
    api("POST", "/demo/reset")
    pg = Page()
    try:
        # 1-2 hero flow: deadline slider flips hybrid -> road
        pg.go(UI)
        pg.shot("01-hero-deadline-10h-hybrid.png")
        pg.set("input[type=range]", 3, idx=1)
        pg.shot("02-hero-deadline-3h-road.png")

        # 3-4 hazardous cargo: banner, then excluded vessels with reasons
        pg.go(UI)
        pg.click("Post cargo")
        pg.set("#pc-desc", "Diesel drums")
        pg.set("#pc-class", "flammable")
        pg.shot("03-post-cargo-flammable-compliance-banner.png")
        pg.click("Post cargo", "button[type=submit]")
        pg.click("Find matching sailings")
        time.sleep(1.0)
        pg.shot("04-matches-excluded-vessels-with-reasons.png")

        # 5-6 disruption demo on a confirmed shipment
        api("POST", "/demo/reset")
        b = api("POST", "/book", {"cargo_id": "cargo-001", "sailing_id": "sailing-001", "deadline_h": 10})
        api("POST", f"/book/{b['id']}/confirm")
        api("POST", f"/demo/booking/{b['id']}/advance")
        api("POST", f"/demo/booking/{b['id']}/advance")
        api("POST", f"/demo/booking/{b['id']}/disrupt", {"scenario_id": "scn-001"})
        pg.go(UI)
        pg.click("My shipments")
        pg.click("Show alternatives")
        time.sleep(0.8)
        pg.shot("05-shipment-disruption-ranked-alternatives.png")
        pg.click("Accept this plan")
        pg.shot("06-replan-confirm-dialog.png")

        # 7 planner disruption summary (the disruption above is recorded)
        pg.click("Planner")
        pg.click("Disruption summary")
        pg.shot("07-planner-disruption-summary-simulated.png")

        pg.click("Corridor viability")
        pg.shot("12-planner-corridor-viability.png")

        # 8-9 boat owner
        pg.click("Boat owner")
        pg.click("Paste a message")
        pg.click("Read message")
        time.sleep(0.8)
        pg.shot("08-owner-register-from-message.png")
        pg.click("My history")
        pg.shot("09-owner-history-trips-simulated.png")

        # 10 warehouse + staging
        pg.click("Warehouse")
        pg.click("Utilisation")
        pg.shot("10-warehouse-utilisation-simulated.png")
        pg.click("Shipper")
        pg.click("Matches")
        pg.set("#m-cargo", "cargo-001")
        pg.click("Waiting a long time")
        pg.click("Check staging options")
        time.sleep(0.8)
        pg.shot("11-staging-plan-itemised.png")
    finally:
        pg.close()
        api("POST", "/demo/reset")


if __name__ == "__main__":
    main()
