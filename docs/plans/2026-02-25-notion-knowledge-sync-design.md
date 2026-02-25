# Notion Knowledge Base Sync — Design Document

**Status:** Approved
**Date:** 2026-02-25

---

## Background

ForeverFurEver Agent 的知识库目前以 `knowledge/` 目录下的 markdown 文件维护，编辑需要直接修改代码仓库。为了让 1-2 位非技术协作者也能方便地管理知识内容，引入 Notion 作为知识库编辑界面，通过 API 同步到 Agent。

## Approach

**Notion API 直接同步（手动触发）**

- Notion Database 作为知识编辑界面
- 管理员通过 API 端点手动触发同步
- 同步过程：Notion → Markdown → knowledge/ 目录 → ChromaDB 重建索引

选择该方案的原因：
- 更新频率低（每月 1-2 次），不需要自动定时任务
- 实现简单，维护成本低
- 支持协作者通过 Notion 编辑，无需接触代码

## Notion Database Structure

| Property    | Type   | Description            |
|-------------|--------|------------------------|
| Title       | Title  | 文档标题               |
| Category    | Select | brand / product / faq / care |
| Status      | Select | Draft / Published      |
| Last Synced | Date   | 上次同步时间           |

当前已有 5 条记录，对应现有 knowledge 文件：
1. About ForeverFurEver (brand)
2. TravelStar Companion (product)
3. Eternal Glow (product)
4. FAQ (faq)
5. How to Use & Care (care)

## Sync Flow

```
POST /admin/sync-knowledge
Authorization: Bearer <ADMIN_TOKEN>
         │
         ▼
  验证 ADMIN_TOKEN
         │
         ▼
  Notion API 查询 Status=Published 的页面
         │
         ▼
  逐页提取 Title + Body → 转 Markdown
         │
         ▼
  写入 knowledge/ 目录（文件名基于 Category + Title）
         │
         ▼
  更新 Notion 页面的 Last Synced 字段
         │
         ▼
  调用 index_all() 重建 ChromaDB 索引
         │
         ▼
  返回结果：synced / skipped / errors
```

## Technical Implementation

### New File: `ff_agent/notion_sync.py`

Core sync logic:
1. 使用 `notion-client` SDK 连接 Notion API
2. 查询 Database 中 Status = "Published" 的页面
3. 提取页面 Title 和 body blocks，转成 markdown
4. 写入 `knowledge/` 目录
5. 回写 Last Synced 时间到 Notion
6. 调用 `index_all()` 重建向量索引

### Modified File: `ff_agent/api_server.py`

新增端点：
- `POST /admin/sync-knowledge` — Bearer token 认证，触发同步

### Environment Variables

| Variable            | Description                          |
|---------------------|--------------------------------------|
| `NOTION_TOKEN`      | Notion Integration Secret (ntn_...) |
| `NOTION_DATABASE_ID`| 8253d66706364524b6ce88a42038fad9     |
| `ADMIN_TOKEN`       | 管理员 API 认证密钥（自定义）       |

### Dependencies

- `notion-client` 添加到 `requirements.txt`

## Out of Scope

- 自动定时同步（当前更新频率不需要）
- 双向同步（Agent → Notion）
- 知识文件版本控制 / diff
- Notion 富文本的完整格式保留（简化为 markdown）
