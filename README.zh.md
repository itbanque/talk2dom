from talk2dom import get_element

# talk2dom — 用自然语言定位网页元素
> 📚 文档语言 | [🇺🇸 English](./README.md) | [🇨🇳 中文](./README.zh.md)

![PyPI](https://img.shields.io/pypi/v/talk2dom)
[![PyPI Downloads](https://static.pepy.tech/badge/talk2dom)](https://pepy.tech/projects/talk2dom)
![Stars](https://img.shields.io/github/stars/itbanque/talk2dom?style=social)
![License](https://img.shields.io/github/license/itbanque/talk2dom)
![CI](https://github.com/itbanque/talk2dom/actions/workflows/test.yaml/badge.svg)

**talk2dom** 是一个专注于网页自动化测试中最困难环节的工具：

> ✅ **准确找到你想操作的 UI 元素。**

---

## 🧠 为什么用 talk2dom？

在写自动化脚本或构建 LLM Agent 时，真正难的不是“怎么点”，而是：

> **怎么找到要点的那个元素。**

举个例子：
- 点击按钮很简单 —— *前提是你知道 selector*
- 输入文字也不难 —— *但你得先找到那个 input*
- 然而，DOM 中成百上千个标签、嵌套结构、Shadow DOM…… 让你寸步难行

**talk2dom 就是为了解决这个问题而生的。**

---

## 🎯 它能做什么？

talk2dom 通过以下方式帮你定位元素：

- 从 Selenium `WebDriver` 或 `WebElement` 获取 HTML
- 用自然语言 + LLM 生成简洁的 selector（`xpath:...` 或 `css:...`）
- 可以用于 Shadow DOM 的子节点（你负责 traversal）

---

## 🤔 为什么选 Selenium？

虽然现在有很多操作浏览器的工具（Playwright、Puppeteer 等），但：

- ✅ Selenium 对 Safari / Firefox / 移动端支持最好
- ✅ 企业级测试中仍以 Selenium 为主
- ✅ Selenium 支持跨平台远程浏览器（如 Grid）

所以 talk2dom 专为 Selenium 打造。

---

## 📦 安装

```bash
pip install talk2dom
```

---

## 🔍 使用示例

### 基础用法

默认使用 OpenAI 的 `gpt-4o-mini`（低成本模型）

```bash
export OPENAI_API_KEY="..."
```

```python
from selenium import webdriver
from talk2dom import get_element

driver = webdriver.Chrome()
driver.get("http://www.python.org")

elem = get_element(driver, "找到搜索框")
elem.send_keys("pycon")
```

---

### 免费模型支持

你也可以用来自 Groq 的免费 LLM，如 `llama-3.3-70b-versatile`

```bash
export GROQ_API_KEY="..."
```

```python
by, value = get_element(driver, "找到搜索框", model="llama-3.3-70b-versatile", model_provider="groq")
```

---

### 输入对象类型

你可以传入：
- ✅ `WebDriver`（整个页面）
- ✅ `WebElement`（局部 HTML）

传入子结构可以：
- ✅ 更精准（适合 modal/popup 等组件）
- ✅ 减少 token 消耗（提升速度、降低成本）

---

## ✨ 设计理念

> 我们不控制浏览器。
>
> 你来操作浏览器，talk2dom 帮你**找到目标元素的位置**。

---

## ✅ 特性概览

- 📍 定位优先，控制自理
- 🤖 面向 LLM-Agent 流程设计
- 🧩 Shadow DOM 友好（返回可用 selector）

---

## 📄 协议

Apache 2.0

---

## 💬 反馈 & 贡献

欢迎提交 [Issue](https://github.com/itbanque/talk2dom/issues)、[PR](https://github.com/itbanque/talk2dom/pulls) 或参与讨论！

GitHub 项目地址：👉 https://github.com/itbanque/talk2dom

如果你觉得这个工具有用，请给个 ⭐️ 鼓励！