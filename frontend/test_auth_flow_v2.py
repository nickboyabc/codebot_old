"""
Codebot Authentication Flow E2E Test - v2
Enhanced with detailed login flow network capture and debugging.
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, Route, Request, Response

# Configuration
BACKEND_URL = "http://127.0.0.1:8080"
USERNAME = "admin"
PASSWORD = "admin123"
REPORT_PATH = "E:/阿里agent研究/笔记/codebot-auth-dev/docs/browser-test-report.md"

# Storage for captured data
captured_requests = []
console_logs = []
test_results = []


def log_test(name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    test_results.append(f"| {name} | {status} | {details} |")
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {details}")


def handle_request(route: Route, request: Request):
    """Intercept and log all network requests with full details."""
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

    # Check Authorization header
    for key in request.headers:
        if key.lower() == "authorization":
            req_info["auth_header_found"] = True
            req_info["auth_header_value"] = request.headers[key]
            break

    # Log ALL requests to console for visibility
    is_api = "/api/" in request.url
    print(f"\n>>> [REQUEST] {request.method} {request.url}")
    if req_info["auth_header_found"]:
        val = str(req_info["auth_header_value"])
        print(f"    Auth: {val[:30]}..." if len(val) > 30 else f"    Auth: {val}")
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
        req_info["response_headers"] = dict(response.headers)

        # Get response body
        try:
            body = response.body()
            if body:
                decoded = body.decode("utf-8", errors="replace")
                req_info["response_body"] = decoded
                print(f"    -> Response {response.status}: {decoded[:300]}")
        except Exception as e:
            print(f"    -> Response {response.status}: (could not read body: {e})")

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
    """Capture console logs."""
    msg_type = msg.type
    text = msg.text
    location = msg.location
    entry = {
        "type": msg_type,
        "text": text,
        "url": location.get("url", ""),
        "line": location.get("lineNumber", ""),
    }
    console_logs.append(entry)
    print(f"[CONSOLE/{msg_type.upper()}] {text}")


def handle_page_error(err):
    """Capture page errors."""
    entry = {
        "type": "pageerror",
        "text": str(err),
    }
    console_logs.append(entry)
    print(f"[PAGE ERROR] {err}")


def handle_response(response: Response):
    """Also capture responses through the event listener for redundancy."""
    pass  # Already captured via route interception


def main():
    print("=" * 80)
    print("Codebot Authentication Flow E2E Test - v2 (Enhanced)")
    print("=" * 80)
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Target: {BACKEND_URL}")
    print(f"Credentials: {USERNAME}/{'*' * len(PASSWORD)}")
    print("=" * 80)

    captured_requests.clear()
    console_logs.clear()
    test_results.clear()

    results = {
        "test_start": datetime.now().isoformat(),
        "test_end": None,
        "steps": [],
    }

    with sync_playwright() as p:
        print("\n[STEP] Launching Chromium browser (fresh profile)...")
        context = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-cache",
                "--disable-application-cache",
                "--disable-offline-load-stale-cache",
                "--window-size=1920,1080",
            ],
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        # Route ALL requests for capture (before navigation)
        page.route("**", handle_request)
        page.on("console", handle_console)
        page.on("pageerror", handle_page_error)
        page.on("response", handle_response)

        try:
            # Step 1: Navigate
            print(f"\n[STEP 1] Navigating to {BACKEND_URL}...")
            response = page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
            log_test("1. Navigate to application", response.status == 200, f"HTTP {response.status}")
            results["steps"].append(f"Navigate to {BACKEND_URL} - {response.status}")

            time.sleep(1)

            # Step 2: Clear storage
            print("\n[STEP 2] Clearing browser storage...")
            page.evaluate("""() => {
                localStorage.clear();
                sessionStorage.clear();
                console.log('[TEST] Storage cleared');
            }""")
            log_test("2. Clear browser storage", True, "localStorage/sessionStorage cleared")
            results["steps"].append("Clear storage")

            # Step 3: Wait for app to mount
            print("\n[STEP 3] Waiting for app to load...")
            time.sleep(2)
            title = page.title()
            log_test("3. Page loaded", True, f"Title: {title}")
            results["steps"].append(f"Page loaded: {title}")

            # Step 4: Check current URL (are we already logged in?)
            url_before = page.url
            print(f"\n[INFO] Current URL: {url_before}")
            results["steps"].append(f"URL before login: {url_before}")

            if "/login" not in url_before and "/chat" in url_before:
                print("[INFO] Already on chat page - may be logged in already")
                log_test("4. Already logged in", True, f"URL: {url_before}")
            else:
                log_test("4. Need to login", True, f"URL: {url_before}")

            # Step 5: Perform login
            print(f"\n[STEP 5] Performing login...")

            # Clear the request log so we can see what login generates
            requests_before_login = len(captured_requests)
            console_logs_before = len(console_logs)

            # Find username input
            username_el = None
            for sel in ['input[type="text"]', 'input[placeholder*="用户名"]', 'input[placeholder*="账号"]']:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0:
                        username_el = el
                        print(f"  Username input: {sel}")
                        break
                except Exception:
                    pass

            # Find password input
            password_el = None
            for sel in ['input[type="password"]', 'input[placeholder*="密码"]']:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0:
                        password_el = el
                        print(f"  Password input: {sel}")
                        break
                except Exception:
                    pass

            # Find login button
            login_btn = None
            for sel in ['button[type="submit"]', 'button:has-text("登录")', 'button']:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0 and "button" in (el.get_attribute("type") or "").lower() or "button" in sel:
                        # Check if it's a submit button or has login text
                        txt = el.text_content()
                        if txt and "登录" in txt:
                            login_btn = el
                            print(f"  Login button: {sel} text='{txt}'")
                            break
                except Exception:
                    pass

            if not username_el or not password_el:
                print("[ERROR] Could not find login form!")
                log_test("5. Find login form", False, "Form elements not found")
            else:
                # Fill the form
                print(f"  Filling username: {USERNAME}")
                username_el.fill(USERNAME)
                time.sleep(0.3)

                print(f"  Filling password: {'*' * len(PASSWORD)}")
                password_el.fill(PASSWORD)
                time.sleep(0.3)

                # Count requests before clicking
                n_before = len(captured_requests)
                n_api_before = len([r for r in captured_requests if "/api/" in r["url"]])

                # Click login button or press Enter
                if login_btn:
                    print("  Clicking login button...")
                    login_btn.click()
                else:
                    print("  Pressing Enter...")
                    password_el.press("Enter")

                # Wait for navigation or API response
                print("  Waiting for login response...")
                time.sleep(5)

                # Check URL after login
                url_after = page.url
                print(f"\n  URL after login attempt: {url_after}")

                # Count requests made during login
                login_requests = captured_requests[n_before:]
                login_api_requests = [r for r in login_requests if "/api/" in r["url"]]

                print(f"\n  Requests during login: {len(login_requests)}")
                print(f"  API requests during login: {len(login_api_requests)}")
                for r in login_api_requests:
                    url_short = r["url"].replace(BACKEND_URL, "")
                    print(f"    - {r['method']} {url_short} -> {r['response_status']}")
                    print(f"      Auth: {'YES' if r.get('auth_header_found') else 'NO'}")
                    if r.get("response_body"):
                        print(f"      Body: {r['response_body'][:200]}")

                results["steps"].append(f"Login API requests: {len(login_api_requests)}")

                # Determine login success
                login_succeeded = "/chat" in url_after and "/login" not in url_after
                log_test("5. Login successful", login_succeeded, f"URL: {url_after}")

                if not login_succeeded:
                    # Let's check what happened
                    # Check for any error messages on the page
                    error_selectors = [
                        '[data-testid="error"]',
                        '.ant-message-error',
                        '.el-message--error',
                        '[class*="error"]',
                        'text=/登录失败|用户名|密码错误/i',
                    ]
                    for sel in error_selectors:
                        try:
                            err_el = page.locator(sel).first
                            if err_el.count() > 0:
                                err_text = err_el.text_content()
                                print(f"  Found error element ({sel}): {err_text}")
                                break
                        except Exception:
                            pass

                    # Check localStorage for token
                    token = page.evaluate("localStorage.getItem('token')")
                    print(f"  Token in localStorage: {'FOUND' if token else 'NOT FOUND'}")
                    if token:
                        print(f"  Token: {token[:30]}...")

                    # Check if we need to wait longer for redirect
                    if "/login" in url_after:
                        print("\n  Login appears to have failed. Staying on login page.")
                        results["steps"].append(f"Login FAILED - URL: {url_after}")
                else:
                    log_test("6. Redirected to /chat", True, url_after)
                    results["steps"].append(f"Login SUCCESS - URL: {url_after}")

                    # Step 7: Check token
                    print("\n[STEP 7] Checking for auth token...")
                    token = page.evaluate("localStorage.getItem('token')")
                    if not token:
                        token = page.evaluate("sessionStorage.getItem('token')")
                    if not token:
                        token = page.evaluate("localStorage.getItem('auth_token')")
                    if not token:
                        token = page.evaluate("localStorage.getItem('access_token')")

                    log_test("7. Auth token stored", token is not None, f"{'FOUND' if token else 'NOT FOUND'}")
                    if token:
                        print(f"  Token: {token[:40]}...")
                        results["steps"].append(f"Token found: {token[:40]}...")
                    else:
                        results["steps"].append("Token NOT found")

                    # Step 8: Try to click "新建对话"
                    print("\n[STEP 8] Looking for '新建对话' button...")
                    new_chat_found = False
                    new_chat_selectors = [
                        'button:has-text("新建对话")',
                        'button:has-text("新对话")',
                        'button:has-text("对话")',
                        '[data-testid="new-chat"]',
                    ]
                    for sel in new_chat_selectors:
                        try:
                            el = page.locator(sel).first
                            if el.count() > 0:
                                print(f"  Found: {sel}")
                                el.click()
                                new_chat_found = True
                                time.sleep(1)
                                break
                        except Exception:
                            pass

                    log_test("8. Click '新建对话'", new_chat_found, "Found" if new_chat_found else "Not found")
                    results["steps"].append(f"新建对话 button: {'FOUND' if new_chat_found else 'NOT FOUND'}")

                    # Step 9: Send a test message
                    if new_chat_found:
                        print("\n[STEP 9] Looking for message input...")
                        msg_selectors = [
                            'textarea',
                            'input[type="text"]',
                            '[contenteditable="true"]',
                            '[data-testid="message-input"]',
                        ]
                        msg_input = None
                        for sel in msg_selectors:
                            try:
                                el = page.locator(sel).first
                                if el.count() > 0:
                                    msg_input = el
                                    print(f"  Found: {sel}")
                                    break
                            except Exception:
                                pass

                        if msg_input:
                            test_msg = "你好，请介绍一下你自己"
                            msg_input.fill(test_msg)
                            time.sleep(0.5)
                            log_test("9. Type message", True, test_msg)

                            # Try to send
                            send_found = False
                            send_selectors = [
                                'button:has-text("发送")',
                                'button:has-text("Send")',
                                '[data-testid="send"]',
                                'button[type="submit"]',
                            ]
                            for sel in send_selectors:
                                try:
                                    el = page.locator(sel).first
                                    if el.count() > 0:
                                        el.click()
                                        send_found = True
                                        print(f"  Clicked send: {sel}")
                                        break
                                except Exception:
                                    pass

                            if not send_found:
                                msg_input.press("Enter")
                                send_found = True
                                print("  Pressed Enter to send")

                            log_test("10. Send message", send_found, "Sent" if send_found else "Not sent")
                            time.sleep(5)  # Wait for streaming response

                            # Capture any new requests
                            print(f"\n  Total requests captured so far: {len(captured_requests)}")
                        else:
                            log_test("9. Type message", False, "Message input not found")
                            log_test("10. Send message", False, "No input")
                    else:
                        log_test("9. Type message", False, "Cannot - no 新建对话")
                        log_test("10. Send message", False, "Cannot - no 新建对话")

            # Final URL
            final_url = page.url
            print(f"\n[FINAL] Current URL: {final_url}")
            results["steps"].append(f"Final URL: {final_url}")

            # Final storage check
            print("\n[FINAL] Browser storage state:")
            storage = page.evaluate("""() => {
                const result = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    result[key] = localStorage.getItem(key);
                }
                return result;
            }""")
            for k, v in storage.items():
                if isinstance(v, str) and len(v) > 50:
                    print(f"  {k}: {v[:30]}...")
                else:
                    print(f"  {k}: {v}")
            results["steps"].append(f"Storage keys: {list(storage.keys())}")

        except Exception as e:
            print(f"\n[ERROR] Test exception: {e}")
            import traceback
            traceback.print_exc()
            log_test("Critical test step", False, str(e))
            results["steps"].append(f"ERROR: {e}")

        # Close
        context.close()
        results["test_end"] = datetime.now().isoformat()

    # Generate report
    print("\n" + "=" * 80)
    print("GENERATING REPORT")
    print("=" * 80)
    generate_report(results)


def generate_report(results: dict):
    """Generate the detailed test report."""

    # Analyze captured requests
    api_requests = [r for r in captured_requests if "/api/" in r["url"]]
    auth_api_requests = [r for r in api_requests if "/api/auth" in r["url"]]
    chat_api_requests = [r for r in api_requests if "/api/chat" in r["url"]]
    unauthorized = [r for r in api_requests if r["response_status"] == 401]
    auth_header_requests = [r for r in api_requests if r.get("auth_header_found", False)]

    # Build report
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
            msg_type = log.get("type", "unknown")
            text = log.get("text", "")
            url = log.get("url", "")
            line = log.get("line", "")
            location = f" ({url}:{line})" if url else ""
            report.append(f"[{msg_type.upper()}{location}] {text}")
        report.append("```")
    else:
        report.append("No console logs captured.")
    report.append("")

    report.append("## Network Request Analysis")
    report.append("")
    report.append(f"| Metric | Count |")
    report.append(f"|--------|-------|")
    report.append(f"| Total API requests | {len(api_requests)} |")
    report.append(f"| Auth API requests | {len(auth_api_requests)} |")
    report.append(f"| Chat API requests | {len(chat_api_requests)} |")
    report.append(f"| Requests with Auth header | {len(auth_header_requests)} |")
    report.append(f"| 401 Unauthorized responses | {len(unauthorized)} |")
    report.append("")

    report.append("### All API Requests (Full Detail)")
    report.append("")
    for i, req in enumerate(api_requests, 1):
        url_short = req["url"].replace(BACKEND_URL, "")
        report.append(f"#### {i}. {req['method']} `{url_short}`")
        report.append("")
        report.append(f"- **Full URL:** `{req['url']}`")
        report.append(f"- **Response Status:** {req.get('response_status', 'N/A')}")
        report.append(f"- **Has Authorization Header:** {'**YES**' if req.get('auth_header_found') else 'NO'}")
        if req.get("auth_header_value"):
            auth_val = str(req["auth_header_value"])
            if len(auth_val) > 60:
                auth_val = auth_val[:57] + "..."
            report.append(f"- **Authorization Value:** `{auth_val}`")
        report.append(f"- **Resource Type:** {req.get('resource_type', 'N/A')}")
        if req.get("post_data"):
            pd = req.get("post_data", "")
            if isinstance(pd, bytes):
                pd = pd.decode("utf-8", errors="replace")
            report.append(f"- **Request Body:** ```\n{pd[:1000]}\n```")
        if req.get("response_body"):
            body = req["response_body"]
            if len(body) > 500:
                body = body[:497] + "..."
            report.append(f"- **Response Body:** ```\n{body}\n```")
        report.append("")

    # 401 Errors
    if unauthorized:
        report.append("## 401 Unauthorized Errors - DETAILED")
        report.append("")
        for i, req in enumerate(unauthorized, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"### {i}. 401 Error on {req['method']} `{url_short}`")
            report.append("")
            report.append(f"- **Full URL:** `{req['url']}`")
            report.append(f"- **Has Authorization Header:** {'YES' if req.get('auth_header_found') else 'NO'}")
            report.append(f"- **Authorization Value:** `{req.get('auth_header_value', 'N/A')}`")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- **Request Body:** ```{pd[:500]}```")
            if req.get("response_body"):
                report.append(f"- **Response Body:** ```{req['response_body'][:500]}```")
            report.append("")
    else:
        report.append("## 401 Unauthorized Errors")
        report.append("No 401 errors were captured during the test.")
        report.append("")

    # Authorization header analysis
    report.append("## Authorization Header Analysis")
    report.append("")
    if auth_header_requests:
        report.append(f"**{len(auth_header_requests)} out of {len(api_requests)} API requests** included an Authorization header.")
        report.append("")
        report.append("| # | Method | URL | Auth Header Value |")
        report.append("|---|--------|-----|-------------------|")
        for i, req in enumerate(auth_header_requests, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            if len(url_short) > 50:
                url_short = url_short[:47] + "..."
            auth_val = str(req.get("auth_header_value", ""))
            if len(auth_val) > 40:
                auth_val = auth_val[:37] + "..."
            report.append(f"| {i} | {req['method']} | `{url_short}` | `{auth_val}` |")
        report.append("")
        report.append("**Conclusion:** The frontend IS sending Authorization headers with API requests.")
    else:
        report.append(f"**0 out of {len(api_requests)} API requests** included an Authorization header.")
        report.append("")
        if len(api_requests) > 0:
            report.append("**Conclusion:** The frontend is NOT sending Authorization headers. Protected API endpoints would fail with 401.")
            report.append("")
            report.append("### Requests That Need Auth (but have none):")
            for req in api_requests:
                url_short = req["url"].replace(BACKEND_URL, "")
                report.append(f"- {req['method']} `{url_short}` -> {req.get('response_status', 'N/A')}")
        else:
            report.append("**Conclusion:** No API requests were captured. Login may not have triggered any API calls.")

    # Other network requests
    other = [r for r in captured_requests if "/api/" not in r["url"]]
    if other:
        report.append("")
        report.append("## Static Asset Requests")
        report.append("")
        report.append("| # | Method | URL | Status |")
        report.append("|---|--------|-----|--------|")
        for i, req in enumerate(other, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            if len(url_short) > 70:
                url_short = url_short[:67] + "..."
            report.append(f"| {i} | {req['method']} | `{url_short}` | {req.get('response_status', 'N/A')} |")

    # Final verdict
    report.append("")
    report.append("## Final Verdict")
    report.append("")

    passed_count = sum(1 for l in test_results if "PASS" in l)
    total_count = len(test_results)
    auth_header_count = len(auth_header_requests)
    auth_needed_but_missing = len([r for r in api_requests if r["response_status"] in (401,)])

    if passed_count == total_count and auth_header_count > 0 and auth_needed_but_missing == 0:
        report.append("**STATUS: PASS** - Authentication flow is working correctly.")
        report.append(f"- All {passed_count}/{total_count} test steps passed.")
        report.append(f"- {auth_header_count} API requests include Authorization headers.")
        report.append("- No 401 errors detected.")
    elif auth_needed_but_missing > 0:
        report.append("**STATUS: FAIL** - Authentication failing with 401 errors.")
        report.append(f"- {auth_needed_but_missing} API requests returned 401 Unauthorized.")
        report.append(f"- API requests with auth headers: {auth_header_count}/{len(api_requests)}")
        report.append("")
        report.append("### Root Cause Analysis:")
        report.append("1. The login form submitted but no token was stored, OR")
        report.append("2. A token exists but is not being sent with API requests, OR")
        report.append("3. The backend token validation is failing")
    elif auth_header_count == 0 and len(api_requests) > 0:
        report.append("**STATUS: FAIL** - No Authorization headers sent with API requests.")
        report.append(f"- {len(api_requests)} API requests made without auth headers.")
        report.append("- All would likely return 401 from backend.")
        report.append("")
        report.append("### Root Cause: Axios/fetch interceptor missing or not working.")
    elif passed_count < total_count:
        report.append(f"**STATUS: PARTIAL** - {passed_count}/{total_count} test steps passed.")
        report.append(f"- Auth headers sent: {auth_header_count}/{len(api_requests)}")
        report.append(f"- 401 errors: {auth_needed_but_missing}")
    else:
        report.append("**STATUS: INCONCLUSIVE**")

    report.append("")
    report.append("---")
    report.append(f"*Report generated: {datetime.now().isoformat()}*")

    report_content = "\n".join(report)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\nReport saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
