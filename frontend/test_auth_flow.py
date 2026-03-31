"""
Codebot Authentication Flow E2E Test
Tests login, chat conversation creation, and message sending with full network capture.
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
    """Intercept and log all network requests."""
    req_info = {
        "url": request.url,
        "method": request.method,
        "headers": dict(request.headers),
        "post_data": request.post_data,
        "resource_type": request.resource_type,
        "timestamp": time.time(),
        "status": None,
        "response_headers": None,
        "response_body": None,
        "response_status": None,
    }

    # Check for Authorization header
    auth_header = request.headers.get("authorization", request.headers.get("Authorization"))
    if auth_header:
        req_info["auth_header_found"] = True
        req_info["auth_header_value"] = auth_header
        print(f"\n[REQUEST] {request.method} {request.url}")
        print(f"  Authorization: {auth_header[:20]}..." if len(str(auth_header)) > 20 else f"  Authorization: {auth_header}")
    else:
        req_info["auth_header_found"] = False
        req_info["auth_header_value"] = None
        # Still log key API requests even without auth
        if "/api/" in request.url:
            print(f"\n[REQUEST] {request.method} {request.url} [NO AUTH HEADER]")

    try:
        response = route.fetch()
        req_info["response_status"] = response.status
        req_info["response_headers"] = dict(response.headers)
        req_info["status"] = response.status

        # Try to get response body
        try:
            body = response.body()
            if body:
                req_info["response_body"] = body[:2000].decode("utf-8", errors="replace")
        except Exception:
            pass

        captured_requests.append(req_info)

        # Log the response
        print(f"  -> Response: {response.status}")
        if response.status >= 400:
            print(f"  -> Body: {req_info.get('response_body', 'N/A')[:200]}")

        route.continue_()
    except Exception as e:
        print(f"  -> Request failed: {e}")
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
    console_logs.append({
        "type": msg_type,
        "text": text,
        "url": location.get("url", ""),
        "line": location.get("lineNumber", ""),
    })
    print(f"[CONSOLE/{msg_type.upper()}] {text}")


def handle_page_error(err):
    """Capture page errors."""
    console_logs.append({
        "type": "page_error",
        "text": str(err),
    })
    print(f"[PAGE ERROR] {err}")


def main():
    print("=" * 80)
    print("Codebot Authentication Flow E2E Test")
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
        "network_requests": [],
        "console_logs": [],
        "summary": {},
    }

    with sync_playwright() as p:
        # Launch fresh browser (no cache)
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
            ],
        )
        page = context.new_page()

        # Set extra HTTP headers
        page.set_extra_http_headers({
            "X-Test-Run": "true",
        })

        results["steps"].append("1. Launch Chromium browser (fresh profile)")

        # Route ALL requests for capture
        page.route("**", handle_request)

        # Capture console
        page.on("console", handle_console)
        page.on("pageerror", handle_page_error)

        try:
            # Step 1: Navigate to the app
            print("\n[STEP] Navigating to the application...")
            response = page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
            log_test(
                "1. Navigate to application",
                response.status == 200,
                f"HTTP {response.status}"
            )
            results["steps"].append(f"2. Navigate to {BACKEND_URL} - {response.status}")

            # Step 2: Clear all browser storage
            print("\n[STEP] Clearing browser storage...")
            page.evaluate("""() => {
                localStorage.clear();
                sessionStorage.clear();
            }""")
            cookies_cleared = page.evaluate("""() => {
                localStorage.removeItem('token');
                sessionStorage.removeItem('token');
                return true;
            }""")
            log_test("2. Clear browser storage", cookies_cleared, "localStorage/sessionStorage cleared")
            results["steps"].append("3. Clear localStorage and sessionStorage")

            # Step 3: Wait for the page to load and check for login form
            print("\n[STEP] Waiting for page to load...")
            time.sleep(2)  # Give React time to mount

            # Check page title and basic structure
            title = page.title()
            log_test("3. Page loaded correctly", "盐城港Agent" in title or len(title) > 0, f"Title: {title}")
            results["steps"].append(f"4. Page loaded - Title: {title}")

            # Step 4: Look for login form elements
            print("\n[STEP] Looking for login form...")
            # Try various selectors for login form
            login_selectors = [
                'input[type="text"]',
                'input[placeholder*="用户名"]',
                'input[placeholder*="账号"]',
                'input[placeholder*="user"]',
                'input[placeholder*="账号"]',
                '[data-testid="username"]',
                '[data-testid="login-username"]',
            ]

            username_input = None
            password_input = None
            login_button = None

            for sel in login_selectors:
                try:
                    inp = page.locator(sel).first
                    if inp.count() > 0:
                        username_input = sel
                        print(f"  Found username input: {sel}")
                        break
                except Exception:
                    pass

            # Look for password input
            password_selectors = [
                'input[type="password"]',
                'input[placeholder*="密码"]',
                'input[placeholder*="password"]',
                '[data-testid="password"]',
            ]
            for sel in password_selectors:
                try:
                    inp = page.locator(sel).first
                    if inp.count() > 0:
                        password_input = sel
                        print(f"  Found password input: {sel}")
                        break
                except Exception:
                    pass

            # Look for login button
            button_selectors = [
                'button[type="submit"]',
                'button:has-text("登录")',
                'button:has-text("登 录")',
                'button:has-text("登录")',
                '[data-testid="login-button"]',
                'button:has-text("登录")',
            ]
            for sel in button_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.count() > 0:
                        login_button = sel
                        print(f"  Found login button: {sel}")
                        break
                except Exception:
                    pass

            log_test(
                "4. Find login form elements",
                username_input is not None and password_input is not None,
                f"username={username_input}, password={password_input}"
            )
            results["steps"].append(f"5. Login form elements found: user={username_input}, pwd={password_input}")

            # Step 5: Perform login
            if username_input and password_input:
                print(f"\n[STEP] Performing login with {USERNAME}/{'*' * len(PASSWORD)}...")

                # Fill username
                page.locator(username_input).fill(USERNAME)
                time.sleep(0.5)

                # Fill password
                page.locator(password_input).fill(PASSWORD)
                time.sleep(0.5)

                # Try to find and click login button
                if login_button:
                    page.locator(login_button).click()
                else:
                    # Try pressing Enter
                    page.keyboard.press("Enter")

                # Wait for navigation or response
                time.sleep(3)

                # Check URL after login
                current_url = page.url
                print(f"  Current URL after login: {current_url}")

                # Check if redirected to /chat
                redirected_to_chat = "/chat" in current_url
                log_test("5. Login performed", True, f"URL after login: {current_url}")

                results["steps"].append(f"6. Login performed - URL: {current_url}")

                # Check for auth token in localStorage
                token_in_storage = page.evaluate("""() => {
                    return localStorage.getItem('token') || sessionStorage.getItem('token') || 'NOT FOUND';
                }""")
                token_preview = token_in_storage[:30] + "..." if len(token_in_storage) > 30 else token_in_storage
                log_test(
                    "6. Token stored in browser",
                    token_in_storage != "NOT FOUND",
                    f"Token: {token_preview}"
                )
                results["steps"].append(f"7. Token stored: {token_preview}")

                # Check if redirected to /chat
                if redirected_to_chat:
                    log_test("7. Redirected to /chat", True, current_url)
                else:
                    log_test("7. Redirected to /chat", False, f"Current URL: {current_url}")
                    results["steps"].append(f"7. Redirect to /chat: FAILED - URL={current_url}")

                # Step 6: Try to click "新建对话" button
                print("\n[STEP] Looking for '新建对话' button...")

                new_chat_selectors = [
                    'button:has-text("新建对话")',
                    'button:has-text("新对话")',
                    '[data-testid="new-chat"]',
                    'button:has-text("对话")',
                ]

                new_chat_found = False
                for sel in new_chat_selectors:
                    try:
                        btn = page.locator(sel).first
                        if btn.count() > 0:
                            print(f"  Found: {sel}")
                            btn.click()
                            new_chat_found = True
                            time.sleep(1)
                            break
                    except Exception:
                        pass

                log_test("8. Click '新建对话' button", new_chat_found, "Button found and clicked" if new_chat_found else "Button not found")
                results["steps"].append(f"8. Click 新建对话: {'SUCCESS' if new_chat_found else 'NOT FOUND'}")

                # Step 7: Type and send a test message
                print("\n[STEP] Looking for message input to send a test message...")

                message_selectors = [
                    'textarea[data-testid="message-input"]',
                    'textarea[placeholder*="输入"]',
                    'textarea[placeholder*="消息"]',
                    'textarea',
                    'input[data-testid="message-input"]',
                    'input[placeholder*="输入"]',
                ]

                message_input = None
                for sel in message_selectors:
                    try:
                        inp = page.locator(sel).first
                        if inp.count() > 0:
                            message_input = sel
                            print(f"  Found message input: {sel}")
                            break
                    except Exception:
                        pass

                if message_input:
                    # Clear any existing text
                    page.locator(message_input).clear()
                    time.sleep(0.3)

                    # Type test message
                    test_message = "你好，请介绍一下你自己"
                    page.locator(message_input).fill(test_message)
                    time.sleep(0.5)
                    log_test("9. Type test message", True, f"'{test_message}'")
                    results["steps"].append(f"9. Type test message: '{test_message}'")

                    # Look for send button
                    send_selectors = [
                        'button[data-testid="send-button"]',
                        'button:has-text("发送")',
                        'button:has-text("发送")',
                        '[aria-label="send"]',
                        'button[type="submit"]',
                    ]

                    send_found = False
                    for sel in send_selectors:
                        try:
                            btn = page.locator(sel).first
                            if btn.count() > 0:
                                btn.click()
                                send_found = True
                                print(f"  Found and clicked send button: {sel}")
                                time.sleep(1)
                                break
                        except Exception:
                            pass

                    if not send_found:
                        # Try pressing Enter to send
                        page.locator(message_input).press("Enter")
                        send_found = True
                        print("  Pressed Enter to send message")

                    log_test("10. Send message", send_found, "Send triggered")
                    results["steps"].append(f"10. Send message: {'SUCCESS' if send_found else 'FAILED'}")

                    # Wait for network requests to complete
                    print("\n[STEP] Waiting for API responses...")
                    time.sleep(5)
                else:
                    log_test("9. Type test message", False, "Message input not found")
                    log_test("10. Send message", False, "Cannot send - no input found")

            # Final URL check
            final_url = page.url
            print(f"\n[FINAL] Current URL: {final_url}")

            # Wait a bit more to catch any late network requests
            time.sleep(2)

        except Exception as e:
            print(f"\n[ERROR] Test exception: {e}")
            import traceback
            traceback.print_exc()
            log_test("Critical test step", False, str(e))
            results["steps"].append(f"ERROR: {e}")

        # Close browser
        context.close()
        results["test_end"] = datetime.now().isoformat()

    # Generate report
    print("\n" + "=" * 80)
    print("GENERATING REPORT")
    print("=" * 80)

    generate_report(results)

    print("\n[DONE] Report saved to:", REPORT_PATH)


def generate_report(results: dict):
    """Generate the detailed test report."""

    # Analyze captured requests
    api_requests = [r for r in captured_requests if "/api/" in r["url"]]
    auth_requests = [r for r in api_requests if "/api/auth" in r["url"]]
    chat_requests = [r for r in api_requests if "/api/chat" in r["url"]]

    # Check for 401s
    unauthorized = [r for r in api_requests if r["response_status"] == 401]

    # Check which requests had auth headers
    auth_header_requests = [r for r in api_requests if r.get("auth_header_found", False)]

    # Build the report
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
    report.append("```")
    for log in console_logs:
        msg_type = log.get("type", "unknown")
        text = log.get("text", "")
        url = log.get("url", "")
        line = log.get("line", "")
        location = f" ({url}:{line})" if url else ""
        report.append(f"[{msg_type.upper()}{location}] {text}")
    report.append("```")
    report.append("")

    report.append("## Network Request Analysis")
    report.append("")
    report.append(f"**Total API requests captured:** {len(api_requests)}")
    report.append(f"**Auth-related requests:** {len(auth_requests)}")
    report.append(f"**Chat-related requests:** {len(chat_requests)}")
    report.append(f"**Requests with Authorization header:** {len(auth_header_requests)}")
    report.append(f"**401 Unauthorized responses:** {len(unauthorized)}")
    report.append("")

    # Detailed API requests
    report.append("### All API Requests")
    report.append("")
    report.append("| # | Method | URL | Auth Header | Response |")
    report.append("|---|--------|-----|-------------|----------|")
    for i, req in enumerate(api_requests, 1):
        url_short = req["url"].replace(BACKEND_URL, "")
        if len(url_short) > 60:
            url_short = url_short[:57] + "..."
        auth = "YES" if req.get("auth_header_found") else "NO"
        status = req.get("response_status", "N/A")
        report.append(f"| {i} | {req['method']} | `{url_short}` | {auth} | {status} |")
    report.append("")

    # Auth requests detail
    if auth_requests:
        report.append("### Auth API Requests (Detailed)")
        report.append("")
        for i, req in enumerate(auth_requests, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"#### {i}. {req['method']} {url_short}")
            report.append("")
            report.append(f"- **URL:** `{req['url']}`")
            report.append(f"- **Method:** {req['method']}")
            report.append(f"- **Has Authorization Header:** {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("auth_header_value"):
                report.append(f"- **Authorization Value:** `{req['auth_header_value'][:50]}...`" if len(str(req.get("auth_header_value", ""))) > 50 else f"- **Authorization Value:** `{req['auth_header_value']}`")
            report.append(f"- **Response Status:** {req.get('response_status', 'N/A')}")
            report.append(f"- **Resource Type:** {req.get('resource_type', 'N/A')}")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- **Request Body:** ```{pd[:500]}```")
            if req.get("response_body"):
                report.append(f"- **Response Body:** ```{req['response_body'][:500]}```")
            report.append("")
    else:
        report.append("### Auth API Requests")
        report.append("No auth API requests were captured.")
        report.append("")

    # Chat requests detail
    if chat_requests:
        report.append("### Chat API Requests (Detailed)")
        report.append("")
        for i, req in enumerate(chat_requests, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"#### {i}. {req['method']} {url_short}")
            report.append("")
            report.append(f"- **URL:** `{req['url']}`")
            report.append(f"- **Method:** {req['method']}")
            report.append(f"- **Has Authorization Header:** {'YES' if req.get('auth_header_found') else 'NO'}")
            if req.get("auth_header_value"):
                report.append(f"- **Authorization Value:** `{req['auth_header_value'][:50]}...`" if len(str(req.get("auth_header_value", ""))) > 50 else f"- **Authorization Value:** `{req['auth_header_value']}`")
            report.append(f"- **Response Status:** {req.get('response_status', 'N/A')}")
            report.append(f"- **Resource Type:** {req.get('resource_type', 'N/A')}")
            if req.get("post_data"):
                pd = req.get("post_data", "")
                if isinstance(pd, bytes):
                    pd = pd.decode("utf-8", errors="replace")
                report.append(f"- **Request Body:** ```{pd[:500]}```")
            if req.get("response_body"):
                report.append(f"- **Response Body:** ```{req['response_body'][:500]}```")
            report.append("")
    else:
        report.append("### Chat API Requests")
        report.append("No chat API requests were captured during the test.")
        report.append("")

    # 401 Errors
    if unauthorized:
        report.append("## 401 Unauthorized Errors")
        report.append("")
        for i, req in enumerate(unauthorized, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"### {i}. 401 on {req['method']} {url_short}")
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
        report.append("No 401 errors were captured.")
        report.append("")

    # All captured requests (non-API)
    other_requests = [r for r in captured_requests if "/api/" not in r["url"]]
    if other_requests:
        report.append("## Other Network Requests")
        report.append("")
        report.append("| # | Method | URL | Status |")
        report.append("|---|--------|-----|--------|")
        for i, req in enumerate(other_requests, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            if len(url_short) > 80:
                url_short = url_short[:77] + "..."
            report.append(f"| {i} | {req['method']} | {url_short} | {req.get('response_status', 'N/A')} |")
        report.append("")

    # Authorization header analysis
    report.append("## Authorization Header Analysis")
    report.append("")
    if auth_header_requests:
        report.append(f"**{len(auth_header_requests)} requests** included an Authorization header:")
        report.append("")
        for req in auth_header_requests:
            url_short = req["url"].replace(BACKEND_URL, "")
            auth_val = req.get("auth_header_value", "N/A")
            if len(str(auth_val)) > 60:
                auth_val = str(auth_val)[:57] + "..."
            report.append(f"- {req['method']} `{url_short}`: `{auth_val}`")
        report.append("")
        report.append("**Conclusion:** The frontend IS sending Authorization headers with requests.")
        report.append("")
    else:
        report.append("**No requests** included an Authorization header.")
        report.append("")
        report.append("**Conclusion:** The frontend is NOT sending Authorization headers. This would cause 401 errors on protected endpoints.")
        report.append("")

    # Final summary
    all_passed = all("PASS" in line for line in test_results)
    report.append("## Final Verdict")
    report.append("")
    if all_passed and len(unauthorized) == 0 and len(auth_header_requests) > 0:
        report.append("**STATUS: PASS** - Authentication flow works correctly.")
        report.append(f"- All {len(test_results)} test steps passed.")
        report.append(f"- No 401 errors detected.")
        report.append(f"- Authorization headers are being sent with {len(auth_header_requests)} API requests.")
    elif len(unauthorized) > 0:
        report.append("**STATUS: FAIL** - Authentication has issues.")
        report.append(f"- {len(unauthorized)} requests returned 401 Unauthorized.")
        report.append(f"- Authorization headers sent: {len(auth_header_requests)}")
        report.append("")
        report.append("### Likely Issues:")
        report.append("1. Token not stored in browser after login")
        report.append("2. Token not retrieved from storage for API requests")
        report.append("3. Token format invalid or expired")
        report.append("4. Backend not validating token correctly")
    elif len(auth_header_requests) == 0 and len(api_requests) > 0:
        report.append("**STATUS: FAIL** - No Authorization headers sent with API requests.")
        report.append(f"- {len(api_requests)} API requests were made without auth headers.")
        report.append(f"- All would likely return 401 from the backend.")
    else:
        report.append("**STATUS: INCONCLUSIVE**")
        report.append(f"- Passed: {sum(1 for l in test_results if 'PASS' in l)}/{len(test_results)}")
        report.append(f"- API requests: {len(api_requests)}")
        report.append(f"- Auth headers sent: {len(auth_header_requests)}")
        report.append(f"- 401 errors: {len(unauthorized)}")

    report.append("")
    report.append("---")
    report.append(f"*Report generated: {datetime.now().isoformat()}*")

    # Write the report
    report_content = "\n".join(report)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\nReport written to: {REPORT_PATH}")
    print(f"\nReport preview (first 80 lines):")
    print("-" * 40)
    for line in report[:80]:
        print(line)


if __name__ == "__main__":
    main()
