import os, requests
from dotenv import load_dotenv

load_dotenv()

SHOP = os.getenv("SHOPIFY_STORE_DOMAIN")
TOKEN = os.getenv("SHOPIFY_STOREFRONT_TOKEN")

url = f"https://{SHOP}/api/2024-07/graphql.json"
query = """
{
  shop { name }
}
"""

r = requests.post(
  url,
  headers={
    "Content-Type": "application/json",
    "X-Shopify-Storefront-Access-Token": TOKEN,
  },
  json={"query": query},
  timeout=20
)

print("status:", r.status_code)
print(r.text)
