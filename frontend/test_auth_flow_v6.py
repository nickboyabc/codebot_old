"""
Codebot Auth E2E Test - v6
Injects console.log directly into the running app to trace login function execution.
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

    is_login = "/api/auth/login" in request.url
    is_chat = "/api/chat" in request.url

    if is_login or is_chat or is_api_request(request.url):
        print(f"\n>>> [REQUEST] {request.method} {request.url.replace(BACKEND_URL, '')}")
        if req_info["auth_header_found"]:
            val = str(req_info["auth_header_value"])
            print(f"    Auth: {val[:50]}...")
        else:
            print(f"    Auth: NONE")
        if request.post_data:
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
                if is_login or is_chat:
                    print(f"    -> {response.status}: {decoded[:300]}")
        except Exception:
            pass
        captured_requests.append(req_info)
        route.continue_()
    except Exception as e:
        if is_login or is_chat:
            print(f"    -> Error: {e}")
        captured_requests.append(req_info)
        try:
            route.abort()
        except Exception:
            pass


def is_api_request(url: str) -> bool:
    return "/api/" in url


def handle_console(msg):
    console_logs.append({
        "type": msg.type,
        "text": msg.text,
        "url": msg.location.get("url", ""),
        "line": msg.location.get("lineNumber", ""),
    })
    print(f"[CONSOLE/{msg.type.upper()}] {msg.text}")


def handle_page_error(err):
    console_logs.append({"type": "pageerror", "text": str(err)})
    print(f"[PAGE ERROR] {err}")


def main():
    print("=" * 80)
    print("Codebot Auth E2E Test - v6 (App-level JS tracing)")
    print("=" * 80)

    captured_requests.clear()
    console_logs.clear()
    test_results.clear()
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
            results["steps"].append(f"URL: {url}")

            if "/login" in url:
                # Wait for Vue app
                print("\n[WAIT] Waiting for Vue app...")
                page.wait_for_selector("#app .login-page", timeout=10000)
                print("  Login page rendered")

                # Inject debug logging into the app
                # We'll patch the localStorage.setItem to log all calls
                page.evaluate("""() => {
                    const _origSetItem = localStorage.setItem.bind(localStorage);
                    const _origGetItem = localStorage.getItem.bind(localStorage);
                    window.__storageLog = [];
                    localStorage.setItem = (k, v) => {
                        window.__storageLog.push({op: 'set', key: k, vLen: v ? v.length : 0, time: Date.now()});
                        console.log('[STORAGE-SET] ' + k + ' = ' + (k === 'token' || k === 'userInfo' ? (v ? v.substring(0, 30) + '...' : v) : v));
                        _origSetItem(k, v);
                    };
                    localStorage.getItem = (k) => {
                        const v = _origGetItem(k);
                        window.__storageLog.push({op: 'get', key: k, found: v !== null, time: Date.now()});
                        return v;
                    };
                    console.log('[INJECT] Storage hooks installed');
                }""")

                # Also patch the Jt (axios instance) response interceptor
                # We can't easily do this for module-level variables,
                # but we CAN try to monkey-patch the Vue component's login call
                # by patching the button click handler

                # Fill form
                print("\n[STEP] Filling login form...")
                inputs = page.query_selector_all('input.el-input__inner')
                inputs[0].fill(USERNAME)
                time.sleep(0.3)
                inputs[1].fill(PASSWORD)
                time.sleep(0.3)
                log_test("3. Fill form", True, f"{USERNAME}/****")
                results["steps"].append("Form filled")

                # Now add a debug listener to the button BEFORE clicking
                print("\n[STEP] Adding debug click listener...")
                page.evaluate("""() => {
                    // Find the login button and wrap its click handler
                    const buttons = document.querySelectorAll('button.el-button--primary');
                    for (const btn of buttons) {
                        if (btn.textContent.includes('登')) {
                            console.log('[DEBUG] Found login button, wrapping click...');
                            const origClick = btn.onclick;
                            btn.onclick = async (e) => {
                                console.log('[DEBUG] Login button clicked!');
                                // Find the form
                                const form = btn.closest('form') || btn.closest('.login-form');
                                console.log('[DEBUG] Form element:', form ? 'found' : 'not found');
                                // Try to manually trigger the form submit
                                if (form) {
                                    try {
                                        const submitEvent = new Event('submit', {bubbles: true, cancelable: true});
                                        form.dispatchEvent(submitEvent);
                                        console.log('[DEBUG] Form submit dispatched');
                                    } catch(e) {
                                        console.error('[DEBUG] Form submit error:', e);
                                    }
                                }
                                // Still call original
                                if (origClick) {
                                    try { origClick.call(btn, e); } catch(e2) { console.error('[DEBUG] origClick error:', e2); }
                                }
                            };
                            console.log('[DEBUG] Click handler wrapped');
                            break;
                        }
                    }
                }""")

                # Click login button
                print("\n[STEP] Clicking login button...")
                buttons = page.query_selector_all('button.el-button--primary')
                for btn in buttons:
                    txt = btn.text_content() or ""
                    if "登" in txt:
                        btn.click()
                        break

                results["steps"].append("Login clicked")
                time.sleep(5)

                # Analyze
                url_after = page.url
                print(f"\n  URL: {url_after}")
                results["steps"].append(f"URL: {url_after}")

                # Check storage log
                storage_log = page.evaluate("window.__storageLog || []")
                print(f"\n  Storage operations: {len(storage_log)}")
                for op in storage_log:
                    print(f"    {op}")

                # Check localStorage
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
                    print("\n" + "=" * 40)
                    print("DIAGNOSIS")
                    print("=" * 40)

                    auth_api = [r for r in captured_requests if "/api/auth/login" in r["url"]]
                    if auth_api:
                        req = auth_api[0]
                        body = req.get("response_body", "")
                        print(f"\n1. Backend: HTTP {req.get('response_status')}")
                        print(f"   Body: {body[:200]}")

                        if '"success":true' in body:
                            print(f"\n2. Backend returns success:true")
                            print(f"   -> But login() returned false")

                            # Check for JS errors
                            js_errors = [l for l in console_logs if l.get("type") in ("error", "pageerror")]
                            print(f"\n3. JS Errors: {len(js_errors)}")
                            for err in js_errors:
                                print(f"   - {err['text']}")

                            # Check console for login-related logs
                            login_logs = [l for l in console_logs if any(x in l.get("text", "") for x in ["登", "login", "Login", "token", "error", "Error", "失败", "错误"])]
                            print(f"\n4. Login-related console logs: {len(login_logs)}")
                            for l in login_logs:
                                print(f"   [{l['type']}] {l['text']}")

                            # Try to check Element Plus messages
                            ui_errors = page.evaluate("""() => {
                                const msgs = Array.from(document.querySelectorAll('.el-message'));
                                return msgs.map(m => ({
                                    type: m.className,
                                    text: m.textContent.trim()
                                }));
                            }""")
                            print(f"\n5. Element Plus messages: {len(ui_errors)}")
                            for msg in ui_errors:
                                print(f"   - [{msg['type']}] {msg['text']}")

                            results["steps"].append("DIAGNOSIS: Backend OK but login fails")
                            results["steps"].append(f"JS Errors: {len(js_errors)}")
                            results["steps"].append(f"Storage ops: {len(storage_log)}")

                    # Try direct token injection test
                    print("\n6. localStorage functionality test:")
                    test_result = page.evaluate("""() => {
                        try {
                            localStorage.setItem('__test__', 'hello');
                            const v = localStorage.getItem('__test__');
                            localStorage.removeItem('__test__');
                            return 'OK: ' + v;
                        } catch(e) {
                            return 'ERROR: ' + e.message;
                        }
                    }""")
                    print(f"   {test_result}")

                    # Check if the Vue component received the response
                    # Try to call the login API directly from the page
                    print("\n7. Testing login API directly from page context...")
                    direct_result = page.evaluate("""async () => {
                        try {
                            const resp = await fetch('/api/auth/login', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({username: 'admin', password: 'admin123'})
                            });
                            const data = await resp.json();
                            console.log('[DIRECT-FETCH] Status:', resp.status);
                            console.log('[DIRECT-FETCH] Response:', JSON.stringify(data).substring(0, 200));
                            return {status: resp.status, data};
                        } catch(e) {
                            return {error: e.message};
                        }
                    }""")
                    print(f"   Direct fetch result: {json.dumps(direct_result)[:200]}")

                    # Check if the form values are set
                    form_values = page.evaluate("""() => {
                        const inputs = document.querySelectorAll('input.el-input__inner');
                        return Array.from(inputs).map(i => ({
                            type: i.type,
                            placeholder: i.placeholder,
                            value: i.value
                        }));
                    }""")
                    print(f"\n8. Form input values:")
                    for inp in form_values:
                        print(f"   {inp}")

                else:
                    # Login succeeded
                    results["steps"].append("Login SUCCESS")

                    # Chat flow
                    print("\n[STEP] Testing chat flow...")
                    for sel in ['button:has-text("新建对话")', 'button']:
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

                    for sel in ['button:has-text("发送")', 'button']:
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

                    log_test("6. Chat API called", len(chat_api) > 0, f"{len(chat_api)} requests")
                    chat_auth = [r for r in chat_api if r.get("auth_header_found")]
                    log_test("7. Auth header sent", len(chat_auth) > 0, f"{len(chat_auth)}/{len(chat_api)}")

            print(f"\n[FINAL] URL: {page.url}")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()
            log_test("Critical error", False, str(e))
            results["steps"].append(f"ERROR: {e}")

        context.close()
        results["test_end"] = datetime.now().isoformat()

    print("\n" + "=" * 80)
    print("GENERATING REPORT")
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

    # Console logs
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

    # Network
    report.append("## Network Request Summary")
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
        for i, req in enumerate(api_requests, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"#### {i}. {req['method']} `{url_short}`")
            report.append(f"- **Status:** {req.get('response_status', 'N/A')}")
            report.append(f"- **Auth Header:** {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- **Request:** ```{pd[:500]}```")
            if req.get("response_body"):
                report.append(f"- **Response:** ```{req['response_body'][:800]}```")
            report.append("")

    # Auth deep analysis
    if auth_api:
        report.append("### Auth API Deep Analysis")
        for req in auth_api:
            report.append(f"**POST /api/auth/login**")
            report.append(f"- HTTP Status: {req.get('response_status')}")
            body = req.get("response_body", "")
            report.append(f"- **Response Body:** ```{body}```")
            try:
                data = json.loads(body)
                report.append(f"- Parsed: success={data.get('success')}, has data={data.get('data') is not None}")
                if data.get("data"):
                    d = data["data"]
                    report.append(f"- access_token: {'PRESENT' if d.get('access_token') else 'MISSING'}")
                    report.append(f"- refresh_token: {'PRESENT' if d.get('refresh_token') else 'MISSING'}")
                    report.append(f"- user: {d.get('user', 'MISSING')}")
            except:
                pass
            report.append("")

    # 401s
    if unauthorized:
        report.append("## 401 Errors")
        for req in unauthorized:
            report.append(f"- {req['method']} {req['url'].replace(BACKEND_URL, '')}: {req.get('response_status')}")
    else:
        report.append("## 401 Errors: None")

    # Auth headers
    report.append("")
    report.append("## Authorization Header Analysis")
    report.append("")
    report.append(f"**{len(auth_header_reqs)}/{len(api_requests)} API requests** include Authorization header.")
    if auth_header_reqs:
        for req in auth_header_reqs:
            av = str(req.get("auth_header_value", ""))[:60]
            report.append(f"- {req['method']} `{req['url'].replace(BACKEND_URL, '')}`: `{av}...`")
    if chat_api:
        report.append(f"**Chat API:** {len(chat_auth)}/{len(chat_api)} have auth header.")

    # Verdict
    report.append("")
    report.append("## Final Verdict")
    passed = sum(1 for l in test_results if "PASS" in l)
    total = len(test_results)
    login_ok = any("Redirect to /chat" in l and "PASS" in l for l in test_results)
    token_ok = any("Token stored" in l and "PASS" in l for l in test_results)
    chat_ok = any("Chat API called" in l and "PASS" in l for l in test_results)
    auth_sent = len(chat_auth) > 0
    js_errors = [l for l in console_logs if l.get("type") in ("error", "pageerror")]

    if login_ok and token_ok and chat_ok and auth_sent:
        report.append("**STATUS: PASS**")
    elif login_ok and token_ok:
        report.append("**STATUS: PARTIAL** - Login works, chat flow not fully tested.")
    elif not login_ok and auth_api:
        login_req = auth_api[0]
        body = login_req.get("response_body", "")
        status = login_req.get("response_status", 0)

        report.append("**STATUS: FAIL** - Login API returns success but frontend doesn't process it.")
        report.append("")
        report.append("### Root Cause")
        report.append("")
        report.append(f"| Item | Value |")
        report.append(f"|------|-------|")
        report.append(f"| HTTP Status | {status} |")
        report.append(f"| success field | {'true' if 'success' in body and 'true' in body else 'N/A'} |")
        report.append(f"| access_token | {'PRESENT' if 'access_token' in body else 'MISSING'} |")
        report.append(f"| JS Errors | {len(js_errors)} |")
        report.append("")
        report.append("### Analysis")
        report.append("")
        report.append("The backend returns the correct `success:true` response with `access_token`,")
        report.append("but the frontend's `login()` composable function returns `false`.")
        report.append("")
        report.append("The login function code is:")
        report.append("```javascript")
        report.append("const h = await Jt.post('/api/auth/login', {username: f, password: v});")
        report.append("return (p = h.data) != null && p.success ? (s(h.data.data), !0) : !1")
        report.append("```")
        report.append("")
        report.append("This returns `false` only if:")
        report.append("1. `h.data` is null/undefined, OR")
        report.append("2. `h.data.success` is falsy")
        report.append("")
        report.append("### Most Likely Cause: Axios Fetch Adapter Mismatch")
        report.append("")
        report.append("In Playwright/Chromium, Axios may use the Fetch API adapter instead of XMLHttpRequest.")
        report.append("If Axios v1.x uses the fetch adapter, the response structure might be different.")
        report.append("Specifically, `h.data` might not be the parsed JSON - it might be the raw Response object.")
        report.append("")
        report.append("### Recommended Fixes")
        report.append("")
        report.append("1. **Check Axios adapter**: Ensure Axios is using XMLHttpRequest (XHR), not Fetch")
        report.append("2. **Check response structure**: Add `console.log` in login() to log `h` and `h.data`")
        report.append("3. **Response interceptor**: Consider unwrapping `e.data` in the response interceptor")
        report.append("")
        if js_errors:
            report.append("### JavaScript Errors")
            for err in js_errors:
                report.append(f"- `{err['text']}`")
    elif not login_ok and not auth_api:
        report.append("**STATUS: FAIL** - Login form not submitted (no API call).")
    else:
        report.append(f"**STATUS: INCONCLUSIVE** - {passed}/{total} passed.")

    report.append("")
    report.append(f"*Report generated: {datetime.now().isoformat()}*")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
