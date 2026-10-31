# 智汇校园 · 二手集市

> 校园闲置交易平台：发布时由**本地 AI** 自动分类、写文案、给定价建议，并拦下违规内容。
> 全部 AI 能力用纯 Python 实现，**不调用任何外部 API，断网也能跑**。

一个面向高校的轻量二手交易站：学生用学号/邮箱注册，发布闲置、收藏、下单、私信；管理员在后台处理商品与用户。
最大的不同在发布页——**边打字，边有 AI 给出品类、文案、价格和审核结果**，让"懒得写描述"这件事不再成为门槛。

---

## 技术栈

| 层 | 选型 |
|---|---|
| Web | Flask 3.1（应用工厂 + 蓝图） |
| 认证 | Flask-Login（session + 密码哈希） |
| 数据 | Flask-SQLAlchemy + SQLite 单文件 |
| 前端 | Jinja2 模板 + 原生 CSS/JS（无构建步骤） |
| AI | 纯 Python 规则引擎（关键词打分 / 模板 / 词库），零外部依赖 |

---

## 7 项本地 AI 能力

| # | 能力 | 函数 | 说明 |
|---|---|---|---|
| 1 | 智能分类 | `classify_product` | 关键词命中打分，返回品类 + 置信度 |
| 2 | 智能定价 | `suggest_price` | 按成色折价（全新 0.85 → 有瑕疵 0.25），给出区间 |
| 3 | 文案生成 | `generate_copy` | 按品类套模板，结合成色与参考价 |
| 4 | 内容审核 | `moderate_text` | 违规词库分类命中，返回拦截原因 |
| 5 | 标签提取 | `extract_tags` | 型号、成色、品类自动成标签 |
| 6 | 个性化推荐 | `recommend_products` | 内容 50% + 分类偏好 35% + 热度 15% |
| 7 | 智能客服 | `chatbot_reply` | 问答库匹配，答不上来转人工 |

单独试用：

```bash
python ai_engine.py
```

---

## 搜索：语义检索 + 个性化排序

搜索不是 `LIKE` 匹配，而是一条可解释的排序链（`search_engine.py`）：

| 步骤 | 做法 |
|---|---|
| 分词 | 中文二元组 + 英文词，单字兜底（否则搜「灯」会零命中） |
| 同义词 | 「便宜的平板」→ 平板 / iPad / air…（`SYNONYMS`） |
| 相似度 | TF-IDF 向量余弦，标题权重 ×3、标签 ×2 |
| 个性化 | 语义 60% + 分类偏好 25%（来自 Behavior 表）+ 热度 15% |
| 理由 | 每条结果给出「匹配『键盘』」或「你常看数码电子」 |

### 可选：接入大模型

`llm.py` 是 OpenAI 兼容适配层，**配了 key 才启用，任何异常自动回落本地**：

```bash
export LLM_API_KEY=sk-xxx          # 不设置 = 纯本地
export LLM_BASE_URL=https://api.deepseek.com/v1   # 可选
export LLM_MODEL=deepseek-chat                     # 可选
```

启用后搜索会多做两件事：把口语查询解析成检索词与意图（页面显示「AI 理解：…」），
再对候选做一次重排并生成推荐理由；超时 6 秒则退回本地结果，页面不报错。

## 3 步跑起来（10 分钟复现）

```bash
# 1. 装依赖（建议先建虚拟环境）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 初始化数据库（6 分类 + 3 账号 + 16 件演示商品）
python init_db.py

# 3. 启动
python app.py
```

浏览器打开 <http://127.0.0.1:5000>。

### 演示账号

| 角色 | 账号 | 密码 |
|---|---|---|
| 管理员 | `admin` | `admin123` |
| 学生 A | `zhangsan` | `123456` |
| 学生 B | `lisi` | `123456` |

> `zhangsan` 预置了浏览行为，登录后首页会出现"为你推荐"而不是热门榜。

### 环境变量（可选）

不需要配置也能跑。想覆盖默认值时，在项目根目录建 `.env` 或直接改 `config.py`：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SECRET_KEY` | 内置字符串 | 生产环境务必换掉 |
| `SQLALCHEMY_DATABASE_URI` | `sqlite:///data/campus_market.db` | 数据库位置 |

---

## 冒烟测试

```bash
python test_smoke.py
```

覆盖 24 个关键点（游客访问、注册登录、AI 六个接口、发布/审核、收藏、下单约束、私信审核、后台权限、退出），
使用独立测试库 `data/test_smoke.db`，不会污染演示数据。

预期输出：

```
✅ 全部通过！24/24
```

---

## 项目结构

```
campus-secondhand/
├── app.py                  # 应用工厂、登录管理、蓝图注册、错误页
├── config.py               # 密钥 / 数据库 / 上传限制 / 站点信息
├── models.py               # 7 张表：User Category Product Favorite Order Message Behavior
├── ai_engine.py            # 7 个本地 AI 能力（可直接 python ai_engine.py 自测）
├── init_db.py              # 建表 + 演示数据
├── test_smoke.py           # 24 项冒烟测试
├── requirements.txt
├── blueprints/
│   ├── __init__.py         # 统一注册
│   ├── main.py             # 首页 / 分类 / 搜索 / 关于 / 健康检查
│   ├── auth.py             # 注册 登录 退出 个人中心
│   ├── product.py          # 发布(AI分类+审核) 详情 编辑 删除 收藏
│   ├── order.py            # 下单 我的订单 完成 取消
│   ├── message.py          # 收件箱 聊天 发送(AI审核) 轮询
│   ├── ai.py               # 6 个 JSON 接口 + 助手页
│   └── admin.py            # 看板 商品 用户 分类
├── templates/              # 20 个 Jinja2 模板
│   ├── base.html  _card.html  index.html  about.html  error.html
│   ├── auth/      login register profile
│   ├── product/   publish detail edit my
│   ├── order/     mine
│   ├── message/   inbox chat
│   ├── ai/        assistant
│   └── admin/     _nav dashboard products users categories
├── static/
│   ├── css/style.css       # 全站样式（响应式）
│   ├── js/main.js          # AI 实时辅助、收藏、聊天轮询、标签页
│   ├── uploads/            # 用户上传图片（.gitkeep 占位）
│   └── vendor/             # 可选：本地 Bootstrap
└── data/                   # SQLite 文件目录
```

---

## 设计要点

**1. 发布即审核。** 表单提交时先过 `moderate_text`，命中违规词直接回填页面并提示原因，不会写入数据库。
**2. 分类可留空。** 用户不选分类时，由 `classify_product` 判定并自动挂到对应品类，提示"AI 已自动归类"。
**3. 商品不能被买两次。** 下单即把 `product.status` 置为 `sold`，并检查"不能买自己的、不能重复下单"。
**4. 私信也过审核。** 发送接口先审核再落库，前端用气泡提示拦截原因。
**5. 权限两道闸。** 蓝图级 `@login_required` + 后台 `before_request` 校验 `is_admin`，普通用户访问后台返回 403。

---

## 参赛信息

- 赛事：传智杯 AI 创新应用大赛
- 赛道：校园场景智能应用
- 提交物：公开仓库 + 细粒度 Git 历史 + Prompt 记录 + 5–8 分钟演示视频 + ≤30 页技术文档
- 许可：[MIT](LICENSE)
