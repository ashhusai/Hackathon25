from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=[
       {
         "host": "search-test-domain-cytn3qyhwkkjflb7fpfg47djwi.us-east-1.es.amazonaws.com",
         "port": 443,
         "scheme": "https"
       }
    ],
    use_ssl=True,
    verify_certs=True
)

# Check doc count
response = client.count(index="test")
print(response)
