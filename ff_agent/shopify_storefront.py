import os
import requests
from dotenv import load_dotenv

load_dotenv()

SHOP = os.getenv("SHOPIFY_STORE_DOMAIN")
TOKEN = os.getenv("SHOPIFY_STOREFRONT_TOKEN")

API_VERSION = "2024-07"
ENDPOINT = f"https://{SHOP}/api/{API_VERSION}/graphql.json"

def storefront_query(query: str, variables: dict | None = None) -> dict:
    if not SHOP or not TOKEN:
        raise RuntimeError("Missing SHOPIFY_STORE_DOMAIN or SHOPIFY_STOREFRONT_TOKEN in .env")

    resp = requests.post(
        ENDPOINT,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Storefront-Access-Token": TOKEN,
        },
        json={"query": query, "variables": variables or {}},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        raise RuntimeError(f"Shopify GraphQL errors: {data['errors']}")
    return data["data"]

def search_products(keyword: str, first: int = 6) -> list[dict]:
    """
    先按 keyword 搜索；如果搜不到结果，就兜底返回最新的 first 个商品。
    """
    keyword = (keyword or "").strip()
    results: list[dict] = []

    # 1) 先尝试按 keyword 搜索（query 可能命中 title/product_type/tag）
    if keyword:
        q = f'title:*{keyword}* OR product_type:*{keyword}* OR tag:*{keyword}*'

        query_search = """
        query SearchProducts($q: String!, $first: Int!) {
          products(first: $first, query: $q, sortKey: UPDATED_AT, reverse: true) {
            edges {
              node {
                title
                handle
                availableForSale
                priceRange {
                  minVariantPrice { amount currencyCode }
                }
              }
            }
          }
        }
        """
        data = storefront_query(query_search, {"q": q, "first": first})
        edges = data.get("products", {}).get("edges", [])
        for e in edges:
            p = e["node"]
            results.append({
                "title": p["title"],
                "handle": p["handle"],
                "available": p["availableForSale"],
                "price": f'{p["priceRange"]["minVariantPrice"]["amount"]} {p["priceRange"]["minVariantPrice"]["currencyCode"]}',
                "url": f"https://foreverfurever.org/products/{p['handle']}",
            })

    # 2) 如果搜索没结果：兜底返回最新商品（不带 query）
    if not results:
        query_fallback = """
        query LatestProducts($first: Int!) {
          products(first: $first, sortKey: UPDATED_AT, reverse: true) {
            edges {
              node {
                title
                handle
                availableForSale
                priceRange {
                  minVariantPrice { amount currencyCode }
                }
              }
            }
          }
        }
        """
        data = storefront_query(query_fallback, {"first": first})
        edges = data.get("products", {}).get("edges", [])
        for e in edges:
            p = e["node"]
            results.append({
                "title": p["title"],
                "handle": p["handle"],
                "available": p["availableForSale"],
                "price": f'{p["priceRange"]["minVariantPrice"]["amount"]} {p["priceRange"]["minVariantPrice"]["currencyCode"]}',
                "url": f"https://foreverfurever.org/products/{p['handle']}",
            })

    return results

