项目名称：ForeverFurEver B2C Shopify Agent（API 形式）

网站：foreverfurever.org

目标：为访客提供情感友好、信息准确的导购与客服问答，降低误解与下单犹豫

MVP 功能范围：

产品解释：强调“文字可定制”，不是宠物形象定制

FAQ/政策：发货、退换、定制规则

导购推荐：根据用途/预算/偏好推荐合适款式（先规则化）

暂不做（阶段 1-3 不做）：

不创建订单、不改价格、不生成优惠码

不触碰支付/个人隐私

技术选型（初版）：

FastAPI：提供 /chat 接口

GPT：生成自然语言回复

LangGraph：后续加入可控流程与记忆

数据：先用手工整理的 FAQ/产品要点，后续接 Shopify API

语言策略： - 默认使用英文回复，匹配网站主要用户; 当用户使用中文或明确请求中文时，Agent 自动切换为中文

**阶段 1：最小 API 跑通**
 - 目标：用 FastAPI 暴露 /chat，使 GPT 能被前端/网页调用
 - 实现：requirements + .env + api_server.py + uvicorn 启动
 - 收获：理解 request/response、如何把 LLM 作为后端服务封装
 - 下一步：加入品牌 Prompt 和“知识稿”约束回答（避免编造）
**阶段 2：品牌知识注入（非RAG）**
  - 目标：让 Agent 回答稳定、符合品牌语气，并避免编造商品信息
  - 方法：将店铺知识整理为 docs/01_store_knowledge.md，并在每次请求时注入到 system prompt
  - 语言策略：默认英文；检测到中文输入或明确要求中文时切换中文
  - 控制策略：降低 temperature；明确要求“只以 Store Knowledge 为准，不确定就说不确定”
  - 收获：在不引入向量库和检索的前提下，快速实现“可信且可控”的 MVP 版本
**阶段 3：引入 LangGraph（流程化对话）**
  - 目标：将单次问答升级为可控流程（Router → Answer），为后续 Clarify/Memory/Tools 打基础
  - 方法：使用 LangGraph StateGraph 定义状态，先用规则路由识别意图（policy/customization/product/other）
  - 输出：API 返回 content + intent，方便调试与前端展示
  - 收获：对话从“生成”变成“可编排系统”，行为更可控、更可解释
**阶段 3.5：Clarify（追问）节点**
  - 目标：当用户需求模糊时先追问关键参数，避免误答/乱推荐，提高导购体验与准确性
  - 方法：LangGraph 增加 check_clarify 分支，判断 needs_clarification 后走 clarify 或 answer
  - 输出：API 返回 type=clarify 或 type=answer，便于前端渲染不同交互
  - 收获：对话从“单轮问答”升级为“多轮引导式咨询”，更接近真实电商导购流程
**阶段 3.6：加入会话记忆（thread_id）**
  - 目标：支持多轮对话连贯，避免重复询问用户已提供的信息（预算/偏好/需求）
  - 方法：LangGraph compile 时启用 MemorySaver 作为 checkpointer，并在每次 invoke 传入 configurable.thread_id
  - API 设计：ChatRequest 增加 thread_id 字段；同一 thread_id 共享对话历史，不同 thread_id 相互隔离
  - 收获：Agent 从“单轮问答”升级为“可持续对话”，更贴近真实电商导购流程
**- 阶段 3.7：工程化记忆（Slot-based Profile）**
  - 目标：不保存全部聊天内容，而是抽取并持久化关键用户偏好（预算/用途/风格/时效/刻字语言与内容）
  - 方法：在 LangGraph 中增加 extract_profile 节点，用 LLM 输出结构化 JSON 并 merge 到 profile；check_clarify 与回答节点都基于 profile 决策与生成
  - API 辅助：返回 profile 作为 debug 字段，便于验证“记住了什么”
  - 收获：对话更连贯、追问更少、成本更可控，并且更符合产品级 Agent 的实现方式
**- 阶段 3.8：接入 Shopify Storefront API（真实商品推荐）**
  - 目标：推荐基于真实商品数据，禁止模型编造产品名/价格
  - 方法：通过 Headless channel 获取 Storefront token；后端使用 Storefront GraphQL 实现 search_products
  - 集成：在 answer 节点根据意图调用 search_products，把结果作为上下文提供给模型
  - 收获：Agent 从“会聊天”升级为“可导购、可落地”的电商推荐系统
**- 阶段 3.81：LangGraph 状态与意图路由**
  - 目标：router → profile → clarify/answer 的稳定流程
  - 改动：GraphState：user_message/intent/profile/answer/clarify 等;
         route_intent()：中英关键词轻量路由
         extract_profile()：从用户话里抽 budget/occasion 等
  - 验证：/chat 可稳定返回结构化 JSON（type/intent/content/profile）
**- 阶段 3.8.2：预算过滤（Budget-aware recommendations）**
  - 目标：用户给出预算时，只推荐预算内商品；无预算内商品则提示并提供少量超预算备选
  - 方法：解析 profile.budget → 过滤 Shopify products 列表 → 将预算过滤后的商品作为 ground truth 传入 LLM
  - 收获：推荐更可信、更贴近真实导购逻辑，减少“看起来懂但不符合预算”的问题
**- 阶段 3.8.3：模糊需求的轻量追问 + 同时给 1 个最佳建议**
  - 改动： Prompt 规则：先问 1 个关键问题（urn vs keepsake），同时给预算内 1 个建议
          输出更客服化：少标题、少废话、带链接 
  - 验证： “something under $60” → 先问品类 + 推荐 Eternal Glow
**- 阶段 3.9.：Quick Actions（Urn vs Keepsake 二选一按钮）**
  - 目标：当用户需要澄清品类时，用按钮替代打字，推进转化
  - 实现：后端规则生成 actions（不由 LLM 生成），检测回答是否包含“urn vs keepsake”澄清语
  - 行为：needs_choice 时返回两个 open_product 按钮（Urn / Keepsake）+ Browse all
  - 验收：回归测试 urn_budget 检测 actions 包含两个选项
- 阶段 3.9.1：Actions（快速选择按钮）
  - 实现：在 answer_node 内基于回答/用户输入规则生成 actions（不交给 LLM）
  - 结果：当出现“Urn vs Keepsake”澄清时，返回两个固定商品按钮 + Browse all
  - 保障：products_debug / tool_error / actions 永不缺失
**- 阶段 3.9.2（计划）：商品对比与购买决策引导**
  - 目标：从简单推荐升级为导购式建议
  - 核心能力：价格对比 + 使用场景匹配
  - 技术方式：LangGraph 增加 compare_and_rank 节点
**- 阶段 4.0：API Response Contract 固化**
  - 目标：后端输出稳定 schema，便于接任何前端/埋点/部署
  - 统一字段：type/intent/content/profile/actions/products_debug/tool_error/version
  - 新增 /health 用于部署自检
- 阶段 4.1：本地可视化聊天前端（Chat Widget MVP）
  - 实现：HTML + JS 调用 FastAPI /chat
  - 功能：聊天显示 + actions 按钮交互
  - 目的：模拟真实电商聊天导购体验
**## 4.2 Guided Shopping Flow: Gift vs Personal keepsake**
- Trigger: user provides budget but no occasion detected
- Behavior: agent asks one guided question (Gift vs Personal keepsake)
- UI: returns two `reply` actions as quick buttons
- Goal: reduce user effort, improve conversion-style conversation
4.3 Stage 4.3 — Choice-to-Profile Wiring (Gift vs Personal)
- Goal: Convert UI choices into structured user profile fields to stabilize recommendations.
- Change: Introduced a deterministic choice encoding for the occasion slot. 
- UI sends a fixed payload (e.g., #choice:occasion=gift or #choice:occasion=self) instead of relying on LLM extraction.
