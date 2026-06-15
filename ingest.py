"""ingest.py — 建立知識庫(離線跑一次)

流程:掃 corpus/**.md → 切塊(chunking)→ 算 embedding → 存進 Chroma 向量庫。
之後 ask.py 就是查這個庫。corpus 內容有更新時,重跑這支即可。

    python ingest.py
"""

import re

import chromadb
from chromadb.utils import embedding_functions

import config


def iter_blocks(text: str):
    """把 markdown 依空行切成一塊塊段落,同時記住「目前所在的標題」。

    回傳 (heading, block):heading 是這個段落最近的章節標題,
    用來在切塊時保留上下文(讓檢索到的片段知道自己屬於哪一節)。
    """
    heading = ""
    for raw in re.split(r"\n\s*\n", text):
        block = raw.strip()
        if not block:
            continue
        first_line = block.splitlines()[0]
        if first_line.lstrip().startswith("#"):
            heading = first_line.lstrip("# ").strip()
        yield heading, block


def chunk_markdown(text: str):
    """把一份 markdown 切成數個 chunk。

    策略:貪婪地把段落塞進同一個 chunk,直到接近 CHUNK_MAX_CHARS 就換下一個;
    每個 chunk 前面補上它的章節標題當作上下文;chunk 之間保留少量重疊段落。
    """
    chunks: list[dict] = []
    cur_blocks: list[str] = []
    cur_heading = ""
    cur_len = 0

    def flush():
        nonlocal cur_blocks, cur_len
        if not cur_blocks:
            return
        # 補章節標題當上下文;但若這個 chunk 本身就以標題開頭,就不重複補
        starts_with_heading = cur_blocks[0].lstrip().startswith("#")
        prefix = f"## {cur_heading}\n\n" if (cur_heading and not starts_with_heading) else ""
        chunks.append({"heading": cur_heading, "text": prefix + "\n\n".join(cur_blocks)})
        # 保留結尾幾個段落,當作下一個 chunk 的重疊(避免上下文斷裂)
        overlap = cur_blocks[-config.CHUNK_OVERLAP_BLOCKS :] if config.CHUNK_OVERLAP_BLOCKS else []
        cur_blocks = list(overlap)
        cur_len = sum(len(b) for b in cur_blocks)

    for heading, block in iter_blocks(text):
        if not cur_blocks:
            cur_heading = heading
        # 單一段落就超過上限 → 硬切成數段
        if len(block) > config.CHUNK_MAX_CHARS:
            flush()
            for i in range(0, len(block), config.CHUNK_MAX_CHARS):
                piece = block[i : i + config.CHUNK_MAX_CHARS]
                starts_with_heading = piece.lstrip().startswith("#")
                prefix = f"## {heading}\n\n" if (heading and not starts_with_heading) else ""
                chunks.append({"heading": heading, "text": prefix + piece})
            continue
        # 塞不下了 → 先收掉目前的 chunk 再開新的
        if cur_len + len(block) > config.CHUNK_MAX_CHARS:
            flush()
            cur_heading = heading
        cur_blocks.append(block)
        cur_len += len(block)

    flush()
    return chunks


def load_corpus():
    """讀 corpus/ 底下所有 .md,切塊,回傳 (ids, documents, metadatas)。"""
    ids, documents, metadatas = [], [], []
    md_files = sorted(config.CORPUS_DIR.rglob("*.md"))
    if not md_files:
        raise SystemExit(f"找不到任何 .md,請確認語料在 {config.CORPUS_DIR}")

    print(f"找到 {len(md_files)} 份文件,開始切塊…\n")
    for path in md_files:
        source = str(path.relative_to(config.CORPUS_DIR))  # 例:profile.md
        text = path.read_text(encoding="utf-8")
        chunks = chunk_markdown(text)
        for i, chunk in enumerate(chunks):
            ids.append(f"{source}::{i}")
            documents.append(chunk["text"])
            metadatas.append({"source": source, "heading": chunk["heading"]})
        print(f"  {source:<45} → {len(chunks)} chunks")
    return ids, documents, metadatas


def main():
    ids, documents, metadatas = load_corpus()
    print(f"\n總共 {len(documents)} 個 chunk。載入 embedding 模型(首次會下載)…")

    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=config.EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))

    # 重建:先刪掉舊的 collection,確保每次 ingest 都是乾淨的
    try:
        client.delete_collection(config.COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(name=config.COLLECTION_NAME, embedding_function=ef)

    print("算 embedding 並寫入向量庫…(這步會花一點時間)")
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    print(f"\n✅ 完成!知識庫已建立於 {config.CHROMA_DIR}")
    print(f"   {len(documents)} 個 chunk,模型:{config.EMBEDDING_MODEL}")
    print("   接下來執行:python ask.py")


if __name__ == "__main__":
    main()
