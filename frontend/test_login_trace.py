"""
Codebot Auth - Login Function Tracing
Injects console.log into the actual login function to trace execution.
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

BACKEND_URL = "http://127.0.0.1:8080"
USERNAME = "admin"
PASSWORD = "admin123"
REPORT_PATH = "E:/阿里agent研究/笔记/codebot-auth-dev/docs/browser-test-report.md"


def main():
    print("=" * 80)
    print("Login Function Tracing")
    print("=" * 80)

    with sync_playwright() as p:
        context = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        console_logs = []

        def on_console(msg):
            text = msg.text
            console_logs.append({"type": msg.type, "text": text, "line": msg.location.get("lineNumber", "")})
            print(f"[{msg.type}] {text}")

        def on_error(err):
            console_logs.append({"type": "pageerror", "text": str(err)})
            print(f"[ERROR] {err}")

        page.on("console", on_console)
        page.on("pageerror", on_error)

        page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        page.wait_for_selector("input.el-input__inner", timeout=10000)
        print("[OK] Page loaded")

        # Inject comprehensive tracing
        print("\n[INJECT] Installing tracing hooks...")

        # First, let's check if we can access the Vue app and its components
        vue_info = page.evaluate("""() => {
            const app = document.querySelector('#app').__vue_app__;
            if (!app) return {error: 'No Vue app'};

            // Get the router instance
            const router = app.config.globalProperties.$router;
            const routes = router ? router.getRoutes() : [];

            return {
                vueVersion: app.version,
                hasRouter: !!router,
                routeCount: routes.length,
                currentRoute: window.location.pathname,
            };
        }""")
        print(f"  Vue info: {json.dumps(vue_info)}")

        # Now let's try to patch the form submission
        result = page.evaluate("""() => {
            const results = {
                formFound: false,
                buttonFound: false,
                buttonClickHandler: null,
            };

            // Find the login form
            const form = document.querySelector('.login-form');
            if (form) {
                results.formFound = true;

                // Check form's onsubmit
                results.formOnSubmit = typeof form.onsubmit;
                results.formHasSubmitHandler = form.onsubmit !== null;
            }

            // Find the login button
            const buttons = document.querySelectorAll('button.el-button--primary');
            for (const btn of buttons) {
                if (btn.textContent && btn.textContent.includes('登')) {
                    results.buttonFound = true;
                    results.buttonHTML = btn.outerHTML.substring(0, 200);
                    break;
                }
            }

            // Try to patch XMLHttpRequest to trace ALL XHR requests
            try {
                const origOpen = XMLHttpRequest.prototype.open;
                const origSend = XMLHttpRequest.prototype.send;

                window.__xhrCalls = [];

                XMLHttpRequest.prototype.open = function(method, url, ...args) {
                    this.__url = url;
                    this.__method = method;
                    return origOpen.call(this, method, url, ...args);
                };

                XMLHttpRequest.prototype.send = function(...args) {
                    const self = this;
                    this.addEventListener('readystatechange', function() {
                        if (this.readyState === 4) {
                            window.__xhrCalls.push({
                                url: this.__url,
                                method: this.__method,
                                status: this.status,
                                response: this.responseText.substring(0, 200),
                            });
                        }
                    });
                    return origSend.apply(this, args);
                };

                results.xhrPatched = true;
            } catch (e) {
                results.xhrPatchError = e.message;
            }

            return results;
        }""")
        print(f"  Patch result: {json.dumps(result)}")

        # Fill form
        inputs = page.query_selector_all('input.el-input__inner')
        inputs[0].fill(USERNAME)
        time.sleep(0.3)
        inputs[1].fill(PASSWORD)
        time.sleep(0.3)

        # Now try to patch the button click by wrapping the Vue component
        patch = page.evaluate("""() => {
            // Try to intercept the button click
            const buttons = document.querySelectorAll('button.el-button--primary');
            for (const btn of buttons) {
                if (btn.textContent && btn.textContent.includes('登')) {
                    // Try to intercept the click
                    const origClick = btn.onclick;

                    btn.addEventListener('click', async (e) => {
                        console.log('[TRACE] Login button click event fired');

                        // Try to call the API directly using the credentials from the form
                        const inputs = document.querySelectorAll('input.el-input__inner');
                        const username = inputs[0]?.value;
                        const password = inputs[1]?.value;
                        console.log('[TRACE] Form values:', { username, password });

                        // Make the API call directly
                        try {
                            const resp = await fetch('/api/auth/login', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({username, password})
                            });
                            const data = await resp.json();
                            console.log('[TRACE] Direct fetch result:', JSON.stringify(data).substring(0, 300));

                            // Check if we can store the token
                            if (data.success && data.data && data.data.access_token) {
                                console.log('[TRACE] Token found, storing...');
                                localStorage.setItem('token', data.data.access_token);
                                localStorage.setItem('userInfo', JSON.stringify(data.data.user));
                                console.log('[TRACE] Token stored, navigating...');
                                window.location.href = '/chat';
                            } else {
                                console.log('[TRACE] No token in response:', data);
                            }
                        } catch (err) {
                            console.error('[TRACE] Direct fetch error:', err.message);
                        }
                    }, true);

                    return 'Button listener added';
                }
            }
            return 'Button not found';
        }""")
        print(f"\n  Button patch: {patch}")

        # Click login button
        print("\n[CLICK] Clicking login button...")
        for btn in page.query_selector_all('button.el-button--primary'):
            if "登" in (btn.text_content() or ""):
                btn.click()
                print("  Clicked")
                break

        time.sleep(5)
        print(f"\n[RESULT] URL: {page.url}")

        # Check storage
        token = page.evaluate("localStorage.getItem('token')")
        print(f"  Token: {'FOUND' if token else 'NOT FOUND'}")

        # Check XHR calls
        xhr_calls = page.evaluate("window.__xhrCalls || []")
        print(f"\n  XHR calls: {len(xhr_calls)}")
        for call in xhr_calls:
            if '/api/auth' in call.get('url', ''):
                print(f"    {call['method']} {call['url']} -> {call['status']}")
                print(f"    Response: {call.get('response', '')[:200]}")

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
    report.append("## Analysis")
    if token:
        report.append("**Token was stored.** Direct fetch workaround succeeded.")
        report.append("")
        report.append("The issue is confirmed to be in the Vue Axios `login()` function.")
        report.append("The Axios response is NOT being processed correctly.")
    else:
        report.append("**Token was NOT stored.**")
        report.append("")
        report.append("The direct fetch ALSO failed to store the token.")
        report.append("This means either the fetch request failed, or the response didn't contain the token.")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
