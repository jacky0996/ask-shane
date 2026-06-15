"""切塊邏輯的單元測試(純函式,不碰網路 / 模型 / API)。"""

import config
from ingest import chunk_markdown, iter_blocks


def test_iter_blocks_tracks_heading():
    md = "# Title\n\nfirst para\n\n## Section\n\nsecond para"
    blocks = list(iter_blocks(md))
    headings = [h for h, _ in blocks]
    assert "Title" in headings
    assert headings[-1] == "Section"  # 段落會記住最近的標題


def test_chunk_markdown_returns_chunks():
    md = "# A\n\n" + "\n\n".join(f"para {i}" for i in range(5))
    chunks = chunk_markdown(md)
    assert chunks
    assert all("text" in c and "heading" in c for c in chunks)


def test_chunk_respects_max_chars():
    big = "x" * (config.CHUNK_MAX_CHARS * 3)
    chunks = chunk_markdown(f"# Big\n\n{big}")
    # 超大段落會被硬切;每塊不應遠超上限(允許標題前綴的少量超出)
    for c in chunks:
        assert len(c["text"]) <= config.CHUNK_MAX_CHARS + 100


def test_heading_recorded():
    chunks = chunk_markdown("# Profile\n\nsome content")
    assert chunks[0]["heading"] == "Profile"
