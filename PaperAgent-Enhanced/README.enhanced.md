# PaperAgent Enhanced

现有PaperAgent的检索增强版本：BM25、MiniLM向量召回、加权RRF、按来源过滤、页码证据、索引保存恢复，以及公开数据评测。保留原项目的重排、问答和PPT代码。

**先运行无需API Key的检索实验室，查看实际代码和结果。** 原始说明见README.original.md；增强内容及简历用语见[docs/ENHANCEMENT.md](docs/ENHANCEMENT.md)。

## 已有实测

BEIR SciFact，5,183篇英文文献、200条开发查询、300条官方测试查询。开发侧剔除2条与测试文本重复的查询。

| 方法 | Recall@20 | nDCG@10 |
|---|---:|---:|
| BM25 | 82.59% | 0.6645 |
| MiniLM向量 | 82.80% | 0.6239 |
| 加权RRF混合 | 88.36% | 0.6793 |

完整报告：[reports/scifact/REPORT.md](reports/scifact/REPORT.md)。原始逐题结果、测试报告和第二次复现结果一并保留。这不是生成答案准确率；没有微调模型。

## 快速运行

推荐Python 3.12，CPU即可。Windows PowerShell进入本目录后运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-workbench.txt
.\.venv\Scripts\python.exe scripts/download_model.py
.\.venv\Scripts\python.exe -m streamlit run enhanced_app.py --server.address 127.0.0.1
```

也可运行 `./Start-Workbench.ps1`，脚本完成上述步骤。不需要配置LLM API Key。首次需要联网安装依赖、下载约90MB模型。下载脚本使用FastEmbed官方镜像并核验固定SHA256，不关闭HTTPS验证。

打开页面后：

1. 点击左侧“加载示例文档”，或上传自己的PDF/TXT/Markdown。
2. 输入 `How is a repeated refund request prevented?` 并检索。
3. 切换BM25、向量、混合，查看原文、来源、页码和两路排名。
4. 限定某一文档，验证来源过滤；可导出证据JSON。
5. 重启后点击“加载上次保存的索引”。“公开数据实测”标签展示报告。

模型暂时下载不了时，取消“启用向量与混合检索”，仍可完成BM25建库和查询。界面不生成答案，避免将检索片段误当作已验证回答。

## 复现实验

```powershell
.\.venv\Scripts\python.exe scripts/download_scifact.py
.\.venv\Scripts\python.exe scripts/download_model.py
.\.venv\Scripts\python.exe scripts/benchmark.py
```

数据和模型首轮下载完成后，后续使用本地文件与缓存。输出默认到 `reports/scifact`，用 `--output reports/my-run` 可保留已有报告。固定权重候选和开发集种子，禁止看过测试结果后再选参数。

原始机器运行采用FastEmbed 0.8.0、MiniLM镜像、128-token截断；模型文件哈希和环境见summary.json。更换模型、分词器或数据后结果不再可直接比较。缓存键包含文本内容和次序、模型名称、查询/文档模式；替换同名模型文件时请使用新的 `--cache` 目录。

## 运行检查

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-integration.txt
.\.venv\Scripts\python.exe -m pytest tests/test_core.py tests/test_enhancement.py tests/test_workbench.py -q
```

本地真实编码器界面测试需要先下载模型，否则仅该项会跳过。测试涵盖原FAISS结果等价性、原应用混合检索入口、Embedding API乱序、来源过滤、缓存键、索引恢复及实际界面操作。测试报告为 `reports/tests.xml`。

## 原问答应用使用增强

按README.original.md安装原应用依赖和配置生成模型。新增配置：

```dotenv
RETRIEVAL_MODE=hybrid
HYBRID_DENSE_WEIGHT=0.5
HYBRID_POOL=100
EMBEDDING_SOURCE=fastembed
RERANKER_ENABLED=false
```

再运行 `streamlit run app.py`。默认仍为dense，便于对照；也可在原界面选择召回方式。需要生成回答/PPT时才配置自己的LLM Key。重排开启时另需原项目的sentence-transformers模型。本次未以真实付费接口验证回答与PPT生成。

## 文件导航

- `rag/hybrid_retrieval.py`：应用和评测共用的召回实现。
- `rag/knowledge_base.py`：PDF/TXT/Markdown解析与可追踪分块。
- `enhanced_app.py`：无需Key的本地检索界面。
- `scripts/benchmark.py`：开发集选择、测试集评测、区间与案例导出。
- `reports/scifact/`：首次实测完整记录。
- `reports/scifact-repro/`：固定配置复现记录。
- `docs/ENHANCEMENT.md`：范围、限制、简历表述和面试说明。

## 边界及来源

内置MiniLM是英文模型，中文仅验证了关键词路径的工程行为，未证明中文语义效果。扫描PDF需先OCR。系统是本机单用户原型，不含生产级认证、并发事务或业务监控。

原仓库：https://github.com/xiuZhmm/paperagent-rag 。保留PROJECT_PROVENANCE.md和LICENSE_NOTE.md，本次不擅自给原代码增加开源许可证。MiniLM模型遵循其Apache-2.0许可，公开数据以原数据发布方许可为准。模型权重和数据不包含在源码压缩包中。
