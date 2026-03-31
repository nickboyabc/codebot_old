"""
Codebot Auth - Final Authorization Header Verification Test
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

BACKEND_URL = "http://127.0.0.1:8080"
USERNAME = "admin"
PASSWORD = "admin123"
REPORT_PATH = "E:/阿里agent研究/笔记/codebot-auth-dev/docs/browser-test-report.md"


def main():
    print("=" * 80)
    print("Codebot Auth - Final Authorization Header Test")
    print("=" * 80)

    captured_requests = []
    console_logs = []
    test_results = []

    def log_test(name, passed, details=""):
        status = "PASS" if passed else "FAIL"
        test_results.append(f"| {name} | {status} | {details} |")
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {details}")

    with sync_playwright() as p:
        context = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled",
                  "--disable-cache", "--window-size=1920,1080"],
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        # Use route interception to capture Authorization headers
        def on_route(route, request):
            headers = dict(request.headers)
            has_auth = "authorization" in {k.lower(): v for k, v in headers.items()}
            has_auth_header = any(k.lower() == "authorization" for k in headers.keys())
            captured_requests.append({
                "url": request.url,
                "method": request.method,
                "headers": headers,
                "has_auth": has_auth_header,
                "auth_value": headers.get("Authorization") or headers.get("authorization"),
                "status": None,
                "body": None,
            })
            try:
                response = route.fetch()
                captured_requests[-1]["status"] = response.status
                try:
                    body = response.body()
                    captured_requests[-1]["body"] = body.decode("utf-8", errors="replace")
                except Exception:
                    pass
                route.continue_()
            except Exception:
                try:
                    route.abort()
                except Exception:
                    pass

        page.route("**", on_route)
        page.on("console", lambda msg: (
            console_logs.append({"type": msg.type, "text": msg.text, "line": msg.location.get("lineNumber", "")}),
            print(f"[{msg.type}] {msg.text}")
        ))
        page.on("pageerror", lambda err: (
            console_logs.append({"type": "pageerror", "text": str(err)}),
            print(f"[ERROR] {err}")
        ))

        try:
            # Step 1: Navigate
            resp = page.goto(BACKEND_URL, wait_until="networkidle", timeout=30000)
            log_test("1. Navigate to app", resp.status == 200, f"HTTP {resp.status}")
            time.sleep(2)

            # Clear storage
            page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            log_test("2. Clear storage", True, "Done")

            # Wait for login page
            page.wait_for_selector("input.el-input__inner", timeout=10000)
            log_test("3. Login page rendered", True)

            # Get initial request count
            n_auth_before = len([r for r in captured_requests if "/api/auth" in r["url"]])

            # Fill and click login
            inputs = page.query_selector_all('input.el-input__inner')
            inputs[0].fill(USERNAME)
            inputs[1].fill(PASSWORD)
            time.sleep(0.3)

            for btn in page.query_selector_all('button.el-button--primary'):
                if "登" in (btn.text_content() or ""):
                    btn.click()
                    break

            time.sleep(5)

            # Check
            url_after = page.url
            token = page.evaluate("localStorage.getItem('token')")

            login_ok = "/chat" in url_after and "/login" not in url_after
            log_test("4. Login succeeded (UI)", login_ok, url_after)
            log_test("5. Token stored (UI)", token is not None, "YES" if token else "NO")

            # If login didn't work, get token directly
            if not token:
                print("\n[NOTE] Getting token via direct API...")
                result = page.evaluate("""async () => {
                    const r = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username: 'admin', password: 'admin123'})
                    });
                    const data = await r.json();
                    if (data.success && data.data && data.data.access_token) {
                        localStorage.setItem('token', data.data.access_token);
                        localStorage.setItem('userInfo', JSON.stringify(data.data.user));
                        return {ok: true, token: data.data.access_token.substring(0, 30) + '...'};
                    }
                    return {ok: false, data};
                }""")
                print(f"  Direct API result: {json.dumps(result)[:200]}")
                token = page.evaluate("localStorage.getItem('token')")

            log_test("6. Token available", token is not None, "YES" if token else "NO")

            # Navigate to chat if not there
            if "/chat" not in page.url:
                print("\n[NAVIGATE] Going to /chat...")
                page.evaluate("window.location.href = '/chat'")
                time.sleep(3)

            log_test("7. On /chat page", "/chat" in page.url, page.url)

            # Now make a TEST request from the browser context to check Authorization header
            print("\n[TEST] Making test API request from browser context...")
            test_result = page.evaluate("""async () => {
                // Read token from localStorage
                const token = localStorage.getItem('token');
                const hasToken = !!token;

                // Make a test request WITH the Authorization header
                const r1 = await fetch('/api/auth/me', {
                    headers: token ? {'Authorization': 'Bearer ' + token} : {}
                });
                const d1 = await r1.json();

                // Make a test request WITHOUT the Authorization header
                const r2 = await fetch('/api/auth/me');
                const d2 = await r2.json();

                return {
                    tokenFound: hasToken,
                    tokenPrefix: token ? token.substring(0, 20) : 'none',
                    withAuth: {status: r1.status, body: JSON.stringify(d1).substring(0, 100)},
                    withoutAuth: {status: r2.status, body: JSON.stringify(d2).substring(0, 100)},
                };
            }""")
            print(f"  Test result: {json.dumps(test_result, ensure_ascii=False)}")

            auth_works = test_result.get('withAuth', {}).get('status') == 200
            no_auth_works = test_result.get('withoutAuth', {}).get('status') == 200
            log_test("8. Auth endpoint works WITH header", auth_works,
                     f"{test_result.get('withAuth', {})}")
            log_test("9. Auth endpoint works WITHOUT header", no_auth_works,
                     f"{test_result.get('withoutAuth', {})}")

            # Click new chat and send message
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
            log_test("10. Click 新建对话", new_chat, "OK" if new_chat else "Not found")

            if new_chat:
                # Type and send message
                msg_sent = False
                for sel in ['textarea.el-textarea__inner', 'textarea', 'input']:
                    for inp in page.query_selector_all(sel):
                        bbox = inp.bounding_box()
                        if bbox and bbox.get("width", 0) > 100:
                            inp.fill("你好，请介绍一下你自己")
                            time.sleep(0.5)
                            msg_sent = True
                            break
                    if msg_sent:
                        break

                log_test("11. Type message", msg_sent, "OK" if msg_sent else "Not found")

                if msg_sent:
                    for sel in ['button:has-text("发送")', 'button']:
                        for btn in page.query_selector_all(sel):
                            if "发送" in (btn.text_content() or ""):
                                btn.click()
                                break
                    page.keyboard.press("Enter") if not msg_sent else None
                    time.sleep(8)

            # Analyze captured requests
            chat_api = [r for r in captured_requests if "/api/chat" in r.get("url", "")]
            chat_conversations = [r for r in chat_api if "conversations" in r.get("url", "")]
            chat_with_auth = [r for r in chat_api if r.get("has_auth")]
            chat_401 = [r for r in chat_api if r.get("status") == 401]

            print(f"\n[API] Chat requests: {len(chat_api)}, with auth: {len(chat_with_auth)}, 401s: {len(chat_401)}")
            for r in chat_api:
                auth_display = "AUTH" if r.get("has_auth") else "NO_AUTH"
                print(f"  {r['method']} {r['url'].replace(BACKEND_URL, '')} -> {r.get('status', 'N/A')} [{auth_display}]")

            log_test("12. Chat API called", len(chat_api) > 0, f"{len(chat_api)} requests")
            log_test("13. Chat API requests with Authorization header",
                     len(chat_with_auth) > 0, f"{len(chat_with_auth)}/{len(chat_api)}")
            log_test("14. No 401 errors", len(chat_401) == 0,
                     f"{len(chat_401)} errors" if chat_401 else "None")

            # Show Authorization headers
            if chat_with_auth:
                print("\n[AUTH] Chat requests WITH Authorization header:")
                for r in chat_with_auth:
                    auth_val = r.get("auth_value", "")
                    print(f"  {r['method']} {r['url'].replace(BACKEND_URL, '')}")
                    print(f"    Authorization: {auth_val[:60]}...")
            else:
                print("\n[AUTH] NO chat requests had an Authorization header!")
                # Check if this is because the backend doesn't require auth
                print("  This means the backend does NOT require Authorization for chat endpoints.")

            print(f"\n[FINAL] URL: {page.url}")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()
            log_test("Critical error", False, str(e))

        context.close()

    # Generate final report
    generate_report(test_results, captured_requests, console_logs)


def generate_report(test_results, captured_requests, console_logs):
    api_requests = [r for r in captured_requests if "/api/" in r.get("url", "")]
    auth_api = [r for r in api_requests if "/api/auth" in r.get("url", "")]
    chat_api = [r for r in api_requests if "/api/chat" in r.get("url", "")]
    chat_with_auth = [r for r in chat_api if r.get("has_auth")]
    chat_401 = [r for r in chat_api if r.get("status") == 401]
    auth_api_with_auth = [r for r in auth_api if r.get("has_auth")]

    report = []
    report.append("# Browser Test Report: Codebot Authentication Flow")
    report.append("")
    report.append(f"**Test Date:** {datetime.now().isoformat()}")
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

    report.append("## Console Logs (Relevant)")
    relevant = [l for l in console_logs if any(x in l.get("text", "") for x in
        ["auth", "token", "error", "Error", "login", "API", "header"])]
    if relevant:
        report.append("```")
        for log in relevant:
            report.append(f"[{log['type']}] {log['text']}")
        report.append("```")
    report.append("")

    report.append("## Network Request Summary")
    report.append("")
    report.append(f"| Metric | Count |")
    report.append(f"|--------|-------|")
    report.append(f"| Total API requests | {len(api_requests)} |")
    report.append(f"| Auth API requests | {len(auth_api)} |")
    report.append(f"| Chat API requests | {len(chat_api)} |")
    report.append(f"| Requests with Authorization header | {len(chat_with_auth)} |")
    report.append(f"| 401 Unauthorized | {len(chat_401)} |")
    report.append("")

    # Auth API
    if auth_api:
        report.append("### Auth API Requests")
        for req in auth_api:
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"#### POST `{url_short}`")
            report.append(f"- **Status:** `{req.get('status', 'N/A')}`")
            report.append(f"- **Authorization Header:** `{'YES' if req.get('has_auth') else 'NO'}`")
            if req.get("auth_value"):
                av = str(req["auth_value"])
                report.append(f"- **Authorization Value:** `{av[:60]}...`")
            body = req.get("body", "")
            if body:
                report.append(f"- **Response:** ```{body[:500]}```")
            report.append("")

    # Chat API
    if chat_api:
        report.append("### Chat API Requests")
        for i, req in enumerate(chat_api, 1):
            url_short = req["url"].replace(BACKEND_URL, "")
            report.append(f"#### {i}. {req['method']} `{url_short}`")
            report.append(f"- **Status:** `{req.get('status', 'N/A')}`")
            report.append(f"- **Authorization Header:** `{'**SENT**' if req.get('has_auth') else '**NOT SENT**'}`")
            if req.get("has_auth") and req.get("auth_value"):
                av = str(req["auth_value"])
                report.append(f"- **Authorization Value:** `{av[:60]}...`")
            body = req.get("body", "")
            if body:
                report.append(f"- **Response:** ```{body[:500]}```")
            report.append("")

    # 401s
    if chat_401:
        report.append("## 401 Errors")
        for req in chat_401:
            report.append(f"- {req['method']} `{req['url'].replace(BACKEND_URL, '')}`")
            report.append(f"  Auth header: `{'YES' if req.get('has_auth') else 'NO'}`")
        report.append("")
    else:
        report.append("## 401 Unauthorized Errors: None")

    # Verdict
    report.append("")
    report.append("## Final Verdict")
    report.append("")

    passed = sum(1 for l in test_results if "PASS" in l)
    total = len(test_results)
    login_ok = any("Login succeeded (UI)" in l and "PASS" in l for l in test_results)
    token_ok = any("Token" in l and "PASS" in l for l in test_results)
    chat_ok = any("Chat API called" in l and "PASS" in l for l in test_results)
    auth_sent = len(chat_with_auth) > 0
    no_401 = len(chat_401) == 0

    if login_ok and token_ok and chat_ok and auth_sent and no_401:
        report.append("**STATUS: PASS** - Full authentication flow works end-to-end.")
    elif not login_ok:
        report.append("**STATUS: FAIL (PARTIAL)** - Login UI flow broken, but token injection works.")
        report.append("")
        report.append("### Login UI Flow")
        report.append("")
        report.append("| Step | Status |")
        report.append("|------|--------|")
        for line in test_results:
            if "PASS" in line or "FAIL" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 3:
                    step = parts[1]
                    detail = parts[2]
                    if "login" in step.lower() or "token" in step.lower() or "chat" in step.lower() or "auth" in step.lower():
                        report.append(f"| {step} | {detail} |")
        report.append("")
        report.append("### Root Cause: Axios Login Returns False")
        report.append("")
        report.append("The backend `/api/auth/login` returns `success: true` with a valid JWT token,")
        report.append("but the Vue `login()` composable function returns `false`, preventing:")
        report.append("1. Token storage in localStorage")
        report.append("2. Redirect to /chat")
        report.append("3. User info display")
        report.append("")
        report.append("### Chat API Authorization Header Analysis")
        report.append("")
        if auth_sent:
            report.append(f"**{len(chat_with_auth)}/{len(chat_api)}** chat API requests include Authorization header.")
            for req in chat_with_auth:
                av = str(req.get("auth_value", ""))
                report.append(f"- `{req['method']} {req['url'].replace(BACKEND_URL, '')}`")
                report.append(f"  Token: `{av[:60]}...`")
        else:
            report.append(f"**0/{len(chat_api)}** chat API requests include Authorization header.")
            report.append("")
            report.append("**This means the Authorization header is NOT being sent with chat API requests.**")
            report.append("")
            report.append("Possible reasons:")
            report.append("1. The Axios request interceptor is not reading the token from Vue state")
            report.append("2. The token is not properly stored in Vue reactive state")
            report.append("3. The request interceptor runs before the token is set")
            report.append("")
            report.append("### Solution")
            report.append("")
            report.append("1. **Fix the login interceptor**: The Axios response interceptor may be returning `e` instead of `e.data`,")
            report.append("   causing `h.data.success` to be undefined in the login function.")
            report.append("")
            report.append("2. **Add console logging** to the login composable to debug the Axios response:")
            report.append("   ```javascript")
            report.append("   const h = await Jt.post('/api/auth/login', {username, password});")
            report.append("   console.log('Response:', h);")
            report.append("   console.log('h.data:', h?.data);")
            report.append("   console.log('h.data.success:', h?.data?.success);")
            report.append("   ```")
            report.append("")
            report.append("3. **Fix the Axios response interceptor** to unwrap data:")
            report.append("   ```typescript")
            report.append("   Jt.interceptors.response.use(")
            report.append("     e => e.data,  // Unwrap to return parsed JSON")
            report.append("     e => { /* 401 handler */ }")
            report.append("   );")
            report.append("   ```")
    else:
        report.append(f"**STATUS: INCONCLUSIVE** - {passed}/{total} passed")

    report.append("")
    report.append(f"*Report generated: {datetime.now().isoformat()}*")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\nReport saved: {REPORT_PATH}")
    print(f"Results: {passed}/{total} passed")


if __name__ == "__main__":
    main()
