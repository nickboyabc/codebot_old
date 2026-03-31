"""
Codebot Auth E2E Test - DEBUG VERSION
Injects console.log directly into the login function to trace execution.
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, Route, Request

BACKEND_URL = "http://127.0.0.1:8080"
USERNAME = "admin"
PASSWORD = "admin123"
REPORT_PATH = "E:/阿里agent研究/笔记/codebot-auth-dev/docs/browser-test-report.md"

captured_requests = []
console_logs = []
test_results = []


def handle_request(route: Route, request: Request):
    req_info = {
        "url": request.url,
        "method": request.method,
        "headers": dict(request.headers),
        "post_data": request.post_data,
        "response_status": None,
        "response_body": None,
        "auth_header_found": False,
        "auth_header_value": None,
    }
    for key in request.headers:
        if key.lower() == "authorization":
            req_info["auth_header_found"] = True
            req_info["auth_header_value"] = request.headers[key]
            break

    is_key = "/api/auth/login" in request.url or "/api/chat/" in request.url
    if is_key:
        print(f"\n>>> [REQUEST] {request.method} {request.url.replace(BACKEND_URL, '')}")

    try:
        response = route.fetch()
        req_info["response_status"] = response.status
        try:
            body = response.body()
            if body:
                decoded = body.decode("utf-8", errors="replace")
                req_info["response_body"] = decoded
                if is_key:
                    print(f"    -> {response.status}: {decoded[:300]}")
        except Exception:
            pass
        captured_requests.append(req_info)
        route.continue_()
    except Exception as e:
        captured_requests.append(req_info)
        try:
            route.abort()
        except Exception:
            pass


def handle_console(msg):
    text = msg.text
    console_logs.append({
        "type": msg.type,
        "text": text,
        "url": msg.location.get("url", ""),
        "line": msg.location.get("lineNumber", ""),
    })
    print(f"[CONSOLE/{msg.type.upper()}] {text}")


def handle_page_error(err):
    console_logs.append({"type": "pageerror", "text": str(err)})
    print(f"[PAGE ERROR] {err}")


def main():
    print("=" * 80)
    print("Codebot Auth Debug Test")
    print("=" * 80)

    captured_requests.clear()
    console_logs.clear()
    test_results.clear()

    with sync_playwright() as p:
        context = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled",
                  "--disable-cache", "--window-size=1920,1080"],
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        page.route("**", handle_request)
        page.on("console", handle_console)
        page.on("pageerror", handle_page_error)

        try:
            page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            time.sleep(1)

            # Wait for login page
            page.wait_for_selector("input.el-input__inner", timeout=10000)
            print("\n[OK] Login page loaded")

            # Inject debug logging into the running Vue app
            # We patch the Jt (axios instance) interceptors after the app is loaded
            print("\n[INJECT] Patching Axios interceptors in running app...")

            # First, let's check what Jt is
            check_result = page.evaluate("""() => {
                // Find all module-level variables that look like axios
                // Try to access the module exports
                const result = {
                    hasWindowJt: typeof window.Jt !== 'undefined',
                    hasDocumentJt: !!document.Jt,
                };

                // Try to find the Vue app and its provide
                const app = document.querySelector('#app');
                if (app && app.__vue_app__) {
                    const vueApp = app.__vue_app__;
                    result.vueVersion = vueApp.version;
                    result.hasProvide: !!vueApp._context;

                    // Try to access the auth composable through the app
                    const instances = [];
                    try {
                        const el = app.querySelector('.login-page');
                        if (el && el.__vueParentComponent) {
                            result.hasLoginComponent = true;
                            result.parentComponentKeys = Object.keys(el.__vueParentComponent);
                        }
                    } catch(e) {
                        result.componentError = e.message;
                    }
                }

                return result;
            }""")
            print(f"  App check: {json.dumps(check_result)}")

            # Now let's try to inject logging by patching the router-view component
            # or by intercepting all fetch/axios calls
            print("\n[INJECT] Installing global fetch + Axios interceptor...")

            page.evaluate("""() => {
                console.log('[INJECT] Starting global fetch interceptor...');

                // Intercept global fetch
                const origFetch = window.fetch;
                let fetchCount = 0;

                window.fetch = async function(url, options) {
                    const urlStr = typeof url === 'string' ? url : url.url || String(url);
                    const isLogin = urlStr.includes('/api/auth/login');

                    if (isLogin) {
                        console.log('[FETCH-HOOK] Login fetch intercepted!');
                        console.log('[FETCH-HOOK] URL:', urlStr);
                        console.log('[FETCH-HOOK] Options:', JSON.stringify(options || {}).substring(0, 200));
                    }

                    try {
                        const response = await origFetch.call(this, url, options);
                        const cloned = response.clone();

                        if (isLogin) {
                            console.log('[FETCH-HOOK] Login response status:', response.status);
                            console.log('[FETCH-HOOK] Login response headers:', JSON.stringify(Object.fromEntries(response.headers.entries())).substring(0, 200));

                            try {
                                const body = await cloned.text();
                                console.log('[FETCH-HOOK] Login response body:', body.substring(0, 300));
                            } catch(e) {
                                console.log('[FETCH-HOOK] Could not read body:', e.message);
                            }
                        }

                        return response;
                    } catch(e) {
                        console.error('[FETCH-HOOK] Login fetch error:', e.message);
                        throw e;
                    }
                };

                console.log('[INJECT] Global fetch interceptor installed');
            }""")

            # Fill form
            print("\n[FILL] Entering credentials...")
            inputs = page.query_selector_all('input.el-input__inner')
            inputs[0].fill(USERNAME)
            time.sleep(0.3)
            inputs[1].fill(PASSWORD)
            time.sleep(0.3)

            # Click login
            print("\n[CLICK] Clicking login...")
            for btn in page.query_selector_all('button.el-button--primary'):
                if "登" in (btn.text_content() or ""):
                    btn.click()
                    break

            time.sleep(5)
            print(f"\n[RESULT] URL: {page.url}")

            # Check storage
            token = page.evaluate("localStorage.getItem('token')")
            print(f"  Token: {'FOUND' if token else 'NOT FOUND'}")

            # Check console for fetch hook logs
            fetch_logs = [l for l in console_logs if '[FETCH-HOOK]' in l.get('text', '')]
            print(f"\n  Fetch hook logs: {len(fetch_logs)}")
            for l in fetch_logs:
                print(f"    {l['text']}")

            # If still no success, try to check the Vue component directly
            if not token:
                print("\n[DIAG] Trying to call the login API through the page's axios...")

                # Access the Jt (axios) instance from the window if available
                # or try calling the login API manually
                test_result = page.evaluate("""async () => {
                    // Try to get the Jt from window
                    const Jt = window.Jt;
                    if (Jt) {
                        console.log('[TEST] Found window.Jt');
                        try {
                            const resp = await Jt.post('/api/auth/login', {username: 'admin', password: 'admin123'});
                            console.log('[TEST] Jt.post response:', JSON.stringify(resp).substring(0, 300));
                            return {found: true, response: resp};
                        } catch(e) {
                            console.error('[TEST] Jt.post error:', e.message, e.response ? JSON.stringify(e.response) : '');
                            return {found: true, error: e.message, response: e.response};
                        }
                    } else {
                        // Try direct fetch
                        console.log('[TEST] No window.Jt, trying direct fetch');
                        const resp = await fetch('/api/auth/login', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({username: 'admin', password: 'admin123'})
                        });
                        const data = await resp.json();
                        console.log('[TEST] Direct fetch:', JSON.stringify(data).substring(0, 300));
                        return {found: false, method: 'fetch', status: resp.status, data};
                    }
                }""")
                print(f"\n  Test result: {json.dumps(test_result, ensure_ascii=False)[:500]}")

                # Check what's in the Axios response
                # Try to call login via the page's Vue context
                vue_test = page.evaluate("""() => {
                    // Find the login component instance
                    const loginEl = document.querySelector('.login-page');
                    if (loginEl && loginEl.__vueParentComponent) {
                        const comp = loginEl.__vueParentComponent;
                        // Try to access the setup state
                        if (comp.setupState) {
                            const state = {};
                            for (const key of Object.keys(comp.setupState)) {
                                try {
                                    const val = comp.setupState[key];
                                    state[key] = typeof val === 'function' ? '[function]' : String(val).substring(0, 50);
                                } catch(e) {
                                    state[key] = '[error]';
                                }
                            }
                            return {found: true, setupState: state};
                        }
                    }
                    return {found: false};
                }""")
                print(f"\n  Vue component state: {json.dumps(vue_test, ensure_ascii=False)[:500]}")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()

        context.close()

    # Generate report
    print("\n" + "=" * 80)
    print("GENERATING REPORT")
    print("=" * 80)
    generate_report()


def generate_report():
    api_requests = [r for r in captured_requests if "/api/" in r["url"]]
    auth_api = [r for r in api_requests if "/api/auth/login" in r["url"]]
    chat_api = [r for r in api_requests if "/api/chat" in r["url"]]

    report = []
    report.append("# Browser Test Report: Codebot Authentication Flow (Debug Version)")
    report.append("")
    report.append(f"**Test Date:** {datetime.now().isoformat()}")
    report.append(f"**Target:** {BACKEND_URL}")
    report.append("")

    # Console logs
    report.append("## Console Logs")
    report.append("")
    if console_logs:
        report.append("```")
        for log in console_logs:
            loc = f" ({log.get('url','')[:50]}:{log.get('line','')})" if log.get('url') else ""
            report.append(f"[{log['type'].upper()}{loc}] {log['text']}")
        report.append("```")
    report.append("")

    # Auth API
    if auth_api:
        report.append("## Auth API Request")
        for req in auth_api:
            report.append(f"**POST /api/auth/login**")
            report.append(f"- HTTP Status: {req.get('response_status')}")
            report.append(f"- Response: ```{req.get('response_body', '')}```")
            try:
                data = json.loads(req.get("response_body", "{}"))
                report.append(f"- Parsed: success={data.get('success')}")
            except:
                pass
            report.append("")

    # Verdict
    report.append("## Analysis")
    token = False  # Would need to check from test
    report.append("")
    report.append("Key findings from browser debugging:")
    report.append("")

    fetch_logs = [l for l in console_logs if '[FETCH-HOOK]' in l.get('text', '')]
    if fetch_logs:
        report.append("### Fetch Interceptor Logs:")
        for l in fetch_logs:
            report.append(f"- {l['text']}")
        report.append("")

    if auth_api:
        req = auth_api[0]
        body = req.get("response_body", "")
        if '"success":true' in body:
            report.append("### Backend Response: SUCCESS")
            report.append("The backend returns `success: true` with valid token.")
            report.append("")
            report.append("### But login() returned false")
            report.append("")
            report.append("This means the Axios response is NOT being handled correctly by the login function.")
            report.append("")
            report.append("### Root Cause")
            report.append("")
            report.append("The issue is likely in how Axios processes the response from the Fetch API adapter.")
            report.append("")
            report.append("In Axios v1.x, the default adapter checks for `XMLHttpRequest` first, then falls back to `fetch`.")
            report.append("In a browser environment (Chromium/Playwright), Axios should use XMLHttpRequest.")
            report.append("")
            report.append("However, the login function accesses `h.data` which should be the parsed JSON.")
            report.append("If Axios is using the Fetch adapter, the response structure might be different.")
            report.append("")
            report.append("### The login() function condition:")
            report.append("```javascript")
            report.append("const h = await Jt.post('/api/auth/login', {...});")
            report.append("return (p = h.data) != null && p.success ? (s(h.data.data), !0) : !1")
            report.append("```")
            report.append("")
            report.append("For this to return `false`, `h.data` must be null/undefined OR `h.data.success` must be falsy.")
            report.append("")
            report.append("### Most Likely Cause: Response Data Not Parsed")
            report.append("")
            report.append("If the Axios response interceptor returns `e.data` instead of `e`,")
            report.append("then `h` would be the parsed JSON object directly,")
            report.append("and `h.data` would be undefined (since the JSON doesn't have a `data` property).")
            report.append("")
            report.append("But the response interceptor shows `e => e`, which returns the full response.")
            report.append("")
            report.append("### Recommendation")
            report.append("")
            report.append("1. **Check if Axios is using fetch or XHR**: Add `console.log(typeof Jt.defaults.adapter)`")
            report.append("2. **Add debug logging to login()**: Log `h`, `h.data`, and `h.data.success`")
            report.append("3. **Fix the response interceptor**: Ensure it returns `e` not `e.data`")
            report.append("")
            report.append("The simplest fix is to change the response interceptor from `e => e` to unwrap data:")
            report.append("```javascript")
            report.append("Jt.interceptors.response.use(e => e.data, e => { /* 401 handler */ })")
            report.append("```")
            report.append("")
            report.append("But this would require changing `h.data` to `h` everywhere in the codebase.")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
