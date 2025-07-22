# talk2dom — Locate Web Elements with One Sentence

> 📚 [English](./README.md) | [中文](./README.zh.md)

![PyPI](https://img.shields.io/pypi/v/talk2dom)
[![PyPI Downloads](https://static.pepy.tech/badge/talk2dom)](https://pepy.tech/projects/talk2dom)
![Stars](https://img.shields.io/github/stars/itbanque/talk2dom?style=social)
![License](https://img.shields.io/github/license/itbanque/talk2dom)
![CI](https://github.com/itbanque/talk2dom/actions/workflows/test.yaml/badge.svg)

**talk2dom** is a focused utility that solves one of the hardest problems in browser automation and UI testing:

> ✅ **Finding the correct UI element on a page.**

---

[![Watch the demo on YouTube](https://img.youtube.com/vi/6S3dOdWj5Gg/0.jpg)](https://youtu.be/6S3dOdWj5Gg)


## 🧠 Why `talk2dom`

In most automated testing or LLM-driven web navigation tasks, the real challenge is not how to click or type — it's how to **locate the right element**.

Think about it:

- Clicking a button is easy — *if* you know its selector.
- Typing into a field is trivial — *if* you've already located the right input.
- But finding the correct element among hundreds of `<div>`, `<span>`, or deeply nested Shadow DOM trees? That's the hard part.

**`talk2dom` is built to solve exactly that.**

---

## 🎯 What it does

`talk2dom` helps you locate elements by:

- Understands natural language instructions and turns them into browser actions  
- Supports single-command execution or persistent interactive sessions  
- Uses LLMs (like GPT-4 or Claude) to analyze live HTML and intent  
- Returns flexible output: actions, selectors, or both — providing flexible outputs: actions, selectors, or both — depending on the instruction and model response  
- Compatible with both desktop and mobile browsers via Selenium

---

## 🗃️ Optional: Enable Locator Caching (PostgreSQL)

To avoid recomputing selectors every time, `talk2dom` can cache results in a PostgreSQL database.

### How it works

* For each `instruction + html` pair, a unique SHA256 hash is generated.
* If a previous result exists, `talk2dom` reuses it and skips the LLM call.
* Greatly improves performance and reduces token usage.

### Setup

Set the `DB_URI` environment variable:

```bash
export DB_URI="postgresql+psycopg2://user:password@localhost:5432/dbname"
```

If `DB_URI` is not set, caching is automatically disabled, and all requests will use LLM inference in real-time.

---

## 🤔 Why Selenium?

While there are many modern tools for controlling browsers (like Playwright or Puppeteer), **Selenium remains the most robust and cross-platform solution**, especially when dealing with:

- ✅ Safari (WebKit)
- ✅ Firefox
- ✅ Mobile browsers
- ✅ Cross-browser testing grids

These tools often have limited support for anything beyond Chrome-based browsers. Selenium, by contrast, has battle-tested support across all major platforms and continues to be the industry standard in enterprise and CI/CD environments.

That’s why `talk2dom` is designed to integrate directly with Selenium — it works where the real-world complexity lives.

---

## 📦 Installation

```bash
pip install talk2dom
```

---

## 🧩 Code-Based ActionChain Mode

For developers and testers who prefer structured Python control, `ActionChain` lets you drive the browser step-by-step.

### Basic Usage

By default, talk2dom uses gpt-4o-mini to balance performance and cost.
However, during testing, gpt-4o has shown the best performance for this task.

#### Make sure you have OPENAI_API_KEY

```bash
export OPENAI_API_KEY="..."
```

Note: All models must support chat completion APIs and follow OpenAI-compatible schema.

#### Sample Code

```python
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

from talk2dom import ActionChain

driver = webdriver.Chrome()

ActionChain(driver) \
    .open("http://www.python.org") \
    .find("Find the Search box") \
    .type("pycon") \
    .wait(2) \
    .type(Keys.RETURN) \
    .assert_page_not_contains("No results found.") \
    .valid("the 'PSF PyCon Trademark Usage Policy' is displayed") \ 
    .close()
```

### Free Models

You can also use `talk2dom` with free models like `llama-3.3-70b-versatile` from [Groq](https://groq.com/).


### Full page vs Scoped element queries
The `find()` function can be used to query the entire page or a specific element.
You can pass either a full Selenium `driver` or a specific `WebElement` to scope the locator to part of the page.
#### Why/When use `WebElement` instead of `driver`?

1. Reduce Token Usage — Passing a smaller HTML subtree (like a modal or container) instead of the full page saves LLM tokens, reducing latency and cost.
2. Improve Locator Accuracy — Scoping the query helps the LLM focus on relevant content, which is especially helpful for nested or isolated components like popups, drawers, and cards.

You don’t need to extract HTML manually — `talk2dom` will automatically use `outerHTML` from any `WebElement` you pass in.

---


## ✨ Philosophy

> Our goal is not to control the browser — you still control your browser. 
> Our goal is to **find the right DOM element**, so you can tell the browser what to do.

---

## ✅ Key Features

- 💬 Natural language interface to control the browser  
- 🔁 Persistent session for multi-step interactions  
- 🧠 LLM-powered understanding of high-level intent  
- 🧩 Outputs: actionable XPath/CSS selectors or ready-to-run browser steps  
- 🧪 Built-in assertions and step validations  
- 💡 Works with both CLI scripts and interactive chat

---

## 📄 License

Apache 2.0

---

## Contributing

Please read [CONTRIBUTING.md](https://github.com/itbanque/talk2dom/blob/main/CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

---

## 💬 Questions or ideas?

We’d love to hear how you're using `talk2dom` in your AI agents or testing flows.  
Feel free to open issues or discussions!  
You can also tag us on GitHub if you’re building something interesting with `talk2dom`!  
⭐️ If you find this project useful, please consider giving it a star!