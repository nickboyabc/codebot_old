"""
Codebot Authentication Flow E2E Test - v3
Using Vue/Axios-aware selectors and element inspection.
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, Route, Request, Response

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
        "timestamp": time.time(),
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

    print(f"\n>>> [REQUEST] {request.method} {request.url}")
    if req_info["auth_header_found"]:
        val = str(req_info["auth_header_value"])
        print(f"    Auth: {val[:40]}..." if len(val) > 40 else f"    Auth: {val}")
    else:
        print(f"    Auth: NONE")
    if request.post_data:
        pd = request.post_data
        if isinstance(pd, bytes):
            pd = pd.decode("utf-8", errors="replace")
        print(f"    Body: {pd[:300]}")

    try:
        response = route.fetch()
        req_info["response_status"] = response.status
        req_info["response_headers"] = dict(response.headers)
        try:
            body = response.body()
            if body:
                decoded = body.decode("utf-8", errors="replace")
                req_info["response_body"] = decoded
                print(f"    -> Response {response.status}: {decoded[:400]}")
        except Exception as e:
            print(f"    -> Response {response.status}: (body error: {e})")
        captured_requests.append(req_info)
        route.continue_()
    except Exception as e:
        print(f"    -> Request failed: {e}")
        captured_requests.append(req_info)
        try:
            route.abort()
        except Exception:
            pass


def handle_console(msg):
    entry = {
        "type": msg.type,
        "text": msg.text,
        "url": msg.location.get("url", ""),
        "line": msg.location.get("lineNumber", ""),
    }
    console_logs.append(entry)
    print(f"[CONSOLE/{msg.type.upper()}] {msg.text}")


def handle_page_error(err):
    console_logs.append({"type": "pageerror", "text": str(err)})
    print(f"[PAGE ERROR] {err}")


def main():
    print("=" * 80)
    print("Codebot Auth Flow E2E Test - v3 (Vue-aware)")
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
            print("\n[STEP 1] Navigating...")
            resp = page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
            log_test("1. Navigate", resp.status == 200, f"HTTP {resp.status}")
            results["steps"].append(f"Navigate: HTTP {resp.status}")
            time.sleep(2)

            # Clear storage
            print("\n[STEP 2] Clearing storage...")
            page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            log_test("2. Clear storage", True, "Done")
            results["steps"].append("Clear storage")

            # Get current URL
            current_url = page.url
            print(f"\n[INFO] Current URL: {current_url}")

            if "/login" in current_url:
                print("\n[STEP 3] On login page - inspecting DOM...")

                # Inspect ALL inputs on the page
                all_inputs = page.query_selector_all("input")
                print(f"  Total input elements: {len(all_inputs)}")
                for i, inp in enumerate(all_inputs):
                    inp_type = inp.get_attribute("type") or "(none)"
                    inp_class = inp.get_attribute("class") or "(none)"
                    inp_placeholder = inp.get_attribute("placeholder") or "(none)"
                    inp_id = inp.get_attribute("id") or "(none)"
                    inp_name = inp.get_attribute("name") or "(none)"
                    # Check visibility
                    bbox = inp.bounding_box()
                    visible = bbox is not None and bbox.get("width", 0) > 0
                    print(f"  Input[{i}]: type={inp_type}, class={inp_class[:50]}, placeholder={inp_placeholder}, id={inp_id}, name={inp_name}, visible={visible}")
                    if bbox:
                        print(f"    BBox: x={bbox['x']:.0f}, y={bbox['y']:.0f}, w={bbox['width']:.0f}, h={bbox['height']:.0f}")

                # Inspect ALL buttons on the page
                all_buttons = page.query_selector_all("button")
                print(f"\n  Total button elements: {len(all_buttons)}")
                for i, btn in enumerate(all_buttons):
                    btn_text = btn.text_content() or ""
                    btn_class = btn.get_attribute("class") or "(none)"
                    btn_type = btn.get_attribute("type") or "(none)"
                    bbox = btn.bounding_box()
                    visible = bbox is not None and bbox.get("width", 0) > 0
                    print(f"  Button[{i}]: text='{btn_text.strip()[:30]}', class={btn_class[:50]}, type={btn_type}, visible={visible}")

                # Also check el-input components (Vue Element Plus)
                el_inputs = page.query_selector_all(".el-input__inner")
                print(f"\n  el-input inner inputs: {len(el_inputs)}")
                for i, inp in enumerate(el_inputs):
                    placeholder = inp.get_attribute("placeholder") or "(none)"
                    bbox = inp.bounding_box()
                    visible = bbox is not None and bbox.get("width", 0) > 0
                    print(f"  el-input[{i}]: placeholder='{placeholder}', visible={visible}")
                    if bbox:
                        print(f"    BBox: x={bbox['x']:.0f}, y={bbox['y']:.0f}, w={bbox['width']:.0f}, h={bbox['height']:.0f}")

                results["steps"].append(f"DOM inspection: {len(all_inputs)} inputs, {len(all_buttons)} buttons, {len(el_inputs)} el-inputs")

                # Try filling using el-input__inner (Element Plus inner input)
                print("\n[STEP 4] Filling login form using el-input selectors...")

                username_selectors = [
                    'input.el-input__inner[placeholder*="用户名"]',
                    'input.el-input__inner',
                    'input[placeholder*="用户名"]',
                    '.el-input__inner',
                ]

                username_filled = False
                for sel in username_selectors:
                    inputs = page.query_selector_all(sel)
                    for inp in inputs:
                        placeholder = inp.get_attribute("placeholder") or ""
                        bbox = inp.bounding_box()
                        if bbox and bbox.get("width", 0) > 0:
                            if "用户名" in placeholder or not username_filled:
                                print(f"  Filling username with: {sel} (placeholder='{placeholder}')")
                                inp.fill(USERNAME)
                                username_filled = True
                                time.sleep(0.5)
                                break
                    if username_filled:
                        break

                log_test("3. Fill username", username_filled, f"Found: {username_filled}")
                results["steps"].append(f"Fill username: {'SUCCESS' if username_filled else 'FAILED'}")

                # Fill password
                password_selectors = [
                    'input.el-input__inner[placeholder*="密码"]',
                    'input.el-input__inner[type="password"]',
                    'input[type="password"]',
                ]

                password_filled = False
                for sel in password_selectors:
                    inputs = page.query_selector_all(sel)
                    for inp in inputs:
                        bbox = inp.bounding_box()
                        if bbox and bbox.get("width", 0) > 0:
                            print(f"  Filling password with: {sel}")
                            inp.fill(PASSWORD)
                            password_filled = True
                            time.sleep(0.5)
                            break
                    if password_filled:
                        break

                log_test("4. Fill password", password_filled, f"Found: {password_filled}")
                results["steps"].append(f"Fill password: {'SUCCESS' if password_filled else 'FAILED'}")

                # Click login button
                print("\n[STEP 5] Clicking login button...")

                # Try to find login button
                login_btn_selectors = [
                    'button.el-button--primary',
                    'button.el-button--primary[type="button"]',
                    'button:has-text(" 登 錄 ")',
                    'button.login-btn',
                    'button:has-text("登")',
                    'button',
                ]

                login_clicked = False
                for sel in login_btn_selectors:
                    btns = page.query_selector_all(sel)
                    for btn in btns:
                        btn_text = btn.text_content() or ""
                        btn_class = btn.get_attribute("class") or ""
                        bbox = btn.bounding_box()
                        if bbox and bbox.get("width", 0) > 0 and bbox.get("height", 0) > 0:
                            if "登" in btn_text or "login" in btn_class.lower() or sel == "button.el-button--primary":
                                print(f"  Clicking button: {sel}, text='{btn_text.strip()[:20]}', class={btn_class[:40]}")
                                btn.click()
                                login_clicked = True
                                print("  Login button clicked!")
                                break
                    if login_clicked:
                        break

                if not login_clicked:
                    # Try pressing Enter on the last password input
                    print("  Trying Enter key on last input...")
                    last_input = page.query_selector_all('input')[-1] if page.query_selector_all('input') else None
                    if last_input:
                        last_input.press("Enter")
                        login_clicked = True

                log_test("5. Click login button", login_clicked, "Clicked" if login_clicked else "Not found")
                results["steps"].append(f"Click login: {'SUCCESS' if login_clicked else 'FAILED'}")

                # Wait for response
                print("\n[STEP 6] Waiting for login response...")
                time.sleep(5)

                # Check URL
                url_after = page.url
                print(f"\n  URL after login: {url_after}")

                # Count API requests made during login
                n_before = 0  # We captured everything, so look at all
                login_api = [r for r in captured_requests if "/api/auth" in r["url"]]
                print(f"  Auth API requests: {len(login_api)}")
                for r in login_api:
                    print(f"    - {r['method']} {r['url'].replace(BACKEND_URL, '')} -> {r['response_status']}")

                login_succeeded = "/chat" in url_after and "/login" not in url_after
                log_test("6. Login succeeded", login_succeeded, f"URL: {url_after}")
                results["steps"].append(f"Login result: {'SUCCESS' if login_succeeded else 'FAILED'} - {url_after}")

                if login_succeeded:
                    # Check token
                    token = page.evaluate("localStorage.getItem('token')")
                    if not token:
                        token = page.evaluate("sessionStorage.getItem('token')")
                    if not token:
                        token = page.evaluate("localStorage.getItem('access_token')")
                    log_test("7. Token stored", token is not None, f"{'FOUND' if token else 'NOT FOUND'}")
                    results["steps"].append(f"Token: {'FOUND' if token else 'NOT FOUND'}")

                    # Try new chat
                    print("\n[STEP 7] Looking for 新建对话...")
                    new_chat_found = False
                    for sel in ['button:has-text("新建对话")', 'button:has-text("新对话")', 'button']:
                        btns = page.query_selector_all(sel)
                        for btn in btns:
                            txt = btn.text_content() or ""
                            bbox = btn.bounding_box()
                            if bbox and bbox.get("width", 0) > 0 and "新建" in txt:
                                print(f"  Found: {sel}, text='{txt.strip()}'")
                                btn.click()
                                new_chat_found = True
                                time.sleep(1)
                                break
                        if new_chat_found:
                            break
                    log_test("8. Click 新建对话", new_chat_found, "Found" if new_chat_found else "Not found")
                    results["steps"].append(f"新建对话: {'FOUND' if new_chat_found else 'NOT FOUND'}")

                    if new_chat_found:
                        # Send message
                        print("\n[STEP 8] Sending message...")
                        msg_selectors = [
                            'textarea.el-textarea__inner',
                            'textarea',
                            'input.el-input__inner',
                            'input',
                        ]
                        msg_filled = False
                        for sel in msg_selectors:
                            inputs = page.query_selector_all(sel)
                            for inp in inputs:
                                bbox = inp.bounding_box()
                                if bbox and bbox.get("width", 0) > 100:
                                    print(f"  Filling: {sel}, bbox w={bbox['width']:.0f}")
                                    inp.fill("你好，请介绍一下你自己")
                                    msg_filled = True
                                    time.sleep(0.5)
                                    break
                            if msg_filled:
                                break

                        log_test("9. Type message", msg_filled, "Done" if msg_filled else "Not found")

                        if msg_filled:
                            # Try to send
                            send_selectors = ['button:has-text("发送")', 'button:has-text("Send")', 'button[type="button"]']
                            sent = False
                            for sel in send_selectors:
                                btns = page.query_selector_all(sel)
                                for btn in btns:
                                    txt = btn.text_content() or ""
                                    bbox = btn.bounding_box()
                                    if bbox and bbox.get("width", 0) > 0 and ("发送" in txt or "send" in txt.lower()):
                                        print(f"  Sending: {sel}")
                                        btn.click()
                                        sent = True
                                        break
                                if sent:
                                    break
                            if not sent:
                                page.keyboard.press("Enter")
                                sent = True

                            log_test("10. Send message", sent, "Done")
                            time.sleep(8)  # Wait for streaming response

                            # Count chat API requests
                            chat_api = [r for r in captured_requests if "/api/chat" in r["url"]]
                            print(f"\n  Chat API requests captured: {len(chat_api)}")
                            for r in chat_api:
                                print(f"    - {r['method']} {r['url'].replace(BACKEND_URL, '')} -> {r['response_status']}")
                                print(f"      Auth: {'YES' if r.get('auth_header_found') else 'NO'}")
                            results["steps"].append(f"Chat API requests: {len(chat_api)}")

                            # Check if streaming worked
                            if chat_api:
                                log_test("11. Chat API called", True, f"{len(chat_api)} requests")
                            else:
                                log_test("11. Chat API called", False, "No chat API requests")
                else:
                    # Login failed - diagnose
                    print("\n[DIAGNOSIS] Login failed - checking why...")

                    # Check console for error messages
                    error_logs = [l for l in console_logs if "error" in l.get("text", "").lower() or "失败" in l.get("text", "") or "错误" in l.get("text", "")]
                    if error_logs:
                        print("  Error console logs:")
                        for l in error_logs:
                            print(f"    {l['text']}")

                    # Check for any visible error messages on page
                    error_elements = page.query_selector_all("[class*='error'], .el-message--error, [data-testid='error']")
                    for el in error_elements:
                        txt = el.text_content()
                        if txt:
                            print(f"  Page error element: {txt[:100]}")

                    # Check localStorage
                    token_check = page.evaluate("localStorage.getItem('token')")
                    print(f"  Token in localStorage: {token_check if token_check else 'NOT FOUND'}")

                    # Check all auth API requests
                    auth_api = [r for r in captured_requests if "/api/auth" in r["url"]]
                    if auth_api:
                        print(f"  Auth API requests found: {len(auth_api)}")
                        for r in auth_api:
                            print(f"    - {r['method']} {r['url'].replace(BACKEND_URL, '')} -> {r['response_status']}")
                    else:
                        print("  NO auth API requests were made at all!")

            # Final
            final_url = page.url
            print(f"\n[FINAL] URL: {final_url}")
            results["steps"].append(f"Final URL: {final_url}")

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
    report.append("### All API Requests")
    report.append("")
    for i, req in enumerate(api_requests, 1):
        url_short = req["url"].replace(BACKEND_URL, "")
        report.append(f"#### {i}. {req['method']} `{url_short}`")
        report.append("")
        report.append(f"- **Response:** {req.get('response_status', 'N/A')}")
        report.append(f"- **Auth Header:** {'**YES**' if req.get('auth_header_found') else 'NO'}")
        if req.get("auth_header_value"):
            av = str(req["auth_header_value"])
            report.append(f"- **Auth Value:** `{av[:60]}{'...' if len(av) > 60 else ''}`")
        if req.get("post_data"):
            pd = req.get("post_data", "")
            if isinstance(pd, bytes):
                pd = pd.decode("utf-8", errors="replace")
            report.append(f"- **Request Body:** ```{pd[:1000]}```")
        if req.get("response_body"):
            rb = req["response_body"]
            report.append(f"- **Response Body:** ```{rb[:1000]}{'...' if len(rb) > 1000 else ''}```")
        report.append("")

    # Auth API detail
    if auth_api:
        report.append("### Auth API Detail")
        for i, req in enumerate(auth_api, 1):
            report.append(f"#### {i}. {req['method']} `{req['url'].replace(BACKEND_URL, '')}`")
            report.append(f"- Response: {req.get('response_status', 'N/A')}")
            report.append(f"- Has Auth Header: {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- Request: ```{pd}```")
            if req.get("response_body"):
                report.append(f"- Response: ```{req['response_body'][:500]}```")
            report.append("")

    # Chat API detail
    if chat_api:
        report.append("### Chat API Detail")
        for i, req in enumerate(chat_api, 1):
            report.append(f"#### {i}. {req['method']} `{req['url'].replace(BACKEND_URL, '')}`")
            report.append(f"- Response: {req.get('response_status', 'N/A')}")
            report.append(f"- Has Auth Header: {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- Request: ```{pd[:500]}```")
            if req.get("response_body"):
                report.append(f"- Response: ```{req['response_body'][:500]}```")
            report.append("")

    # 401s
    if unauthorized:
        report.append("## 401 Errors")
        for i, req in enumerate(unauthorized, 1):
            report.append(f"### {i}. 401: {req['method']} {req['url'].replace(BACKEND_URL, '')}")
            report.append(f"- Has Auth: {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("response_body"):
                report.append(f"- Body: ```{req['response_body'][:300]}```")
            report.append("")
    else:
        report.append("## 401 Errors: None captured")

    # Auth header analysis
    report.append("")
    report.append("## Authorization Header Analysis")
    report.append("")
    if auth_header_reqs:
        report.append(f"**{len(auth_header_reqs)}/{len(api_requests)} API requests** include Authorization header.")
        report.append("")
        for req in auth_header_reqs:
            av = str(req.get("auth_header_value", ""))
            if len(av) > 50:
                av = av[:47] + "..."
            report.append(f"- {req['method']} `{req['url'].replace(BACKEND_URL, '')}`: `{av}`")
    else:
        report.append(f"**0/{len(api_requests)} API requests** include Authorization header.")
        if len(api_requests) > 0:
            report.append("")
            report.append("**Conclusion:** Frontend is NOT sending Authorization headers with API requests.")
            report.append("")
            report.append("### Protected endpoints that need auth (but have no header):")
            for req in api_requests:
                report.append(f"- {req['method']} {req['url'].replace(BACKEND_URL, '')}")

    # Verdict
    report.append("")
    report.append("## Final Verdict")
    passed = sum(1 for l in test_results if "PASS" in l)
    total = len(test_results)
    if passed == total and auth_header_reqs:
        report.append("**STATUS: PASS** - All tests passed, auth headers sent correctly.")
    elif len(unauthorized) > 0:
        report.append("**STATUS: FAIL** - 401 errors detected.")
    elif len(auth_api) == 0:
        report.append("**STATUS: FAIL** - Login API was never called.")
    else:
        report.append(f"**STATUS: PARTIAL** - {passed}/{total} passed.")

    report.append("")
    report.append(f"*Report generated: {datetime.now().isoformat()}*")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
