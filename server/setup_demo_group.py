#!/usr/bin/env python3
"""E3 分组路由演示 —— 一键搭建（幂等）。

通过管理 API（/api/admin）创建：
  供应商 mock
  上游 mock-fail  http://127.0.0.1:8100/v1   （故障实例，脚本会尝试切到 scenario=500）
  上游 mock-ok    http://127.0.0.1:8101/v1   （正常实例）
  分组 demo（routeKey=demo，maxAttempts=3）
  成员顺序：mock-fail(rank 1) -> mock-ok(rank 2)

幂等：按 displayName / routeKey 复用已存在对象，不重复创建；成员按
upstreamEndpointId 判断，缺失才追加。重跑安全。

前置：
  1. 网关已启动（默认 http://127.0.0.1:8000，可用 --base 覆盖）
  2. 两个模拟上游已启动：
       python mock_upstream.py                       # 8100
       MOCK_PORT=8101 python mock_upstream.py        # 8101
  3. （推荐）server/.env 中设置固定 GATEWAY_MASTER_KEY，
     否则密钥用进程内临时密钥加密，重启后无法解密。

用法：
  python setup_demo_group.py            # 用默认地址
  python setup_demo_group.py --base http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import sys

import httpx

DEFAULT_BASE = "http://127.0.0.1:8000"

# 演示对象定义
PROVIDER = {"name": "mock"}
UPSTREAMS = [
    {
        "displayName": "mock-fail",
        "baseUrl": "http://127.0.0.1:8100/v1",
        "defaultModel": "mock-model",
    },
    {
        "displayName": "mock-ok",
        "baseUrl": "http://127.0.0.1:8101/v1",
        "defaultModel": "mock-model",
    },
]
GROUP = {"name": "demo 分组（故障切换演示）", "routeKey": "demo", "maxAttempts": 3}
# 成员顺序：rank 1 先失败，rank 2 兜底成功
MEMBER_ORDER = [
    ("mock-fail", 1),
    ("mock-ok", 2),
]
# 脚本尝试把故障实例切到 500、正常实例切回 normal；连不上只告警不中断
MOCK_SCENARIOS = {
    "http://127.0.0.1:8100": "500",
    "http://127.0.0.1:8101": "normal",
}


def _request(client: httpx.Client, method: str, path: str, **kwargs):
    url = f"{client.base_url}{path.lstrip('/')}"
    resp = client.request(method, url, **kwargs)
    if resp.status_code >= 400:
        detail = resp.text[:300]
        raise RuntimeError(f"{method} {url} -> HTTP {resp.status_code}: {detail}")
    return resp.json() if resp.content else None


def _find(items: list[dict], key: str, value: str):
    return next((item for item in items if item.get(key) == value), None)


def main() -> int:
    parser = argparse.ArgumentParser(description="E3 分组路由演示一键搭建（幂等）")
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"网关地址（默认 {DEFAULT_BASE}）")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    with httpx.Client(base_url=f"{base}/", timeout=10) as client:
        print(f"[1/5] 健康检查：{base}")
        try:
            health = _request(client, "GET", "/health")
            print(f"      数据库状态：{health.get('database')}")
        except Exception as exc:
            print(f"      网关不可达：{exc}", file=sys.stderr)
            print("提示：请先启动 server（uvicorn app.main:app --reload --port 8000）", file=sys.stderr)
            return 1

        print("[2/5] 供应商 mock")
        providers = _request(client, "GET", "/api/admin/providers")
        if _find(providers, "name", "mock"):
            print("      已存在，跳过")
        else:
            created = _request(client, "POST", "/api/admin/providers", json=PROVIDER)
            print(f"      已创建：{created['id']}")

        print("[3/5] 上游 upstream（密钥写入时加密）")
        upstream_ids: dict[str, str] = {}
        existing = _request(client, "GET", "/api/admin/upstreams")
        for spec in UPSTREAMS:
            found = _find(existing, "displayName", spec["displayName"])
            if found:
                upstream_ids[spec["displayName"]] = found["id"]
                print(f"      {spec['displayName']} 已存在：{found['id']}")
                continue
            created = _request(
                client, "POST", "/api/admin/upstreams",
                json={**spec, "providerId": _provider_id(client), "apiKey": "demo-key"},
            )
            upstream_ids[spec["displayName"]] = created["id"]
            print(f"      {spec['displayName']} 已创建：{created['id']}（last4={created['apiKeyLastFour']}）")

        print("[4/5] 分组 demo（routeKey=demo）")
        groups = _request(client, "GET", "/api/admin/groups")
        group = _find(groups, "routeKey", "demo")
        if group is None:
            group = _request(client, "POST", "/api/admin/groups", json=GROUP)
            print(f"      已创建：{group['id']}")
        else:
            print(f"      已存在：{group['id']}")

        print("[5/5] 组成员（rank 1=mock-fail, rank 2=mock-ok）")
        detail = _request(client, "GET", f"/api/admin/groups/{group['id']}")
        existing_member_upstreams = {m["upstreamEndpointId"] for m in detail["members"]}
        for display_name, rank in MEMBER_ORDER:
            upstream_id = upstream_ids[display_name]
            if upstream_id in existing_member_upstreams:
                print(f"      {display_name}(rank {rank}) 已存在，跳过")
                continue
            _request(
                client, "POST", f"/api/admin/groups/{group['id']}/members",
                json={
                    "upstreamEndpointId": upstream_id,
                    "upstreamModelName": "mock-model",
                    "priorityRank": rank,
                },
            )
            print(f"      {display_name}(rank {rank}) 已加入")

    # 尝试设置模拟上游场景（非关键步骤）
    for base_url, scenario in MOCK_SCENARIOS.items():
        try:
            with httpx.Client(base_url=f"{base_url}/", timeout=3) as client:
                resp = client.put("/_mock/scenario", json={"scenario": scenario})
                if resp.status_code == 200:
                    print(f"[mock] {base_url} 场景已设为 {scenario}")
                else:
                    print(f"[mock] {base_url} 设置场景返回 HTTP {resp.status_code}")
        except Exception:
            print(f"[mock] 警告：{base_url} 不可达，请手动启动并设置场景 {scenario}")

    print()
    print("搭建完成。验证故障切换：")
    print("  curl -s http://127.0.0.1:8000/v1/chat/completions \\")
    print('       -H "Content-Type: application/json" \\')
    print('       -d \'{"model":"demo","messages":[{"role":"user","content":"你好"}]}\'')
    print("  响应头 X-Upstream 应为 mock-ok；请求 ID 可在 /api/admin/requests/{id}/attempts 查看两条记录。")
    return 0


def _provider_id(client: httpx.Client) -> str:
    providers = _request(client, "GET", "/api/admin/providers")
    found = _find(providers, "name", "mock")
    if found is None:
        found = _request(client, "POST", "/api/admin/providers", json=PROVIDER)
    return found["id"]


if __name__ == "__main__":
    sys.exit(main())
