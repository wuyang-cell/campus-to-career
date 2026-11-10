# 各平台搜索技术方法详解

> 汇总自 9 个技能源的方法提炼：boss-cli、agentbay boss-job-search、boss-job-recommand (CDP)、ai-job-hunter、job-hunter-new2、liepin-cli、liepin-job-hunter、tiandao-job-hunter、job-advisor。

## 一、方式1：CLI 工具

### boss-cli（BOSS直聘，最完整的结构化方案）

安装与认证：

```bash
uv tool install kabi-boss-cli        # 或 pipx install kabi-boss-cli
boss login                           # 从 10+ 浏览器自动提取 cookie
boss login --cookie-source chrome    # 指定浏览器
boss login --qrcode                  # Boss App 扫码
boss status --json                   # 检查登录态
```

搜索与筛选：

```bash
boss search "golang" --city 杭州 --salary 20-30K --json
# 筛选参数：--city / --salary(3K以下…50K以上) / --exp(1-3年…) / --degree(大专…博士)
#           --industry(互联网/人工智能…) / --scale(0-20人…10000人以上) / --stage(已上市…) / --job-type(全职/兼职/实习)
boss show <index>                    # 查看上次搜索第 N 条
boss detail <securityId> --json      # 完整 JD（skills/salaryDesc/jobInfo）
boss export "Python" -n 100 --format json -o jobs.json
boss recommend --json                # 个性化推荐
```

关键运维经验：
- 输出信封：数据在 `.data` 下；Rich 输出走 stderr，管道安全
- `__zp_stoken__` 过期 → `boss logout && boss login`
- rate_limited（code=9）→ 内置冷却 10s→20s→40s→60s 自动恢复
- **禁止并行请求**（内置高斯抖动延迟保护账号）
- 已知限制：发消息、改简历、公司页搜索不可用；BOSS 薪资在部分接口被服务端隐藏

### liepin-cli（猎聘）

```bash
liepin-cli job search --job-name "Java开发" --address "北京" --salary-floor 25 --page 0 --output json
liepin-cli resume get --output json
liepin-cli job apply --job-id 123456 --job-kind 2 --output json   # job-kind 必须复用搜索返回值
# token 优先级：--token > LIEPIN_USER_TOKEN > ~/.config/liepin-cli/config.json
# token 过期：liepin-cli auth open && liepin-cli auth setup
```

## 二、方式2：HTTP 直接抓取

### 猎聘

模板 A（城市页，推荐）：
```
https://www.liepin.com/city-{城市码}/zp{URL编码关键词}/?currentPage={页码从1}
```

模板 B（搜索页，支持薪资与排序）：
```
https://www.liepin.com/search/?dqs={dqs码}&key={关键词}&compsalary={下限},100&sortFlag=15&d_pageSize=40&d_curPage={页码从0}
```
- `sortFlag=15` = 按最新发布排序（活跃优先的关键参数）
- `compsalary=25,100` = 25K 以上

城市码（拼音缩写）：北京bj 上海sh 广州gz 深圳sz 杭州hz 成都cd 南京nj 武汉wh 西安xa 重庆cq 天津tj 苏州sz2 长沙cs 郑州zz 东莞dg 沈阳sy 青岛qd 合肥hf 佛山fs 昆明km 大连dl 福州fz 厦门xm 济南jn 等

dqs 数字码：北京010 上海020 深圳030 广州050000 杭州050020 南京060000 苏州070000 西安080020 成都090020 武汉180020

解析选择器（多级兜底）：
```
卡片: div.job-detail-wrap | div.so-job-item | [class*='job-card']
标题: .job-title | h3 | [class*='title']
公司: .company-name | [class*='company-name'] | .employer-name
薪资: .job-salary | [class*='salary']
地区: .job-area | [class*='area'] | [class*='district']
学历: [class*='edu'] | [class*='degree']
经验: [class*='experience'] | [class*='year']
```

### 智联招聘

```
https://sou.zhaopin.com/?jl={城市码}&kw={关键词}&p={页码}
```
城市码：北京530 上海538 广州763 深圳765 杭州653 成都801 南京635 武汉736 西安854 重庆854 天津531 苏州636 长沙749 郑州719 东莞768 沈阳565 青岛609 合肥571 佛山769 昆明782 大连588 福州681 厦门682 哈尔滨586 济南613 等

### BOSS直聘 CDP 直连（子分支，需用户配合）

```bash
# 独立 Chrome 开 CDP 9222，已登录 BOSS
python3 boss_cdp_raw.py --keyword "Java" --city 101210100 --pages 3
python3 boss_cdp_raw.py --keyword "Java" --scale 305 --salary 406   # 规模/薪资筛选
python3 boss_cdp_raw.py --keyword "Java" --detail --max-details 10  # 附 JD 详情
```
- API：`GET /wapi/zpgeek/search/joblist.json?query=&city=&page=`
- 城市/岗位辅助数据：`/wapi/zpgeek/search/job/hot/city.json`、`/wapi/zpCommon/data/cityGroup.json`
- 上限：单次 ≤10 页、≤500 请求
- 城市气象码：全国100010000 北京101010100 上海101020100 广州101280100 深圳101280600 杭州101210100 天津101030100 西安101110100 苏州101190400 武汉101200100 长沙101250100 成都101270100 郑州101180100 重庆101040100 等（完整表可从 cityGroup.json 拉取）

### 通用反爬策略

- UA 伪装桌面 Chrome + `Accept-Language: zh-CN,zh;q=0.9`
- 随机延迟 `random.uniform(2, 5)` 秒；渐进式延迟（第 n 次请求等待 min(2 + 0.5n, 10) 秒）
- 失败重试前先换方式，不要硬刚
- 猎聘反爬较强，HTTP 抓不动直接转方式3 聚合

## 三、方式3：搜索引擎聚合

```
site:zhipin.com {岗位} {城市} 招聘
site:liepin.com {岗位} {城市} 招聘
site:zhaopin.com {岗位} {城市} 招聘
site:lagou.com {岗位} {城市}
site:huibo.com {岗位} {城市} 招聘
site:51job.com {岗位} {城市} 招聘
site:eleduck.com {岗位} 远程
site:v2ex.com 酷工作 {岗位}
site:xiaomifeng.work {技能}
```

- recency 过滤默认 week；BOSS 结果优先取有明确薪资区间的（过滤广告位）
- 每平台 ≤3 query、每 query 取前 5 条、总量 ≤20 次搜索
- site: 失败 → 去掉 site: 用 "平台名 岗位 城市 招聘"
- 摘要字段抽取：title / company / location / pay / skills / link；缺 title/pay 则丢弃计数

## 四、方式4/5：单点 WebFetch 与人工

- WebFetch 每平台 ≤3 条高价值详情页，提取完整 JD
- 智联静态结构多，WebFetch 成功率较高；BOSS/拉勾是动态 SPA，失败属正常
- 云沙箱浏览器（阿里云百炼 wuying-agentbay-sdk `browser_latest` 镜像，`agent.browser.execute_task` 自然语言步骤驱动）可作为有 API key 时的增强备选；任务模板：
  ```
  1. 前往 zhipin.com 2. 搜索框输入关键词 3. 点搜索 4. 设筛选条件
  5. 遍历前 15 条，提取 职位/公司/规模/薪资/地点/发布时间/简介 6. markdown 返回
  ```
  注意：耗时 1-2 分钟，勿重试；验证码需人工；控制台会打印流化可视链接。

## 五、平台特性速查

| 平台 | 特点 | 适用 |
|---|---|---|
| BOSS直聘 | 更新快、中小公司多、直聊 | 互联网/科技/创业公司 |
| 猎聘 | 中高端、猎头多 | 5年+ 经验、高薪岗 |
| 智联 | 传统行业覆盖广、静态页可抓 | 国企/央企/金融/制造 |
| 拉勾 | 互联网垂直、JD 质量高 | 技术岗/产品岗 |
| 汇博 | 重庆/西南集中 | 西南区域求职 |
| 51job | 长三角/珠三角 | 制造/外贸/综合 |
| 电鸭/V2EX/小蜜蜂 | 远程/自由职业 | 远程需求 |
