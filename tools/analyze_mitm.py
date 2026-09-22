"""mitmproxy / Charles 抓包分析工具。

把抓到的 .flow / .har / .pcapng 文件丢给它,自动:
    1. 找出短剧平台相关的请求(api.* / search / video / play)
    2. 提取签名 header(常见: sign / X-Sign / X-Bogus / a-bogus)
    3. 导出 JSON 报告,方便逆向

依赖:pip install mitmproxy  (或只装这个脚本也行,纯 Python)

用法:
    python tools/analyze_mitm.py dump.flow > report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 短剧相关接口关键词
DOMAIN_PATTERNS = re.compile(
    r"(hongguo|hema|duanju|shortplay|xigua|douyin|bytedance|byteic|"
    r"snssdk|amemv|byteicp)\.",
    re.IGNORECASE,
)

PATH_PATTERNS = re.compile(
    r"(/api/|/v[0-9]+/|/api/v\d+/|/search|/video|/play|/drama|/episode|/detail)",
    re.IGNORECASE,
)

SIGN_HEADERS = {"sign", "x-sign", "x-bogus", "a-bogus", "x-livetime", "x-argus",
                "x-auth-signature", "authorization", "x-token", "x-tt-token"}


def analyze_flow_file(path: Path) -> list[dict]:
    """分析 mitmproxy 的 .flow 文件(JSON Lines 格式)。"""
    results = []
    if not path.exists():
        print(f"[!] 文件不存在: {path}", file=sys.stderr)
        return results

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            r = _parse_mitm_entry(entry, idx=i)
            if r:
                results.append(r)
    return results


def _parse_mitm_entry(entry: dict, idx: int) -> dict | None:
    """mitmproxy flow entry 的结构:
        {
          "type": "request",
          "request": {"method": ..., "url": ..., "headers": [...]},
          "response": {"status_code": ..., "content": {...}}
        }
    """
    if entry.get("type") not in ("request", "http"):
        return None
    req = entry.get("request") or {}
    url = req.get("url", "")
    if not (DOMAIN_PATTERNS.search(url) or PATH_PATTERNS.search(url)):
        return None
    headers = {h["name"].lower(): h["value"] for h in req.get("headers", [])}
    sig_headers = {k: v for k, v in headers.items() if k in SIGN_HEADERS}
    resp = entry.get("response") or {}
    body_preview = ""
    try:
        c = resp.get("content", {})
        text = c.get("text", "")
        if isinstance(text, str) and len(text) < 500:
            body_preview = text
        elif text:
            body_preview = f"<{c.get('size', len(text))} bytes>"
    except Exception:
        pass
    return {
        "idx": idx,
        "method": req.get("method"),
        "url": url,
        "sign_headers": sig_headers,
        "user_agent": headers.get("user-agent", ""),
        "referer": headers.get("referer", ""),
        "status": resp.get("status_code"),
        "body_preview": body_preview,
    }


def main():
    ap = argparse.ArgumentParser(description="短剧平台抓包分析工具")
    ap.add_argument("flow", type=Path, help="mitmproxy dump 文件(.flow)")
    ap.add_argument("--out", type=Path, default=None, help="输出 JSON 报告")
    args = ap.parse_args()

    print(f"[>] 读取 {args.flow} ...", file=sys.stderr)
    results = analyze_flow_file(args.flow)
    print(f"[>] 命中短剧相关请求 {len(results)} 条", file=sys.stderr)

    report = {"summary": {"total_hits": len(results)}, "requests": results}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"[>] 写入 {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()