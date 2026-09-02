# GitHub 上传检查表

## 上传这些内容

- `README.md`
- `app.py`
- `config.py`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `rag/`
- `tests/`
- `docs/images/`

## 绝对不要上传

- `.env` 和 `.env.free`
- `data/` 下的论文和 PPT
- `test_*key.py`、`test_siliconflow*.py`等本地 Key 测试脚本
- `.codeartsdoer/`、`node_modules/`、`__pycache__/`

## GitHub 网页上传后检查

1. 仓库首页能正常显示 6 张截图。
2. 仓库根目录能看到 `.env.example` 和 `.gitignore`。
3. GitHub 搜索仓库不能搜到你的真实 API Key。
4. `data/papers/` 中没有上传论文原文。
5. 从一个干净目录按 README 的步骤可以启动项目。

## 仓库首页建议

- Description：`Explainable multi-PDF RAG assistant with reranking, page citations and PPT generation`
- Topics：`rag` `langchain` `faiss` `reranker` `streamlit` `qwen` `pdf` `pptx`
- 把该仓库 Pin 到 GitHub 个人主页。
