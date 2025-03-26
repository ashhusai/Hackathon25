import os
import requests
from dotenv import load_dotenv
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
from requests.auth import HTTPBasicAuth
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

# Initialize OpenAI LLM
llm = OpenAI(model_name="gpt-4", api_key="your_openai_api_key")
AUTH = HTTPBasicAuth(os.getenv('OPENSEARCH_USERNAME'), os.getenv('OPENSEARCH_PASSWORD'))
headers = {"Content-Type": "application/json"}
# Define a custom retriever function
def search_opensearch(query):
    embedding_model = HuggingFaceEmbeddings(model_name="Qodo/Qodo-Embed-1-7B")
    query_vector = embedding_model.embed_query(query)
    query_payload = {
        "size": 5,
        "query": {
            "knn": {
                "vector_field": {
                    "vector": query_vector,
                    "k": 5
                }
            }
        }
    }
    search_url = f"{os.getenv('OPENSEARCH_URL')}/{os.getenv('OPENSEARCH_INDEX')}/_search"
    response = requests.post(search_url, auth=AUTH, json=query_payload, headers=headers)
    results = response.json()
    docs = [hit["_source"]["text"] for hit in results["hits"]["hits"]]
    context=format_dynamic_list_to_string(docs)
    return context


def format_dynamic_list_to_string(dynamic_list):
    formatted_str = ""
    for idx, item in enumerate(dynamic_list, 1):
        formatted_str += f"Item {idx}:\n{'-' * 40}\n"
        formatted_str += f"{item}\n"
        formatted_str += "\n" + "=" * 40 + "\n"
    return formatted_str


# Create RAG pipeline using LangChain
retriever = RetrievalQA.from_llm(
    llm=llm,
    retriever=lambda query: search_opensearch(query)
)

# Query with RAG
query = "How to configure OpenSearch?"
response = retriever.run(query)

print(response)