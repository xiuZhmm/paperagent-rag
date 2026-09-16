"""Page-aware local ingestion for the no-key retrieval workbench."""
from pathlib import Path
from io import BytesIO
import hashlib
import json
from pypdf import PdfReader
from src.paperagent.chunking import split_text
from .hybrid_retrieval import HybridIndex, cached_encode


def parse_upload(name, payload, chunk_size=500, overlap=100):
    # Basename is metadata only: uploaded names are never used as write paths.
    name=name.replace('\\','/').split('/')[-1]
    suffix=Path(name).suffix.lower()
    if suffix=='.pdf':
        reader=PdfReader(BytesIO(payload))
        if reader.is_encrypted: raise ValueError('请先解密PDF')
        pages=[page.extract_text() or '' for page in reader.pages]
    elif suffix in {'.txt','.md'}:
        pages=[payload.decode('utf-8-sig')]
    else:
        raise ValueError('仅支持PDF、UTF-8 TXT和Markdown')
    identity=hashlib.sha256(name.encode()+b'\0'+payload).hexdigest()[:16]
    records=[]
    for page,text in enumerate(pages,1):
        for number,chunk in enumerate(split_text(text,chunk_size,overlap)):
            records.append({'id':f'{identity}:p{page}:c{number}','source':name,
                            'page':page,'text':chunk,'document_sha256':hashlib.sha256(payload).hexdigest()})
    if not records: raise ValueError('文档没有可提取文本；扫描件需先做OCR')
    return records


def build_index(files, encoder=None, cache_dir='.cache/embeddings'):
    records=[]; seen=set()
    for name,payload in files:
        for record in parse_upload(name,payload):
            if record['id'] not in seen:
                records.append(record); seen.add(record['id'])
    vectors=cached_encode(encoder,[r['text'] for r in records],cache_dir) if encoder else None
    return HybridIndex(records,vectors,encoder)


def save_kb(index, directory, model_name=None):
    index.save(directory)
    (Path(directory)/'manifest.json').write_text(json.dumps({'version':1,'model':model_name,
        'chunks':len(index.records),'chunk_size':500,'overlap':100},ensure_ascii=False,indent=2),encoding='utf-8')
