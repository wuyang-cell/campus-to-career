#!/usr/bin/env python3
"""
跨平台去重合并 + 清单渲染（纯标准库，无第三方依赖）
用法：
  python3 dedup_merge.py --input merged.json --out final.json --format md
merged.json: 各平台采集结果拼接的数组，元素含
  title/company/salary/location/experience/education/job_desc/activity/sources/crawl_time
"""
import argparse
import json
import re
import sys
from datetime import datetime

COMPANY_SUFFIX = re.compile(r"(有限公司|有限责任公司|股份有限公司|集团有限公司|集团)$")
BRACKETS = re.compile(r"[（(【\[][^）)】\]]*[）)】\]]")
LEVEL_WORDS = ("初级", "高级", "资深", "专家", "junior", "senior", "lead", "staff")


def norm(text):
    if not text:
        return ""
    t = str(text).strip().replace("\u3000", " ").replace(" ", "").lower()
    t = BRACKETS.sub("", t)
    return t


def norm_company(text):
    t = norm(text)
    prev = None
    while prev != t:
        prev = t
        t = COMPANY_SUFFIX.sub("", t)
    return t


def has_level_word(title):
    low = title.lower()
    return any(w in low for w in LEVEL_WORDS)


def salary_num(s):
    """取薪资下限（K）用于排序，面议返回 0"""
    if not s:
        return 0
    m = re.search(r"(\d+)-(\d+)", s)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 0


def norm_location(text):
    if not text:
        return ""
    t = norm(text)
    t = re.sub(r"[-·•,，/|]", "", t)
    t = re.sub(r"(市|区|县)$", "", t)
    return t


def merge_jobs(jobs):
    merged = {}
    order = []
    for j in jobs:
        key = f"{norm_company(j.get('company'))}|{norm(j.get('title'))}|{norm_location(j.get('location'))[:6]}"
        if key not in merged:
            j["_key"] = key
            j.setdefault("sources", [])
            merged[key] = j
            order.append(key)
        else:
            old = merged[key]
            for s in j.get("sources", []):
                if s not in old["sources"]:
                    old["sources"].append(s)
            if len(j.get("job_desc", "")) > len(old.get("job_desc", "")):
                old["job_desc"] = j["job_desc"]
            if j.get("activity") and not old.get("activity"):
                old["activity"] = j["activity"]
            if salary_num(j.get("salary")) > salary_num(old.get("salary")) and j.get("salary"):
                old["salary"] = j["salary"]
            if j.get("crawl_time", "") > old.get("crawl_time", ""):
                old["crawl_time"] = j["crawl_time"]
    return [merged[k] for k in order]


def sort_jobs(jobs):
    def score(j):
        multi = 2 if len(j.get("sources", [])) >= 2 else 0
        salary_known = 1 if salary_num(j.get("salary")) > 0 else 0
        return (multi, salary_known, salary_num(j.get("salary")))
    return sorted(jobs, key=score, reverse=True)


def render_md(jobs, meta=None):
    lines = []
    if meta:
        lines.append(f"# 岗位搜索清单 — {meta.get('keyword', '')} · {meta.get('city', '')} · {datetime.now():%Y-%m-%d}")
        lines.append("")
        if meta.get("note"):
            lines.append(meta["note"])
            lines.append("")
    # 岗位速览表（不含 JD 列，避免表格被长文本撑爆）
    lines.append("## 岗位速览表")
    lines.append("")
    lines.append("| # | 招聘岗位 | 公司 | 薪资 | 地点 | 经验 | 活跃度 | 平台链接 |")
    lines.append("|---|---------|------|------|------|------|--------|---------|")
    for i, j in enumerate(jobs, 1):
        links = " ".join(f"[{s.get('platform', '')}]({s.get('url', '')})" for s in j.get("sources", []))
        lines.append(f"| {i} | {j.get('title','')} | {j.get('company','')} | {j.get('salary','面议')} | "
                     f"{j.get('location','')} | {j.get('experience','')} | {j.get('activity','未知')} | "
                     f"{links} |")
    lines.append("")
    # 岗位清单：每条内联完整 JD 原文，不做摘要，不设单独「JD 详情」章节
    lines.append("## 岗位清单（含完整 JD，按活跃度排序）")
    lines.append("")
    for i, j in enumerate(jobs, 1):
        links = " ｜ ".join(f"{s.get('platform','')}: {s.get('url','')}" for s in j.get("sources", []))
        lines.append(f"### {i}. {j.get('title','')} — {j.get('company','')}")
        lines.append(f"- 薪资：{j.get('salary','面议')} ｜ 地点：{j.get('location','')} ｜ "
                     f"经验：{j.get('experience','不限')} ｜ 学历：{j.get('education','不限')}")
        lines.append(f"- JD内容：{j.get('job_desc') or '（JD 需平台内查看，请点击链接登录后查看完整职责）'}")
        lines.append(f"- 链接：{links}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="各平台结果拼接的 JSON 数组文件")
    ap.add_argument("--out", help="去重后 JSON 输出路径")
    ap.add_argument("--format", choices=["md", "json"], default="json")
    ap.add_argument("--md-out", help="Markdown 清单输出路径")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        jobs = json.load(f)
    if isinstance(jobs, dict):
        jobs = jobs.get("jobs", [])

    before = len(jobs)
    merged = sort_jobs(merge_jobs(jobs))
    print(f"去重: {before} -> {len(merged)} 条（合并 {before - len(merged)} 条）", file=sys.stderr)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
    if args.format == "md" or args.md_out:
        md = render_md(merged)
        if args.md_out:
            with open(args.md_out, "w", encoding="utf-8") as f:
                f.write(md)
        else:
            print(md)

if __name__ == "__main__":
    main()
