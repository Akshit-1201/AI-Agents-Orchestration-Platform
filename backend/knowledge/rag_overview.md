# Retrieval-Augmented Generation (RAG) in Yuno

RAG lets an agent answer questions using an ingested knowledge base instead of relying
only on the model's training data.

## How it works in Yuno
1. **Ingestion**: documents in `backend/knowledge/` are split into ~1000-character
   chunks (150-character overlap), embedded, and stored in a local **Chroma** vector
   database under `VECTOR_STORE_DIR`.
2. **Embeddings**: the query and chunks are embedded with Gemini `text-embedding-004`,
   falling back to the local Ollama `nomic-embed-text` model.
3. **Retrieval**: the `knowledge_search` tool embeds the user's query, finds the
   top-K most similar chunks (default K=4), and returns them with their source filenames.
4. **Generation**: the agent uses the retrieved context to ground its answer.

## Adding documents
Drop `.txt`, `.md`, or `.pdf` files into `backend/knowledge/` and run:

    python -m runtime.ingest backend/knowledge --collection default

Ingestion is idempotent — re-running updates existing chunks rather than duplicating them.
