from langchain.chains import RetrievalQA
from langchain.llms import OpenAI

# Initialize OpenAI LLM
llm = OpenAI(model_name="gpt-4", api_key="your_openai_api_key")

# Define a custom retriever function
def search_opensearch(query):
    query_vector = embedding_model.embed_query(query)
    query_payload = {
        "size": 5,
        "query": {
            "knn": {
                "vector_embedding": {
                    "vector": query_vector,
                    "k": 5
                }
            }
        }
    }
    search_url = f"{OPENSEARCH_URL}/{OPENSEARCH_INDEX}/_search"
    response = requests.post(search_url, auth=AUTH, json=query_payload, headers=headers)
    results = response.json()
    docs = [hit["_source"]["content"] for hit in results["hits"]["hits"]]
    return docs

# Create RAG pipeline using LangChain
retriever = RetrievalQA.from_llm(
    llm=llm,
    retriever=lambda query: search_opensearch(query)
)

# Query with RAG
query = "How to configure OpenSearch?"
response = retriever.run(query)

print(response)