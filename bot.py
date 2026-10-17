import asyncio
import os
import sys
from playwright.async_api import async_playwright

MSG = "Automa test message"
TICK = 0.02
SESSION_DIR = "./snap_session"

def log(msg):
    print(msg, flush=True)

JS_CYCLE = r"""
(args) => {
  const MSG = args.MSG;
  const getPKEY = () => {
    const probe = document.querySelector('[contenteditable="true"]');
    if (probe) for (const k of Object.keys(probe)) if (k.startsWith('__reactProps$')) return k;
    return null;
  };
  const PKEY = getPKEY();
  if (!PKEY) return { status: 'no_pkey' };
  const cs = [...document.querySelectorAll('[contenteditable="true"]')].filter(e => e.isConnected);
  if (!cs.length) return { status: 'no_composer' };
  cs.sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top);
  const c = cs[0];
  if (document.activeElement !== c) { try { c.click(); } catch(_){} try { c.focus(); } catch(_){} }
  if ((c.textContent || '').trim()) {
    document.execCommand('selectAll', false, null);
    document.execCommand('delete', false, null);
  }
  document.execCommand('insertText', false, MSG);
  if (!(c.textContent || '').includes(MSG)) return { status: 'type_failed' };
  let sendBtn = null, sendFn = null;
  for (const b of document.querySelectorAll('button')) {
    if (b.disabled) continue;
    const r = b.getBoundingClientRect();
    if (r.top < innerHeight / 2) continue;
    if (r.width < 12 || r.width > 22 || r.height < 12 || r.height > 22) continue;
    const k = Object.keys(b).find(x => x.startsWith('__reactProps$'));
    if (!k) continue;
    const fn = b[k] && b[k].onClick;
    if (typeof fn !== 'function') continue;
    sendBtn = b; sendFn = fn; break;
  }
  if (!sendBtn) return { status: 'no_send_btn' };
  const evt = {
    type: 'click', target: sendBtn, currentTarget: sendBtn,
    nativeEvent: { type: 'click', target: sendBtn, isTrusted: true },
    bubbles: true, cancelable: true,
    preventDefault(){}, stopPropagation(){},
    button: 0, buttons: 0, clientX: 0, clientY: 0
  };
  try { sendFn.call(sendBtn, evt); } catch (e) { return { status: 'onclick_threw', err: e.message }; }
  return { status: 'clicked' };
}
"""

JS_CLEARED = r"""
([msg]) => {
  const cs = [...document.querySelectorAll('[contenteditable="true"]')].filter(e => e.isConnected);
  if (!cs.length) return true;
  cs.sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top);
  return !(cs[0].textContent || '').includes(msg);
}
"""

async def main():
    log("[startup] bot.py started")
    log(f"[startup] cwd={os.getcwd()}")
    log(f"[startup] session dir exists: {os.path.exists(SESSION_DIR)}")
    if os.path.exists(SESSION_DIR):
        log(f"[startup] session contents: {os.listdir(SESSION_DIR)}")

    log("[startup] launching playwright...")
    try:
        async with async_playwright() as p:
            log("[startup] playwright context created")
            ctx = await p.chromium.launch_persistent_context(
                SESSION_DIR,
                headless=False,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
                viewport={"width": 1280, "height": 900},
            )
            log("[startup] browser launched")
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            log("[startup] navigating to snapchat...")
            await page.goto("https://web.snapchat.com/web", timeout=60000)
            log("[startup] page loaded")

            # Only wait for input if no session cookies present
            if not os.path.exists(os.path.join(SESSION_DIR, "Default")) and not os.listdir(SESSION_DIR):
                log(">>> NO SESSION: log in manually, then press Enter. (Will hang on Railway)")
                input()

            log("[run] entering send loop")
            sent, fails = 0, 0
            while True:
                try:
                    r = await page.evaluate(JS_CYCLE, {"MSG": MSG})
                    status = r.get("status", "?")
                    if status in ("no_pkey", "no_composer", "no_send_btn", "type_failed"):
                        fails += 1
                        log(f"[cycle] {status} (fails={fails})")
                        await asyncio.sleep(0.2 if fails < 3 else 1.0)
                        continue
                    if status == "clicked":
                        await asyncio.sleep(TICK)
                        if await page.evaluate(JS_CLEARED, [MSG]):
                            sent += 1; fails = 0
                            log(f"[send] sent={sent}")
                        else:
                            try: await page.keyboard.press("Enter")
                            except Exception: pass
                            await asyncio.sleep(TICK)
                            if await page.evaluate(JS_CLEARED, [MSG]):
                                sent += 1; fails = 0
                                log(f"[send] sent={sent} (via Enter)")
                            else:
                                fails += 1
                                log(f"[cycle] not cleared (fails={fails})")
                                await asyncio.sleep(0.1 if fails < 3 else 1.0)
                except Exception as e:
                    log(f"[cycle] error: {type(e).__name__}: {e}")
                    await asyncio.sleep(0.5)
    except Exception as e:
        log(f"[fatal] {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
