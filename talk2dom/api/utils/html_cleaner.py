from bs4 import BeautifulSoup, Comment


def clean_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")

    # 定义不需要的标签
    blacklist = [
        "script",
        "style",
        "meta",
        "link",
        "noscript",
        "iframe",
        "svg",
        "object",
        "embed",
    ]

    for tag in soup(blacklist):
        tag.decompose()  # 彻底移除标签及其内容

    # 可选：还可以去掉注释
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
        # 只保留 <body>
    body = soup.body
    return str(body) if body else ""
