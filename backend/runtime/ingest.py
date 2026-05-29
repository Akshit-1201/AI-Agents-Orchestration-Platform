"""CLI to ingest documents into the RAG vector store.

Usage (from backend/):  python -m runtime.ingest <path> [--collection NAME]
Example:                python -m runtime.ingest knowledge --collection default
"""
import argparse

from runtime.rag import ingest_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest documents into the RAG vector store.")
    ap.add_argument("path", help="A file or folder of .txt/.md/.pdf documents")
    ap.add_argument("--collection", default="default", help="Target collection name")
    args = ap.parse_args()
    count = ingest_path(args.path, args.collection)
    print(f"Ingested {count} chunks into collection '{args.collection}'.")


if __name__ == "__main__":
    main()
