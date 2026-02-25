# ForeverFurEver Agent 全面优化设计文档

> 日期: 2026-02-25
> 状态: 已批准
> 版本: 从 v0.4.0 升级

## 1. 背景与目标

ForeverFurEver 是一个宠物纪念品电商网站 (https://foreverfurever.org)，基于 Shopify。
当前 AI 购物助手 (v0.4.0) 存在以下核心问题:

- **推荐不准**: 商品搜索策略粗糙，关键词提取简单
- **对话僵硬**: 意图路由和追问逻辑硬编码，无法适应多样化表达
- **覆盖面窄**: 只能处理有限的意图类型，复杂问题答不好
- **UI 引导局限**: 按钮硬编码为 "Urn vs Keepsake"，无法适应品类扩展
- **知识库薄弱**: 仅 1.4KB 的 markdown，覆盖 2 款核心产品
- **无持久化**: 内存存储，重启丢失

### 优化目标

1. Agent 从"硬编码路由"升级为"LLM 驱动决策"
2. 角色从"简单导购"升级为"全能客服"（导购 + 售后 + 政策 + FAQ）
3. LLM 从 GPT-4o-mini 切换到 Gemini
4. 知识库引入向量检索 (ChromaDB)
5. 前端升级为产品卡片 + 动态按钮
6. 对话持久化 (SQLite)
7. 具备品类扩展能力，新增产品不需要改代码

---

## 2. 核心 Agent 架构

### 2.1 LangGraph 状态图重构

从 7 个硬编码节点简化为 **3 个核心节点 + Tool 循环**:

```
用户消息 → [preprocess] → [agent] ←→ Tools → [postprocess] → 返回前端
```

#### GraphState 定义

```python
class GraphState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # 完整对话历史
    language: str          # "en" | "zh"，自动检测
    ui_actions: list[dict] # 前端动态按钮/卡片
    products: list[dict]   # 推荐的产品数据（含图片）
    thread_id: str         # 会话 ID
```

#### 节点职责

**preprocess**:
- 检测用户语言 (中/英)
- 将用户消息封装为 HumanMessage 加入 messages

**agent**:
- 调用 Gemini，带上 system prompt + tools 定义
- Gemini 自主决定: 直接回答 / 调用 tool / 追问用户
- 支持多轮 tool 调用 (搜索商品 → 查详情 → 生成推荐)
- LangGraph 的 ToolNode 自动处理 tool 调用循环

**postprocess**:
- 从 agent 回复中提取产品引用，构建产品卡片数据
- 生成动态 UI 按钮 (由 LLM 在回复中标记)
- 格式化最终响应

### 2.2 Tools 定义 (Gemini Function Calling)

```python
@tool
def search_products(query: str, max_results: int = 6) -> list[dict]:
    """Search the Shopify store for products.
    Returns: list of {title, handle, price, available, url, image_url}
    """

@tool
def get_product_details(handle: str) -> dict:
    """Get detailed info for a specific product including description,
    images, variants, and customization options.
    """

@tool
def get_store_policy(topic: str) -> str:
    """Query store policies. Topics: shipping, returns, customization, payment.
    """

@tool
def get_collection(collection_name: str) -> list[dict]:
    """Browse products by collection/category.
    """

@tool
def search_knowledge(query: str, category: str = "all") -> list[str]:
    """Search the knowledge base for brand info, policies, FAQ.
    Categories: policy, faq, brand, all.
    """
```

### 2.3 System Prompt

```
You are a customer service agent for ForeverFurEver (foreverfurever.org),
a pet memorial products store.

## Language
- Default to English
- Switch to Chinese if the user writes in Chinese

## Behavior
- Use the provided tools to search products, check policies, and answer questions
- ONLY recommend products returned by search_products or get_collection tools
- NEVER invent or hallucinate products that don't exist in the store
- When user needs are unclear, ask 1-2 clarifying questions (never more)
- Keep responses concise: 2-4 sentences for answers, bullet points for product lists

## Tone
- Warm, empathetic, and supportive (customers may be grieving)
- Professional but not overly formal
- Avoid overly cheerful language

## Capabilities
- Product recommendations and search
- Policy inquiries (shipping, returns, customization)
- Product customization guidance (text-only engraving)
- General store questions (FAQ)

## Constraints
- Do not process orders or payments
- Do not access customer account information
- Redirect complex complaints to human support: support@foreverfurever.org
```

---

## 3. 知识库与数据层

### 3.1 向量知识库 (ChromaDB + Gemini Embedding)

#### 知识文件结构

```
knowledge/
├── brand.md          # 品牌故事、使命、语气指南
├── policies.md       # 运费、退换货、定制流程
├── faq.md            # 高频问题标准答案
└── products.json     # 产品补充信息（使用场景、推荐话术）
```

#### 检索流程

```
用户提问 → Gemini Embedding API → query 向量
                                      ↓
                              ChromaDB 相似度搜索
                                      ↓
                              返回 top-3 相关片段
                                      ↓
                              注入 LLM context
```

#### 索引脚本

`ff_agent/index_knowledge.py`:
- 读取 `knowledge/` 下所有文件
- 按段落/FAQ 条目切分
- 调用 Gemini Embedding API 生成向量
- 写入 ChromaDB (持久化到 `data/chroma/`)
- 新增/修改知识后重新运行: `python -m ff_agent.index_knowledge`

#### search_knowledge Tool

```python
@tool
def search_knowledge(query: str, category: str = "all") -> list[str]:
    results = chroma_collection.query(
        query_texts=[query],
        n_results=3,
        where={"category": category} if category != "all" else None
    )
    return results["documents"][0]
```

### 3.2 持久化存储

| 数据 | 存储方案 | 说明 |
|------|---------|------|
| 对话历史 | SQLite (LangGraph SqliteSaver) | 替换 MemorySaver，重启不丢失 |
| 知识向量 | ChromaDB (磁盘持久化) | `data/chroma/` 目录 |
| 产品实时数据 | Shopify Storefront API | 实时查询，不缓存 |
| 对话日志 | SQLite + Python logging | 用于后续分析 |

---

## 4. 前端升级

### 4.1 产品卡片

Agent 推荐产品时，前端渲染结构化卡片而非纯文本:

```
┌──────────────────────────┐
│  [产品图片]               │
│  Eternal Glow             │
│  $47.00                   │
│  [View Product]           │
└──────────────────────────┘
```

后端返回 `products` 数组，每项含 `title, price, image_url, product_url`。

### 4.2 动态快捷按钮

不再硬编码。后端返回 `ui_actions` 数组:

```json
{
  "actions": [
    {"type": "quick_reply", "label": "Show me urns", "value": "I want to see urns"},
    {"type": "quick_reply", "label": "Under $50", "value": "Show items under $50"},
    {"type": "open_url", "label": "Browse All", "url": "https://foreverfurever.org/collections/all"}
  ]
}
```

前端根据 type 渲染不同组件:
- `quick_reply`: 可点击文字芯片，点击后发送 value 作为用户消息
- `open_url`: 外链按钮，新窗口打开

### 4.3 交互增强

- "Agent is typing..." 加载动画
- 消息渐入动画
- 产品卡片横向滚动（多个产品时）
- 移动端响应式适配

### 4.4 技术选择

保持原生 HTML/CSS/JS，不引入框架。原因:
- 作为 Shopify 嵌入 widget，需要轻量
- 避免与 Shopify 主题样式冲突
- 当前规模不需要框架

---

## 5. API 设计

### 5.1 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `POST /chat` | 对话主接口 | 升级响应结构 |
| `GET /health` | 健康检查 | 不变 |
| `GET /` | 聊天 UI | 升级后的前端 |
| `POST /feedback` | 用户反馈 | 收集 helpful/not helpful |

### 5.2 POST /chat 响应结构

```json
{
  "type": "answer | error",
  "content": "Here are some memorial options within your budget...",
  "products": [
    {
      "title": "Eternal Glow",
      "handle": "eternal-glow",
      "price": "$47.00",
      "image_url": "https://cdn.shopify.com/...",
      "product_url": "https://foreverfurever.org/products/eternal-glow",
      "available": true
    }
  ],
  "actions": [
    {"type": "quick_reply", "label": "Tell me more about this", "value": "Tell me more about Eternal Glow"}
  ],
  "thread_id": "uuid-here",
  "version": "1.0.0"
}
```

### 5.3 POST /feedback 请求

```json
{
  "thread_id": "uuid-here",
  "message_index": 3,
  "rating": "helpful | not_helpful",
  "comment": "optional free text"
}
```

---

## 6. 部署

- **平台**: Render.com（不变）
- **数据库**: SQLite 文件（Render 持久磁盘）
- **向量库**: ChromaDB 持久化到 Render 磁盘
- **环境变量**:
  - 新增: `GEMINI_API_KEY`
  - 移除: `OPENAI_API_KEY`
  - 保留: `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_STOREFRONT_TOKEN`

---

## 7. 实施阶段

| Phase | 内容 | 依赖 |
|-------|------|------|
| **Phase 1** | 核心 Agent 重构 (LangGraph 3节点 + Gemini + Tools) | 无 |
| **Phase 2** | 知识库 (ChromaDB + Embedding + 知识文件) | Phase 1 |
| **Phase 3** | 前端升级 (产品卡片 + 动态按钮 + 交互) | Phase 1 |
| **Phase 4** | API 升级 + 持久化 + 反馈 + 部署 | Phase 1-3 |

---

## 8. 文件结构（重构后）

```
ForeverFurEver-Agent/
├── ff_agent/
│   ├── __init__.py
│   ├── api_server.py           # FastAPI 服务 (升级)
│   ├── graph.py                # LangGraph 状态图 (重写)
│   ├── tools.py                # Tool 定义 (新增)
│   ├── shopify_storefront.py   # Shopify API (升级，增加图片/详情)
│   ├── knowledge.py            # ChromaDB 知识检索 (新增)
│   ├── index_knowledge.py      # 知识库索引脚本 (新增)
│   └── prompts.py              # System prompt 管理 (新增)
├── knowledge/
│   ├── brand.md                # 品牌知识 (新增)
│   ├── policies.md             # 政策知识 (新增)
│   ├── faq.md                  # FAQ (新增)
│   └── products.json           # 产品补充信息 (新增)
├── static/
│   └── chat.html               # 聊天 UI (重写)
├── data/
│   ├── chroma/                 # ChromaDB 持久化 (自动生成)
│   └── conversations.db        # SQLite 对话历史 (自动生成)
├── scripts/
│   └── regression_suite.py     # 测试 (更新)
├── docs/
│   ├── 00_project_log.md
│   ├── 01_store_knowledge.md   # 保留作参考
│   └── plans/
│       └── 2026-02-25-agent-optimization-design.md  # 本文档
├── requirements.txt            # 更新依赖
├── README.md
└── .env
```
