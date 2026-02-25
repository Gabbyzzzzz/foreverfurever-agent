# 📘 ForeverFurEver B2C Shopify Agent — Project Log

项目名称：ForeverFurEver B2C Shopify Agent（API 架构）

官网：[https://foreverfurever.org](https://foreverfurever.org)

目标（Goal）
为访客提供情感友好、信息准确的导购与客服问答，减少误解、降低下单犹豫，提高转化体验。

---

## 🎯 MVP 功能范围

### 已覆盖

• 产品解释：强调「文字可定制（TEXT-ONLY personalization）」而非宠物形象定制
• FAQ/政策解答：发货、退换、定制规则
• 导购推荐：基于用途、预算、偏好推荐真实商品
• 多轮对话引导：澄清需求 → 推荐 → 快捷选择

### 暂不做（阶段 1–3 不涉及）

• 不创建订单
• 不修改价格
• 不生成优惠码
• 不触及支付与隐私数据

---

## 🧱 技术选型（初版）

• Backend：FastAPI
• LLM：GPT 系列模型
• Agent Orchestration：LangGraph
• 数据源：手工知识文档 + Shopify Storefront API
• Frontend：HTML + JS Chat Widget

语言策略：
默认英文回复（English-first），检测到中文输入时自动切换中文。

---

# 🚀 阶段演进记录

---

## Stage 1 — 最小 API 跑通（LLM Serviceization）

目标：
通过 FastAPI 暴露 /chat 接口，让 GPT 能被前端调用。

实现：
• api_server.py
• uvicorn 启动服务
• 基础 request / response 封装

收获：
理解如何将大模型封装成可复用后端服务。

---

## Stage 2 — 品牌知识注入（Non-RAG）

目标：
让回答稳定可信，避免编造产品信息。

方法：
• docs/01_store_knowledge.md
• 每次请求注入 system prompt
• 明确规则：只基于 Store Knowledge 回答

控制策略：
• 低 temperature
• 不确定就说明不确定

收获：
无需引入向量库，即实现可控知识问答 MVP。

---

## Stage 3 — LangGraph 流程化对话系统

目标：
从单轮问答升级为可编排 Agent 流程。

实现：
• StateGraph 定义状态
• router → answer 基础链路
• intent 分类：policy / customization / product / other

收获：
对话行为可控、可解释、可扩展。

---

## Stage 3.5 — Clarify 追问节点

目标：
当需求模糊时先追问关键参数。

实现：
• needs_clarification 判断
• clarify_node 生成简短追问

收获：
对话从问答升级为引导式咨询。

---

## Stage 3.6 — 会话记忆（thread_id）

目标：
支持多轮上下文。

方法：
• MemorySaver 作为 checkpointer
• 同一 thread_id 共享状态

收获：
避免重复询问用户信息。

---

## Stage 3.7 — Slot-based Profile Engineering

目标：
结构化保存用户关键偏好，而不是完整聊天记录。

抽取字段：
• budget
• occasion
• style
• deadline
• engraving_language
• engraving_text

实现：
• extract_profile 节点
• LLM 输出 JSON → merge 到 profile

收获：
成本更低、行为更稳定、工程级 Agent 设计。

---

## Stage 3.8 — Shopify Storefront API 接入

目标：
基于真实商品数据推荐，杜绝模型编造。

实现：
• Headless storefront channel
• GraphQL search_products
• Answer 节点实时查询商品

收获：
Agent 从“会聊天”升级为“真实导购系统”。

---

## Stage 3.8.2 — Budget-aware Recommendations

目标：
严格按预算推荐商品。

实现：
• 解析 profile.budget
• 过滤 Shopify 产品列表
• 预算内优先，超预算最多给 1 个备选

收获：
推荐逻辑贴近真实电商导购。

---

## Stage 3.8.3 — 模糊需求 + 轻量追问

行为优化：
当用户只给预算但未说明用途：

• 先问一个关键问题（Urn vs Keepsake）
• 同时给一个最佳预算内建议

输出风格：
简洁、客服化、带链接。

---

## Stage 3.9 — Quick Actions（快捷选择按钮）

目标：
用按钮替代输入，加快决策路径。

实现：
• 后端规则生成 actions
• 非 LLM 生成，保证稳定性

行为：
出现“Urn vs Keepsake”时返回：
• Urn 按钮
• Keepsake 按钮
• Browse all

验证：
回归测试确保 actions 始终存在。

---

## Stage 4.0 — API Response Contract 固化

统一返回结构：

```json
{
  type,
  intent,
  content,
  profile,
  actions,
  products_debug,
  tool_error,
  version
}
```

新增：
• /health 自检接口

收获：
前后端解耦，便于部署与扩展。

---

## Stage 4.1 — 本地可视化 Chat Widget

实现：
• HTML + JS 前端
• 实时调用 /chat
• 支持 action 按钮交互

目标：
模拟真实电商聊天体验。

---

## Stage 4.2 — Guided Shopping Flow

场景：
用户提供预算但未说明用途。

行为：
• Agent 提问：Gift vs Personal keepsake
• UI 返回两个快捷按钮

目标：
减少用户输入负担，提高转化式对话体验。

---

## Stage 4.3 — Choice-to-Profile Wiring

目标：
将 UI 选择转化为结构化用户偏好。

实现：
• 前端发送固定 payload（如 #choice:occasion=gift）
• 后端直接写入 profile slot
• 不再依赖 LLM 抽取

收获：
推荐逻辑更稳定、确定性更强。

---

## Stage 4.4 — Shopify 嵌入 + CORS 支持

实现：
• FastAPI CORS middleware
• 允许 storefront domain 访问
• Render 部署 + Shopify 页面集成

结果：
Agent 可直接运行在官网页面中。

---

# 📌 后续规划（Backlog）

• 商品对比与推荐排序（compare_and_rank 节点）
• 运营可控知识更新机制
• 轻量埋点与转化分析
• 高并发与稳定性优化
