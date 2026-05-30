# -*- coding: utf-8 -*-
"""
番茄小说书源服务 v1.0
为阅读App(legado)提供番茄小说书源

功能：
- 搜索番茄小说（多引擎fallback）
- 获取书籍详情和章节列表
- 解密番茄小说加密正文
- 生成legado可导入的书源JSON
- Web管理界面

部署：python fanqie_server.py
访问：http://localhost:8900
"""

import httpx
import json
import re
import time
import os
import sys
from urllib.parse import unquote, quote_plus
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from lxml import etree

app = FastAPI(title="番茄小说书源服务")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ============================================================
# 字符解密（番茄小说使用自定义字体加密正文）
# ============================================================
CODE = [[58344, 58715], [58345, 58716]]
CHARSET = None

def load_charset():
    global CHARSET
    if CHARSET is None:
        charset_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "charset.json")
        with open(charset_path, "r", encoding="utf-8") as f:
            CHARSET = json.load(f)
    return CHARSET

def decode_text(text: str) -> str:
    """解密番茄小说的字体加密文字"""
    charset = load_charset()
    result = []
    for ch in text:
        uni = ord(ch)
        decoded = False
        for mode in range(2):
            if CODE[mode][0] <= uni <= CODE[mode][1]:
                bias = uni - CODE[mode][0]
                if 0 <= bias < len(charset[mode]) and charset[mode][bias] != "?":
                    result.append(charset[mode][bias])
                    decoded = True
                    break
        if not decoded:
            result.append(ch)
    return "".join(result)

# ============================================================
# HTTP 客户端
# ============================================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

def get_client():
    return httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True)

# ============================================================
# 搜索功能（通过 novel.snssdk.com 移动端API）
# ============================================================
SNSSDK_HEADERS = {
    "User-Agent": "com.ss.android.article.news/7.0.3 (Linux; U; Android 12; zh_CN; Pixel 6)",
}

def search_books(keyword: str) -> list:
    """通过番茄小说移动端搜索API搜索书籍"""
    try:
        with httpx.Client(headers=SNSSDK_HEADERS, timeout=10) as client:
            r = client.get(
                "https://novel.snssdk.com/api/novel/channel/homepage/search/search/v1/",
                params={
                    "device_platform": "android",
                    "parent_enterfrom": "novel_channel_search.tab.",
                    "offset": "0",
                    "aid": "1967",
                    "q": keyword,
                },
            )
        d = r.json()
        books = d.get("data", {}).get("ret_data", [])
        results = []
        seen = set()
        for b in books:
            bid = b.get("book_id", "")
            if bid and bid not in seen:
                seen.add(bid)
                title = re.sub(r'<[^>]+>', '', b.get("title", ""))
                results.append({
                    "book_id": bid,
                    "book_name": title,
                    "book_author": b.get("author", ""),
                    "book_category": b.get("category", ""),
                    "book_score": b.get("score", ""),
                })
        return results
    except Exception as e:
        print(f"[search] Error: {e}")
        return []

# ============================================================
# 书籍详情
# ============================================================
def get_book_info(book_id: str) -> dict:
    """获取书籍详情和完整章节列表"""
    with get_client() as client:
        r = client.get(f"https://fanqienovel.com/page/{book_id}")

    ele = etree.HTML(r.text)
    title = (ele.xpath('//h1/text()') or ["未知"])[0]
    author = (ele.xpath('//span[@class="author-name-text"]/text()') or ["未知"])[0]
    desc_list = ele.xpath('//div[@class="page-abstract-content"]/p/text()')
    desc = desc_list[0] if desc_list else ""
    cover_list = ele.xpath('//img[contains(@class,"book-cover")]/@src')
    if not cover_list:
        cover_list = ele.xpath('//meta[@property="og:image"]/@content')
    cover = cover_list[0] if cover_list else ""
    status_list = ele.xpath('//span[@class="info-label-yellow"]/text()')
    status = status_list[0] if status_list else ""

    chapters = []
    for ch in ele.xpath('//div[@class="chapter"]/div/a'):
        ch_text = ch.text or ""
        ch_href = ch.xpath("@href")
        ch_id = ch_href[0].split("/")[-1] if ch_href else ""
        if ch_id:
            chapters.append({"title": decode_text(ch_text), "id": ch_id})

    return {
        "book_id": book_id,
        "title": decode_text(title),
        "author": decode_text(author),
        "desc": decode_text(desc),
        "cover": cover,
        "status": decode_text(status),
        "chapter_count": len(chapters),
        "chapters": chapters,
    }

# ============================================================
# 章节正文
# ============================================================
def get_chapter_content(chapter_id: str) -> str:
    """获取并解密章节正文"""
    with get_client() as client:
        r = client.get(f"https://fanqienovel.com/reader/{chapter_id}")

    ele = etree.HTML(r.text)
    p_elements = ele.xpath('//div[@class="muye-reader-content noselect"]//p')
    if not p_elements:
        p_elements = ele.xpath('//div[contains(@class,"reader-content")]//p')

    paragraphs = []
    for p in p_elements:
        text = p.text or ""
        if text.strip():
            paragraphs.append(decode_text(text))
    return "\n".join(paragraphs)

# ============================================================
# Web 界面
# ============================================================
WEB_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🍅 番茄小说书源</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     background:#f5f5f5;color:#333;min-height:100vh}
.container{max-width:700px;margin:0 auto;padding:20px}
h1{text-align:center;padding:30px 0;font-size:28px}
h1 span{font-size:36px}
.card{background:#fff;border-radius:12px;padding:24px;margin:16px 0;
      box-shadow:0 2px 8px rgba(0,0,0,.08)}
.card h2{font-size:18px;margin-bottom:16px;color:#e74c3c}
input[type=text]{width:100%;padding:12px 16px;border:2px solid #e0e0e0;
                 border-radius:8px;font-size:16px;outline:none;transition:.2s}
input[type=text]:focus{border-color:#e74c3c}
.btn{display:inline-block;padding:12px 24px;background:#e74c3c;color:#fff;
     border:none;border-radius:8px;font-size:16px;cursor:pointer;margin-top:12px;
     transition:.2s}
.btn:hover{background:#c0392b}
.btn-sm{padding:8px 16px;font-size:14px;margin:4px}
.result{margin-top:16px;padding:12px;background:#f9f9f9;border-radius:8px;
        display:none;word-break:break-all}
.result.show{display:block}
.copy-btn{background:#27ae60;color:#fff;border:none;padding:6px 12px;
          border-radius:6px;cursor:pointer;font-size:13px}
.copy-btn:hover{background:#219a52}
code{background:#f0f0f0;padding:2px 6px;border-radius:4px;font-size:14px}
.step{display:flex;align-items:flex-start;margin:8px 0}
.step-num{background:#e74c3c;color:#fff;width:24px;height:24px;border-radius:50%;
          display:flex;align-items:center;justify-content:center;font-size:13px;
          font-weight:bold;margin-right:10px;flex-shrink:0}
.api-table{width:100%;border-collapse:collapse;margin-top:12px}
.api-table td,.api-table th{padding:8px 12px;border-bottom:1px solid #eee;text-align:left}
.api-table th{color:#888;font-weight:normal;font-size:13px}
.api-table a{color:#e74c3c;text-decoration:none}
.api-table a:hover{text-decoration:underline}
.loading{display:none;color:#888;margin-top:12px}
.loading.show{display:block}
#search-results .book-item{padding:10px;border-bottom:1px solid #eee;cursor:pointer;transition:.2s}
#search-results .book-item:hover{background:#fff5f5}
#search-results .book-item:last-child{border-bottom:none}
.book-title{font-weight:bold;font-size:15px}
.book-id{color:#888;font-size:12px}
</style>
</head>
<body>
<div class="container">
<h1><span>🍅</span> 番茄小说书源</h1>

<div class="card">
<h2>📖 导入到阅读App</h2>
<div class="step"><div class="step-num">1</div><div>复制下方书源链接</div></div>
<div class="step"><div class="step-num">2</div><div>打开阅读App → 书源管理 → 右上角+ → 网络导入</div></div>
<div class="step"><div class="step-num">3</div><div>粘贴链接，确认导入</div></div>
<div style="margin-top:16px">
<input type="text" id="source-url" readonly>
<button class="btn btn-sm" onclick="copySource()" style="margin-left:8px">复制链接</button>
</div>
</div>

<div class="card">
<h2>🔍 搜索书籍</h2>
<p style="color:#e74c3c;font-size:14px;margin-bottom:12px">
⚠️ 番茄小说搜索接口有滑块验证，自动搜索暂不可用。<br>
请在番茄小说App/网页中搜索书籍，然后复制链接粘贴到下方。</p>
<div style="display:flex;gap:8px;align-items:center">
<input type="text" id="search-input" placeholder="输入书名，如：斗破苍穹" 
       onkeydown="if(event.key==='Enter')doSearch()" style="flex:1">
<button class="btn" onclick="doSearch()">搜索</button>
</div>
<div class="loading" id="search-loading">搜索中...</div>
<div id="search-results"></div>
</div>

<div class="card">
<h2>🔗 通过链接添加</h2>
<p style="color:#666;font-size:14px;margin-bottom:12px">
粘贴番茄小说链接，自动提取book_id</p>
<input type="text" id="url-input" placeholder="https://fanqienovel.com/page/7143038691944959011">
<button class="btn" onclick="addByUrl()">添加</button>
<div class="result" id="url-result"></div>
</div>

<div class="card">
<h2>📡 API 接口</h2>
<table class="api-table">
<tr><th>接口</th><th>说明</th></tr>
<tr><td><a href="/search?keyword=斗破苍穹">/search?keyword=xxx</a></td><td>搜索书籍</td></tr>
<tr><td><a href="/info?book_id=7143038691944959011">/info?book_id=xxx</a></td><td>书籍详情+目录</td></tr>
<tr><td><a href="/content?chapter_id=7173216089122439711">/content?chapter_id=xxx</a></td><td>章节正文</td></tr>
<tr><td><a href="/booksource">/booksource</a></td><td>legado书源JSON</td></tr>
</table>
</div>

<div class="card">
<h2>🛠️ 部署说明</h2>
<p style="font-size:14px;color:#666;line-height:1.8">
本服务需要部署到能访问外网的服务器上。<br>
安装依赖：<code>pip install fastapi uvicorn httpx lxml</code><br>
启动服务：<code>python fanqie_server.py</code><br>
默认端口 8900，启动后访问此页面获取书源链接。<br><br>
<b>⚠️ 注意：</b>番茄小说的搜索/正文接口有反爬机制，搜索可能偶尔失败。
建议直接从番茄小说App或网页复制链接，通过"链接添加"功能导入。
</p>
</div>
</div>

<script>
var host = location.origin;
document.getElementById("source-url").value = host + "/booksource";

function copySource() {
    var inp = document.getElementById("source-url");
    inp.select();
    document.execCommand("copy");
    alert("已复制！");
}

function doSearch() {
    var kw = document.getElementById("search-input").value.trim();
    if (!kw) return;
    document.getElementById("search-loading").classList.add("show");
    document.getElementById("search-results").innerHTML = "";
    
    fetch("/search?keyword=" + encodeURIComponent(kw))
    .then(r => r.json())
    .then(data => {
        document.getElementById("search-loading").classList.remove("show");
        var html = "";
        if (data.code === 0 && data.data && data.data.length > 0) {
            data.data.forEach(function(b) {
                html += '<div class="book-item" onclick="showBook(\'' + b.book_id + '\')">' +
                    '<div class="book-title">' + (b.book_name || b.book_id) + '</div>' +
                    '<div class="book-id">ID: ' + b.book_id + '</div></div>';
            });
        } else {
            html = '<div style="padding:12px;color:#888">未找到结果，请尝试复制链接直接添加</div>';
        }
        document.getElementById("search-results").innerHTML = html;
    })
    .catch(function(e) {
        document.getElementById("search-loading").classList.remove("show");
        document.getElementById("search-results").innerHTML = 
            '<div style="padding:12px;color:#e74c3c">搜索失败: ' + e.message + '</div>';
    });
}

function showBook(bookId) {
    fetch("/info?book_id=" + bookId)
    .then(r => r.json())
    .then(data => {
        if (data.code === 0) {
            var d = data.data;
            alert("《" + d.title + "》\\n作者：" + d.author + 
                  "\\n章节数：" + d.chapter_count + 
                  "\\n\\n已在阅读App中可搜索到此书");
        }
    });
}

function addByUrl() {
    var url = document.getElementById("url-input").value.trim();
    var m = url.match(/fanqienovel\\.com\\/(?:page|reader)\\/(\\d+)/);
    if (!m) {
        alert("无法从链接中提取book_id，请检查链接格式");
        return;
    }
    var bookId = m[1];
    var res = document.getElementById("url-result");
    res.classList.add("show");
    res.innerHTML = "正在获取书籍信息...";
    
    fetch("/info?book_id=" + bookId)
    .then(r => r.json())
    .then(data => {
        if (data.code === 0) {
            var d = data.data;
            res.innerHTML = '<b>《' + d.title + '》</b><br>' +
                '作者：' + d.author + '<br>' +
                '状态：' + d.status + '<br>' +
                '章节数：' + d.chapter_count + '<br><br>' +
                '在阅读App中搜索 "<b>' + d.title + '</b>" 即可找到此书';
        } else {
            res.innerHTML = "获取失败：" + (data.msg || "未知错误");
        }
    })
    .catch(function(e) {
        res.innerHTML = "请求失败：" + e.message;
    });
}
</script>
</body></html>"""

@app.get("/")
def index():
    return HTMLResponse(WEB_HTML)

# ============================================================
# API 端点
# ============================================================
@app.get("/search")
def api_search(keyword: str = Query(..., description="搜索关键词")):
    """搜索番茄小说，返回book_id列表"""
    try:
        results = search_books(keyword)
        for r in results:
            r["book_url"] = f"https://fanqienovel.com/page/{r['book_id']}"
        return {"code": 0, "data": results}
    except Exception as e:
        return {"code": -1, "msg": str(e)}

@app.get("/info")
def api_info(book_id: str = Query(..., description="书籍ID")):
    """获取书籍详情和章节列表"""
    try:
        info = get_book_info(book_id)
        return {"code": 0, "data": info}
    except Exception as e:
        return {"code": -1, "msg": str(e)}

@app.get("/content")
def api_content(chapter_id: str = Query(..., description="章节ID")):
    """获取解密后的章节正文"""
    try:
        content = get_chapter_content(chapter_id)
        return {"code": 0, "data": {"content": content}}
    except Exception as e:
        return {"code": -1, "msg": str(e)}

@app.get("/booksource")
def api_booksource(request: Request, host: str = Query(None, description="服务地址")):
    """生成legado书源JSON"""
    if not host:
        # 自动从请求中获取实际访问地址
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        req_host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost:8900"))
        host = f"{scheme}://{req_host}"
    host = host.rstrip("/")

    source = [
        {
            "bookSourceName": "番茄小说（自建）",
            "bookSourceGroup": "番茄小说",
            "bookSourceUrl": host,
            "enabled": True,
            "enabledExplore": False,
            "lastUpdateTime": int(time.time() * 1000),
            "searchUrl": "https://novel.snssdk.com/api/novel/channel/homepage/search/search/v1/?device_platform=android&parent_enterfrom=novel_channel_search.tab.&offset={{(page-1)*10}}&aid=1967&q={{key}}",
            "ruleSearch": {
                "bookList": "$.data.ret_data[*]",
                "name": "title##<em>|</em>|《|》",
                "author": "author",
                "bookUrl": host + "/info?book_id={{$.book_id}}",
                "coverUrl": "$.thumb_url",
                "intro": "$.abstract"
            },
            "ruleBookInfo": {
                "name": "$.data.title",
                "author": "$.data.author",
                "coverUrl": "$.data.cover",
                "intro": "$.data.desc",
                "lastChapter": "",
                "wordCount": "",
                "tocUrl": host + "/info?book_id={{$.data.book_id}}"
            },
            "ruleToc": {
                "chapterList": "$.data.chapters",
                "chapterName": "$.title",
                "chapterUrl": host + "/content?chapter_id={{$.id}}"
            },
            "ruleContent": {
                "content": "$.data.content"
            }
        }
    ]
    return JSONResponse(content=source)

# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("🍅 番茄小说书源服务")
    print("=" * 50)
    print(f"访问 http://localhost:8900 获取书源")
    print(f"书源链接: http://localhost:8900/booksource")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8900)
