# A股量化分析系统 — CRUD完整性 & 功能合理性 审查报告

> **审查日期**：2026-04-27 | **审查范围**：全系统12大模块 | **审查方式**：逐模块源码级审计  
> **结论先行**：系统核心功能链路完整可用，但存在 **2个🔴必修复项 + 5个🟡建议改进项 + 3个🟢可选优化项**

---

## 总体评价矩阵

| 模块 | Create | Read | Update | Delete | 合理性评级 | 问题数 |
|------|--------|------|--------|--------|-----------|--------|
| 1. 用户认证(注册/登录/个人中心) | ✅ | ✅ | ✅ | ⚠️缺 | 🟢 良好 | 1 |
| 2. 管理员后台-用户管理 | — | ✅ | ✅ | ✅ | 🟢 良好 | 0 |
| 3. 股票行情数据 | — | ✅(只读) | — | — | 🟢 设计如此 | 0 |
| 4. 自选股(Watchlist) | ✅ | ✅ | ❌缺 | ✅ | 🟡 有缺口 | 1 |
| 5. 分析记录(AnalysisRecord) | ✅ | ✅(profile页) | ❌缺 | ❌缺 | 🔴 不完整 | 1 |
| 6. AI对话(Conversation+Message) | ✅ | ✅ | ✅(重命名) | ✅ | 🟢 良好 | 1 |
| 7. 聊天记录(ChatHistory-Legacy) | ✅ | ✅(profile页) | ❌缺 | ❌缺 | 🟡 可接受 | 0 |
| 8. 新闻资讯 | — | ✅(只读) | — | — | 🟢 设计如此 | 0 |
| 9. 选股筛选 | — | ✅(查询接口) | — | — | 🟢 良好 | 1 |
| 10. 策略回测 | — | ✅(执行+结果) | — | — | 🟢 良好 | 0 |
| 11. 实时监控 | — | ✅(只读) | — | — | 🟢 良好 | 0 |
| 12. 系统日志(SystemLog) | ✅(自动写入) | ✅ | ❌缺 | ❌缺 | 🟡 可接受 | 1 |

---

## 逐模块详细分析

---

### 模块1：用户认证（auth_routes.py, 579行）

#### 已实现操作清单

| 操作 | 方法 | 路由 | 状态 | 说明 |
|------|------|------|------|------|
| **C - 注册** | POST | `/auth/register` | ✅ 完整 | 用户名/邮箱/密码二次确认 + **邮箱验证码强制校验** + 去重检查 + 密码强度>=6位 + 用户名>=3字符 |
| **R - 登录** | GET/POST | `/auth/login` | ✅ 完整 | 用户名或邮箱登录 + 记住我 + disabled/banned拦截 + 登录日志 + **限流5次/分钟**(防暴力破解) |
| **U - 个人资料修改** | POST | `/auth/profile/update` | ✅ 完整 | 昵称/手机/头像 修改 |
| **U - 密码修改** | POST | `/auth/profile/password` | ✅ 完整 | 当前密码校验 + 新密码强度校验 + 二次确认 |
| **U - 邮箱变更** | POST | `/auth/profile/email` | ✅ 完整 | 新邮箱验证码 + 占用检查 + 不能与当前相同 |
| **D - 退出登录** | GET | `/auth/logout` | ✅ 完整 | Session清除 + 日志记录 |
| **发送验证码** | POST | `/auth/send-verify-code` | ✅ 完整 | 支持 register/reset_password/change_email 三种类型 + 限流6次/分钟 |
| **忘记密码-Step1** | GET/POST | `/auth/forgot-password` | ✅ 完整 | 账号+邮箱校验 → 发送验证码 → Step2表单 |
| **忘记密码-Step2** | POST | `/auth/forgot-password/reset` | ✅ 完整 | 验证码校验 + 新密码确认 + 重置完成 |
| **个人中心概览** | GET | `/auth/profile` | ✅ 完整 | 展示自选股/分析记录/聊天记录概览统计 |

#### 缺失操作

| 操作 | 严重程度 | 说明 | 修复方案 |
|------|---------|------|---------|
| **D - 用户自行注销账号** | 🟡 建议 | 无"删除我的账号"功能。用户无法自行销毁账户，只能联系管理员删除。 | 新增 `POST /auth/delete-account`：需输入密码二次确认 → soft_delete(标记deleted_at)或hard delete → Session清除 → 重定向到首页并提示 |

#### 其他发现

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | `register`路由缺少 `@login_required` 的反向保护 | ⚪ 无需修 | 已有 `if current_user: redirect(profile)` 手动判断，功能等价 |
| 2 | 邮箱格式校验过于简单(`'@' in email and '.' in email`) | 🟡 建议 | 不符合RFC标准，但实际够用；可改用 `re.match(r'^[^@]+@[^@]+\.[^@]+$')` 或直接用 `email-validator` 库 |
| 3 | 注册无密码强度规则(仅长度>=6) | 🟡 建议 | 建议增加：必须包含字母+数字、禁止纯常见弱密码 |

**小结**：认证模块是系统中**实现最完善的模块之一**，安全措施到位（验证码、限流、密码哈希pbkdf2:sha256）。唯一明显缺失的是用户自主注销。

---

### 模块2：管理员后台-用户管理（admin_routes.py, 428行）

#### 已实现操作清单

| 操作 | 方法 | 路由 | 状态 |
|------|------|------|------|
| **R - 仪表盘** | GET | `/admin/` | ✅ 11项KPI统计卡片 + 最近12条日志时间线 |
| **R - 用户列表** | GET | `/admin/users` | ✅ 全量展示 + 关键字搜索(username/email模糊) |
| **R - 用户详情** | GET | `/admin/users/<id>` | ✅ 基本信息 + 自选股/分析记录/聊天记录三个子Tab(各10条) |
| **U - 启用/停用切换** | POST | `/admin/users/<id>/toggle-status` | ✅ active↔disabled切换 + **禁止操作自身账号** |
| **U - 状态精确设置** | POST | `/admin/users/<id>/set-status` | ✅ 支持active/disabled/banned三态 + 禁止操作自身 |
| **U - 角色升降级** | POST | `/admin/users/<id>/set-role` | ✅ user↔admin 切换 |
| **D - 删除用户** | POST | `/admin/users/<id>/delete` | ✅ 物理删除(cascade删除关联的watchlist/records/chats/conversations) + **禁止删除自身** |
| **R - 操作日志** | GET | `/admin/logs` | ✅ 类型+状态筛选 + 最新300条 |
| **R - 数据中心** | GET | `/admin/data` | ✅ 股票数量/分钟数据量统计 |
| **U - 手动数据同步** | POST | `/admin/data/sync-one` | ✅ 按代码+周期同步分钟线 |
| **R - 系统自检** | GET+POST | `/admin/system-check` + `/admin/api/system-check` | ✅ MySQL/Redis/Tushare/AkShare 四组件连通性检测 |

#### 发现的问题

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | 用户列表**无分页** | 🟡 建议 | `users()` 直接 `.all()` 返回全部用户。当用户量达到1000+时会有性能问题。建议增加 `page`/`page_size` 参数，使用 `paginate(page=page, per_page=page_size)` |
| 2 | 删除用户为物理删除且**无确认机制**（仅后端禁止删自身） | 🟡 建议 | 前端应增加 `confirm('确定要删除该用户吗？此操作不可恢复！')` 弹窗确认 |
| 3 | 日志限制300条**无可配置性** | ⚪ 无需改 | 对于毕设项目足够；生产环境可考虑分页或增加清理策略 |
| 4 | 管理员登录与普通用户登录**完全独立的两套逻辑** | ⚪ 设计选择 | admin_routes.login vs auth_routes.login 功能高度重复，但不构成bug |

**小结**：管理员后台CRUD完整，权限守卫严格（禁止操作自身账号），功能齐全。

---

### 模块3：股票行情数据（stock_api.py + stock_service.py）

#### 已实现API清单

| API | 方法 | 功能 | 状态 |
|-----|------|------|------|
| `GET /api/stocks` | 查询 | A股列表（行业/地域/关键字筛选 + 分页） | ✅ |
| `GET /api/stocks/<ts_code>` | 查询 | 个股详情 + daily_basic估值数据 | ✅ |
| `GET /api/stocks/<ts_code>/realtime` | 查询 | 个股实时行情（含K线走势） | ✅ |
| `GET /api/stocks/<ts_code>/history` | 查询 | 日K线历史数据（支持日期范围 + 1~5000条限制） | ✅ |
| `GET /api/stocks/<ts_code>/factors` | 查询 | 13种技术因子指标数据 | ✅ |
| `GET /api/stocks/<ts_code>/moneyflow` | 查询 | 资金流向（主力/大单/中单/小单） | ✅ |
| `GET /api/stocks/<ts_code>/cyq` | 查询 | 筹码分布性能数据 | ✅ |
| `GET /api/stocks/<ts_code>/cyq_chips` | 查询 | 筹码分布明细（各价位占比） | ✅ |
| `GET /api/industries` | 查询 | 行业列表（用于筛选下拉框） | ✅ |
| `GET /api/areas` | 查询 | 地域列表（用于筛选下拉框） | ✅ |
| `GET /api/market/index/<ts_code>/kline` | 查询 | 指数K线（上证/深证/创业板） | ✅ |
| `GET /api/market/overview` | 查询 | 市场概览（指数/涨跌/热门） | ✅ |
| `GET /api/market/health` | 检测 | Tushare服务状态 | ✅ |
| `GET /api/market/akshare/health` | 检测 | AkShare服务状态 | ✅ |

#### 设计合理性说明

**股票数据的CRUD设计是合理的"只读模型"**：
- 股票基础信息来自Tushare/AkShare外部数据源，由数据同步脚本统一维护
- 前端用户和管理员都**不应手动创建/编辑/删除**股票记录
- 所有写操作通过 ` MinuteDataSyncService ` 和数据采集脚本完成
- **无需增删改操作**，这是正确的设计决策

#### 发现的问题

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | `get_stock_realtime` 与 `get_monitor_stock_detail` **功能重复** | 🟡 建议 | 两个API都调用 `RealtimeMonitorService.get_stock_detail()` 且参数几乎一致。建议统一为一个入口或在文档中明确分工 |
| 2 | 股票详情缺少 **PE-TTM(滚动市盈率)** 字段 | ⚪ 可选 | 当前只有PE(静态)，部分投资者更关注PE-TTM |

**小结**：行情数据模块作为只读数据层，API覆盖全面，参数校验完善（limit范围限制），设计合理。

---

### 模块4：自选股（Watchlist）

涉及文件：`api/stock_api.py`(第192-267行) + `routes/auth_routes.py`(第480-526行) + `services/user_activity_service.py`

#### 已实现操作清单

| 操作 | 方法 | 路由 | 来源 | 状态 |
|------|------|------|------|------|
| **C - 添加自选** | POST | `/api/watchlist/<ts_code>` | api_bp | ✅ 去重检查 + 自动解析股票名称/市场 |
| **C - 添加自选(备选)** | POST | `/auth/profile/watchlist` | auth_bp | ✅ 通过UserActivityService（功能等价） |
| **R - 查看自选列表** | GET | `/api/watchlist` | api_bp | ✅ 按created_at倒序 |
| **R - Profile页预览** | GET | `/auth/profile` | auth_bp | ✅ 展示最近12条 |
| **D - 移除自选** | DELETE | `/api/watchlist/<ts_code>` | api_bp | ✅ 物理删除 |
| **D - 移除自选(备选)** | POST | `/auth/profile/watchlist/<ts_code>/delete` | auth_bp | ✅ 支持JSON/HTML双响应 |

#### 缺失操作

| 操作 | 严重程度 | 修复方案 |
|------|---------|---------|
| **U - 编辑自选备注/分组/排序** | 🟡 建议 | 当前UserWatchlist只有 ts_code/stock_name/market/source/created_at 字段，**无备注(note)、无分组(group)、无排序权重(sort_order)**。对于少量自选股够用，但如果用户添加了20+只股票，缺乏组织能力。建议：(1) UserWatchlist模型增加 `note`(String/256) 和 `sort_order`(Integer, 默认0) 字段；(2) 新增 `PATCH /api/watchlist/<ts_code>` 接口支持修改备注和排序；(3) 前端列表增加拖拽排序或上下箭头 |

#### 其他问题

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | **两套添加/删除API功能重复** | 🟡 | `api_bp` 的 `/api/watchlist/*` 和 `auth_bp` 的 `/auth/profile/watchlist/*` 存在功能重叠。虽然前者返回JSON（给前端AJAX调用）、后者同时支持HTML跳转（给传统表单），但对前端开发者造成困惑。建议统一使用 `api_bp` 版本，`auth_bp` 版本标记 `@deprecated` 或直接移除 |
| 2 | 自选股列表**无分页** | ⚪ | profile页面 limit(12) 截断，API版本 `.all()` 全量返回。如果用户自选超过50只可能影响加载速度 |

**小结**：核心CRUD齐全，但缺少编辑能力和去重API设计。

---

### 模块5：分析记录（AnalysisRecord）

涉及文件：`routes/auth_routes.py`(第529-554行) + `services/user_activity_service.py`(第54-69行)

#### 已实现操作

| 操作 | 方法 | 路由 | 状态 |
|------|------|------|------|
| **C - 保存分析记录** | POST | `/auth/profile/records/analysis` | ✅ JSON API，含module_name/summary/ts_code/stock_name |
| **R - Profile页展示** | GET | `/auth/profile` | ✅ 最近8条摘要 |

#### 缺失操作（🔴 核心缺陷）

| 操作 | 严重程度 | 当前状态 | 详细修复方案 |
|------|---------|---------|-------------|
| **R - 分析记录完整列表** | 🔴 **必须补** | ❌ 缺失独立列表页/API | **方案A（推荐-轻量）**：新增 `GET /api/user/records/analysis?page=&limit=` 接口返回分页的完整分析记录列表（含id/module_name/summary/ts_code/stock_name/created_at）；在Profile页的"分析记录Tab"增加"查看全部→"链接跳转或展开更多<br/>**方案B（完整）**：新增独立页面 `GET /auth/analysis-history` + 模板 `auth/analysis_history.html`，以表格形式展示全部分析记录，支持按股票/模块/时间筛选 |
| **U - 编辑分析记录** | 🟡 建议 | ❌ 缺失 | 用户保存的分析摘要可能有错别字或需要补充内容。新增 `PUT /api/user/records/analysis/<id>` 允许修改 summary 字段 |
| **D - 删除分析记录** | 🟡 建议 | ❌ 缺失 | 误存或过时的记录无法清除。新增 `DELETE /api/user/records/analysis/<id>` ，前端加确认弹窗 |

#### 其他问题

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | 分析记录**未被自动触发保存** | 🔴 **重要** | 当前查看个股详情页(stock_detail.html)执行分析操作后，**需要前端主动调用** `/auth/profile/records/analysis` 才会保存。如果前端没有在合适的时机（如切换Tab/离开页面）调用该API，用户的分析操作就**不会被记录**。建议确认 `stock_detail.html` 中是否有调用此API的逻辑；如果没有，应在用户点击"技术分析"等按钮时自动触发一次保存 |
| 2 | AnalysisRecord模型字段偏少 | ⚪ 可选 | 只有 user_id/ts_code/stock_name/module_name/summary/created_at。可以考虑增加 `detail`(Text, 详细分析内容)、`tags`(String, 标签如"看好"/"观望")、`images`(JSON, 截图引用) 等字段丰富记录内容 |

**小结**：这是本次审查发现的**最不完整的模块**。"Create有了但Read不完整、Update/Delete完全缺失"，且自动保存机制存疑。强烈建议优先补充。

---

### 模块6：AI对话管理（ai_conversation_service.py + ai_assistant_api.py, 302行）

#### 已实现操作清单

| 操作 | 方法 | 路由 | 状态 |
|------|------|------|------|
| **C - 新建会话** | POST | `/api/ai/conversations` | ✅ 支持自定义title，默认"新对话" |
| **R - 会话列表** | GET | `/api/ai/conversations` | ✅ 支持keyword搜索(title+summary模糊匹配) + 最近50条 |
| **R - 会话消息列表** | GET | `/api/ai/conversations/<id>/messages` | ✅ 返回conversation + messages数组 |
| **U - 重命名会话** | PATCH | `/api/ai/conversations/<id>` | ✅ title非空校验 |
| **D - 删除会话** | DELETE | `/api/ai/conversations/<id>` | ✅ cascade删除关联messages |
| **C - 发送消息(SSE流式)** | POST | `/api/ai/chat?stream=true` | ✅ 完整SSE流式管线：创建占位消息→流式写入→chunk持久化(每8条commit)→最终化→失败标记 |
| **C - 发送消息(非流式)** | POST | `/api/ai/chat?stream=false` | ✅ 同步模式fallback |
| **R - AI服务状态** | GET | `/api/ai/status` | ✅ LLM服务连通性检测 |

#### 架构亮点

```
AI对话完整生命周期:
新建会话 → (自动从question生成title) → 发送消息(user)
    → 构建LLM context(最多12条消息/12000字符) → 调用DeepSeek API
    → [流式] chunk逐字返回 + 每8个chunk DB持久化 → 最终化completed
    → [异常] 标记failed + 保留已生成内容
    → 同时写入Legacy ChatHistory(向后兼容)
```

#### 发现的问题

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | **Legacy双重写入** | 🟡 | 每次AI对话同时写入两张表：`UserAiConversation+UserAiMessage`(新体系) 和 `UserChatHistory`(旧体系)。这导致：(a)存储翻倍 (b)Profile页的"聊天记录"和AI助手页的"对话历史"数据来源不同步。(c)删除会话时只删除新体系的conversation，旧chat_history残留。<br/>**修复建议**：确认前端是否还在使用 `GET /auth/profile` 中的 `chat_records`(来自UserChatHistory)。如果AI助手页面已经完全不依赖Legacy表，可以移除 `record_chat()` 调用；否则明确两套体系的定位（如：ChatHistory=全局搜索索引，Conversation=结构化对话） |
| 2 | 会话列表**无分页** | ⚪ | limit(50)硬编码。对重度使用者可能不够 |
| 3 | 无**消息编辑/重新生成**功能 | 🟡 | 用户对AI回复不满意时无法单独重新生成某条消息（主流AI产品标配功能）。可在 `POST /api/ai/chat` 增加 `regenerate_message_id` 参数，删除该message之后的所有user/assistant消息对，然后重新调用LLM |
| 4 | `ensure_tables()` 在每次API调用时执行 | ⚪ 性能 | `create(checkfirst=True)` 在表已存在时开销极小(~1ms)，但可以在应用启动时一次性调用替代 |

**小结**：AI对话模块工程质量**很高**——SSE流式管线完整、错误处理周全、context窗口管理智能。主要问题是Legacy双重写入的历史包袱。

---

### 模块7：聊天记录-legacy（UserChatHistory / ChatHistory）

涉及文件：`routes/auth_routes.py`(第557-578行) + `services/user_activity_service.py`(第71-83行)

#### 已实现操作

| 操作 | 路由 | 状态 |
|------|------|------|
| **C - 保存聊天记录** | `POST /auth/profile/records/chat` | ✅ question + answer |
| **R - Profile页预览** | `GET /auth/profile` | ✅ 最近6条 |

#### 分析

这是**被新AI对话体系(UserAiConversation)部分替代的遗留模块**：

| 维度 | Legacy (UserChatHistory) | New (UserAiConversation+Message) |
|------|--------------------------|----------------------------------|
| 结构 | 扁平(question-answer对) | 层次化(conversation → messages[]) |
| 多轮对话 | ❌ 不支持 | ✅ 完整支持 |
| SSE流式 | ❌ | ✅ 支持 |
| 会话管理 | ❌ | ✅ CRUD齐全 |
| 状态跟踪 | ❌ | ✅ (streaming/completed/failed) |
| 数据来源 | 仅AI对话手动写入 | AI对话自动写入 + **也写入Legacy(冗余)** |

**结论**：Legacy模块可以视为"已半废弃"。它存在的唯一价值是Profile页的"聊天记录"预览。
- 如果保留：至少需要**独立的列表页**和**删除功能**
- 如果废弃：将Profile页改为读取UserAiConversation的最新消息即可，然后移除record_chat调用

---

### 模块8：新闻资讯（news_api.py + news_service.py）

#### 已实现API

| API | 方法 | 数据源 | 状态 |
|-----|------|--------|------|
| `GET /api/news?source=all` | 查询 | 4源聚合 | ✅ |
| `GET /api/news?source=cjzc` | 查询 | 东财·财经早餐 | ✅ |
| `GET /api/news?source=global_em` | 查询 | 东财·全球快讯 | ✅ |
| `GET /api/news?source=cls` | 查询 | 财联社·电报 | ✅ |
| `GET /api/news?source=ths` | 查询 | 同花顺·直播 | ✅ |
| `GET /api/news/cjzc` | 查询 | 东财·财经早餐(独立入口) | ✅ |
| `GET /api/news/global` | 查询 | 全球快照(合并入口) | ✅ |

#### 设计合理性

新闻数据属于**第三方实时抓取的只读数据**：
- 新闻内容由外部网站实时抓取（AkShare接口）
- **不需要用户端的增删改操作**
- 如果未来需要"收藏新闻"功能，则需要新增 UserNewsFavorite 模型

#### 发现的问题

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | **无本地缓存/去重** | 🟡 | 每次 `GET /api/news` 都会实时调用 AkShare 抓取外部数据。如果有大量并发用户访问新闻页，会对数据源造成压力且响应慢。建议使用Redis缓存（TTL=5分钟）：`cache_key = f"news:{source}"`，先查缓存，miss再抓取 |
| 2 | 新闻API **无限流风险** | ⚪ | 未对返回数量做限制。如果某个数据源返回数千条（如全球快讯全天累积），可能导致响应体积过大。建议每源默认返回 latest 50~100 条 |
| 3 | 无 **关键词搜索/日期筛选** | 🟡 | 只能按 source 过滤。用户如果想找"某只股票相关新闻"或"某天的新闻"无法做到。建议增加 `?keyword=&date=` 参数，在前端对返回结果做客户端过滤（零成本） |

**小结**：功能完整但性能有优化空间。

---

### 模块9：选股筛选（analysis_api.py 第12-26行 + StockService.screen_stocks()）

#### 已实现

| API | 方法 | 功能 | 状态 |
|-----|------|------|------|
| `POST /api/analysis/screen` | 查询 | 多条件组合筛选 | ✅ |

#### 发现的问题

| # | 问题 | 严重度 | 详细分析与修复方案 |
|---|------|--------|---------------------|
| 1 | **筛选条件无法保存/复用** | 🟡 建议 | 用户精心设置的一组筛选条件（如"PE<30 + 换手率>3% + 主力净流入"）每次都需要重新填写。这是高频使用场景的核心痛点。<br/><br/>**修复方案**：<br/>(1) 新建ORM模型 `UserScreenPreset`：<br/>```python<br/>class UserScreenPreset(db.Model):<br/>    id = Column(Integer, primary_key=True)<br/>    user_id = Column(Integer, nullable=False, index=True)<br/>    name = Column(String(100))  # 如"低估值白马"<br/>    conditions = Column(JSON)  # 存储完整筛选条件JSON<br/>    created_at = Column(DateTime, default=datetime.utcnow)<br/>```<br/>(2) 新增API：<br/>- `POST /api/analysis/screen/presets` — 保存当前筛选条件为预设<br/>- `GET /api/analysis/screen/presets` — 获取我的预设列表<br/>- `PUT /api/analysis/screen/presets/<id>` — 更新预设<br/>- `DELETE /api/analysis/screen/presets/<id>` — 删除预设<br/>(3) 前端screen.html增加"保存为预设"/"我的预设"下拉面板 |
| 2 | 筛选结果**无法导出** | ⚪ 可选 | 用户可能想将筛选出的股票列表导出为CSV/Excel。新增 `POST /api/analysis/screen/export?format=csv|xlsx` 接口，返回文件下载 |

---

### 模块10：策略回测（analysis_api.py 第29-454行 BacktestEngine）

#### 已实现

| API | 方法 | 功能 | 状态 |
|-----|------|------|------|
| `POST /api/analysis/backtest` | 执行 | 5种策略回测 | ✅ |

**回测引擎内部能力**：

| 能力 | 状态 | 说明 |
|------|------|------|
| MA均线交叉策略 | ✅ | ma_short/ma_long参数可配 |
| MACD策略 | ✅ | 使用已有因子数据计算金叉死叉 |
| KDJ策略 | ✅ | oversold/overbought阈值可配 |
| RSI策略 | ✅ | oversold/overbought阈值可配 |
| 布林带策略 | ✅ | 修复版：避免连续触发重复信号 |
| 佣金/滑点模拟 | ✅ | commission_rate可配(默认0.1%) |
| 买入规则(按手) | ✅ | 1手=100股，至少买1手 |
| 绩效指标计算 | ✅ | 年化收益/最大回撤/夏普比率/波动率/胜率/平均持仓天数/基准对比/总手续费 |

#### 发现的问题

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | 回测结果**无法保存** | 🟡 建议 | 用户执行完回测后关闭页面就丢失了结果。建议新增 `UserBacktestResult` 模型保存回测配置+绩效指标+交易记录，并在Profile页或独立的"我的回测"页面展示历史回测记录 |
| 2 | 回测报告**无法导出** | 🟡 建议 | 无法下载PDF/图片格式的回测报告。ECharts图表可通过 `getDataURL()` 导出PNG，表格数据可导出CSV |
| 3 | **services/backtest_engine.py 是空壳** | ⚪ 需注意 | 项目根目录的 `app/services/backtest_engine.py` 是预留的高级引擎空壳（所有方法 raise NotImplementedError）。**实际的回测逻辑在 `app/api/analysis_api.py` 内部定义了一个同名类 `BacktestEngine`**。这在论文描述时需要注意——不要引用 services 目录下的那个空壳文件作为实现证据 |
| 4 | 无**基准对比可视化** | ⚪ 可选 | 虽然计算了 benchmark_return(买入持有)，但在ECharts图表中未绘制基准线。建议在收益曲线图上叠加一条"基准(买入持有)"虚线 |

**小结**：回测引擎本身实现质量较高，策略信号逻辑清晰，绩效计算全面。主要是结果持久化和导出方面有提升空间。

---

### 模块11：实时监控（realtime_monitor_api.py + realtime_monitor_service.py）

#### 已实现API

| API | 方法 | 功能 | 状态 |
|-----|------|------|------|
| `GET /api/monitor/dashboard` | 查询 | 监控面板(自选股矩阵) | ✅ |
| `GET /api/monitor/ranking` | 查询 | 涨跌排行(limit≤50) | ✅ |
| `GET /api/monitor/stocks/<ts_code>` | 查询 | 个股监控详情 | ✅ |
| `GET /api/monitor/intraday/<ts_code>` | 查询 | 分时走势(1/5/15/30/60min) | ✅ |
| `GET /api/monitor/shock` | 查询 | 异动波动数据 | ✅ |

#### 发现的问题

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | **无预警/告警规则配置** | 🟡 | "监控"一词暗示应该有价格突破/异常波动时的主动通知。目前只能手动刷新查看，无法设置"贵州茅台跌破1500元时提醒我"这类规则。不过系统中有 `RiskAlerts` ORM模型（已定义但未见使用），说明可能预留了扩展点 |
| 2 | 监控仪表盘**依赖前端传入ts_codes** | ⚪ | `dashboard` 接口的 `raw_codes` 参数由前端传入。如果用户未配置自选股或前端传参有误，面板为空。建议增加默认行为：未传codes时返回全市场TOP20活跃股票 |
| 3 | 异动数据(StockShock) **写入机制不明** | ⚪ | `StockShock` 模型和 `/monitor/shock` API 都已存在，但未见定时任务往这张表写数据。需要确认是否有 APScheduler 定时任务在填充此表 |

---

### 模块12：系统日志（SystemLog）

#### 已实现

| 操作 | 路由 | 状态 |
|------|------|------|
| **C - 写入日志** | `SystemLogService.write()` (各处调用) | ✅ 自动写入(action_type/message/user/status/timestamp) |
| **R - 日志查看** | `GET /admin/logs` | ✅ 类型+状态筛选，最新300条 |

#### 缺失操作

| 操作 | 严重程度 | 修复方案 |
|------|---------|---------|
| **D - 日志清理/归档** | 🟡 | SystemLog只会增长不会减少。长期运行后表会膨胀。建议：(1) 新增管理员操作 `POST /admin/logs/cleanup?days=90` 清理N天前的日志 (2) 或在 `SystemLogService.write()` 中增加定期清理逻辑 |
| **导出日志** | ⚪ 可选 | 管理员可能需要导出日志做审计。新增 `GET /admin/logs/export?format=csv&date_from=&date_to=` |

---

## 🔴 必须修复项汇总（影响答辩/论文可信度）

### 🔴 #1：分析记录模块功能不完整（模块5）

**问题本质**：AnalysisRecord 有 Create 但 **缺独立 Read 列表页、缺 Update、缺 Delete**

**影响范围**：
- 论文中如果提到"用户可以查看历史分析记录"，实际只有Profile页的8条摘要预览
- 用户误操作保存了错误记录后无法删除或修改
- 可能导致答辩质询："你的分析记录能删除吗？"

**最小修复方案**（预计工作量：2-3小时）：

```
1. 新增API（在 analysis_api.py 中）:
   GET    /api/user/records/analysis?page=&limit=     -- 分页列表
   PUT    /api/user/records/analysis/<id>             -- 修改摘要
   DELETE /api/user/records/analysis/<id>             -- 删除记录

2. 确认 stock_detail.html 是否在适当时机调用了保存API
   （如果没有，在用户查看技术指标/资金流等Tab时触发一次自动保存）

3. Profile页的"分析记录"区域增加"查看全部"链接
```

---

### 🔴 #2：回测结果无法保存（模块10）

**问题本质**：回测是系统**核心差异化功能之一**，但执行完即丢弃

**影响范围**：
- 论文中说"支持五种策略回测"，但无法证明用户可以"对比不同时期的回测结果"
- 答辩演示时无法展示"我昨天回测过的策略今天还能看到"

**最小修复方案**（预计工作量：2小时）：

```
1. 新增模型 UserBacktestResult:
   id / user_id / ts_code / stock_name / strategy_type / params(JSON)
   / start_date / end_date / initial_capital
   / performance(JSON: total_return/annual_return/sharpe/max_drawdown/win_rate...)
   / trades(JSON: 最近20笔交易记录)
   / created_at

2. 回测完成后自动保存（在 backtest_strategy() 末尾追加写入）

3. 新增API:
   GET    /api/user/backtests?page=&limit=           -- 我的回测历史
   GET    /api/user/backtests/<id>                    -- 回测详情
   DELETE /api/user/backtests/<id>                    -- 删除回测记录

4. 在 backtest.html 底部增加"历史回测"折叠区域
```

---

## 🟡 建议改进项汇总（提升完整性）

| # | 模块 | 问题 | 工作量估计 | 建议 |
|---|------|------|-----------|------|
| 🟡1 | 自选股(模块4) | 缺少备注/分组/排序编辑功能 | 2h | 加 note+sort_order 字段 + PATCH API |
| 🟡2 | 选股筛选(模块9) | 筛选条件无法保存为预设 | 3h | 新增 UserScreenPreset 表 + CRUD API |
| 🟡3 | 新闻(模块8) | 无缓存，每次实时抓取 | 1h | Redis TTL=5min 缓存 |
| 🟡4 | AI对话(模块6) | Legacy ChatHistory 双重写入 | 1h | 统一为新体系或明确分离定位 |
| 🟡5 | 管理员-用户列表(模块2) | 用户列表无分页 | 30min | 加 paginate |

---

## 🟢 可选优化项（锦上添花）

| # | 模块 | 优化点 | 工作量 |
|---|------|--------|--------|
| 🟢1 | 用户认证 | 增加密码强度规则 + 邮箱格式正则校验 | 30min |
| 🟢2 | 回测(模块10) | 收益曲线图叠加"买入持有"基准虚线 | 1h |
| 🟢3 | 新闻(模块8) | 增加关键词搜索/日期筛选（前端过滤即可） | 30min |
| 🟢4 | 实时监控(模块11) | 利用 RiskAlerts 模型实现简单预警规则 | 4h |
| 🟢5 | 系统日志(模块12) | 日志清理/导出功能 | 1h |

---

## 跨模块架构级问题

| # | 问题 | 影响范围 | 严重度 | 建议 |
|---|------|---------|--------|------|
| 1 | **自选股有两套功能重复的API** | 模块4 | 🟡 | 统一到 api_bp (`/api/watchlist/*`)，移除 auth_bp 中的备选接口 |
| 2 | **个股实时行情有两个重复API** | 模块3 | 🟡 | `get_stock_realtime`(stock_api.py) 和 `get_monitor_stock_detail`(realtime_monitor_api.py) 功能重叠，明确分工或合并 |
| 3 | **backtest_engine.py 存在空壳陷阱** | 文档/论文 | ⚠️注意 | `services/backtest_engine.py` 是空壳，实际实现在 `api/analysis_api.py` 内部类。论文引用时务必指明正确位置 |
| 4 | **22个ORM模型中有多個未被任何API/页面使用** | 整体 | ⚪ 可选 | `TradingSignals`/`PortfolioPositions`/`RiskAlerts`/`StockBusiness`/`StockIncomeStatement`/`StockBalanceSheet`/`StockShock` 模型已定义但未见读写操作。论文中如果提到这些功能需要有对应实现，否则不建议提及 |

---

## 修复优先级路线图

```
第一阶段（必须，影响答辩，预估 4-5 小时）:
  └─ 🔴#1 补全 AnalysisRecord 的 R/U/D
  └─ 🔴#2 实现 BacktestResult 持久化

第二阶段（建议，提升完整性，预估 7-8 小时）:
  └─ 🟡1 自选股备注/排序功能
  └─ 🟡2 选股条件预设保存
  └─ 🟡3 新闻Redis缓存
  └— 🟡4 清理AI对话Legacy双重写入
  └─ 🟡5 管理员用户列表分页

第三阶段（可选，锦上添花，预估 7 小时）:
  └─ 🟢1~3 认证增强 + 回测基准线 + 新闻搜索
  └─ 🟢4~5 监控预警 + 日志清理导出
  └─ 跨模块：统一重复API + 明确空壳文件定位
```

---

*本报告基于 2026-04-27 版本源码逐行审计生成，覆盖 12 个功能模块的全部路由/服务/模型代码。*
