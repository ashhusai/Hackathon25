# file: rag.py

import os
import requests
import json
import boto3
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from requests.auth import HTTPBasicAuth
# from langchain_openai import ChatOpenAI

load_dotenv()

############################################
# 1) The retrieval function for OpenSearch
############################################
def opensearch_knn_search(query: str, index_name: str, k=5):
    """
    1. Embed the query with Qodo/Qodo-Embed-1-7B
    2. Send a k-NN search request to OpenSearch
    3. Return the top 'k' chunk texts
    """
    # A) embed the query
    embedding_model = HuggingFaceEmbeddings(model_name="Qodo/Qodo-Embed-1-1.5B")
    query_vector = embedding_model.embed_query(query)

    # B) Build the knn payload
    if "architecture" in query or "diagram" in query:
        payload = {
            "query": {
                "match_all": {}
            },
            "size": 100
        }
    else:
        payload = {
            "size": 5,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_vector,
                        "k": 5
                    }
                }
            }
        }

    # C) Perform the request
    auth = HTTPBasicAuth(os.getenv("OPENSEARCH_USERNAME"), os.getenv("OPENSEARCH_PASSWORD"))
    os_url = os.getenv("OPENSEARCH_URL")
    if not os_url:
        raise ValueError("Please set OPENSEARCH_URL in your environment.")
    search_url = f"{os_url}/{index_name}/_search"

    headers = {"Content-Type": "application/json"}
    resp = requests.post(search_url, auth=auth, json=payload, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenSearch search failed: {resp.status_code} {resp.reason} - {resp.text}")

    data = resp.json()
    # D) Extract chunk text from the hits
    docs = [hit["_source"]["text"] for hit in data["hits"]["hits"]]
    context = format_dynamic_list_to_string(docs)
    return context


#Formatting response received from OpenSearch to something readable
def format_dynamic_list_to_string(dynamic_list):
    formatted_str = ""
    for idx, item in enumerate(dynamic_list, 1):
        formatted_str += f"Item {idx}:\n{'-' * 40}\n"
        formatted_str += f"{item}\n"
        formatted_str += "\n" + "=" * 40 + "\n"
    return formatted_str

############################################
# 2) Prompt Construction
############################################
def build_prompt(query: str, retrieved_docs: list[str]) -> str:
    """
    Combine top docs + user query into a final prompt for the LLM.
    You can make this as fancy or minimal as you like.
    """
    context_str = "\n\n".join(retrieved_docs)
    if "architecture" in query.lower() or "diagram" in query.lower():
        prompt = f"""You are the smartest code analyzer. 
        Use the following code context to answer the user's question.

        Context:
        {context_str}
        
        Question: Create an architecture diagram of the source code using the context provided above. It should:
                  1. Display all the possible flows starting from the entrypoint in the source code
                  2. Mention the file name involved in that step and the function/method being called
                  3. A one line description of what that function does
                  4. Create it in the form of a sequence diagram and it should be very neat and clean
                  Anything else specified in the {query} should also be addressed

        Answer:
        """
    else:
        prompt = f"""You are the smartest code analyzer. 
        Use the following code context to answer the user's question.
        
        Context:
        {context_str}
        
        Question: {query}
        
        Answer:
        """
    return prompt

############################################
# 3) LLM_Claude 3.7 Sonnet Endpoint
############################################
def call_llm_endpoint(prompt: str) -> dict:
    # Initialize the Bedrock client
    bedrock = boto3.client(
        service_name='bedrock-runtime',
        region_name='us-east-1'  # Change region if needed
    )

    # Define the payload
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "top_k": 250,
        "stop_sequences": [],
        "temperature": 1,
        "top_p": 0.999,
        "messages": [
            {
                #This specifies that the message is coming from the user.
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }

    # Call the Claude 3.7 Sonnet model
    response = bedrock.invoke_model(
        modelId="arn:aws:bedrock:us-east-1:354488063238:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload)
    )

    # Parse and print the response
    response_body = json.loads(response['body'].read())
    print(type(response_body))
    print(json.dumps(response_body, indent=2))

    return response_body

############################################
# 4) The main RAG function
############################################
def rag_query(index_name: str, user_query: str, k=5) -> dict:
    """
    1) Embeds the query & retrieves top chunks from 'index_name'
    2) Builds a final prompt
    3) Calls LLM (GPT-4 in this scaffold)
    4) Returns the final response
    """
    # If no index_name was specified, skip retrieval
    if not index_name:
        # just call the LLM with the raw question
        prompt = f"Question: {user_query}\nAnswer:"
    else:
        # A) Retrieve docs from OpenSearch
        docs = opensearch_knn_search(user_query, index_name, k=k)
        if not docs:
            # fallback: no docs found
            prompt = f"No relevant docs found, but user asked:\n{user_query}\nAnswer as best you can:"
        else:
            # B) Build final prompt
            prompt = build_prompt(user_query, docs)

        # C) Call LLM
    answer = call_llm_endpoint(prompt)
    return answer

