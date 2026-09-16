"""No-key local document search UI. It does not pretend retrieved text is an answer."""
from pathlib import Path
import json
import os
import time
import streamlit as st
from rag.hybrid_retrieval import FastEncoder, HybridIndex
from rag.knowledge_base import build_index, save_kb

ROOT=Path(__file__).resolve().parent
KB=Path(os.environ.get('PAPERAGENT_KB_DIR',str(ROOT/'knowledge_base/workbench')))
MODEL='sentence-transformers/all-MiniLM-L6-v2'
st.set_page_config(page_title='PaperAgent 检索实验室',layout='wide')
st.title('PaperAgent · 检索实验室')
st.caption('文档检索、原文核验与方法对比。无需API Key；此界面不调用生成模型。')

@st.cache_resource
def encoder():
    local=ROOT/'.cache/models/fast-all-MiniLM-L6-v2'
    if not (local/'model.onnx').exists():
        raise ValueError('尚未下载向量模型。先运行 python scripts/download_model.py，或关闭向量检索，仅使用BM25。')
    return FastEncoder(MODEL,model_dir=str(local))

with st.sidebar:
    st.header('知识库')
    use_dense=st.checkbox('启用向量与混合检索',value=True)
    st.caption('内置MiniLM是英文模型。中文文档可先用BM25，语义检索需更换并评测多语言模型。')
    uploads=st.file_uploader('上传PDF、TXT或Markdown',type=['pdf','txt','md'],accept_multiple_files=True)
    build=st.button('构建上传文档索引',disabled=not uploads)
    example=st.button('加载示例文档')
    if build or example:
        try:
            files=[(p.name,p.read_bytes()) for p in sorted((ROOT/'examples/documents').glob('*.txt'))] if example else [(f.name,f.getvalue()) for f in uploads]
            if sum(len(data) for _,data in files)>50*1024*1024: raise ValueError('单次上传请控制在50MB以内')
            with st.spinner('构建索引…'):
                idx=build_index(files,encoder() if use_dense else None,ROOT/'.cache/embeddings')
                save_kb(idx,KB,MODEL if use_dense else None)
                st.session_state['index']=idx
            st.success(f'已保存 {len(idx.records)} 个文本块')
        except Exception as e: st.error(str(e))
    if st.button('加载上次保存的索引'):
        try:
            manifest=json.loads((KB/'manifest.json').read_text(encoding='utf-8'))
            if manifest['model'] not in {None,MODEL}: raise ValueError('索引模型与当前编码器不匹配，请重建')
            st.session_state['index']=HybridIndex.load(KB,encoder() if manifest['model'] else None)
            st.success('索引已恢复')
        except Exception as e: st.error(str(e))

search_tab,report_tab=st.tabs(['文档检索','公开数据实测'])
with search_tab:
    idx=st.session_state.get('index')
    if idx is None:
        st.info('在左侧上传文档并构建索引，或加载示例文档。示例为人工编写的功能演示，不作为效果评测数据。')
    else:
        st.write(f'当前知识库：{len({r["source"] for r in idx.records})}份文档 / {len(idx.records)}个文本块')
        sources=['全部文档']+sorted({r['source'] for r in idx.records})
        source=st.selectbox('限定文档',sources)
        modes=['bm25','dense','hybrid'] if idx.vectors is not None else ['bm25']
        mode=st.selectbox('检索方法',modes,index=len(modes)-1)
        weight=st.slider('混合检索中的向量权重',0.0,1.0,0.5,0.05)
        question=st.text_input('输入检索问题',placeholder='How is a repeated refund request prevented?')
        if st.button('检索',type='primary'):
            start=time.perf_counter()
            try:
                hits=idx.search(question,k=5,pool=100,mode=mode,weight=weight,source=None if source==sources[0] else source)
                st.caption(f'耗时 {(time.perf_counter()-start)*1000:.1f}ms。分数仅用于排序，不代表答案正确概率。')
                if not hits: st.warning('没有匹配文本。尝试其他关键词或文档范围。')
                for number,hit in enumerate(hits,1):
                    with st.expander(f'{number}. {hit["source"]} · 第{hit["page"]}页',expanded=True):
                        st.text(hit['text'])
                        st.caption(f'向量排名：{hit["dense_rank"]}｜关键词排名：{hit["bm25_rank"]}｜排序分数：{hit["score"]:.6f}')
                        st.code(hit['id'],language=None)
                st.download_button('导出检索证据JSON',json.dumps(hits,ensure_ascii=False,indent=2),'retrieval-evidence.json','application/json')
            except Exception as e: st.error(str(e))
with report_tab:
    report=ROOT/'reports/scifact/REPORT.md'
    if report.exists(): st.markdown(report.read_text(encoding='utf-8'))
    else: st.info('运行 scripts/benchmark.py 后显示真实评测结果。')
