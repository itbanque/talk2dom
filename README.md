# talk2dom — Locate Web Elements with One Sentence

> 📚 [English](./README.md) | [中文](./README.zh.md)

![Stars](https://img.shields.io/github/stars/itbanque/talk2dom?style=social)
[![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
![CI](https://github.com/itbanque/talk2dom/actions/workflows/test.yaml/badge.svg)

**talk2dom** is a focused utility that solves one of the hardest problems in browser automation and UI testing:

> ✅ **Finding the correct UI element on a page.**

---

[![Watch the demo on YouTube](https://img.youtube.com/vi/6S3dOdWj5Gg/0.jpg)](https://youtu.be/6S3dOdWj5Gg)

---

## ⭐ Support the Project

If you like `talk2dom`, consider giving it a star on GitHub! It helps others discover the project and keeps the community growing.

<a href="https://github.com/itbanque/talk2dom">
  <img src="https://github.com/user-attachments/assets/6735404a-f54d-448c-91e7-808138c46454" alt="Light up the Star to support us" width="400"/>
</a>


## 🧠 Why `talk2dom`

In most automated testing or LLM-driven web navigation tasks, the real challenge is not how to click or type — it's how to **locate the right element**.

Think about it:

- Clicking a button is easy — *if* you know its selector.
- Typing into a field is trivial — *if* you've already located the right input.
- But finding the correct element among hundreds of `<div>`, `<span>`, or deeply nested Shadow DOM trees? That's the hard part.

**`talk2dom` is built to solve exactly that.**

---

## ✨ Philosophy

> Our goal is not to control the browser — you still control your browser. 
> Our goal is to **find the right DOM element**, so you can tell the browser what to do.

---

## ✅ Key Features

- 🔁 Persistent session for multi-step interactions  
- 🧠 LLM-powered understanding of high-level intent  
- 🧩 Outputs: actionable XPath/CSS selectors or ready-to-run browser steps  

---

## 🌐 Hosted API Service

`talk2dom` powers a **production-ready hosted service** — making it easy to integrate into your automation agents, testing pipelines, and internal tools.

### Getting Started

```bash
# Clone the repository
git clone https://github.com/itbanque/talk2dom.git
cd talk2dom

# Launch the talk2dom-integrated stack
docker compose up
```

The API is available at `http://localhost:8000/docs` with full OpenAPI schema and interactive Swagger UI.

---

## ⚙️ Service Features

The hosted version of `talk2dom` includes a full-featured backend system with:

* 🔐 **User Authentication & Account Management** — including registration, login, and session handling
* 🧾 **Project Management** — organize different workflows under separate projects
* 🔑 **API Key Management** — issue and revoke keys per project
* 💳 **Subscription & Credit System** — users can purchase or subscribe for API usage credits (Stripe supported)
* 🧠 **Intelligent Selector Caching** — automatic deduplication and re-use of prior LLM results via PostgreSQL

This transforms `talk2dom` from a Python utility into a scalable service with all necessary infrastructure to support production-grade applications.

Deploy on your own cloud or integrate with tools like Zapier, Retool, or internal RPA systems.

For detailed deployment instructions, contact us via GitHub discussions.

---

## 📄 License

This project is licensed under the [Creative Commons Attribution-NonCommercial 4.0 International License](https://creativecommons.org/licenses/by-nc/4.0/).

You may:
- ✅ Use, modify, and share the code for personal or research purposes
- ❌ Not use it in commercial applications without permission
- ✅ You must give appropriate credit, provide a link to the license, and indicate if changes were made.

📩 For commercial licensing, please contact: contact@itbanque.com

---

## Contributing

Please read [CONTRIBUTING.md](https://github.com/itbanque/talk2dom/blob/main/CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

---

## 💬 Questions or ideas?

We’d love to hear how you're using `talk2dom` in your AI agents or testing flows.  
Feel free to open issues or discussions!  
You can also tag us on GitHub if you’re building something interesting with `talk2dom`!  
⭐️ If you find this project useful, please consider giving it a star!
