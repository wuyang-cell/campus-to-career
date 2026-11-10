#!/usr/bin/env python3
"""
全平台岗位搜索 — HTTP 直接抓取（方式2）
覆盖：猎聘（liepin）、智联（zhaopin）
依赖：pip3 install requests beautifulsoup4
用法：
  python3 scrape_platforms.py --platform liepin --keyword "AI产品经理" --city "北京" --pages 2
  python3 scrape_platforms.py --platform zhaopin --keyword "AI产品经理" --city "北京" --pages 2 --output jobs.json
失败（反爬/空结果/超时）时退出码 3，上层应降级到搜索引擎聚合（方式3）。
"""
import argparse
import json
import re
import sys
import time
import random
from datetime import datetime
from urllib.parse import quote

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: 请先安装依赖 pip3 install requests beautifulsoup4", file=sys.stderr)
    sys.exit(2)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

STOP_KEYWORDS = ["停止招聘", "已暂停", "已下线", "暂停招聘", "停止职位", "已结束"]

LIEPIN_CITY = {"北京": "bj", "上海": "sh", "广州": "gz", "深圳": "sz", "杭州": "hz", "成都": "cd",
               "南京": "nj", "武汉": "wh", "西安": "xa", "重庆": "cq", "天津": "tj", "苏州": "sz2",
               "长沙": "cs", "郑州": "zz", "青岛": "qd", "合肥": "hf", "大连": "dl", "厦门": "xm",
               "济南": "jn", "福州": "fz", "昆明": "km", "沈阳": "sy", "东莞": "dg", "佛山": "fs"}
LIEPIN_DQS = {"北京": "010", "上海": "020", "深圳": "030", "广州": "050000", "杭州": "050020",
              "南京": "060000", "苏州": "070000", "西安": "080020", "成都": "090020", "武汉": "180020"}
ZHAOPIN_CITY = {"北京": "530", "上海": "538", "广州": "763", "深圳": "765", "杭州": "653",
                "成都": "801", "南京": "635", "武汉": "736", "西安": "854", "重庆": "854",
                "天津": "531", "苏州": "636", "长沙": "749", "郑州": "719", "青岛": "609",
                "合肥": "571", "大连": "588", "厦门": "682", "济南": "613", "福州": "681"}

_req_count = 0

def polite_sleep():
    global _req_count
    _req_count += 1
    time.sleep(random.uniform(2, 5))

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        if r.status_code != 200 or len(r.text) < 500:
            return None
        return r.text
    except requests.RequestException:
        return None

def sel(card, *selectors):
    for s in selectors:
        el = card.select_one(s) if s else None
        if el:
            t = el.get_text(strip=True)
            if t:
                return t
    return ""

def is_stopped(*texts):
    return any(kw in t for t in texts for kw in STOP_KEYWORDS)

def scrape_liepin(keyword, city, pages, salary_floor):
    code = LIEPIN_CITY.get(city, "bj")
    jobs = []
    for page in range(1, pages + 1):
        if salary_floor and city in LIEPIN_DQS:
            url = (f"https://www.liepin.com/search/?dqs={LIEPIN_DQS[city]}&key={quote(keyword)}"
                   f"&compsalary={salary_floor},100&sortFlag=15&d_pageSize=40&d_curPage={page-1}")
        else:
            url = f"https://www.liepin.com/city-{code}/zp{quote(keyword)}/?currentPage={page}"
        html = fetch(url)
        polite_sleep()
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        cards = (soup.select("div.job-detail-wrap") or soup.select("div.so-job-item")
                 or soup.select("[class*='job-card']") or soup.select("[class*='job-card-pc']"))
        for c in cards:
            title = sel(c, ".job-title", "h3", "[class*='title']")
            company = sel(c, ".company-name", "[class*='company-name']", ".employer-name")
            if not title or not company or is_stopped(title, company):
                continue
            link_el = c.select_one("a[href]") or c.find_parent("a")
            href = link_el.get("href", "") if link_el else ""
            if href and not href.startswith("http"):
                href = "https://www.liepin.com" + href
            jobs.append({
                "title": title, "company": company,
                "salary": sel(c, ".job-salary", "[class*='salary']"),
                "location": sel(c, ".job-area", "[class*='area']", "[class*='district']"),
                "experience": sel(c, "[class*='experience']", "[class*='year']"),
                "education": sel(c, "[class*='edu']", "[class*='degree']"),
                "job_desc": "", "activity": "猎聘最新发布排序",
                "sources": [{"platform": "猎聘", "url": href}],
                "crawl_time": datetime.now().isoformat(timespec="seconds"),
            })
    return jobs

def scrape_zhaopin(keyword, city, pages, salary_floor):
    code = ZHAOPIN_CITY.get(city, "530")
    jobs = []
    for page in range(1, pages + 1):
        url = f"https://sou.zhaopin.com/?jl={code}&kw={quote(keyword)}&p={page}"
        html = fetch(url)
        polite_sleep()
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        cards = (soup.select("[class*='joblist-box'] a") or soup.select("[class*='positionList'] li")
                 or soup.select("[class*='job'] li"))
        seen = set()
        for c in cards:
            title = sel(c, "[class*='jobName']", "[class*='job-name']", "span[class*='name']", "h3")
            company = sel(c, "[class*='companyName']", "[class*='company-name']", "[class*='company']")
            if not title or not company or title in seen:
                continue
            seen.add(title)
            if is_stopped(title, company):
                continue
            href = c.get("href", "") if c.name == "a" else ""
            if href and not href.startswith("http"):
                href = "https://www.zhaopin.com" + href
            jobs.append({
                "title": title, "company": company,
                "salary": sel(c, "[class*='salary']", "[class*='money']"),
                "location": sel(c, "[class*='job-area']", "[class*='area']", "[class*='city']"),
                "experience": sel(c, "[class*='workExp']", "[class*='experience']"),
                "education": sel(c, "[class*='edu']", "[class*='education']"),
                "job_desc": "", "activity": "",
                "sources": [{"platform": "智联招聘", "url": href}],
                "crawl_time": datetime.now().isoformat(timespec="seconds"),
            })
    return jobs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=["liepin", "zhaopin"], required=True)
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--city", default="北京")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--salary-floor", type=int, default=0)
    ap.add_argument("--output")
    args = ap.parse_args()

    fn = scrape_liepin if args.platform == "liepin" else scrape_zhaopin
    jobs = fn(args.keyword, args.city, args.pages, args.salary_floor)

    if not jobs:
        print(f"WARN: {args.platform} 抓取 0 条（反爬/动态渲染），请降级到搜索引擎聚合（方式3）", file=sys.stderr)
        sys.exit(3)

    print(json.dumps(jobs, ensure_ascii=False, indent=2))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        print(f"OK: {len(jobs)} 条已写入 {args.output}", file=sys.stderr)

if __name__ == "__main__":
    main()
