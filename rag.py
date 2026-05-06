import os

import weaviate
from weaviate.classes.config import Property
from weaviate.collections.classes.config import Configure, DataType

class WeaviateRag:
    def __init__(self, docs_dir="./docs", collection_name="Documentation"):
        self.docs_dir = docs_dir
        self.collection_name = collection_name
        self.weaviate_client = weaviate.connect_to_local()

        self._setup_collection()

    def _setup_collection(self):
        try:
            if self.weaviate_client.collections.exists(self.collection_name):
                return
            
            self.weaviate_client.collections.create(
                name=self.collection_name,
                vector_config=Configure.Vectors.text2vec_transformers(),
                properties=[
                    Property(
                        name="content",
                        data_type=DataType.TEXT,
                        description="The text content of the documentation chunk",
                    ),
                     Property(
                        name="filename",
                        data_type=DataType.TEXT,
                        description="Source filename",
                        skip_vectorization=True,
                    ),
                     Property(
                        name="chunk_id",
                        data_type=DataType.INT,
                        description="Chunk number within the file",
                        skip_vectorization=True,
                    ),
                ]
            )
            
            print(f"Created collection: {self.collection_name}")
        
        except Exception as e:
            print(f"Erro setting up the collection: {e}")
            raise
    
    def chunk_text(self, text, chunk_size=500, overlap=50):
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i : i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)

        return chunks
    
    def index_documents(self, clear_existing=False):
        collection = self.weaviate_client.collections.get(self.collection_name)

        if clear_existing:
            self.weaviate_client.collections.delete(self.collection_name)
            self._setup_collection()

        total_chunks = 0

        for filename in os.listdir(self.docs_dir):
            if not filename.endswith(".md"):
                continue

            filepath = os.path.join(self.docs_dir, filename)
            print(f"Indexing {filename}...")

            try:
                with open(filepath, "r") as file:
                    content = file.read()

                chunks = self.chunk_text(content)

                with collection.batch.dynamic() as batch:
                    for i, chunk in enumerate(chunks):
                        batch.add_object(
                            properties={
                                "content": chunk,
                                "filename": filename,
                                "chunk_id": i,
                            }
                        )

                        total_chunks += 1
                    
                print(f"   -> Indexed {len(chunks)} chunks")

            except Exception as e:
                print(f"   => Exception while indexing: {e}")
        

        return total_chunks
    
    def search(self, query, top_k):
        collection = self.weaviate_client.collections.get(self.collection_name)

        try:
            reponse = collection.query.near_text(
                query=query, limit=top_k, return_metadata=['distance']
            )

            results = []

            for obj in reponse.objects:
                results.append(
                    {
                        "content": obj.properties["content"],
                        "filename": obj.properties["filename"],
                        "chunk_id": obj.properties["chunk_id"],
                        "distance": obj.metadata.distance,
                    }
                )

            
            return results

        except Exception as e:  
            print(f"Search error: {e}")
            raise
    
    def close(self):
        self.weaviate_client.close()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc, tb):
        self.close()

