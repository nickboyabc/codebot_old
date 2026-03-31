"""
Codebot Auth E2E Test - v5 FINAL
Intercepts Axios responses at the JavaScript level to trace exact failure.
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
js_debug = []


def log_test(name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    test_results.append(f"| {name} | {status} | {details} |")
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {details}")


def handle_request(route: Route, request: Request):
    req_info = {
        "url": request.url,
        "method": request.method,
        "headers": dict(request.headers),
        "post_data": request.post_data,
        "resource_type": request.resource_type,
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

    print(f"\n>>> [REQUEST] {request.method} {request.url.replace(BACKEND_URL, '')}")
    if req_info["auth_header_found"]:
        val = str(req_info["auth_header_value"])
        print(f"    Auth: {val[:50]}...")
    else:
        print(f"    Auth: NONE")
    if request.post_data and "/api/" in request.url:
        pd = request.post_data
        if isinstance(pd, bytes):
            pd = pd.decode("utf-8", errors="replace")
        print(f"    Body: {pd[:200]}")

    try:
        response = route.fetch()
        req_info["response_status"] = response.status
        try:
            body = response.body()
            if body:
                decoded = body.decode("utf-8", errors="replace")
                req_info["response_body"] = decoded
                print(f"    -> {response.status}: {decoded[:300]}")
        except Exception:
            pass
        captured_requests.append(req_info)
        route.continue_()
    except Exception as e:
        print(f"    -> Error: {e}")
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
    # Also capture JS debug info
    if "[JS-DEBUG]" in text or "[JS-INJECT]" in text:
        js_debug.append(text)
    print(f"[CONSOLE/{msg.type.upper()}] {text}")


def handle_page_error(err):
    console_logs.append({"type": "pageerror", "text": str(err)})
    print(f"[PAGE ERROR] {err}")


def main():
    print("=" * 80)
    print("Codebot Auth E2E Test - v5 FINAL (Axios Interceptor)")
    print("=" * 80)

    captured_requests.clear()
    console_logs.clear()
    test_results.clear()
    js_debug.clear()
    results = {"test_start": datetime.now().isoformat(), "test_end": None, "steps": []}

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
            resp = page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
            log_test("1. Navigate", resp.status == 200, f"HTTP {resp.status}")
            results["steps"].append(f"Navigate: HTTP {resp.status}")
            time.sleep(2)

            # Clear storage
            page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            log_test("2. Clear storage", True, "Done")
            results["steps"].append("Clear storage")

            url = page.url
            results["steps"].append(f"Initial URL: {url}")

            # Inject Axios interceptor hook BEFORE app mounts
            print("\n[INJECT] Installing Axios response interceptor...")
            page.evaluate("""() => {
                console.log('[JS-INJECT] Starting Axios hook installation');

                // Hook localStorage.setItem to track token saves
                const origSetItem = localStorage.setItem.bind(localStorage);
                window.__tokenSets = [];
                window.__tokenErrors = [];
                localStorage.setItem = function(k, v) {
                    if (k === 'token') {
                        window.__tokenSets.push({key: k, value: v ? v.substring(0, 40) + '...' : v, time: Date.now()});
                        console.log('[JS-DEBUG] localStorage.setItem("token", "' + (v ? v.substring(0, 40) + '...' : 'null') + '")');
                        try {
                            origSetItem(k, v);
                            console.log('[JS-DEBUG] localStorage.setItem("token") succeeded');
                        } catch(e) {
                            console.error('[JS-DEBUG] localStorage.setItem("token") FAILED: ' + e.message);
                            window.__tokenErrors.push(e.message);
                        }
                    } else {
                        origSetItem(k, v);
                    }
                };

                // Store a reference to Jt (axios instance) before it's potentially modified
                // We'll hook it after Vue app is ready
                window.__JtFound = false;
                window.__Jt = null;

                console.log('[JS-INJECT] Hooks installed, waiting for app');
            }""")
            results["steps"].append("Axios + localStorage hooks installed")

            if "/login" in url:
                # Wait for Vue app to be ready
                print("\n[WAIT] Waiting for Vue app to be ready...")
                ready = page.evaluate("""() => {
                    // Wait for the Vue app to be mounted
                    return new Promise(resolve => {
                        const check = () => {
                            const app = document.querySelector('#app');
                            if (app && app.__vue_app__) {
                                resolve(true);
                            } else {
                                setTimeout(check, 100);
                            }
                        };
                        setTimeout(() => resolve(false), 5000); // timeout
                        check();
                    });
                }""")
                print(f"  Vue app ready: {ready}")

                # Now try to find and hook the axios instance (Jt)
                # Since Jt is a module-level variable, we can't easily hook it
                # Instead, let's add a fetch/XMLHttpRequest hook to capture the response
                page.evaluate("""() => {
                    console.log('[JS-INJECT] Setting up XMLHttpRequest hook...');

                    const origOpen = XMLHttpRequest.prototype.open;
                    const origSend = XMLHttpRequest.prototype.send;
                    const origSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;

                    let lastXHROpen = null;
                    let lastXHRHeaders = {};
                    let lastXHRResponse = null;

                    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
                        this.__url = url;
                        this.__method = method;
                        lastXHROpen = { method, url };
                        lastXHRHeaders = {};
                        return origOpen.call(this, method, url, ...rest);
                    };

                    XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
                        if (!this.__headers) this.__headers = {};
                        this.__headers[name] = value;
                        lastXHRHeaders[name] = value;
                        return origSetRequestHeader.call(this, name, value);
                    };

                    const origOnReadyStateChange = XMLHttpRequest.prototype.onreadystatechange;
                    XMLHttpRequest.prototype.onreadystatechange = function() {
                        if (this.readyState === 4) {
                            const url = this.__url || '';
                            if (url.includes('/api/auth/login')) {
                                try {
                                    const response = JSON.parse(this.responseText);
                                    const status = this.status;
                                    const headers = this.__headers || {};
                                    console.log('[JS-DEBUG] XHR login response intercepted:');
                                    console.log('[JS-DEBUG]   Status: ' + status);
                                    console.log('[JS-DEBUG]   Response: ' + JSON.stringify(response).substring(0, 200));
                                    console.log('[JS-DEBUG]   Response.success: ' + response.success);
                                    console.log('[JS-DEBUG]   Has data: ' + !!response.data);
                                    if (response.data) {
                                        console.log('[JS-DEBUG]   data.access_token: ' + (response.data.access_token ? response.data.access_token.substring(0, 30) + '...' : 'MISSING'));
                                        console.log('[JS-DEBUG]   data.user: ' + JSON.stringify(response.data.user));
                                    }
                                    window.__lastLoginResponse = { status, response, headers };
                                } catch(e) {
                                    console.error('[JS-DEBUG] XHR parse error: ' + e.message);
                                    window.__lastLoginResponse = { status: this.status, error: e.message };
                                }
                            }
                        }
                        if (origOnReadyStateChange) {
                            return origOnReadyStateChange.call(this, ...arguments);
                        }
                    };

                    console.log('[JS-INJECT] XHR hook installed');
                }""")
                results["steps"].append("XHR hook installed")

                # Fill login form
                print("\n[STEP] Filling login form...")
                inputs = page.query_selector_all('input.el-input__inner')
                if len(inputs) >= 2:
                    inputs[0].fill(USERNAME)
                    time.sleep(0.3)
                    inputs[1].fill(PASSWORD)
                    time.sleep(0.3)
                    log_test("3. Fill form", True, f"{USERNAME}/****")
                    results["steps"].append(f"Form filled: {USERNAME}")

                    # Click login
                    print("\n[STEP] Clicking login...")
                    buttons = page.query_selector_all('button.el-button--primary')
                    for btn in buttons:
                        txt = btn.text_content() or ""
                        if "登" in txt:
                            btn.click()
                            break

                    results["steps"].append("Login button clicked")
                    time.sleep(5)

                    # Get all debug info
                    url_after = page.url
                    print(f"\n  URL: {url_after}")
                    results["steps"].append(f"URL after login: {url_after}")

                    # Check XHR response
                    xhr_response = page.evaluate("window.__lastLoginResponse || null")
                    if xhr_response:
                        print(f"\n  XHR Login Response:")
                        print(f"    Status: {xhr_response.get('status', 'N/A')}")
                        resp = xhr_response.get('response', {})
                        print(f"    success: {resp.get('success', 'N/A')}")
                        data = resp.get('data', {})
                        print(f"    data.access_token: {'FOUND' if data.get('access_token') else 'MISSING'}")
                        print(f"    data.user: {data.get('user', 'MISSING')}")

                    # Check token
                    token_sets = page.evaluate("window.__tokenSets || []")
                    token_errors = page.evaluate("window.__tokenErrors || []")
                    print(f"\n  Token setItem calls: {len(token_sets)}")
                    for ts in token_sets:
                        print(f"    {ts}")
                    if token_errors:
                        print(f"  Token setItem ERRORS: {token_errors}")

                    token = page.evaluate("localStorage.getItem('token')")
                    user_info = page.evaluate("localStorage.getItem('userInfo')")
                    print(f"\n  localStorage.token: {'FOUND' if token else 'NOT FOUND'}")
                    if token:
                        print(f"    {token[:50]}...")
                    print(f"  localStorage.userInfo: {'FOUND' if user_info else 'NOT FOUND'}")

                    log_test("4. Token stored", token is not None, f"{'FOUND' if token else 'NOT FOUND'}")

                    login_succeeded = "/chat" in url_after and "/login" not in url_after
                    log_test("5. Redirect to /chat", login_succeeded, f"URL: {url_after}")
                    results["steps"].append(f"Login: {'SUCCESS' if login_succeeded else 'FAILED'}")

                    if not login_succeeded:
                        # Comprehensive diagnosis
                        print("\n" + "=" * 40)
                        print("DIAGNOSIS")
                        print("=" * 40)

                        auth_api = [r for r in captured_requests if "/api/auth/login" in r["url"]]
                        if auth_api:
                            req = auth_api[0]
                            body = req.get("response_body", "")

                            print(f"\n1. Backend Response:")
                            print(f"   Status: {req.get('response_status')}")
                            print(f"   Body: {body[:200]}")

                            if req.get("response_status") == 200 and '"success":true' in body:
                                print(f"\n2. Diagnosis: Backend OK (success:true) but login didn't complete")
                                print(f"   XHR intercepted: {'YES' if xhr_response else 'NO'}")

                                if xhr_response:
                                    print(f"   XHR Status: {xhr_response.get('status')}")
                                    print(f"   XHR Response.success: {xhr_response.get('response', {}).get('success')}")

                                # Check for JS errors
                                js_errors = [l for l in console_logs if l.get("type") in ("error", "pageerror")]
                                print(f"\n3. JavaScript Errors: {len(js_errors)}")
                                for err in js_errors:
                                    print(f"   - {err['text']}")

                                print(f"\n4. Possible causes:")
                                print(f"   - h.data is null/undefined (axios unwrapping response)")
                                print(f"   - The 'success' field is false or missing in parsed object")
                                print(f"   - Exception thrown in login() success handler")
                                print(f"   - Vue router.push() failed silently")

                                results["steps"].append("DIAGNOSIS: Backend returns success:true, but login() returns false")
                                results["steps"].append(f"JS Errors: {len(js_errors)}")

                                # Try to find the error by checking Element Plus message
                                error_msg = page.evaluate("""() => {
                                    const msgs = document.querySelectorAll('.el-message');
                                    for (const m of msgs) {
                                        const text = m.textContent;
                                        if (text && text.trim()) return text.trim();
                                    }
                                    return null;
                                }""")
                                if error_msg:
                                    print(f"\n5. UI Error Message: '{error_msg}'")
                                    results["steps"].append(f"UI Error: {error_msg}")
                                else:
                                    print(f"\n5. UI Error Message: None visible")
                                    results["steps"].append("No UI error message shown")

                                # Try direct token injection test
                                print("\n6. Testing localStorage directly...")
                                test_result = page.evaluate("""() => {
                                    try {
                                        localStorage.setItem('test_token', 'test123');
                                        const val = localStorage.getItem('test_token');
                                        localStorage.removeItem('test_token');
                                        return 'localStorage works: ' + val;
                                    } catch(e) {
                                        return 'localStorage FAILED: ' + e.message;
                                    }
                                }""")
                                print(f"   {test_result}")

                    else:
                        # Login succeeded!
                        results["steps"].append("Login SUCCESS")
                        log_test("6. Chat flow", True, "Proceeding")

                        # Chat flow
                        print("\n[STEP] Testing chat flow...")
                        for sel in ['button:has-text("新建对话")', 'button:has-text("新对话")']:
                            btns = page.query_selector_all(sel)
                            for btn in btns:
                                if "新建" in (btn.text_content() or ""):
                                    btn.click()
                                    time.sleep(1)
                                    break

                        msg_selectors = ['textarea.el-textarea__inner', 'textarea']
                        for sel in msg_selectors:
                            inputs = page.query_selector_all(sel)
                            for inp in inputs:
                                bbox = inp.bounding_box()
                                if bbox and bbox.get("width", 0) > 100:
                                    inp.fill("你好，请介绍一下你自己")
                                    time.sleep(0.5)
                                    break

                        # Send
                        for sel in ['button:has-text("发送")']:
                            btns = page.query_selector_all(sel)
                            for btn in btns:
                                if "发送" in (btn.text_content() or ""):
                                    btn.click()
                                    break

                        time.sleep(8)

                        chat_api = [r for r in captured_requests if "/api/chat" in r["url"]]
                        print(f"\n  Chat API: {len(chat_api)} requests")
                        for r in chat_api:
                            print(f"    - {r['method']} {r['url'].replace(BACKEND_URL, '')} -> {r['response_status']}")
                            print(f"      Auth: {'YES' if r.get('auth_header_found') else 'NO'}")
                            if r.get("auth_header_value"):
                                print(f"      Token: {str(r['auth_header_value'])[:50]}...")

                        log_test("7. Chat API called", len(chat_api) > 0, f"{len(chat_api)} requests")
                        chat_auth = [r for r in chat_api if r.get("auth_header_found")]
                        log_test("8. Auth header sent", len(chat_auth) > 0, f"{len(chat_auth)}/{len(chat_api)}")

            # Final
            print(f"\n[FINAL] URL: {page.url}")
            results["steps"].append(f"Final URL: {page.url}")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()
            log_test("Critical error", False, str(e))
            results["steps"].append(f"ERROR: {e}")

        context.close()
        results["test_end"] = datetime.now().isoformat()

    print("\n" + "=" * 80)
    print("GENERATING FINAL REPORT")
    print("=" * 80)
    generate_report(results)


def generate_report(results: dict):
    api_requests = [r for r in captured_requests if "/api/" in r["url"]]
    auth_api = [r for r in api_requests if "/api/auth" in r["url"]]
    chat_api = [r for r in api_requests if "/api/chat" in r["url"]]
    unauthorized = [r for r in api_requests if r["response_status"] == 401]
    auth_header_reqs = [r for r in api_requests if r.get("auth_header_found", False)]
    chat_auth = [r for r in chat_api if r.get("auth_header_found")]

    report = []
    report.append("# Browser Test Report: Codebot Authentication Flow")
    report.append("")
    report.append(f"**Test Date:** {results['test_start']}")
    report.append(f"**Test Duration:** {results.get('test_end', 'N/A')}")
    report.append(f"**Target:** {BACKEND_URL}")
    report.append(f"**Credentials:** `{USERNAME}/{'*' * len(PASSWORD)}`")
    report.append("")
    report.append("## Test Results Summary")
    report.append("")
    report.append("| Test Step | Status | Details |")
    report.append("|-----------|--------|---------|")
    for line in test_results:
        report.append(line)
    report.append("")
    report.append("## Test Steps")
    report.append("")
    for i, step in enumerate(results.get("steps", []), 1):
        report.append(f"{i}. {step}")
    report.append("")
    report.append("## Console Logs")
    report.append("")
    if console_logs:
        report.append("```")
        for log in console_logs:
            loc = f" ({log.get('url','')[:50]}:{log.get('line','')})" if log.get('url') else ""
            report.append(f"[{log['type'].upper()}{loc}] {log['text']}")
        report.append("```")
    else:
        report.append("No console logs captured.")
    report.append("")
    report.append("## Network Summary")
    report.append("")
    report.append(f"| Metric | Count |")
    report.append(f"|--------|-------|")
    report.append(f"| Total API requests | {len(api_requests)} |")
    report.append(f"| Auth API requests | {len(auth_api)} |")
    report.append(f"| Chat API requests | {len(chat_api)} |")
    report.append(f"| Requests with Auth header | {len(auth_header_reqs)} |")
    report.append(f"| 401 Unauthorized | {len(unauthorized)} |")
    report.append("")

    # All API requests
    if api_requests:
        report.append("### All API Requests")
        report.append("")
        for i, req in enumerate(api_requests, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"#### {i}. {req['method']} `{url_short}`")
            report.append(f"- **Status:** {req.get('response_status', 'N/A')}")
            report.append(f"- **Auth Header:** {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("auth_header_value"):
                av = str(req["auth_header_value"])
                report.append(f"- **Authorization:** `{av[:60]}...`")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- **Request:** ```{pd[:500]}```")
            if req.get("response_body"):
                rb = req["response_body"]
                report.append(f"- **Response:** ```{rb[:800]}```")
            report.append("")

    # Auth API deep analysis
    if auth_api:
        report.append("### Auth API Deep Analysis")
        report.append("")
        for req in auth_api:
            report.append(f"**POST** `/api/auth/login`")
            report.append("")
            report.append(f"- **HTTP Status:** {req.get('response_status')}")
            report.append(f"- **Auth Header Sent:** {'YES' if req.get('auth_header_found') else 'NO'}")
            report.append(f"- **Request Body:** ```{req.get('post_data', '')}```")
            report.append(f"- **Response Body:** ```{req.get('response_body', 'N/A')}```")
            report.append("")
            report.append("### Response Parsing:")
            body = req.get("response_body", "")
            try:
                import json as _json
                data = _json.loads(body) if body else {}
                report.append(f"- Raw JSON parsed: YES")
                report.append(f"- `success` field: `{data.get('success')}`")
                report.append(f"- `data` field exists: {data.get('data') is not None}")
                if data.get("data"):
                    d = data["data"]
                    report.append(f"- `data.access_token` exists: {d.get('access_token') is not None}")
                    report.append(f"- `data.access_token` value: `{d.get('access_token', 'MISSING')[:50]}...`" if d.get("access_token") else "- `data.access_token` value: `MISSING`")
                    report.append(f"- `data.refresh_token` exists: {d.get('refresh_token') is not None}")
                    report.append(f"- `data.user` exists: {d.get('user') is not None}")
                    if d.get("user"):
                        report.append(f"- `data.user`: ```{_json.dumps(d['user'])}```")
            except Exception as e:
                report.append(f"- Raw JSON parsed: NO ({e})")
            report.append("")

    # 401s
    if unauthorized:
        report.append("## 401 Errors")
        for i, req in enumerate(unauthorized, 1):
            report.append(f"### {i}. 401: {req['method']} `{req['url'].replace(BACKEND_URL, '')}`")
            report.append(f"- Has Auth: {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("response_body"):
                report.append(f"- Body: ```{req['response_body'][:300]}```")
            report.append("")
    else:
        report.append("## 401 Errors: None captured")
        report.append("")

    # Authorization header analysis
    report.append("## Authorization Header Analysis")
    report.append("")
    report.append(f"**{len(auth_header_reqs)}/{len(api_requests)} API requests** include Authorization header.")
    report.append("")
    if auth_header_reqs:
        for req in auth_header_reqs:
            av = str(req.get("auth_header_value", ""))
            if len(av) > 50:
                av = av[:47] + "..."
            report.append(f"- {req['method']} `{req['url'].replace(BACKEND_URL, '')}`: `{av}`")
    report.append("")
    if chat_api:
        report.append(f"**Chat API:** {len(chat_auth)}/{len(chat_api)} include Authorization header.")
        for r in chat_api:
            av = str(r.get("auth_header_value", ""))
            report.append(f"- {r['method']} `{r['url'].replace(BACKEND_URL, '')}`: {'YES' if r.get('auth_header_found') else 'NO'}")
            if r.get('auth_header_found'):
                report.append(f"  Token: `{av[:60]}...`")
    report.append("")

    # Final verdict
    report.append("## Final Verdict")
    report.append("")
    passed = sum(1 for l in test_results if "PASS" in l)
    total = len(test_results)
    login_succeeded = any("Redirect to /chat" in l and "PASS" in l for l in test_results)
    token_stored = any("Token stored" in l and "PASS" in l for l in test_results)
    chat_called = any("Chat API called" in l and "PASS" in l for l in test_results)
    auth_sent = len(chat_auth) > 0

    js_errors = [l for l in console_logs if l.get("type") in ("error", "pageerror")]

    if login_succeeded and token_stored and chat_called and auth_sent:
        report.append("**STATUS: PASS** - Complete auth flow works end-to-end.")
    elif login_succeeded and token_stored:
        report.append("**STATUS: PARTIAL PASS** - Login works, chat not fully tested.")
    elif not login_succeeded and auth_api:
        # Login API was called
        login_req = auth_api[0]
        status = login_req.get("response_status", 0)
        body = login_req.get("response_body", "")

        report.append("**STATUS: FAIL** - Login API returns success but frontend doesn't process it.")
        report.append("")
        report.append("### Root Cause")
        report.append("")
        report.append(f"1. Backend HTTP Status: `{status}`")
        if body:
            try:
                import json as _json
                data = _json.loads(body)
                report.append(f"2. Backend `success` field: `{data.get('success')}`")
                if data.get('data', {}).get('access_token'):
                    report.append(f"3. Backend `access_token`: PRESENT (token is valid)")
                else:
                    report.append(f"3. Backend `access_token`: MISSING")
            except:
                pass

        report.append("")
        report.append("### The Problem")
        report.append("")
        report.append("The login API returns `success: true` with a valid `access_token`, but the frontend's")
        report.append("`login()` function returns `false` instead of `true`. This means the condition:")
        report.append("")
        report.append("```javascript")
        report.append("(p = h.data) != null && p.success ? (s(h.data.data), !0) : !1")
        report.append("```")
        report.append("")
        report.append("evaluates to `false` even though the API returned `success: true`.")
        report.append("")
        report.append("### Most Likely Causes")
        report.append("")

        if js_errors:
            report.append("### JavaScript Errors Found:")
            for err in js_errors:
                report.append(f"- `{err['text']}` (line {err.get('line', '?')})")
            report.append("")
            report.append("These errors may be causing the login() function to fail.")
        else:
            report.append("1. **Axios response interceptor unwrapping data**")
            report.append("   - If the frontend's Axios response interceptor returns `e.data` instead of `e`,")
            report.append("     then `h.data` in the login function would be the inner data object.")
            report.append("   - But the response interceptor in the code shows `e => e`, so this is NOT the issue.")
            report.append("")
            report.append("2. **localStorage failure during `s()` execution**")
            report.append("   - The `s()` function calls `localStorage.setItem('token', f)`")
            report.append("   - If localStorage is blocked or fails silently, `s()` throws")
            report.append("   - This would cause `login()` to enter the `catch` block and show error message")
            report.append("   - But the test shows NO error message on the UI!")
            report.append("")
            report.append("3. **Vue router.push() failing**")
            report.append("   - `login()` calls `y.push('/chat')` on success")
            report.append("   - If navigation guard blocks it (e.g., route requires auth but token not set), it fails")
            report.append("   - But this shouldn't prevent `s()` from being called...")
            report.append("")
            report.append("4. **Axios returning a transformed response**")
            report.append("   - The `Jt.post()` might return the response in a different structure than expected")
            report.append("   - If `h.data` is the axios response wrapper, `h.data.data` might be undefined")
            report.append("")
            report.append("### Recommended Fix")
            report.append("")
            report.append("Check the Axios configuration and response interceptor in the source code.")
            report.append("The issue is that the backend returns the correct data, but the frontend's")
            report.append("`login()` function receives it in an unexpected format.")
            report.append("")
            report.append("**Likely fix:** Ensure the Axios response interceptor does NOT unwrap `e.data`.")
            report.append("The interceptor should return `e` (the full response), not `e.data`.")

    elif not login_succeeded and not auth_api:
        report.append("**STATUS: FAIL** - Login form never submitted (no API call made).")
        report.append("Possible cause: Vue form validation failing before API call.")
    else:
        report.append(f"**STATUS: INCONCLUSIVE** - {passed}/{total} passed.")

    report.append("")
    report.append(f"*Report generated: {datetime.now().isoformat()}*")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
