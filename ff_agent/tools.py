"""LangGraph tools for the ForeverFurEver agent.

Each tool is a function that Gemini can call via function calling.
The agent autonomously decides when to invoke each tool.
"""

from langchain_core.tools import tool

from ff_agent.shopify_storefront import (
    search_products as _search_products,
    get_product_details as _get_product_details,
    get_collection as _get_collection,
)


@tool
def search_products(query: str, max_results: int = 6) -> list[dict]:
    """Search the Shopify store for products by keyword.

    Use this when a customer asks about products, wants recommendations,
    or mentions a specific type of item. Returns product title, price,
    availability, URL, and image.

    Args:
        query: Search keywords (e.g. "memorial", "urn", "keepsake", "engraved")
        max_results: Maximum number of results to return (default 6)
    """
    return _search_products(query, max_results)


@tool
def get_product_details(handle: str) -> dict:
    """Get detailed information about a specific product.

    Use this when a customer asks for more details about a particular product,
    wants to know about variants, customization options, or see more images.

    Args:
        handle: The product handle/slug (e.g. "eternal-glow-a-soulful-tribute")
    """
    result = _get_product_details(handle)
    if result is None:
        return {"error": f"Product '{handle}' not found"}
    return result


@tool
def get_collection(collection_name: str) -> list[dict]:
    """Browse products by collection or category.

    Use this when a customer wants to browse a specific category of products
    rather than search for something specific.

    Args:
        collection_name: The collection handle (e.g. "all", "memorial-urns", "keepsakes")
    """
    return _get_collection(collection_name)


# Collected list of all tools for the agent
ALL_TOOLS = [search_products, get_product_details, get_collection]
