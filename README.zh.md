# talk2dom — 一句话定位网页元素

> 📚 [English](./README.md) | [中文](./README.zh.md)

![PyPI](https://img.shields.io/pypi/v/talk2dom)
[![PyPI 下载量](https://static.pepy.tech/badge/talk2dom)](https://pepy.tech/projects/talk2dom)
![Stars](https://img.shields.io/github/stars/itbanque/talk2dom?style=social)
![License](https://img.shields.io/github/license/itbanque/talk2dom)
![CI](https://github.com/itbanque/talk2dom/actions/workflows/test.yaml/badge.svg)

**talk2dom** 是一个专注于解决浏览器自动化和 UI 测试中最困难问题的工具：

> ✅ **在页面中定位正确的 UI 元素。**

---

[![在 YouTube 上观看演示](https://img.youtube.com/vi/6S3dOdWj5Gg/0.jpg)](https://youtu.be/6S3dOdWj5Gg)


## 🧠 为什么使用 `talk2dom`

在自动化测试或 LLM 驱动的网页操作任务中，最大的问题通常不是点击或输入，而是**找到正确的元素**。

想象一下：

- 点击按钮很简单 — *前提是*你知道它的选择器。
- 输入字段也不难 — *前提是*你已经定位到正确的输入框。
- 但在上百个 `<div>`、`<span>` 和深度嵌套的 Shadow DOM 中找出正确的目标？这才是真正的挑战。

**`talk2dom` 正是为了解决这个问题而设计的。**

---

## 🎯 它的功能

`talk2dom` 可通过以下方式帮助你定位元素：

- 理解自然语言指令并将其转为浏览器操作  
- 支持单次执行或持续交互会话  
- 使用 LLM（如 GPT-4 或 Claude）分析实时 HTML 和用户意图  
- 根据指令和模型响应提供灵活输出：操作、选择器，或两者兼有  
- 支持桌面与移动浏览器，通过 Selenium 实现

---

## 🗃️ 可选功能：启用 PostgreSQL 缓存定位器结果

为了避免每次都重新调用 LLM 推理选择器，`talk2dom` 支持通过 PostgreSQL 数据库缓存结果。

### 工作原理

* 对于每一对 `instruction + url` 输入，系统会生成一个唯一的 SHA256 哈希 ID。
* 如果数据库中已有对应缓存，将直接返回缓存结果，跳过 LLM 调用。
* 该机制可显著提升性能，降低延迟和 token 成本。

### 配置方式

通过环境变量启用数据库缓存：

```bash
export TALK2DOM_DB_URI="postgresql+psycopg2://user:password@localhost:5432/dbname"
```

如果未设置 `TALK2DOM_DB_URI`，缓存功能将自动禁用，所有请求默认使用 LLM 实时推理。

---

## 🤔 为什么选择 Selenium？

虽然 Playwright、Puppeteer 等现代浏览器控制工具层出不穷，**但 Selenium 依然是最健壮、最具跨平台支持的解决方案**，尤其在以下环境中：

- ✅ Safari（WebKit）
- ✅ Firefox
- ✅ 移动浏览器
- ✅ 跨浏览器测试网格

许多工具对非 Chrome 浏览器的支持有限，而 Selenium 在所有主流平台上都有经过验证的稳定表现，是企业和 CI/CD 环境的标准方案。

这也是为什么 `talk2dom` 直接集成 Selenium —— 因为它能应对真实复杂场景。

---

## 📦 安装方式

```bash
pip install talk2dom
```

---

## 🧩 基于代码的 ActionChain 模式

如果你偏好使用结构化 Python 控制浏览器，`ActionChain` 让你可以逐步操作浏览器。

### 基本用法

talk2dom 默认使用 gpt-4o-mini，在性能与成本间实现良好平衡。
测试中显示，gpt-4o 表现最佳。

#### 确保设置 OPENAI_API_KEY

```bash
export OPENAI_API_KEY="..."
```

注意：所用模型需支持 Chat Completion API，并遵循 OpenAI 兼容协议。

#### 示例代码

```python
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

from talk2dom import ActionChain

driver = webdriver.Chrome()

ActionChain(driver) \
    .open("http://www.python.org") \
    .find("Find the Search box") \
    .type("pycon") \
    .type(Keys.RETURN) \
    .assert_page_not_contains("No results found.") \
    .valid("the 'PSF PyCon Trademark Usage Policy' is exist") \ 
    .close()
```

### 免费模型支持

talk2dom 也支持来自 [Groq](https://groq.com/) 的免费模型，如 `llama-3.3-70b-versatile`

---

### 整页 vs 范围查询
`find()` 可用于查询整个页面，也可仅查询指定元素。
你可以传入完整的 Selenium `driver`，或传入 `WebElement` 限定查询范围。

#### 何时使用 `WebElement` 替代 `driver`

1. 减少 Token 使用 —— 只传较小的 HTML 子树（如弹窗）可节省 Token，降低延迟与成本。
2. 提升定位准确性 —— 限定范围有助于模型专注于相关内容，尤其适用于嵌套组件如弹窗、抽屉、卡片等。

无需手动提取 HTML —— `talk2dom` 会自动使用你传入的元素的 `outerHTML`。

---

## ✨ 我们的理念

> 我们不控制浏览器。
> 你来操作浏览器，talk2dom 帮你**找到目标元素的位置**

---

## ✅ 核心特性

- 💬 使用自然语言控制浏览器  
- 🔁 支持多步持久交互会话  
- 🧠 基于 LLM 的高级意图理解  
- 🧩 输出可操作的 XPath/CSS 选择器 或 可直接执行的操作链  
- 🧪 内建断言与步骤校验  
- 💡 适用于 CLI 脚本或对话交互式应用

---

## 📄 许可证

Apache 2.0

---

## 贡献方式

请阅读 [CONTRIBUTING.md](https://github.com/itbanque/talk2dom/blob/main/CONTRIBUTING.md) 了解行为准则及提交 Pull Request 流程。

---

## 💬 问题或建议？

欢迎分享你在 AI agent 或测试流程中如何使用 `talk2dom`！  
欢迎提交 Issue 或开启讨论。  
如果你正在用 `talk2dom` 构建有趣项目，也欢迎在 GitHub 上 @我们！  
⭐️ 如果觉得有帮助，别忘了给我们点个 Star！

