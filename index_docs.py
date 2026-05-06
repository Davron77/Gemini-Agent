from rag import WeaviateRag


def main():
    print("Starting documentation indexing...")

    with WeaviateRag() as rag:
        total_chunks = rag.index_documents()
        print(f"Indexed {total_chunks} chunks")


if __name__ == "__main__":
    main()