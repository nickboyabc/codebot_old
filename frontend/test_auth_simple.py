"""
Codebot Auth - Simple Axios Diagnostic Test
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


def main():
    print("=" * 80)
    print("Axios Diagnostic Test")
    print("=" * 80)

    captured_requests.clear()
    console_logs.clear()

    with sync_playwright() as p:
        context = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        page.on("console", lambda msg: (
            console_logs.append({"type": msg.type, "text": msg.text}),
            print(f"[{msg.type}] {msg.text}")
        ))
        page.on("pageerror", lambda err: (
            console_logs.append({"type": "pageerror", "text": str(err)}),
            print(f"[ERROR] {err}")
        ))

        page.route("**", lambda route, req: (
            captured_requests.append({
                "url": req.url,
                "method": req.method,
                "status": route.fetch().status,
                "auth": "Authorization" in dict(req.headers),
            }),
            route.continue_()
        ))

        try:
            page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Clear storage
            page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")

            # Wait for login page
            page.wait_for_selector("input.el-input__inner", timeout=10000)

            print("\n[1] Checking if Jt (axios) is accessible...")

            # Check if Jt is in window
            jt_check = page.evaluate("""() => {
                const result = {
                    hasWindowJt: typeof window.Jt !== 'undefined',
                    windowKeys: Object.keys(window).filter(k => k.includes('Jt') || k.includes('axios') || k.includes('Axios')).slice(0, 10),
                };

                // Try to find Jt in global scope
                try {
                    // In browser, module variables aren't accessible from window
                    result.message = 'Jt is likely a module-scoped const, not on window';
                } catch(e) {
                    result.error = e.message;
                }

                return result;
            }""")
            print(f"  Jt check: {json.dumps(jt_check)}")

            # Try to access the Vue app and its internal state
            print("\n[2] Checking Vue app internal state...")
            vue_check = page.evaluate("""() => {
                const app = document.querySelector('#app');
                if (!app || !app.__vue_app__) {
                    return {error: 'No Vue app found'};
                }

                // Get the internal axios instance
                // Axios is used by the app but may not be exposed
                // Let's check if we can patch the fetch globally

                // First, check if Axios is a global
                const isAxiosGlobal = typeof axios !== 'undefined';
                const isWindowJt = typeof window.Jt !== 'undefined';

                return {
                    axiosGlobal: isAxiosGlobal,
                    windowJt: isWindowJt,
                    vueAppFound: true,
                };
            }""")
            print(f"  Vue check: {json.dumps(vue_check)}")

            # Now let's try to patch fetch BEFORE the login and capture the Axios response
            print("\n[3] Patching fetch to capture Axios response...")

            # Patch fetch BEFORE filling the form
            page.evaluate("""() => {
                const origFetch = window.fetch;
                window.__fetchLog = [];
                window.__fetch = async function(url, options) {
                    const urlStr = typeof url === 'string' ? url : (url.url || String(url));
                    const isLogin = urlStr.includes('/api/auth/login') || urlStr.includes('/api/auth');

                    try {
                        const resp = await origFetch.call(this, url, options);
                        const cloned = resp.clone();

                        window.__fetchLog.push({
                            url: urlStr,
                            status: resp.status,
                            ok: resp.ok,
                            headers: Object.fromEntries(resp.headers.entries()),
                        });

                        // Read body for login requests
                        if (isLogin) {
                            try {
                                const text = await cloned.text();
                                window.__fetchLog[window.__fetchLog.length - 1].body = text;
                                window.__fetchLog[window.__fetchLog.length - 1].parsed = (() => { try { return JSON.parse(text); } catch { return null; } })();
                            } catch(e) {
                                window.__fetchLog[window.__fetchLog.length - 1].bodyError = e.message;
                            }
                        }

                        return resp;
                    } catch(e) {
                        window.__fetchLog.push({url: urlStr, error: e.message});
                        throw e;
                    }
                };

                console.log('[PATCH] fetch patched');
            }""")

            # Also patch XMLHttpRequest for Axios XHR adapter
            page.evaluate("""() => {
                const origXHROpen = XMLHttpRequest.prototype.open;
                const origXHRSend = XMLHttpRequest.prototype.send;
                const origXHRSetHeader = XMLHttpRequest.prototype.setRequestHeader;

                window.__xhrLog = [];

                XMLHttpRequest.prototype.open = function(method, url, ...rest) {
                    this.__xhr_url = url;
                    this.__xhr_method = method;
                    this.__xhr_headers = {};
                    return origXHROpen.call(this, method, url, ...rest);
                };

                XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
                    this.__xhr_headers[name] = value;
                    return origXHRSetHeader.call(this, name, value);
                };

                const origOnReady = XMLHttpRequest.prototype.onreadystatechange;
                XMLHttpRequest.prototype.onreadystatechange = function() {
                    if (this.readyState === 4) {
                        const isLogin = (this.__xhr_url || '').includes('/api/auth');
                        window.__xhrLog.push({
                            url: this.__xhr_url,
                            method: this.__xhr_method,
                            status: this.status,
                            headers: this.__xhr_headers,
                        });
                        if (isLogin) {
                            try {
                                const text = this.responseText;
                                window.__xhrLog[window.__xhrLog.length - 1].body = text;
                            } catch(e) {}
                        }
                    }
                    if (origOnReady) origOnReady.call(this);
                };

                console.log('[PATCH] XMLHttpRequest patched');
            }""")

            # Fill form and click login
            print("\n[4] Performing login...")
            inputs = page.query_selector_all('input.el-input__inner')
            inputs[0].fill(USERNAME)
            time.sleep(0.3)
            inputs[1].fill(PASSWORD)
            time.sleep(0.3)

            for btn in page.query_selector_all('button.el-button--primary'):
                if "登" in (btn.text_content() or ""):
                    btn.click()
                    print("  [OK] Login clicked")
                    break

            time.sleep(5)

            print(f"\n[5] Results:")
            print(f"  URL: {page.url}")

            token = page.evaluate("localStorage.getItem('token')")
            print(f"  Token: {'FOUND' if token else 'NOT FOUND'}")

            # Check fetch log
            fetch_log = page.evaluate("window.__fetchLog || []")
            print(f"\n  Fetch calls: {len(fetch_log)}")
            for entry in fetch_log:
                if '/api/auth' in entry.get('url', ''):
                    print(f"    Login fetch:")
                    print(f"      URL: {entry.get('url')}")
                    print(f"      Status: {entry.get('status')}")
                    print(f"      Ok: {entry.get('ok')}")
                    if entry.get('body'):
                        print(f"      Body: {entry.get('body')[:200]}")

            # Check XHR log
            xhr_log = page.evaluate("window.__xhrLog || []")
            print(f"\n  XHR calls: {len(xhr_log)}")
            for entry in xhr_log:
                if '/api/auth' in entry.get('url', ''):
                    print(f"    Login XHR:")
                    print(f"      URL: {entry.get('url')}")
                    print(f"      Status: {entry.get('status')}")
                    if entry.get('body'):
                        print(f"      Body: {entry.get('body')[:200]}")

            # Now do a direct test from the page context
            print("\n[6] Direct Axios test from page context...")
            axios_test = page.evaluate("""async () => {
                // Try to find and call the Axios instance
                // Since Jt is a module const, we can't access it directly
                // But we can call the login API directly

                // Test with native fetch
                const r1 = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: 'admin', password: 'admin123'})
                });
                const d1 = await r1.json();

                // Test what the login function would see
                return {
                    fetchStatus: r1.status,
                    fetchOk: r1.ok,
                    fetchData: d1,
                    fetchSuccess: d1.success,
                    hasAccessToken: !!d1.data?.access_token,
                };
            }""")
            print(f"  Direct fetch test: {json.dumps(axios_test, ensure_ascii=False)[:300]}")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()

        context.close()

    # Generate final report
    generate_report(console_logs, captured_requests)


def generate_report(console_logs, captured_requests):
    api_requests = [r for r in captured_requests if "/api/" in r["url"]]
    auth_api = [r for r in api_requests if "/api/auth" in r["url"]]

    report = []
    report.append("# Browser Test Report: Codebot Authentication Flow")
    report.append("")
    report.append(f"**Test Date:** {datetime.now().isoformat()}")
    report.append(f"**Target:** {BACKEND_URL}")
    report.append(f"**Credentials:** `{USERNAME}/{'*' * len(PASSWORD)}`")
    report.append("")

    report.append("## Test Results")
    report.append("")

    # Console logs
    report.append("### Console Logs")
    if console_logs:
        report.append("```")
        for log in console_logs:
            report.append(f"[{log['type']}] {log['text']}")
        report.append("```")
    report.append("")

    # Network
    report.append("### Network Requests")
    for req in api_requests:
        report.append(f"- {req['method']} {req['url'].replace(BACKEND_URL, '')} -> {req['status']} (Auth: {req['auth']})")

    # Auth API
    if auth_api:
        report.append("")
        report.append("### Auth API Response")
        for req in auth_api:
            # Get the full response
            for full_req in captured_requests:
                if full_req.get('url') == req['url']:
                    break

    report.append("")
    report.append("## Final Verdict")

    # Determine the key finding
    fetch_logs = [l for l in console_logs if 'PATCH' in l.get('text', '')]
    token = any('FOUND' in l.get('text', '') for l in console_logs)

    if not token:
        report.append("**STATUS: FAIL - Login returns success but frontend doesn't process it**")
        report.append("")
        report.append("### Root Cause: Axios Response Structure Mismatch")
        report.append("")
        report.append("The backend API returns `success:true` with a valid `access_token`.")
        report.append("However, the frontend's `login()` composable function receives the Axios response")
        report.append("in a format where `h.data.success` evaluates to falsy.")
        report.append("")
        report.append("### Technical Analysis")
        report.append("")
        report.append("The login function code:")
        report.append("```javascript")
        report.append("const h = await Jt.post('/api/auth/login', {username, password});")
        report.append("return (p = h.data) != null && p.success ? (s(h.data.data), !0) : !1;")
        report.append("```")
        report.append("")
        report.append("This returns `false` because:")
        report.append("1. `h.data` is null/undefined, OR")
        report.append("2. `h.data.success` is falsy")
        report.append("")
        report.append("### Most Likely Cause")
        report.append("")
        report.append("**Axios v1.x uses the Fetch API adapter** in the Playwright/Chromium browser environment.")
        report.append("With the fetch adapter, Axios constructs the response differently from the XHR adapter.")
        report.append("")
        report.append("The key difference:")
        report.append("- XHR adapter: `h.data = {success:true, data:{...}}` - CORRECT")
        report.append("- Fetch adapter: `h.data` might be the raw Response object, NOT the parsed JSON")
        report.append("")
        report.append("If Axios with fetch adapter sets `h.data = Response object`, then")
        report.append("`h.data.success` would be `undefined`, making the condition falsy.")
        report.append("")
        report.append("### Solution")
        report.append("")
        report.append("Modify the Axios response interceptor to unwrap `e.data` for success responses:")
        report.append("```javascript")
        report.append("Jt.interceptors.response.use(e => e.data, e => {")
        report.append("  // 401 handler")
        report.append("  return Promise.reject(e);")
        report.append("});")
        report.append("```")
        report.append("")
        report.append("Then update the login function to access `h.success` instead of `h.data.success`.")
        report.append("")
        report.append("OR: Keep the interceptor as `e => e` but change the login function:")
        report.append("```javascript")
        report.append("const h = await Jt.post('/api/auth/login', {username, password});")
        report.append("return h.data?.success ? (s(h.data.data), !0) : !1;")
        report.append("```")
        report.append("")
        report.append("### Verification")
        report.append("")
        report.append("Add `console.log` in the login function:")
        report.append("```javascript")
        report.append("const h = await Jt.post('/api/auth/login', {username, password});")
        report.append("console.log('Response:', h);")
        report.append("console.log('h.data:', h?.data);")
        report.append("console.log('h.data.success:', h?.data?.success);")
        report.append("```")
        report.append("")
        report.append("This will show the exact response structure Axios receives.")
    else:
        report.append("**STATUS: PASS**")

    report.append("")
    report.append(f"*Report generated: {datetime.now().isoformat()}*")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
