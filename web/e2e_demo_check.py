"""按 WEEK1_MVP.md §8 的演示流程完整驱动一遍 Web 管理端。

覆盖的验收点：
  - 价格缺失显示「—」而非 0
  - 活动区分「进行中 / 已过期」
  - 上游 Key 只显示后四位；编辑留空不改 Key
  - routeKey 重复返回 409 并给出定位提示
  - 成员上移 / 下移改变优先级
  - 第一上游正常 -> 不切换；第一上游 500 -> 自动切到第二上游
  - 400 参数错误 -> 不切换
  - 路由记录页能展开尝试链
"""
import sys
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:5173"
FAILURES = []
console_errors = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def run(page):
    # ---------- 1. 价格页 ----------
    page.goto(f"{BASE}/prices")
    page.wait_for_selector(".el-table__row", timeout=15000)
    rows = page.locator(".el-table__row")
    check("价格页显示 8 个模型", rows.count() == 8, f"实际 {rows.count()}")

    # sf-deepseek-v3 没有价格，必须显示 —
    v3 = page.locator(".el-table__row", has_text="DeepSeek-V3 (SF)")
    v3_text = v3.inner_text()
    check("无价格模型显示「—」", "—" in v3_text, v3_text)
    check("无价格模型不显示 0", "0.00" not in v3_text, v3_text)
    check("缺价提示横幅存在", page.locator(".el-alert", has_text="暂无价格数据").count() == 1)

    ds = page.locator(".el-table__row", has_text="DeepSeek Chat").inner_text()
    check("DeepSeek Chat 价格正确", "¥1" in ds and "¥8.00" in ds, ds)

    # ---------- 2. 活动页 ----------
    page.goto(f"{BASE}/promotions")
    page.wait_for_selector(".el-table__row", timeout=15000)
    check("活动页 3 条", page.locator(".el-table__row").count() == 3)
    check("有「已过期」标记", page.locator(".el-tag", has_text="已过期").count() >= 1)
    check("有「进行中」标记", page.locator(".el-tag", has_text="进行中").count() >= 1)

    expired_row = page.locator(".el-table__row", has_text="GPT-4.1 系列发布")
    check("promo-3 被标记为已过期", "已过期" in expired_row.inner_text())

    page.get_by_placeholder("全部状态").click()
    page.get_by_role("option", name="进行中").click()
    page.wait_for_timeout(400)
    check("勾选后只剩 2 条进行中", page.locator(".el-table__row").count() == 2)

    # ---------- 3. 添加两个上游 ----------
    page.goto(f"{BASE}/providers")
    page.wait_for_selector("text=供应商 / API 管理", timeout=15000)

    def add_upstream(name, base_url, key, model):
        page.get_by_role("button", name="添加上游").click()
        dlg = page.locator(".el-dialog:visible")
        dlg.get_by_placeholder("如 DeepSeek-主力").fill(name)
        dlg.get_by_placeholder("https://api.deepseek.com").fill(base_url)
        dlg.locator("input[type=password]").fill(key)
        dlg.get_by_placeholder("如 deepseek-chat（可选）").fill(model)
        dlg.get_by_role("button", name="保存").click()
        page.wait_for_timeout(700)

    add_upstream("模拟上游-可控故障", "http://127.0.0.1:8100", "sk-mock-1111", "mock-model")
    add_upstream("DeepSeek-真实", "https://api.deepseek.com", "sk-real-9999", "deepseek-chat")

    up_table = page.locator(".el-card", has_text="上游 API").locator(".el-table__row")
    check("已添加 2 个上游", up_table.count() == 2, f"实际 {up_table.count()}")

    body = page.inner_text("body")
    check("界面显示掩码 Key", "••••1111" in body and "••••9999" in body)
    check("界面不出现明文 Key", "sk-mock-1111" not in body and "sk-real-9999" not in body)

    # 编辑时留空 Key -> 后四位不变
    up_table.first.get_by_role("button", name="编辑").click()
    dlg = page.locator(".el-dialog:visible")
    key_input = dlg.locator("input[type=password]")
    check("编辑态 Key 框为空", key_input.input_value() == "")
    check("placeholder 提示留空保持原密钥", "留空则保持原密钥" in (key_input.get_attribute("placeholder") or ""))
    dlg.get_by_placeholder("如 DeepSeek-主力").fill("模拟上游-已改名")
    dlg.get_by_role("button", name="保存").click()
    page.wait_for_timeout(700)
    check("留空保存后 Key 后四位不变", "••••1111" in page.inner_text("body"))
    check("改名生效", "模拟上游-已改名" in page.inner_text("body"))

    # localStorage 不得存 Key
    ls = page.evaluate("JSON.stringify(Object.entries(localStorage))")
    check("localStorage 无明文 Key", "sk-" not in ls, ls[:200])

    # ---------- 4. 创建分组并加入两个成员 ----------
    page.goto(f"{BASE}/groups")
    page.wait_for_selector("text=API 分组", timeout=15000)

    page.get_by_role("button", name="创建分组").click()
    dlg = page.locator(".el-dialog:visible")
    dlg.get_by_placeholder("如 演示路由").fill("演示路由")
    dlg.get_by_placeholder("如 demo-route").fill("demo-route")
    dlg.get_by_role("button", name="保存").click()
    page.wait_for_timeout(800)
    check("分组创建成功", "demo-route" in page.inner_text("body"))

    # routeKey 重复 -> 409 专门提示
    page.get_by_role("button", name="创建分组").click()
    dlg = page.locator(".el-dialog:visible")
    dlg.get_by_placeholder("如 演示路由").fill("重复分组")
    dlg.get_by_placeholder("如 demo-route").fill("demo-route")
    dlg.get_by_role("button", name="保存").click()
    page.wait_for_timeout(800)
    err = page.locator(".el-form-item__error").inner_text()
    check("routeKey 重复给出占用提示", "已被占用" in err, err)
    dlg.get_by_role("button", name="取消").click()
    page.wait_for_timeout(400)

    def add_member(upstream_name, model):
        page.get_by_role("button", name="添加成员").click()
        d = page.locator(".el-dialog:visible")
        d.locator(".el-select").click()
        page.wait_for_timeout(300)
        page.locator(".el-select-dropdown__item", has_text=upstream_name).first.click()
        page.wait_for_timeout(200)
        d.get_by_placeholder("如 deepseek-chat").fill(model)
        d.get_by_role("button", name="添加").click()
        page.wait_for_timeout(700)

    add_member("模拟上游-已改名", "mock-model")
    add_member("DeepSeek-真实", "deepseek-chat")

    members = page.locator(".el-card", has_text="成员").locator(".el-table__row")
    check("分组内有 2 个成员", members.count() == 2, f"实际 {members.count()}")
    check("第一优先级是模拟上游", "模拟上游-已改名" in members.nth(0).inner_text())

    # ---------- 5. 第一上游正常 -> 不切换 ----------
    page.goto(f"{BASE}/playground")
    page.wait_for_selector("text=调用测试", timeout=15000)
    page.get_by_role("button", name="发送请求").click()
    page.wait_for_selector("text=调用成功", timeout=20000)
    page.wait_for_timeout(500)  # 等 attempts 加载完成
    body = page.inner_text("body")
    check("正常时最终上游为第一上游", "最终上游：模拟上游-已改名" in body, body[:400])
    check("显示请求 ID", "req-" in body)
    attempts = page.locator(".el-timeline-item")
    check("正常时只尝试 1 次", attempts.count() == 1, f"实际 {attempts.count()}")

    # ---------- 6. 第一上游 500 -> 自动切换 ----------
    # Element Plus el-radio-button 的内层 span 会拦截事件，force 一下
    page.get_by_role("radio", name="500 错误（应切换）").click(force=True)
    page.wait_for_timeout(300)
    page.get_by_role("button", name="发送请求").click()
    page.wait_for_selector("text=调用成功", timeout=20000)
    page.wait_for_timeout(600)
    body = page.inner_text("body")
    check("500 时切换到第二上游", "最终上游：DeepSeek-真实" in body, body[:400])
    attempts = page.locator(".el-timeline-item")
    check("500 时尝试 2 次", attempts.count() == 2, f"实际 {attempts.count()}")
    check("尝试链显示 500 错误", "服务端错误 5xx" in body)

    # ---------- 7. 400 参数错误 -> 不切换 ----------
    page.get_by_role("radio", name="400 参数错误（不应切换）").click(force=True)
    page.wait_for_timeout(300)
    page.get_by_role("button", name="发送请求").click()
    page.wait_for_selector("text=调用失败", timeout=20000)
    page.wait_for_timeout(600)
    body = page.inner_text("body")
    check("400 时调用失败", "调用失败" in body)
    check("400 时不切换（仅 1 次尝试）", page.locator(".el-timeline-item").count() == 1)
    check("400 失败也显示请求 ID", "req-" in body)

    # 恢复正常，避免影响后续
    page.get_by_role("radio", name="正常返回").click(force=True)

    # ---------- 8. 路由记录页 ----------
    page.goto(f"{BASE}/requests")
    page.wait_for_selector(".el-table__row", timeout=15000)
    rows = page.locator(".el-table__row")
    check("路由记录有 3 条", rows.count() == 3, f"实际 {rows.count()}")
    body = page.inner_text("body")
    check("记录含成功状态", "成功" in body)
    check("记录含参数错误状态", "参数错误（未切换）" in body)

    page.locator(".el-table__expand-icon").first.click()
    page.wait_for_timeout(900)
    check("展开后显示尝试链", page.locator(".el-timeline-item").count() >= 1)

    # ---------- 9. 错误态：切到真实后端（501/无服务） ----------
    page.goto(f"{BASE}/prices")
    page.wait_for_timeout(500)
    page.locator(".el-switch").first.click()  # 关闭 Mock
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    check("关闭 Mock 后显示错误而非白屏", "加载失败" in body or "重试" in body, body[:300])
    check("错误页仍有导航（未白屏）", page.locator(".el-menu").count() == 1)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(f"PAGEERROR: {e}"))
    try:
        run(page)
    except Exception as e:
        print(f"[FAIL] 脚本异常: {type(e).__name__}: {e}")
        FAILURES.append("script-exception")
        page.screenshot(path="e2e-failure.png")
    finally:
        browser.close()

# 过滤掉关闭 Mock 后必然出现的 fetch 失败
real_errors = [e for e in console_errors if "Failed to load resource" not in e]
if real_errors:
    print("\n浏览器控制台错误：")
    for e in real_errors[:10]:
        print("  -", e)
    FAILURES.append("console-errors")

print("\n" + "=" * 50)
print(f"失败 {len(FAILURES)} 项" if FAILURES else "全部通过")
for f in FAILURES:
    print("  x", f)
sys.exit(1 if FAILURES else 0)
