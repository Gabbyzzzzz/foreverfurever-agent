import os
import requests
from dotenv import load_dotenv

load_dotenv()

SHOP = os.getenv("SHOPIFY_STORE_DOMAIN")
TOKEN = os.getenv("SHOPIFY_STOREFRONT_TOKEN")

url = f"https://{SHOP}/api/2024-07/graphql.json"

query = """
{
  products(first: 5) {
    edges {
      node {
        title
        handle
      }
    }
  }
}
"""

resp = requests.post(
    url,
    headers={
        "Content-Type": "application/json",
        "X-Shopify-Storefront-Access-Token": TOKEN,
    },
    json={"query": query},
    timeout=20,
)

print("Status:", resp.status_code)
print(resp.text)
