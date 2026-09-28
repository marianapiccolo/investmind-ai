# InvestMind AI Architecture

## Overview

InvestMind AI combines deterministic financial analytics with large language
models, controlled tool calling, persistent conversations, and
retrieval-augmented generation (RAG).

The core architectural principle is:

> Python calculates. Tools retrieve trusted data. RAG retrieves knowledge.
> AI explains.

The language model is not the source of truth for portfolio calculations.

## Architecture

```text
User
  |
  v
Django REST API
  |
  v
Conversational AI Analyst
  |
  +--------------------+
  |                    |
  v                    v
Conversation        Tool Calling
History                 |
                         +-----------------------------+
                         |              |              |
                         v              v              v
                    Portfolio      Financial      Other approved
                    Analytics      Knowledge      read-only tools
                         |              |
                         v              v
                    PostgreSQL      pgvector
                    Market Data     Knowledge Base
                         |              |
                         +-------+------+
                                 |
                                 v
                                LLM
                                 |
                                 v
                         Natural-language
                              response
```

## Deterministic Financial Analytics

Portfolio-specific financial calculations are performed by Python services.

Examples include:

- portfolio performance;
- risk analytics;
- composition;
- concentration;
- diversification;
- correlation;
- time-weighted returns;
- money-weighted returns;
- performance attribution;
- risk-adjusted performance.

The LLM does not independently calculate these metrics when backend tools are
available.

## AI Reports

Structured portfolio reports are generated from deterministic analytics.

Reports use schema-constrained outputs and are evaluated before being accepted.

AI reports can be generated asynchronously using Celery and persisted with
their context snapshot, evaluation result, model, status, and error state.

## Tool Calling

The AI Analyst can invoke an allowlisted set of read-only tools.

Portfolio tools include:

- `get_portfolio_performance`;
- `get_portfolio_risk`;
- `get_portfolio_composition`;
- `get_portfolio_diversification`.

Portfolio ownership is resolved by Django.

The LLM never selects or supplies a portfolio identifier.

## Persistent Conversations

AI conversations and user/assistant messages are stored in PostgreSQL.

Recent conversation history is supplied to the model so that follow-up
questions can be understood.

Conversation history provides linguistic context but is not treated as the
source of truth for current portfolio values.

When current financial information is required, the model can call the
appropriate backend tool again.

## Retrieval-Augmented Generation

RAG supplies curated financial knowledge used to explain concepts,
interpretations, and analytical limitations.

Portfolio-specific live data is not stored in the RAG knowledge base.

The RAG indexing flow is:

```text
Markdown documents
    |
    v
Heading-aware chunking
    |
    v
Token-limited chunks with overlap
    |
    v
OpenAI embeddings
    |
    v
PostgreSQL + pgvector
```

The retrieval flow is:

```text
User query
    |
    v
Query embedding
    |
    v
Cosine-distance search
    |
    v
Top-K knowledge chunks
```

The AI Analyst exposes retrieval through the tool:

- `search_financial_knowledge`.

This allows portfolio data and financial knowledge to be combined in the same
answer.

Example:

```text
Question:
"Why is my portfolio diversification weak?"

AI Analyst
    |
    +--> get_portfolio_diversification
    |
    +--> search_financial_knowledge
              |
              v
        diversification and
        correlation knowledge
```

## Knowledge Base

The curated knowledge base covers topics including:

- portfolio risk;
- volatility;
- maximum drawdown;
- diversification;
- concentration;
- correlation;
- investment returns;
- TWR;
- money-weighted returns;
- XIRR;
- performance attribution;
- analytical limitations.

Knowledge documents are version-detected using SHA-256 content hashes.

Unchanged documents are not re-embedded during ingestion.

## RAG Evaluation

Retrieval quality is evaluated using curated queries with expected source
sections.

Metrics include:

- Hit@K;
- Mean Reciprocal Rank (MRR).

The evaluation suite tests semantic retrieval rather than simple keyword
matching.

## Security

The AI architecture applies multiple controls:

- authenticated API access;
- portfolio ownership enforced by Django;
- allowlisted read-only tools;
- strict function schemas;
- no model-controlled portfolio identifiers;
- deterministic financial calculations;
- curated RAG documents;
- retrieved content treated as untrusted reference material;
- instructions inside retrieved content must not be followed;
- bounded tool-call rounds;
- bounded knowledge-search query length;
- explicit provider and orchestration error handling.

## Failure Handling

The system distinguishes between failures such as:

- AI provider errors;
- invalid model responses;
- invalid tool calls;
- unavailable market data;
- embedding provider failures;
- retrieval failures.

Existing portfolio information is preserved when RAG reindexing fails before
the database update transaction.

## Testing Strategy

The AI layer includes tests for:

- OpenAI client behavior;
- structured portfolio reports;
- AI evaluations;
- asynchronous report generation;
- tool registry and execution;
- tool calling;
- AI Analyst API;
- persistent conversations;
- embeddings;
- chunking;
- knowledge ingestion;
- pgvector retrieval;
- RAG tools;
- RAG evaluation;
- RAG security controls.

External providers are mocked in automated tests where appropriate.

PostgreSQL and pgvector retrieval are exercised through integration tests.

## Design Principle

The InvestMind AI architecture separates responsibilities:

```text
Python
→ calculates financial metrics

Portfolio tools
→ expose current structured portfolio facts

Conversation history
→ preserves conversational context

RAG
→ retrieves curated financial knowledge

LLM
→ selects approved capabilities and explains results
```

This separation reduces hallucination risk and keeps financial calculations
auditable and deterministic.
