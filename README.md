# 番茄小说书源服务 🍅

为阅读 App（legado）搭建番茄小说书源服务，实现搜索、目录、正文解密的完整链路。

## 功能

- 🔍 搜索番茄小说（移动端 API，无需签名）
- 📖 获取书籍详情和章节列表
- 📝 解密番茄小说加密正文
- 📦 生成 legado 可导入的书源 JSON
- 🌐 Web 管理界面

## 快速开始

```bash
# 克隆项目
git clone https://github.com/gs1147/fanqie-booksource.git
cd fanqie-booksource

# 安装依赖
pip install fastapi uvicorn httpx lxml

# 启动服务
python fanqie_server.py
```

访问 `http://localhost:8900` 查看管理界面。

## 文档

详细搭建教程请查看 [搭建指南](搭建指南.md)

## 相关项目

- [fanqienovel-downloader](https://github.com/ying-ck/fanqienovel-downloader) - charset.json 来源
- [aoaostar/legado](https://github.com/aoaostar/legado) - 番茄书源参考
- [legado 官方](https://github.com/gedoor/legado) - 阅读 App

## 许可证

MIT
