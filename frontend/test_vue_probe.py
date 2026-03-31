"""
Codebot Auth - Vue Component Probe
Access Vue component internals to check reactive state during login.
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

BACKEND_URL = "http://127.0.0.1:8080"
REPORT_PATH = "E:/阿里agent研究/笔记/codebot-auth-dev/docs/browser-test-report.md"


def main():
    print("=" * 80)
    print("Vue Component Probe")
    print("=" * 80)

    with sync_playwright() as p:
        context = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        console_logs = []
        captured_requests = []

        def on_console(msg):
            text = msg.text
            console_logs.append({"type": msg.type, "text": text, "line": msg.location.get("lineNumber", "")})
            if any(x in text for x in ["[DEBUG]", "[PROBE]", "[ERROR]", "login", "token", "error"]):
                print(f"[{msg.type}] {text}")

        def on_error(err):
            console_logs.append({"type": "pageerror", "text": str(err)})
            print(f"[ERROR] {err}")

        def on_request(req):
            if "/api/auth" in req.url:
                captured_requests.append({"url": req.url, "method": req.method})

        def on_response(resp):
            if "/api/auth" in resp.url:
                try:
                    body = resp.text()
                    captured_requests.append({"url": resp.url, "status": resp.status, "body": body})
                    print(f"\n>>> RESPONSE: {resp.status} {body[:200]}")
                except Exception:
                    pass

        page.on("console", on_console)
        page.on("pageerror", on_error)
        page.on("request", on_request)
        page.on("response", on_response)

        page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        page.wait_for_selector("input.el-input__inner", timeout=10000)
        print("[OK] Login page loaded")

        # Inject a comprehensive probe script
        page.evaluate("""() => {
            console.log('[PROBE] Starting Vue component probe...');

            // Try to get the login form element
            const loginEl = document.querySelector('.login-page');
            if (!loginEl) {
                console.log('[PROBE] No login-page element found');
                return;
            }

            // Walk up the DOM tree to find Vue component instance
            let el = loginEl;
            let vueInstance = null;
            let depth = 0;
            while (el && depth < 10) {
                if (el.__vue__) {
                    vueInstance = el.__vue__;
                    console.log('[PROBE] Found __vue__ at depth', depth);
                    break;
                }
                if (el.__vueParentComponent) {
                    vueInstance = el.__vueParentComponent;
                    console.log('[PROBE] Found __vueParentComponent at depth', depth);
                    break;
                }
                el = el.parentElement;
                depth++;
            }

            if (!vueInstance) {
                console.log('[PROBE] No Vue instance found in DOM tree');
            } else {
                console.log('[PROBE] Vue instance type:', vueInstance.type?.name || vueInstance.__name || 'unknown');
                console.log('[PROBE] Vue instance keys:', Object.keys(vueInstance).join(', '));
            }

            // Try to access the Vue app's provides
            const app = document.querySelector('#app').__vue_app__;
            if (app) {
                console.log('[PROBE] Vue app version:', app.version);
                console.log('[PROBE] Vue app provides keys:', Object.keys(app._context.provides || {}).join(', '));
            }

            // Store for later access
            window.__vueInstance = vueInstance;
        }""")

        # Fill form
        inputs = page.query_selector_all('input.el-input__inner')
        inputs[0].fill("admin")
        inputs[1].fill("admin123")
        time.sleep(0.3)

        # Now inject MORE debug code that overrides the login form's submit
        print("\n[PROBE] Installing submit override...")
        page.evaluate("""() => {
            // Find the form
            const form = document.querySelector('.login-form');
            if (!form) {
                console.log('[PROBE] No form found');
                return;
            }
            console.log('[PROBE] Form found, installing override...');

            // Store original submit
            const origSubmit = form.onsubmit;

            // Override submit
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                console.log('[DEBUG] Form submit intercepted!');

                // Get form values
                const inputs = form.querySelectorAll('input.el-input__inner');
                const username = inputs[0]?.value;
                const password = inputs[1]?.value;
                console.log('[DEBUG] Form values:', { username, password });

                // Try to call the login API directly using native fetch
                try {
                    const resp = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username, password})
                    });
                    const data = await resp.json();
                    console.log('[DEBUG] Direct fetch result:', JSON.stringify(data).substring(0, 200));

                    if (data.success) {
                        console.log('[DEBUG] Setting token directly...');
                        localStorage.setItem('token', data.data.access_token);
                        localStorage.setItem('userInfo', JSON.stringify(data.data.user));
                        console.log('[DEBUG] Token stored, redirecting...');
                        window.location.href = '/chat';
                    }
                } catch(err) {
                    console.error('[DEBUG] Direct fetch error:', err.message);
                }
            }, true);

            console.log('[PROBE] Submit override installed');
        }""")

        # Click login button
        print("\n[CLICK] Clicking login button...")
        for btn in page.query_selector_all('button.el-button--primary'):
            if "登" in (btn.text_content() or ""):
                btn.click()
                print("  [OK] Clicked")
                break

        time.sleep(5)
        print(f"\n[RESULT] URL: {page.url}")

        # Check
        token = page.evaluate("localStorage.getItem('token')")
        print(f"  Token: {'FOUND' if token else 'NOT FOUND'}")

        # Check Vue state
        vue_state = page.evaluate("""() => {
            const loginEl = document.querySelector('.login-page');
            if (!loginEl) return {error: 'no login page'};

            // Try to find the Vue component instance
            let el = loginEl;
            for (let i = 0; i < 10; i++) {
                if (el.__vue__) return {found: '__vue__', type: el.__vue__.type?.name || el.__vue__.$options?.name};
                if (el.__vueParentComponent) return {found: '__vueParentComponent', type: el.__vueParentComponent.type?.name};
                el = el.parentElement;
            }
            return {found: false};
        }""")
        print(f"  Vue component: {vue_state}")

        context.close()

    # Generate report
    report = []
    report.append("# Browser Test Report: Codebot Authentication Flow")
    report.append(f"**Date:** {datetime.now().isoformat()}")
    report.append(f"**Target:** {BACKEND_URL}")
    report.append("")

    report.append("## Console Logs")
    for log in console_logs:
        report.append(f"[{log['type']}] {log['text']}")

    report.append("")
    report.append("## Network Requests")
    for req in captured_requests:
        if isinstance(req, dict) and "body" in req:
            report.append(f"- {req.get('url', '').replace(BACKEND_URL, '')}: {req.get('status')} -> {req.get('body', '')[:100]}")

    report.append("")
    report.append("## Analysis")
    if token:
        report.append("**Direct fetch workaround stores token successfully.**")
    else:
        report.append("**Login still fails even with direct fetch.**")

    report.append("")
    report.append("## Root Cause")
    report.append("")
    report.append("The Vue component's login function `l(f, v)` calls `Jt.post(...)` and processes")
    report.append("the Axios response. The Axios response has `data: {success: true, data: {...}}`.")
    report.append("But the login function condition evaluates to false.")
    report.append("")
    report.append("This strongly suggests that the Axios response structure is NOT what we expect.")
    report.append("Most likely: Axios is using the Fetch adapter, which returns responses differently.")
    report.append("")
    report.append("### Recommended Fix")
    report.append("")
    report.append("Change the Axios response interceptor to unwrap `e.data`:")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
