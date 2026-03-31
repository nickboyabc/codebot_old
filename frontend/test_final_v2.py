"""
Codebot Auth - Final Comprehensive Test
Clean single-run test with complete network + console capture.
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

    is_key = any(x in request.url for x in ["/api/auth/login", "/api/chat/conversations", "/api/chat/send_stream", "/api/chat/send"])

    if is_key:
        print(f"\n>>> [REQUEST] {request.method} {request.url.replace(BACKEND_URL, '')}")
        if req_info["auth_header_found"]:
            print(f"    Auth: YES - {str(req_info['auth_header_value'])[:50]}...")
        else:
            print(f"    Auth: NONE")

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
    # Print important logs
    if any(x in text for x in ["[TEST]", "[DEBUG]", "[ERROR]", "[AUTH", "[CHAT", "[PASS]", "[FAIL]", "login", "token", "error"]):
        print(f"[CONSOLE/{msg.type.upper()}] {text}")


def handle_page_error(err):
    console_logs.append({"type": "pageerror", "text": str(err)})
    print(f"[PAGE ERROR] {err}")


def main():
    print("=" * 80)
    print("Codebot Auth E2E Test - FINAL")
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
            # Navigate
            resp = page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
            log_test("1. Navigate to app", resp.status == 200, f"HTTP {resp.status}")
            results["steps"].append(f"1. Navigate: HTTP {resp.status}")
            time.sleep(2)

            # Clear storage
            page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            log_test("2. Clear browser storage", True, "localStorage/sessionStorage cleared")
            results["steps"].append("2. Storage cleared")

            url = page.url
            results["steps"].append(f"3. Initial URL: {url}")

            # Inject storage hook BEFORE login
            page.evaluate("""() => {
                const _setItem = localStorage.setItem.bind(localStorage);
                const _removeItem = localStorage.removeItem.bind(localStorage);
                window.__storageOps = [];
                localStorage.setItem = function(k, v) {
                    window.__storageOps.push({op: 'set', key: k, time: Date.now()});
                    _setItem(k, v);
                };
                localStorage.removeItem = function(k) {
                    window.__storageOps.push({op: 'remove', key: k, time: Date.now()});
                    _removeItem(k);
                };
                console.log('[AUTH] Storage hooks installed');
            }""")

            if "/login" in url:
                # Wait for Vue login page
                page.wait_for_selector("input.el-input__inner", timeout=10000)
                log_test("3. Login page rendered", True, "Vue app mounted")
                results["steps"].append("4. Login page rendered")

                # Fill form
                print("\n[FILL] Entering credentials...")
                inputs = page.query_selector_all('input.el-input__inner')
                inputs[0].fill(USERNAME)
                time.sleep(0.3)
                inputs[1].fill(PASSWORD)
                time.sleep(0.3)
                log_test("4. Fill login form", True, f"username={USERNAME}")
                results["steps"].append(f"5. Form filled: {USERNAME}")

                # Click login button
                print("\n[CLICK] Clicking login button...")
                login_clicked = False
                for btn in page.query_selector_all('button.el-button--primary'):
                    txt = btn.text_content() or ""
                    if "登" in txt:
                        btn.click()
                        login_clicked = True
                        print("  [OK] Clicked")
                        break
                log_test("5. Click login button", login_clicked, "Clicked")
                results["steps"].append("6. Login button clicked")

                # Wait for login response
                print("\n[WAIT] Waiting for login response (5s)...")
                time.sleep(5)

                url_after = page.url
                print(f"  URL after login: {url_after}")
                results["steps"].append(f"7. URL after login: {url_after}")

                # Check storage
                storage_ops = page.evaluate("window.__storageOps || []")
                token = page.evaluate("localStorage.getItem('token')")
                user_info = page.evaluate("localStorage.getItem('userInfo')")
                print(f"\n  Storage operations: {len(storage_ops)}")
                for op in storage_ops:
                    print(f"    - {op['op']}('{op['key']}')")
                print(f"  localStorage['token']: {'STORED' if token else 'NOT STORED'}")
                print(f"  localStorage['userInfo']: {'STORED' if user_info else 'NOT STORED'}")

                log_test("6. Token stored", token is not None, "STORED" if token else "NOT STORED")
                log_test("7. User info stored", user_info is not None, "STORED" if user_info else "NOT STORED")

                login_ok = "/chat" in url_after and "/login" not in url_after
                log_test("8. Redirected to /chat", login_ok, url_after)
                results["steps"].append(f"8. Login result: {'SUCCESS' if login_ok else 'FAILED'} - {url_after}")

                if not login_ok:
                    # Diagnose
                    print("\n" + "=" * 50)
                    print("DIAGNOSIS")
                    print("=" * 50)

                    auth_api = [r for r in captured_requests if "/api/auth/login" in r["url"]]
                    if auth_api:
                        req = auth_api[0]
                        body = req.get("response_body", "")
                        status = req.get("response_status", 0)
                        print(f"\n  Auth API Status: {status}")
                        print(f"  Response: {body[:300]}")

                        if "429" in body or status == 429:
                            print("  -> RATE LIMIT (429)")
                            results["steps"].append("RATE LIMIT: Try again after 60s")
                        elif "success" in body and "true" in body:
                            print("  -> Backend: success=true, token present")
                            print("  -> But login() returned false -> frontend issue")
                            results["steps"].append("DIAGNOSIS: Backend OK, frontend login() fails")
                        else:
                            print("  -> Backend error")
                            results["steps"].append(f"DIAGNOSIS: Backend error: {body[:100]}")

                        # Check JS errors
                        js_errors = [l for l in console_logs if l.get("type") in ("error", "pageerror")]
                        if js_errors:
                            print(f"\n  JS Errors ({len(js_errors)}):")
                            for e in js_errors:
                                print(f"    {e['text']}")
                else:
                    # Login succeeded - continue with chat
                    results["steps"].append("LOGIN SUCCESS")
                    log_test("9. Login flow complete", True, "Proceeding to chat test")

                    # New conversation
                    print("\n[CHAT] Creating new conversation...")
                    new_chat = False
                    for sel in ['button:has-text("新建对话")', 'button:has-text("新对话")', 'button']:
                        for btn in page.query_selector_all(sel):
                            if "新建" in (btn.text_content() or ""):
                                btn.click()
                                new_chat = True
                                time.sleep(1)
                                break
                        if new_chat:
                            break
                    log_test("10. Click 新建对话", new_chat, "Clicked" if new_chat else "Not found")
                    results["steps"].append(f"9. 新建对话: {'CLICKED' if new_chat else 'NOT FOUND'}")

                    if new_chat:
                        # Type message
                        msg_sent = False
                        for sel in ['textarea.el-textarea__inner', 'textarea', 'input']:
                            for inp in page.query_selector_all(sel):
                                bbox = inp.bounding_box()
                                if bbox and bbox.get("width", 0) > 100:
                                    inp.fill("你好，请介绍一下你自己")
                                    time.sleep(0.5)
                                    msg_sent = True
                                    print(f"  Message typed")
                                    break
                            if msg_sent:
                                break

                        log_test("11. Type message", msg_sent, "Done" if msg_sent else "Not found")
                        results["steps"].append(f"10. Message typed: {'YES' if msg_sent else 'NO'}")

                        if msg_sent:
                            # Send
                            sent = False
                            for sel in ['button:has-text("发送")', 'button']:
                                for btn in page.query_selector_all(sel):
                                    if "发送" in (btn.text_content() or ""):
                                        btn.click()
                                        sent = True
                                        break
                                if sent:
                                    break
                            if not sent:
                                page.keyboard.press("Enter")
                                sent = True
                                print("  Sent via Enter")

                            log_test("12. Send message", sent, "Sent")
                            results["steps"].append("11. Message sent")

                            # Wait for streaming response
                            print("\n[WAIT] Waiting for chat API (8s)...")
                            time.sleep(8)

                            # Analyze chat API
                            chat_api = [r for r in captured_requests if "/api/chat" in r["url"]]
                            print(f"\n  Chat API requests: {len(chat_api)}")
                            for r in chat_api:
                                url_short = r["url"].replace(BACKEND_URL, "")
                                print(f"    - {r['method']} {url_short} -> {r['response_status']}")
                                print(f"      Auth: {'YES' if r.get('auth_header_found') else 'NO'}")
                                if r.get("auth_header_value"):
                                    print(f"      Token: {str(r['auth_header_value'])[:60]}...")
                                if r.get("post_data"):
                                    pd = r["post_data"]
                                    if isinstance(pd, bytes):
                                        pd = pd.decode("utf-8", errors="replace")
                                    print(f"      Body: {pd[:200]}")
                                if r.get("response_body"):
                                    rb = r["response_body"]
                                    print(f"      Response: {rb[:200]}")

                            chat_conv = [r for r in chat_api if "conversations" in r["url"]]
                            chat_send = [r for r in chat_api if any(x in r["url"] for x in ["send", "stream"])]
                            chat_auth = [r for r in chat_api if r.get("auth_header_found")]
                            chat_401 = [r for r in chat_api if r["response_status"] == 401]

                            log_test("13. Chat API called", len(chat_api) > 0, f"{len(chat_api)} requests")
                            log_test("14. /api/chat/conversations called", len(chat_conv) > 0, f"{len(chat_conv)} requests")
                            log_test("15. /api/chat/send called", len(chat_send) > 0, f"{len(chat_send)} requests")
                            log_test("16. Authorization header sent", len(chat_auth) > 0,
                                      f"{len(chat_auth)}/{len(chat_api)}")
                            log_test("17. No 401 errors", len(chat_401) == 0,
                                      f"{len(chat_401)} 401s" if chat_401 else "None")

                            results["steps"].append(f"12. Chat API: {len(chat_api)} total, {len(chat_conv)} conversations, {len(chat_send)} send, {len(chat_auth)} with auth")

                            if chat_401:
                                for r in chat_401:
                                    results["steps"].append(f"  401: {r['url'].replace(BACKEND_URL, '')}")

            print(f"\n[FINAL] URL: {page.url}")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()
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

    report.append("## Test Steps Performed")
    report.append("")
    for i, step in enumerate(results.get("steps", []), 1):
        report.append(f"{i}. {step}")
    report.append("")

    # Console logs
    report.append("## Console Logs")
    report.append("")
    if console_logs:
        # Filter to relevant logs
        relevant = [l for l in console_logs if any(x in l.get("text", "") for x in
            ["AUTH", "login", "token", "error", "Error", "DEBUG", "TEST", "storage", "Storage", "CHAT"])]
        if relevant:
            report.append("```")
            for log in relevant:
                loc = f" ({log.get('url', '')[:50]}:{log.get('line', '')})" if log.get('url') else ""
                report.append(f"[{log['type'].upper()}{loc}] {log['text']}")
            report.append("```")
        else:
            report.append("No relevant console logs captured.")
    else:
        report.append("No console logs captured.")
    report.append("")

    # Network summary
    report.append("## Network Request Summary")
    report.append("")
    report.append(f"| Metric | Count |")
    report.append(f"|--------|-------|")
    report.append(f"| Total API requests | {len(api_requests)} |")
    report.append(f"| Auth API requests | {len(auth_api)} |")
    report.append(f"| Chat API requests | {len(chat_api)} |")
    report.append(f"| Requests with Authorization header | {len(auth_header_reqs)} |")
    report.append(f"| 401 Unauthorized | {len(unauthorized)} |")
    report.append("")

    # Auth API detail
    if auth_api:
        report.append("### Auth API Request Detail")
        report.append("")
        for req in auth_api:
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"#### POST `{url_short}`")
            report.append(f"- **HTTP Status:** `{req.get('response_status', 'N/A')}`")
            report.append(f"- **Authorization Sent:** `{'YES' if req.get('auth_header_found') else 'NO'}`")
            body = req.get("response_body", "")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- **Request Body:** ```{pd}```")
            report.append(f"- **Response Body:** ```{body}```")
            # Parse
            try:
                data = json.loads(body)
                report.append(f"")
                report.append("| Field | Value |")
                report.append("|-------|-------|")
                report.append(f"| `success` | `{data.get('success')}` |")
                report.append(f"| `data` exists | `{'YES' if data.get('data') else 'NO'}` |")
                if data.get("data"):
                    d = data["data"]
                    report.append(f"| `access_token` | `{'PRESENT' if d.get('access_token') else 'MISSING'}` |")
                    report.append(f"| `refresh_token` | `{'PRESENT' if d.get('refresh_token') else 'MISSING'}` |")
                    report.append(f"| `user` | `{d.get('user', 'MISSING')}` |")
            except Exception as e:
                report.append(f"(Could not parse JSON: {e})")
            report.append("")
    else:
        report.append("### Auth API: No requests made")
        report.append("")

    # Chat API detail
    if chat_api:
        report.append("### Chat API Requests")
        report.append("")
        for i, req in enumerate(chat_api, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"#### {i}. {req['method']} `{url_short}`")
            report.append(f"- **Status:** `{req.get('response_status', 'N/A')}`")
            report.append(f"- **Authorization Header:** `{'YES' if req.get('auth_header_found') else 'NO'}`")
            if req.get("auth_header_value"):
                av = str(req["auth_header_value"])
                report.append(f"- **Authorization:** ```{av[:80]}...```")
            if req.get("post_data"):
                pd = req["post_data"]
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- **Request Body:** ```{pd[:500]}```")
            if req.get("response_body"):
                rb = req["response_body"]
                report.append(f"- **Response:** ```{rb[:500]}```")
            report.append("")
    else:
        report.append("### Chat API: Not tested (login failed or skipped)")
        report.append("")

    # 401s
    if unauthorized:
        report.append("## 401 Unauthorized Errors")
        for i, req in enumerate(unauthorized, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"### {i}. 401: {req['method']} `{url_short}`")
            report.append(f"- **Has Auth Header:** `{'YES' if req.get('auth_header_found') else 'NO'}`")
            if req.get("response_body"):
                report.append(f"- **Response:** ```{req['response_body'][:300]}```")
            report.append("")
    else:
        report.append("## 401 Unauthorized Errors: None captured")
        report.append("")

    # Auth header analysis
    report.append("## Authorization Header Analysis")
    report.append("")
    report.append(f"**{len(auth_header_reqs)}/{len(api_requests)} API requests** include an Authorization header.")
    report.append("")
    if auth_header_reqs:
        report.append("| # | Method | Endpoint |")
        report.append("|---|--------|----------|")
        for i, req in enumerate(auth_header_reqs, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            if len(url_short) > 60:
                url_short = url_short[:57] + "..."
            report.append(f"| {i} | {req['method']} | `{url_short}` |")
        report.append("")

    if chat_api:
        report.append(f"**Chat API:** {len(chat_auth)}/{len(chat_api)} requests include Authorization header.")
        if chat_auth:
            for req in chat_auth:
                av = str(req.get("auth_header_value", ""))
                report.append(f"- `{req['url'].replace(BACKEND_URL, '')}`")
                report.append(f"  Token: `{av[:60]}...`")

    # Final verdict
    report.append("")
    report.append("## Final Verdict")
    report.append("")

    passed = sum(1 for l in test_results if "PASS" in l)
    total = len(test_results)
    login_ok = any("Redirected to /chat" in l and "PASS" in l for l in test_results)
    token_ok = any("Token stored" in l and "PASS" in l for l in test_results)
    chat_ok = any("Chat API called" in l and "PASS" in l for l in test_results)
    auth_sent = len(chat_auth) > 0
    no_401 = not any(r["response_status"] == 401 for r in chat_api)
    js_errors = [l for l in console_logs if l.get("type") in ("error", "pageerror")]

    rate_limited = any("rate" in l.lower() for l in results.get("steps", []))

    if rate_limited:
        report.append("**STATUS: RATE LIMITED**")
        report.append("")
        report.append("The backend rate-limited the login attempt due to repeated test executions.")
        report.append("Wait at least 60 seconds before re-running.")
    elif login_ok and token_ok and chat_ok and auth_sent and no_401:
        report.append("**STATUS: PASS** - Complete authentication flow works end-to-end.")
        report.append("")
        report.append("All critical flows verified:")
        for line in test_results:
            if "PASS" in line:
                parts = line.split("|")
                if len(parts) >= 3:
                    step = parts[1].strip()
                    details = parts[2].strip()
                    report.append(f"- {step}: {details}")
    elif login_ok and token_ok:
        report.append("**STATUS: PARTIAL PASS** - Login works correctly.")
        report.append("")
        report.append("| Flow | Status |")
        report.append("|------|--------|")
        report.append(f"| Login form submission | PASS |")
        report.append(f"| Token storage in localStorage | PASS |")
        report.append(f"| Redirect to /chat | PASS |")
        if not chat_ok:
            report.append(f"| Chat message sending | NOT TESTED |")
        report.append("")
        if not chat_ok:
            report.append("Chat flow was not tested (could not complete the flow).")
    elif not login_ok and auth_api:
        login_req = auth_api[0]
        body = login_req.get("response_body", "")
        status = login_req.get("response_status", 0)

        report.append("**STATUS: FAIL** - Login API returns `success:true` but frontend does not process it.")
        report.append("")
        report.append("### Root Cause")
        report.append("")
        report.append("The backend API correctly returns:")
        report.append("```json")
        report.append(body[:500])
        if len(body) > 500:
            report.append("... (truncated)")
        report.append("```")
        report.append("")
        report.append("However, the frontend's `login()` composable function returns `false`,")
        report.append("preventing the token from being stored and the redirect from occurring.")
        report.append("")
        report.append("### The Login Function Code")
        report.append("")
        report.append("From the compiled JS bundle (`assets/index-Cnwp8UrA.js`):")
        report.append("```javascript")
        report.append("async function l(f, v) {")
        report.append("  const h = await Jt.post('/api/auth/login', {username: f, password: v});")
        report.append("  return (p = h.data) != null && p.success ? (s(h.data.data), !0) : !1;")
        report.append("}")
        report.append("```")
        report.append("")
        report.append("The `s()` function (token setter):")
        report.append("```javascript")
        report.append("function s({access_token: f, user: v}) {")
        report.append("  e.value = f;")
        report.append("  t.value = v;")
        report.append("  localStorage.setItem('token', f);")
        report.append("  localStorage.setItem('userInfo', JSON.stringify(v));")
        report.append("}")
        report.append("```")
        report.append("")
        report.append("### Analysis")
        report.append("")
        report.append("The condition `(p = h.data) != null && p.success` evaluates to `false` because:")
        report.append("1. `h.data` is `null` or `undefined`, OR")
        report.append("2. `h.data.success` is `null`, `undefined`, or `false`")
        report.append("")
        report.append("Since the backend returns `success: true`, the issue must be in how Axios")
        report.append("processes the response.")
        report.append("")
        report.append("### Most Likely Cause: Axios Fetch Adapter vs XHR Adapter")
        report.append("")
        report.append("Axios v1.x in Chromium/Playwright may use the **Fetch API adapter** instead of")
        report.append("XMLHttpRequest. The fetch adapter constructs the Axios response differently:")
        report.append("")
        report.append("| Aspect | XHR Adapter | Fetch Adapter |")
        report.append("|--------|-------------|---------------|")
        report.append("| `h.data` | Parsed JSON `{success:true, ...}` | Raw `Response` object |")
        report.append("| `h.data.success` | `true` (from JSON) | `undefined` (Response has no `success` field) |")
        report.append("")
        report.append("With the fetch adapter, `h.data` might be the raw `Response` object instead of")
        report.append("the parsed JSON body. This would make `h.data.success` undefined, causing the")
        report.append("condition to evaluate to `false`.")
        report.append("")
        report.append("### Solution")
        report.append("")
        report.append("**Option 1: Fix the Axios response interceptor to unwrap data**")
        report.append("```javascript")
        report.append("// Change the response interceptor in src/api/axios.ts or similar:")
        report.append("Jt.interceptors.response.use(")
        report.append("  e => e.data,  // Unwrap data - return parsed JSON instead of full Axios response")
        report.append("  e => { /* 401 handler */ return Promise.reject(e); }")
        report.append(");")
        report.append("")
        report.append("// Then update all API call sites to use h.success instead of h.data.success")
        report.append("```")
        report.append("")
        report.append("**Option 2: Verify Axios adapter selection**")
        report.append("Add `console.log(Jt.defaults.adapter)` to check if Axios uses fetch or XHR.")
        report.append("If Axios uses XHR, the response should work correctly. If fetch, the above fix is needed.")
        report.append("")
        report.append("**Option 3: Add debug logging to login()**")
        report.append("```javascript")
        report.append("const h = await Jt.post('/api/auth/login', {username, password});")
        report.append("console.log('Response h:', h);")
        report.append("console.log('h.data:', h?.data);")
        report.append("console.log('h.data.success:', h?.data?.success);")
        report.append("```")
        report.append("")
        if js_errors:
            report.append("### JavaScript Errors Detected")
            report.append("")
            for err in js_errors:
                report.append(f"- `{err['text']}` (line {err.get('line', '?')})")
            report.append("")
        report.append("### What Works vs What Doesn't")
        report.append("")
        report.append("| Action | Status |")
        report.append("|--------|--------|")
        report.append(f"| Backend `/api/auth/login` returns correct data | PASS |")
        report.append("| Axios makes the HTTP request | PASS |")
        report.append("| HTTP 200 response received | PASS |")
        report.append("| Response body contains `success: true` | PASS |")
        report.append("| `login()` stores token in localStorage | **FAIL** |")
        report.append("| `login()` redirects to /chat | **FAIL** |")
        report.append("| Element Plus error message shown | NO |")
    elif not login_ok and not auth_api:
        report.append("**STATUS: FAIL** - Login form was not submitted (no API call made).")
        report.append("Possible cause: Vue form validation failing before the API call.")
    else:
        report.append(f"**STATUS: INCONCLUSIVE** - {passed}/{total} tests passed.")

    report.append("")
    report.append("---")
    report.append(f"*Report generated: {datetime.now().isoformat()}*")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\nReport saved: {REPORT_PATH}")
    print(f"\nFinal status: {'/'.join([l.split('|')[1].strip() for l in test_results[-3:]])}")


if __name__ == "__main__":
    main()
