"""
Codebot Auth E2E Test - v4 FINAL
With JavaScript-level debugging to trace exact auth flow failure.
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
    print(f"[CONSOLE/{msg.type.upper()}] {text}")


def handle_page_error(err):
    console_logs.append({"type": "pageerror", "text": str(err)})
    print(f"[PAGE ERROR] {err}")


def main():
    print("=" * 80)
    print("Codebot Auth E2E Test - v4 FINAL (JS Debug)")
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
            log_test("1. Navigate", resp.status == 200, f"HTTP {resp.status}")
            results["steps"].append(f"Navigate: HTTP {resp.status}")
            time.sleep(2)

            # Clear storage
            page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            log_test("2. Clear storage", True, "Done")
            results["steps"].append("Clear storage")

            url = page.url
            results["steps"].append(f"URL: {url}")

            # Inject debug hooks BEFORE login
            print("\n[DEBUG] Injecting JavaScript debug hooks...")
            page.evaluate("""() => {
                // Hook into localStorage.setItem to log token saves
                const _setItem = localStorage.setItem.bind(localStorage);
                window.__tokenSets = [];
                localStorage.setItem = (k, v) => {
                    if (k === 'token') {
                        window.__tokenSets.push({key: k, value: v ? v.substring(0, 30) + '...' : v, time: Date.now()});
                        console.log('[DEBUG] localStorage.setItem("token", "' + (v ? v.substring(0, 30) + '...' : v) + '")');
                    }
                    _setItem(k, v);
                };
                window.__getToken = () => localStorage.getItem('token');
                window.__getUserInfo = () => localStorage.getItem('userInfo');
                console.log('[DEBUG] localStorage hook installed');
            }""")
            results["steps"].append("JS debug hooks installed")

            if "/login" in url:
                print("\n[STEP] Filling login form...")

                # Fill using el-input__inner
                inputs = page.query_selector_all('input.el-input__inner')
                print(f"  Found {len(inputs)} el-input__inner elements")

                if len(inputs) >= 2:
                    # Username
                    inputs[0].fill(USERNAME)
                    time.sleep(0.3)
                    # Password
                    inputs[1].fill(PASSWORD)
                    time.sleep(0.3)
                    log_test("3. Fill form", True, f"admin/****")
                    results["steps"].append("Form filled")

                    # Click login button
                    print("\n[STEP] Clicking login button...")
                    buttons = page.query_selector_all('button.el-button--primary')
                    print(f"  Found {len(buttons)} primary buttons")
                    for i, btn in enumerate(buttons):
                        txt = btn.text_content() or ""
                        if "登" in txt:
                            print(f"  Clicking button {i}: '{txt.strip()}'")
                            btn.click()
                            break

                    results["steps"].append("Login button clicked")

                    # Wait for login API response
                    print("\n[STEP] Waiting for login API...")
                    time.sleep(5)

                    # Check URL
                    url_after = page.url
                    print(f"\n  URL after login: {url_after}")
                    results["steps"].append(f"URL after login: {url_after}")

                    # Check token via our hook
                    token_sets = page.evaluate("window.__tokenSets || []")
                    print(f"\n  Token setItem calls: {len(token_sets)}")
                    for ts in token_sets:
                        print(f"    {ts}")

                    # Check localStorage directly
                    token = page.evaluate("localStorage.getItem('token')")
                    user_info = page.evaluate("localStorage.getItem('userInfo')")
                    print(f"  Token in localStorage: {token[:40] + '...' if token else 'NOT FOUND'}")
                    print(f"  UserInfo in localStorage: {user_info[:50] + '...' if user_info else 'NOT FOUND'}")

                    log_test("4. Token stored", token is not None, f"{'FOUND' if token else 'NOT FOUND'}")

                    # Check all API requests
                    auth_api = [r for r in captured_requests if "/api/auth" in r["url"]]
                    print(f"\n  Auth API requests: {len(auth_api)}")
                    for r in auth_api:
                        print(f"    - {r['method']} {r['url'].replace(BACKEND_URL, '')} -> {r['response_status']}")

                    login_succeeded = "/chat" in url_after and "/login" not in url_after
                    log_test("5. Login redirect", login_succeeded, f"URL: {url_after}")
                    results["steps"].append(f"Login: {'SUCCESS' if login_succeeded else 'FAILED'} - {url_after}")

                    if not login_succeeded:
                        # Analyze why
                        print("\n[DIAGNOSIS] Login failed. Analyzing...")

                        # Check for console error messages
                        error_logs = [l for l in console_logs if any(x in l.get("text","") for x in ["错误", "失败", "error", "Error", "fail"])]
                        if error_logs:
                            print("  Error logs:")
                            for l in error_logs:
                                print(f"    {l['text']}")
                        else:
                            print("  No error logs found")

                        # Check if there were any auth API requests
                        if not auth_api:
                            print("  -> No auth API was called at all!")
                            results["steps"].append("DIAGNOSIS: No auth API called")
                        else:
                            # Auth API was called - check the response
                            login_req = auth_api[0]
                            if login_req.get("response_status") == 200:
                                body = login_req.get("response_body", "")
                                print(f"  -> Auth API returned 200, but login didn't complete")
                                print(f"     Response body: {body[:200]}")

                                # Check if the body has success:true
                                if '"success":true' in body or '"success": true' in body:
                                    print("  -> Backend returned success:true")
                                    print("  -> Issue is in frontend response handling")
                                    results["steps"].append("DIAGNOSIS: Backend OK, frontend handling issue")
                                else:
                                    print("  -> Backend did NOT return success:true")
                                    results["steps"].append("DIAGNOSIS: Backend returned error")
                            else:
                                print(f"  -> Auth API returned {login_req.get('response_status')}")
                                results["steps"].append(f"DIAGNOSIS: Auth API returned {login_req.get('response_status')}")

                        # Check if Vue refs were set
                        vue_refs = page.evaluate("""() => {
                            // Try to find the Vue app instance
                            const app = document.querySelector('#app').__vue_app__;
                            if (app) {
                                return 'Vue app found';
                            }
                            return 'Vue app not found';
                        }""")
                        print(f"  Vue state: {vue_refs}")

                    else:
                        # Login succeeded
                        results["steps"].append("Login SUCCESS")

                        # Continue with chat flow
                        print("\n[STEP] Testing chat flow...")

                        # Try new chat
                        new_chat_found = False
                        for sel in ['button:has-text("新建对话")', 'button:has-text("新对话")', 'button']:
                            btns = page.query_selector_all(sel)
                            for btn in btns:
                                txt = btn.text_content() or ""
                                if "新建" in txt:
                                    btn.click()
                                    new_chat_found = True
                                    time.sleep(1)
                                    break
                            if new_chat_found:
                                break
                        log_test("6. Click 新建对话", new_chat_found, "Found" if new_chat_found else "Not found")
                        results["steps"].append(f"新建对话: {'FOUND' if new_chat_found else 'NOT FOUND'}")

                        if new_chat_found:
                            # Send message
                            msg_selectors = ['textarea.el-textarea__inner', 'textarea', 'input']
                            msg_filled = False
                            for sel in msg_selectors:
                                inputs = page.query_selector_all(sel)
                                for inp in inputs:
                                    bbox = inp.bounding_box()
                                    if bbox and bbox.get("width", 0) > 100:
                                        inp.fill("你好，请介绍一下你自己")
                                        msg_filled = True
                                        time.sleep(0.5)
                                        break
                                if msg_filled:
                                    break

                            log_test("7. Type message", msg_filled, "Done" if msg_filled else "Not found")

                            if msg_filled:
                                # Try to send
                                sent = False
                                for sel in ['button:has-text("发送")', 'button']:
                                    btns = page.query_selector_all(sel)
                                    for btn in btns:
                                        txt = btn.text_content() or ""
                                        if "发送" in txt:
                                            btn.click()
                                            sent = True
                                            break
                                    if sent:
                                        break
                                if not sent:
                                    page.keyboard.press("Enter")
                                    sent = True

                                log_test("8. Send message", sent, "Done")
                                time.sleep(8)

                                # Check chat API requests
                                chat_api = [r for r in captured_requests if "/api/chat" in r["url"]]
                                print(f"\n  Chat API requests: {len(chat_api)}")
                                for r in chat_api:
                                    print(f"    - {r['method']} {r['url'].replace(BACKEND_URL, '')} -> {r['response_status']}")
                                    print(f"      Auth: {'YES' if r.get('auth_header_found') else 'NO'}")
                                    if r.get("post_data"):
                                        pd = r["post_data"]
                                        if isinstance(pd, bytes):
                                            pd = pd.decode("utf-8", errors="replace")
                                        print(f"      Body: {pd[:200]}")

                                log_test("9. Chat API called", len(chat_api) > 0, f"{len(chat_api)} requests")
                                results["steps"].append(f"Chat API: {len(chat_api)} requests")

                                # Check if auth header was sent with chat API
                                chat_with_auth = [r for r in chat_api if r.get("auth_header_found")]
                                log_test("10. Auth header sent", len(chat_with_auth) > 0, f"{len(chat_with_auth)}/{len(chat_api)}")

            # Final
            final_url = page.url
            print(f"\n[FINAL] URL: {final_url}")
            results["steps"].append(f"Final URL: {final_url}")

            # Final storage check
            print("\n[FINAL] localStorage:")
            storage_keys = page.evaluate("Object.keys(localStorage)")
            for k in storage_keys:
                v = page.evaluate(f"localStorage.getItem('{k}')")
                if k == 'token':
                    print(f"  {k}: {v[:40]}..." if v and len(v) > 40 else f"  {k}: {v}")
                else:
                    print(f"  {k}: {v[:60]}..." if v and len(v) > 60 else f"  {k}: {v}")

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
    report.append("## Test Steps Performed")
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
    report.append("## Network Request Summary")
    report.append("")
    report.append(f"| Metric | Count |")
    report.append(f"|--------|-------|")
    report.append(f"| Total API requests | {len(api_requests)} |")
    report.append(f"| Auth API requests | {len(auth_api)} |")
    report.append(f"| Chat API requests | {len(chat_api)} |")
    report.append(f"| Requests with Authorization header | {len(auth_header_reqs)} |")
    report.append(f"| 401 Unauthorized responses | {len(unauthorized)} |")
    report.append("")

    # All API requests
    if api_requests:
        report.append("### All API Requests (Detail)")
        report.append("")
        for i, req in enumerate(api_requests, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"#### {i}. {req['method']} `{url_short}`")
            report.append(f"- **Status:** {req.get('response_status', 'N/A')}")
            report.append(f"- **Auth Header:** {'**YES**' if req.get('auth_header_found') else 'NO'}")
            if req.get("auth_header_value"):
                av = str(req["auth_header_value"])
                report.append(f"- **Authorization:** `{av[:60]}{'...' if len(av) > 60 else ''}`")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- **Request Body:** ```{pd[:800]}```")
            if req.get("response_body"):
                rb = req["response_body"]
                report.append(f"- **Response Body:** ```{rb[:800]}{'...' if len(rb) > 800 else ''}```")
            report.append("")

    # Auth API detail
    if auth_api:
        report.append("### Auth API Analysis")
        report.append("")
        for req in auth_api:
            report.append(f"**Endpoint:** `{req['url'].replace(BACKEND_URL, '')}`")
            report.append(f"- **Method:** {req['method']}")
            report.append(f"- **Status:** {req.get('response_status', 'N/A')}")
            report.append(f"- **Sent Auth Header:** {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- **Request:** ```{pd}```")
            if req.get("response_body"):
                report.append(f"- **Response:** ```{req['response_body']}```")
            report.append("")

    # Chat API detail
    if chat_api:
        report.append("### Chat API Analysis")
        report.append("")
        for req in chat_api:
            report.append(f"**Endpoint:** `{req['url'].replace(BACKEND_URL, '')}`")
            report.append(f"- **Method:** {req['method']}")
            report.append(f"- **Status:** {req.get('response_status', 'N/A')}")
            report.append(f"- **Sent Auth Header:** {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("auth_header_value"):
                av = str(req["auth_header_value"])
                report.append(f"- **Authorization:** `{av[:60]}{'...' if len(av) > 60 else ''}`")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- **Request Body:** ```{pd[:500]}```")
            if req.get("response_body"):
                report.append(f"- **Response Body:** ```{req['response_body'][:500]}```")
            report.append("")

    # 401s
    if unauthorized:
        report.append("## 401 Unauthorized Errors")
        for i, req in enumerate(unauthorized, 1):
            report.append(f"### {i}. 401: {req['method']} `{req['url'].replace(BACKEND_URL, '')}`")
            report.append(f"- **Has Auth Header:** {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("response_body"):
                report.append(f"- **Body:** ```{req['response_body'][:300]}```")
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
        for req in auth_header_reqs:
            av = str(req.get("auth_header_value", ""))
            if len(av) > 50:
                av = av[:47] + "..."
            report.append(f"- {req['method']} `{req['url'].replace(BACKEND_URL, '')}`: `{av}`")
    report.append("")
    if chat_api:
        report.append(f"**Chat API requests:** {len(chat_auth)}/{len(chat_api)} include Authorization header.")
    report.append("")

    # Verdict
    report.append("## Final Verdict")
    report.append("")
    passed = sum(1 for l in test_results if "PASS" in l)
    total = len(test_results)

    login_succeeded = any("Login redirect" in l and "PASS" in l for l in test_results)
    token_stored = any("Token stored" in l and "PASS" in l for l in test_results)
    chat_api_called = any("Chat API called" in l and "PASS" in l for l in test_results)
    auth_sent = len(chat_auth) > 0

    if login_succeeded and token_stored and auth_sent:
        report.append("**STATUS: PASS** - Authentication flow works end-to-end.")
        report.append(f"- Login redirected to /chat")
        report.append(f"- Token stored in localStorage")
        report.append(f"- Authorization headers sent with chat API requests")
    elif login_succeeded and token_stored:
        report.append("**STATUS: PARTIAL** - Login works but chat flow not tested.")
        report.append(f"- Login: SUCCESS")
        report.append(f"- Token storage: SUCCESS")
        if not auth_sent:
            report.append(f"- Chat API auth headers: NONE (chat not tested or no auth sent)")
    elif not login_succeeded and auth_api:
        # Login API was called but login didn't succeed
        login_req = auth_api[0]
        status = login_req.get("response_status", 0)
        body = login_req.get("response_body", "")

        report.append("**STATUS: FAIL** - Login API returned success but frontend did not process it.")
        report.append("")
        report.append("### Root Cause Analysis")
        report.append("")
        report.append(f"1. **API Response:** HTTP {status}")
        if body:
            report.append(f"2. **Response Body:** ```{body[:500]}```")

        # Check if it's a frontend handling issue
        if status == 200 and ("success" in body.lower() if body else False):
            report.append("")
            report.append("3. **Diagnosis:** Backend returns `success:true` but frontend `login()` returns `false`.")
            report.append("")
            report.append("### Possible Causes:")
            report.append("- The `login()` composable function is not matching the response structure")
            report.append("- Vue reactivity issue preventing token storage")
            report.append("- localStorage hook interfering with token storage")
            report.append("- The token/access_token key mismatch")
            report.append("- JS error during the success handler `s()` execution")

            # Check for JS errors
            js_errors = [l for l in console_logs if l.get("type") in ("error", "pageerror")]
            if js_errors:
                report.append("")
                report.append("### JavaScript Errors Detected:")
                for err in js_errors:
                    report.append(f"- `{err['text']}` (line {err.get('line', '?')})")

    elif not login_succeeded and not auth_api:
        report.append("**STATUS: FAIL** - Login form was not submitted (no auth API call).")
        report.append("### Possible Causes:")
        report.append("- Vue form validation failing before API call")
        report.append("- Button click not triggering form submit")
        report.append("- JavaScript error preventing form submission")
    else:
        report.append(f"**STATUS: PARTIAL** - {passed}/{total} tests passed.")

    report.append("")
    report.append(f"*Report generated: {datetime.now().isoformat()}*")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
