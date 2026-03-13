# 生存行动计划 v2 — 2026.03.11

> 基于市场研究、资产评估、竞品分析的综合决策

## 核心判断

**问题**：月缺口 -5000 RMB，AI费用2个月runway，必须在4-6周内产生额外收入。

**关键发现**：
1. Upwork AI Agent开发时薪 $175-$300/hr，AI技能需求同比增长 109%
2. Chatbase（solo founder）6个月做到 $64K MRR，2个月MVP
3. SiteGPT 上线首月 $10K MRR，靠Twitter病毒式传播
4. Ying已有完整的 YepAI（Shopify AI SaaS）生产级经验 — 这是最大的竞争优势
5. Fiverr AI聊天机器人项目 $200-$5000/项目，月维护 $500-$2000

**决策**：聚焦两条线，不分散。

---

## 第一条线：Upwork接单（最快变现，本周启动）

**目标**：4周内获得第一笔收入，8周达到 $3000+/月

### 第一步（今天 → 3月14日）
- [ ] 注册Upwork账号（用真名、专业照片）
- [ ] 按 upwork-profile-draft.md 完善个人资料
- [ ] 准备3个作品截图：YepAI Dashboard、MyAgent系统、ShopifyAPI
- [ ] 设定起步价 $45/hr

### 第二步（3月15日 → 3月31日）
- [ ] 每天发送5-10个定制提案
- [ ] 重点搜索关键词：AI chatbot, Claude API, Shopify AI, RAG system, AI agent, n8n automation
- [ ] 接1-2个小项目（$200-$500）快速积累评价
- [ ] 所有交付提前完成，主动沟通，争取5星

### 第三步（4月 → 5月）
- [ ] 3+好评后提价到 $60/hr
- [ ] 申请长期合同（按时计费）
- [ ] 目标：20-30 billable hours/week × $60 = $4800-$7200/月

### Upwork热门品类（按溢价排序）
1. AI Agent开发（LangChain/CrewAI）— $175-$300/hr
2. RAG系统搭建（pgvector/Pinecone）— $80-$150/hr
3. AI聊天机器人（WhatsApp/Shopify/Web）— $50-$80/hr
4. AI自动化工作流（n8n + Claude/GPT）— $40-$80/hr
5. Shopify应用开发（含AI功能）— $40-$70/hr

---

## 第二条线：Shopify AI聊天机器人 Micro SaaS（中期变现）

**为什么选这个**：
- Ying 已经在 YepAI 工作，拥有完整的 Shopify + AI chatbot 技术栈
- Chatbase/SiteGPT 验证了市场（$8M+ ARR）
- 但它们是通用方案，**没有人专门为Shopify做深度集成**
- Shopify有 200万+ 活跃商家，这是一个巨大的利基市场

**产品定位**：ShopBot — AI Customer Service for Shopify（一键安装，无需配置）

### 与竞品的差异化
| 维度 | Chatbase/SiteGPT | ShopBot（我们） |
|------|------------------|----------------|
| 安装 | 需要手动嵌入代码 | Shopify应用商店一键安装 |
| 数据源 | 手动上传PDF/网页 | 自动同步Shopify产品、订单、FAQ |
| 功能 | 通用问答 | 订单查询、产品推荐、购物车追回 |
| 价格 | $19-$99/月 | $29-$79/月 |
| 集成 | 无 | 原生Shopify Admin + HubSpot |

### 技术栈（全部已掌握）
- 前端：React + Tailwind（Shopify Polaris可选）
- 后端：Python FastAPI 或 NestJS
- AI：Claude API / OpenAI API + RAG
- 数据库：PostgreSQL + pgvector
- 部署：Docker + 任意VPS

### 开发计划
| 周 | 里程碑 | 交付物 |
|----|--------|--------|
| W1-2 | MVP核心 | Widget嵌入 + 基础问答 + Shopify产品同步 |
| W3-4 | 关键功能 | 订单查询 + 产品推荐 + 管理后台 |
| W5-6 | 商用准备 | 计费系统 + Landing Page + 文档 |
| W7-8 | 上线推广 | Shopify App Store提交 + ProductHunt |

### 变现路径
1. **免费层**：每月100条消息，吸引安装量
2. **Pro $29/月**：无限消息 + 3个数据源
3. **Business $79/月**：多语言 + HubSpot集成 + 订单追踪
4. **Enterprise $199/月**：自定义训练 + API访问 + 优先支持

### 获客策略（零成本）
- [ ] Shopify社区发帖分享AI聊天机器人案例
- [ ] Reddit r/shopify, r/ecommerce 提供免费诊断
- [ ] Twitter/X 发布Shopify AI案例研究（效仿SiteGPT的病毒式传播）
- [ ] 找5个Shopify店主提供免费试用换评价

---

## 时间分配

| 时间段 | 活动 | 优先级 |
|--------|------|--------|
| 工作日白天 | YepAI/Vanka外包工作（保住基本收入） | 必须 |
| 工作日晚上 7-10pm | Upwork提案 + 项目交付 | 最高 |
| 周末 | ShopBot MVP开发 | 高 |
| 碎片时间 | 研究Upwork需求 + 社交媒体发帖 | 中 |

---

## 财务目标

| 时间 | Upwork收入 | ShopBot收入 | 月总额外收入 | 是否存活 |
|------|-----------|------------|-------------|---------|
| 3月 | $0 | $0 | 0 | 消耗储备 |
| 4月 | $1000-$2000 | $0 | 7000-14000 RMB | 接近盈亏平衡 |
| 5月 | $3000-$5000 | $0 | 21000-35000 RMB | 安全 |
| 6月 | $3000-$5000 | $500-$1000 | 24500-42000 RMB | 舒适 |
| 7月+ | $4000+ | $2000+ | 42000+ RMB | 加速还债 |

---

## 立即执行的第一步

**今天（2026.03.11）必须完成的3件事：**

1. 注册Upwork账号 → https://www.upwork.com/nx/signup/
2. 完善个人资料（参考 upwork-profile-draft.md）
3. 准备3张作品截图（YepAI Dashboard、MyAgent、ShopifyAPI）

**本周必须完成的3件事：**

1. 在Upwork发送20+个定制提案
2. 创建 ShopBot 项目目录结构
3. 在 r/shopify 发一篇"How I built an AI chatbot for Shopify"帖子

---

## 风险对冲

| 风险 | 对策 |
|------|------|
| Upwork 2周没拿到项目 | 降价到$35/hr，扩展到中国平台（猪八戒、程序员客栈） |
| ShopBot 开发太慢 | 先做Landing Page收集waitlist，验证需求 |
| AI费用耗尽 | 切换到免费/便宜的模型（DeepSeek、Qwen），减少Agent使用 |
| 外包工作占满时间 | 只做Upwork最高价值的项目，宁可少做高价不做低价 |

---

## 竞品参考

| 产品 | 创始人类型 | MRR | 到达时间 | 关键成功因素 |
|------|-----------|-----|---------|-------------|
| Chatbase | Solo founder | $64K → $8M ARR | 6个月 | 早期入场 + 简单好用 + 零融资 |
| SiteGPT | Solo (24岁) | $20K+ | 首月$10K | Twitter病毒传播，Day1 1.5万访客 |
| PDF.ai | Small team | ~$80K | 几个月 | 优质域名 + 极简功能 |
| Photo AI | Pieter Levels | $132K | 18个月 | 创始人个人IP + Twitter |
| Cameron(AI营销) | Solo | $62K | 90天 | 辞职全力冲刺 + 精准定位 |

**成功公式**: 早入场 + 明确痛点 + ≤2周MVP + 单一获客渠道All-in

**Shopify生态数据**: 应用开发者总收入累计 $15亿+，头部年收入 $16.7万。
但超$500万/月的应用都不是靠商店自然流量，而是代理商/KOL/销售团队。

**我们的差异化**：这些都是通用AI聊天方案。没有一个是为 Shopify 深度定制的。
Shopify商家需要的是：自动同步产品目录、回答订单状态、推荐商品、处理退换货 — 这些Chatbase都做不到。
获客策略应侧重：Reddit/Twitter内容营销 + Shopify社区 + 早期免费试用换评价。

---

*计划制定时间：2026-03-11 10:25*
*竞品数据更新：2026-03-11 10:30*
*下次review：2026-03-18*
*目标：活下来，然后活得好*
