# talk2dom — 一句话定位网页元素

> 📚 [English](./README.md) | [中文](./README.zh.md)

![Stars](https://img.shields.io/github/stars/itbanque/talk2dom?style=social)
[![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
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

## ✨ 我们的理念

> 我们不控制浏览器。
> 你来操作浏览器，talk2dom 帮你**找到目标元素的位置**

---

## ✅ 核心特性

- 🔁 支持多步持久交互会话  
- 🧠 基于 LLM 的高级意图理解  
- 🧩 输出可操作的 XPath/CSS 选择器 或 可直接执行的操作链  

## 🌐 托管 API 服务

`talk2dom` 提供了一个**可直接部署的云服务版本**，适用于构建 AI agent、测试平台及低代码系统。

### 快速启动

```bash
git clone https://github.com/itbanque/talk2dom.git
cd talk2dom
docker compose up
```

启动后，API 可通过 `http://localhost:8000/docs` 访问，包含完整的 OpenAPI 文档与交互式 Swagger UI。

---

## ⚙️ 服务能力

托管版 `talk2dom` 提供完善的后端基础设施，包括：

- 🔐 **用户认证与账户管理** —— 支持注册、登录、角色控制、会话处理等
- 🗂️ **项目隔离机制** —— 每个项目独立管理 API Key 与调用分析
- 🔑 **API Key 管理** —— 支持生成、吊销、轮换，粒度控制访问权限
- 📈 **调用追踪与分析** —— 实时查看每个项目和用户的 API 调用与统计
- 💳 **订阅与充值系统** —— 支持基于 Credit 的计费机制，集成 Stripe 支付
- 🧠 **智能选择器缓存** —— 基于 PostgreSQL 自动缓存 LLM 推理结果，提升响应速度与一致性

可用于私有部署、企业内嵌集成，或连接第三方平台如 Zapier、Retool、低代码平台等。

部署方案或有任何疑问请在Github上联系我们。

---

## 📄 许可证

本项目采用 Creative Commons Attribution-NonCommercial 4.0 International License（CC BY-NC 4.0） 授权发布。

您可以：
	•	✅ 出于非商业目的使用、修改和分享本项目代码；
	•	❌ 禁止将本项目用于任何商业用途，包括但不限于售卖、作为付费产品的一部分或在收费服务中使用；
	•	✅ 在使用或传播本项目时，必须注明原作者。

如需商业授权，请联系：contact@itbanque.com

---

## 贡献方式

请阅读 [CONTRIBUTING.md](https://github.com/itbanque/talk2dom/blob/main/CONTRIBUTING.md) 了解行为准则及提交 Pull Request 流程。

---

## 💬 问题或建议？

欢迎分享你在 AI agent 或测试流程中如何使用 `talk2dom`！  
欢迎提交 Issue 或开启讨论。  
如果你正在用 `talk2dom` 构建有趣项目，也欢迎在 GitHub 上 @我们！  
⭐️ 如果觉得有帮助，别忘了给我们点个 Star！
