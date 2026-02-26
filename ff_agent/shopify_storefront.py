"""Shopify Storefront API client for ForeverFurEver."""

from __future__ import annotations

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SHOP = os.getenv("SHOPIFY_STORE_DOMAIN")
TOKEN = os.getenv("SHOPIFY_STOREFRONT_TOKEN")
STORE_URL = "https://foreverfurever.org"

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


def _node_to_product(node: dict) -> dict:
    """Convert a Shopify product node to our standard product dict."""
    price_info = node.get("priceRange", {}).get("minVariantPrice", {})
    images = node.get("images", {}).get("edges", [])
    image_url = images[0]["node"]["url"] if images else None

    # Extract variant ID for checkout URL
    variants = node.get("variants", {}).get("edges", [])
    variant_gid = variants[0]["node"]["id"] if variants else None
    variant_id = variant_gid.split("/")[-1] if variant_gid else None
    checkout_url = f"{STORE_URL}/cart/{variant_id}:1" if variant_id else None

    return {
        "title": node["title"],
        "handle": node["handle"],
        "available": node.get("availableForSale", False),
        "price": f'{price_info.get("amount", "0")} {price_info.get("currencyCode", "USD")}',
        "url": f"{STORE_URL}/products/{node['handle']}",
        "image_url": image_url,
        "checkout_url": checkout_url,
    }


_PRODUCT_FIELDS = """
    title
    handle
    availableForSale
    priceRange {
      minVariantPrice { amount currencyCode }
    }
    images(first: 1) {
      edges { node { url(transform: {maxWidth: 400, maxHeight: 400, preferredContentType: JPG}) } }
    }
    variants(first: 1) {
      edges { node { id } }
    }
"""


def search_products(query: str, max_results: int = 6) -> list[dict]:
    """Search the Shopify store for products by keyword.
    Falls back to latest products if no results found.
    """
    query_text = (query or "").strip()
    results: list[dict] = []

    if query_text:
        # Use plain text search so Shopify searches all indexed fields
        # (title, description, tags, product_type, vendor, etc.)
        q = query_text
        gql = f"""
        query SearchProducts($q: String!, $first: Int!) {{
          products(first: $first, query: $q, sortKey: UPDATED_AT, reverse: true) {{
            edges {{ node {{ {_PRODUCT_FIELDS} }} }}
          }}
        }}
        """
        data = storefront_query(gql, {"q": q, "first": max_results})
        for edge in data.get("products", {}).get("edges", []):
            results.append(_node_to_product(edge["node"]))

    # Supplement with latest products if search returned few results.
    # This ensures the AI always sees the full catalog for small stores,
    # while larger stores still benefit from search filtering.
    if len(results) < max_results:
        gql = f"""
        query LatestProducts($first: Int!) {{
          products(first: $first, sortKey: UPDATED_AT, reverse: true) {{
            edges {{ node {{ {_PRODUCT_FIELDS} }} }}
          }}
        }}
        """
        data = storefront_query(gql, {"first": max_results})
        seen_handles = {r["handle"] for r in results}
        for edge in data.get("products", {}).get("edges", []):
            p = _node_to_product(edge["node"])
            if p["handle"] not in seen_handles:
                results.append(p)
                seen_handles.add(p["handle"])

    return results


def get_product_details(handle: str) -> dict | None:
    """Get detailed info for a single product by handle."""
    gql = """
    query ProductByHandle($handle: String!) {
      product(handle: $handle) {
        title
        handle
        description
        availableForSale
        priceRange {
          minVariantPrice { amount currencyCode }
        }
        images(first: 5) {
          edges { node { url altText } }
        }
        variants(first: 10) {
          edges {
            node {
              title
              availableForSale
              price { amount currencyCode }
            }
          }
        }
      }
    }
    """
    data = storefront_query(gql, {"handle": handle})
    product = data.get("product")
    if not product:
        return None

    price_info = product.get("priceRange", {}).get("minVariantPrice", {})
    images = [e["node"]["url"] for e in product.get("images", {}).get("edges", [])]
    variants = []
    for e in product.get("variants", {}).get("edges", []):
        v = e["node"]
        variants.append({
            "title": v["title"],
            "available": v["availableForSale"],
            "price": f'{v["price"]["amount"]} {v["price"]["currencyCode"]}',
        })

    return {
        "title": product["title"],
        "handle": product["handle"],
        "description": product.get("description", ""),
        "available": product.get("availableForSale", False),
        "price": f'{price_info.get("amount", "0")} {price_info.get("currencyCode", "USD")}',
        "url": f"{STORE_URL}/products/{product['handle']}",
        "images": images,
        "variants": variants,
    }


def get_collection(collection_handle: str, max_results: int = 12) -> list[dict]:
    """Browse products in a specific collection."""
    gql = f"""
    query CollectionProducts($handle: String!, $first: Int!) {{
      collection(handle: $handle) {{
        title
        products(first: $first) {{
          edges {{ node {{ {_PRODUCT_FIELDS} }} }}
        }}
      }}
    }}
    """
    data = storefront_query(gql, {"handle": collection_handle, "first": max_results})
    collection = data.get("collection")
    if not collection:
        return []

    return [
        _node_to_product(edge["node"])
        for edge in collection.get("products", {}).get("edges", [])
    ]
