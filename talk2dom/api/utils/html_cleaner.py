from bs4 import BeautifulSoup, Comment
import re


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

    for tag in soup.find_all(style=True):
        original_style = tag["style"]
        cleaned_style = re.sub(
            r"opacity\s*:\s*[^;]+;?", "", original_style, flags=re.IGNORECASE
        ).strip()
        if cleaned_style:
            tag["style"] = cleaned_style
        else:
            del tag["style"]

    # 只保留 body 内容（不包括 body 标签）
    if soup.body:
        cleaned = "".join(str(child) for child in soup.body.children)
    else:
        cleaned = str(soup)

        # 去掉所有换行、回车、制表符
    cleaned = cleaned.replace("\n", "").replace("\r", "").replace("\t", "")
    # 只保留 <body>
    return cleaned.strip()
