# InvestMind AI Knowledge Base

This directory contains the curated financial knowledge used by the
InvestMind AI retrieval-augmented generation (RAG) system.

The knowledge base contains educational and explanatory financial
content.

It must not contain portfolio-specific live data such as positions,
transactions, balances, market prices, returns, or current risk
metrics.

Portfolio-specific data is retrieved through controlled backend tools.

The RAG knowledge base is intended for concepts such as:

- portfolio risk;
- performance measurement;
- diversification;
- returns;
- financial metric interpretation;
- analytical limitations.

Documents are ingested into PostgreSQL, split into chunks, converted
into vector embeddings, and retrieved through semantic similarity
search.
