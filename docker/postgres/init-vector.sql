-- Enable pgvector in the application database on first initialization.
CREATE EXTENSION IF NOT EXISTS vector;

-- Django creates test databases from template1 by default.
-- Enable pgvector there too, so fresh test databases inherit the extension.
\connect template1
CREATE EXTENSION IF NOT EXISTS vector;
