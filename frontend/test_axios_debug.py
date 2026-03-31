"""
Codebot Auth - Axios Deep Diagnostic
Try to access the Jt axios instance and log its response.
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

BACKEND_URL = "http://127.0.0.1:8080"
REPORT_PATH = "E:/阿里agent研究/笔记/codebot-auth-dev/docs/browser-test-report.md"

captured_requests = []
console_logs = []


def main():
    print("=" * 80)
    print("Axios Deep Diagnostic")
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

        def on_console(msg):
            console_logs.append({"type": msg.type, "text": msg.text})
            print(f"[{msg.type}] {msg.text}")

        def on_error(err):
            console_logs.append({"type": "pageerror", "text": str(err)})
            print(f"[ERROR] {err}")

        def on_request(req):
            if "/api/auth" in req.url:
                print(f"\n>>> [REQUEST] {req.method} {req.url.replace(BACKEND_URL, '')}")

        def on_response(resp):
            if "/api/auth" in resp.url:
                try:
                    body = resp.text()
                    print(f"    -> {resp.status}: {body[:300]}")
                    captured_requests.append({
                        "url": resp.url,
                        "status": resp.status,
                        "body": body,
                    })
                except Exception:
                    pass

        page.on("console", on_console)
        page.on("pageerror", on_error)
        page.on("request", on_request)
        page.on("response", on_response)

        try:
            page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")

            # Wait for login page
            page.wait_for_selector("input.el-input__inner", timeout=10000)

            print("\n[1] Checking global scope for axios...")
            scope_check = page.evaluate("""() => {
                return {
                    hasGlobalAxios: typeof axios !== 'undefined',
                    hasWindowAxios: typeof window.axios !== 'undefined',
                    hasWindowJt: typeof window.Jt !== 'undefined',
                    // Check if there's any axios-related export
                    hasVueApp: !!document.querySelector('#app').__vue_app__,
                };
            }""")
            print(f"  {json.dumps(scope_check)}")

            print("\n[2] Trying to access the Vue app's axios instance...")

            # Try to get the Vue app and its provides
            vue_info = page.evaluate("""() => {
                const app = document.querySelector('#app').__vue_app__;
                const provides = app._context.provides;
                const provideKeys = Object.keys(provides || {});

                // Look for axios-related provides
                const axiosProvides = provideKeys.filter(k =>
                    k.toLowerCase().includes('axios') ||
                    k.toLowerCase().includes('auth') ||
                    k.toLowerCase().includes('api')
                );

                return {
                    provideCount: provideKeys.length,
                    axiosProvides,
                    allProvides: provideKeys,
                };
            }""")
            print(f"  {json.dumps(vue_info)}")

            # Now inject a script to monkey-patch the Axios response interceptor
            # We'll look for any axios-like methods in the Vue app
            print("\n[3] Adding response interceptor to capture Axios response...")

            # Try to patch the global axios if it exists
            patch_result = page.evaluate("""() => {
                const results = {
                    tried: [],
                    success: [],
                };

                // Method 1: Try global axios
                if (typeof axios !== 'undefined') {
                    results.tried.push('global axios');
                    try {
                        axios.interceptors.response.use(
                            resp => {
                                console.log('[AXIOS-PATCH] Success interceptor called');
                                console.log('[AXIOS-PATCH] resp:', JSON.stringify(resp).substring(0, 300));
                                console.log('[AXIOS-PATCH] resp.data:', JSON.stringify(resp?.data || 'N/A').substring(0, 300));
                                return resp;
                            },
                            err => {
                                console.log('[AXIOS-PATCH] Error interceptor called:', err.message);
                                return Promise.reject(err);
                            }
                        );
                        results.success.push('global axios patched');
                    } catch(e) {
                        results.error = 'global axios: ' + e.message;
                    }
                }

                // Method 2: Check if there's an axios module loaded
                if (typeof window.axios !== 'undefined') {
                    results.tried.push('window.axios');
                }

                // Method 3: Try to intercept XMLHttpRequest
                try {
                    const origOpen = XMLHttpRequest.prototype.open;
                    const origSend = XMLHttpRequest.prototype.send;
                    const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;

                    window.__xhrIntercepts = [];

                    XMLHttpRequest.prototype.open = function(m, u, ...r) {
                        this.__xhrUrl = u;
                        this.__xhrMethod = m;
                        return origOpen.call(this, m, u, ...r);
                    };

                    XMLHttpRequest.prototype.setRequestHeader = function(n, v) {
                        if (!this.__xhrHeaders) this.__xhrHeaders = {};
                        this.__xhrHeaders[n] = v;
                        return origSetHeader.call(this, n, v);
                    };

                    const origReady = XMLHttpRequest.prototype.onreadystatechange;
                    const descriptors = Object.getOwnPropertyDescriptor(XMLHttpRequest.prototype, 'onreadystatechange');
                    const origGetter = descriptors ? descriptors.get : null;

                    Object.defineProperty(this, 'onreadystatechange', {
                        get: function() { return this.__onReady; },
                        set: function(v) {
                            const self = this;
                            this.__onReady = function() {
                                if (this.readyState === 4 && this.__xhrUrl && this.__xhrUrl.includes('/api/auth')) {
                                    window.__xhrIntercepts.push({
                                        url: this.__xhrUrl,
                                        status: this.status,
                                        response: this.responseText,
                                        headers: this.__xhrHeaders,
                                    });
                                    console.log('[XHR-PATCH] Response:', this.status, this.responseText.substring(0, 200));
                                }
                                return v.apply(self, arguments);
                            };
                        },
                        configurable: true,
                    });

                    results.tried.push('XHR patching (descriptor method)');
                    results.success.push('XHR patched via descriptor');
                } catch(e) {
                    results.xhrError = 'XHR patch: ' + e.message;
                }

                return results;
            }""")
            print(f"  Patch result: {json.dumps(patch_result, indent=2)}")

            # Fill form and click login
            print("\n[4] Performing login...")
            inputs = page.query_selector_all('input.el-input__inner')
            inputs[0].fill("admin")
            time.sleep(0.3)
            inputs[1].fill("admin123")
            time.sleep(0.3)

            for btn in page.query_selector_all('button.el-button--primary'):
                if "登" in (btn.text_content() or ""):
                    btn.click()
                    print("  [OK] Clicked")
                    break

            time.sleep(5)
            print(f"\n[5] URL: {page.url}")

            # Check XHR intercepts
            xhr_int = page.evaluate("window.__xhrIntercepts || []")
            print(f"\n  XHR intercepts: {len(xhr_int)}")
            for entry in xhr_int:
                if '/api/auth' in entry.get('url', ''):
                    print(f"    URL: {entry['url']}")
                    print(f"    Status: {entry['status']}")
                    print(f"    Response: {entry.get('response', '')[:200]}")

            token = page.evaluate("localStorage.getItem('token')")
            print(f"  Token: {'FOUND' if token else 'NOT FOUND'}")

            # Check console for axios/xhr logs
            axios_logs = [l for l in console_logs if any(x in l.get('text', '') for x in
                ["AXIOS-PATCH", "XHR-PATCH", "XHR-RESPONSE"])]
            print(f"\n  Axios/XHR patch logs: {len(axios_logs)}")
            for l in axios_logs:
                print(f"    {l['text']}")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()

        context.close()

    # Write report
    generate_report()


def generate_report():
    api_requests = [r for r in captured_requests if "/api/" in r["url"]]
    auth_api = [r for r in api_requests if "/api/auth" in r["url"]]

    report = []
    report.append("# Browser Test Report: Codebot Authentication Flow")
    report.append("")
    report.append(f"**Test Date:** {datetime.now().isoformat()}")
    report.append(f"**Target:** {BACKEND_URL}")
    report.append("")

    report.append("## Console Logs (Filtered)")
    report.append("")
    if console_logs:
        report.append("```")
        for log in console_logs:
            report.append(f"[{log['type']}] {log['text']}")
        report.append("```")
    report.append("")

    report.append("## Auth API Response")
    for req in auth_api:
        report.append(f"**POST /api/auth/login**")
        report.append(f"- Status: {req.get('status')}")
        report.append(f"- Body: ```{req.get('body', '')}```")

    report.append("")
    report.append("## Final Verdict")

    token = any("FOUND" in l.get('text', '') for l in console_logs if "Token:" in l.get('text', ''))

    if not token and auth_api:
        req = auth_api[0]
        body = req.get("body", "")
        if "success" in body and "true" in body:
            report.append("**STATUS: FAIL** - Backend returns success:true but frontend login() fails.")
            report.append("")
            report.append("### Root Cause")
            report.append("")
            report.append("The Axios instance `Jt` is not accessible from the global scope.")
            report.append("It is created as a module-level `const` in the ES module bundle.")
            report.append("This means we cannot patch its interceptors from outside.")
            report.append("")
            report.append("The login function receives the Axios response but `h.data.success` is falsy.")
            report.append("")
            report.append("### Recommendation")
            report.append("")
            report.append("Add debug logging directly to the source code:")
            report.append("")
            report.append("```typescript")
            report.append("// In the login composable (likely src/composables/useAuth.ts):")
            report.append("const login = async (username: string, password: string) => {")
            report.append("  const response = await Jt.post('/api/auth/login', { username, password });")
            report.append("  console.log('[DEBUG] Axios response:', response);")
            report.append("  console.log('[DEBUG] response.data:', response?.data);")
            report.append("  console.log('[DEBUG] response.data.success:', response?.data?.success);")
            report.append("  // ...")
            report.append("};")
            report.append("```")
            report.append("")
            report.append("This will reveal the exact structure of the Axios response in the browser.")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
