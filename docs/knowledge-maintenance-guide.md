# ForeverFurEver 知识库维护指南

## 概览

我们的客服 Agent 依赖知识库来回答客户问题。知识内容统一在 **Notion** 中编辑，编辑完成后通过一条命令同步到 Agent。

```
Notion 编辑内容 → 触发同步 → Agent 使用最新知识
```

---

## 1. 在 Notion 中编辑知识

### 打开知识库

登录 Notion，找到 **Knowledge Base** 数据库。你会看到 5 篇知识文档：

| 标题 | 分类 | 说明 |
|------|------|------|
| About ForeverFurEver | brand | 品牌故事 |
| TravelStar Companion – Product Overview | product | TravelStar 产品知识 |
| Eternal Glow – Product Overview | product | Eternal Glow 产品知识 |
| FAQ | faq | 常见问题 |
| How to Use & Care | care | 使用与保养 |

### 编辑现有内容

1. 点击任意一行，打开页面
2. 直接编辑正文内容（支持标题、列表、加粗等常用格式）
3. 编辑完成后无需额外保存，Notion 自动保存

### 添加新知识文档

1. 在数据库中点击 **+ New** 新建一行
2. 填写 **Title**（标题）
3. 选择 **Category**（分类）：brand / product / faq / care
4. 将 **Status** 设为 **Published**
5. 在页面正文中写入知识内容

> **注意：** 只有 Status 为 **Published** 的文档才会被同步。如果内容还没写完，可以先设为 **Draft**。

### 暂时隐藏某篇内容

将该文档的 Status 改为 **Draft**，下次同步时 Agent 就不会包含这篇内容。

---

## 2. 同步到 Agent

编辑完成后，需要触发一次同步，Agent 才会使用最新内容。

### 方法一：网页按钮同步（推荐）

1. 在浏览器打开：`https://foreverfurever-agent.onrender.com/admin`
2. 输入管理员密码
3. 点击 **「同步知识库」**
4. 页面会显示同步结果（成功/跳过/出错的文档）

### 方法二：命令行同步

```bash
curl -X POST https://foreverfurever-agent.onrender.com/admin/sync-knowledge \
  -H "Authorization: Bearer foreverfurever2026"
```

### 同步结果说明

- **synced** — 成功同步的文档
- **skipped** — 跳过的文档（空内容或非 Published 状态）
- **errors** — 出错的文档（如有，联系开发者）

---

## 3. 内容编写规范

为了让 Agent 能准确理解和引用知识，请遵循以下规范：

### 格式建议

- 用 **标题**（H1/H2/H3）划分章节，Agent 会按章节检索
- 用 **列表** 列举要点，比大段文字更容易被准确引用
- 重要信息用 **加粗** 标注（如价格、时间、政策）

### 内容建议

- 用客户能理解的语言，避免内部术语
- 回答要完整，包含客户可能追问的细节
- 数字信息要准确（价格、天数、尺寸等）
- 每个 FAQ 条目用 "Q: xxx" 格式的标题，方便 Agent 匹配问题

### 避免

- 不要放内部备注或开发笔记
- 不要放图片（Agent 无法读取图片内容）
- 不要在正文中放 Notion 的 callout/toggle 等特殊块（可能无法正确转换）

---

## 4. 常见问题

### Q: 编辑后忘了同步怎么办？

没关系，Notion 的修改不会丢失。随时都可以再触发同步。

### Q: 同步会覆盖之前的内容吗？

会。每次同步会用 Notion 最新内容替换本地文件，然后重建索引。

### Q: 可以同时编辑吗？

可以。多人可以同时在 Notion 中编辑不同文档，同步时会拉取所有最新内容。

### Q: Last Synced 字段是什么？

每次同步成功后，该字段会自动更新为同步时间，方便你确认哪些文档已同步。

### Q: 新增的文档需要改代码吗？

如果新文档的分类是已有的（brand/product/faq/care），不需要改代码，直接同步即可。
