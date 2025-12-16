"""
HAL+JSON response formatter for OpenProject API v3 compliance.
"""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel


class Link(BaseModel):
    """HAL link representation."""
    href: str
    title: Optional[str] = None


class HalResponse(BaseModel):
    """Base HAL+JSON response structure."""
    _type: str
    _links: Dict[str, Union[Link, Dict[str, str]]]
    _embedded: Optional[Dict[str, Any]] = None


def format_user_response(
    user_data: Dict[str, Any],
    base_url: str = "/api/v3"
) -> Dict[str, Any]:
    """
    Format a single user response in HAL+JSON format.

    Args:
        user_data: User data dictionary
        base_url: Base API URL

    Returns:
        HAL+JSON formatted response
    """
    user_id = user_data.get("id")

    response = {
        "_type": "User",
        "_links": {
            "self": {
                "href": f"{base_url}/users/{user_id}",
                "title": user_data.get("login")
            }
        },
        "id": user_id,
        "login": user_data.get("login"),
        "firstName": user_data.get("first_name"),
        "lastName": user_data.get("last_name"),
        "email": user_data.get("email"),
        "admin": user_data.get("admin", False),
        "status": user_data.get("status", "active"),
        "createdAt": user_data.get("created_at"),
        "updatedAt": user_data.get("updated_at")
    }

    return response


def format_collection_response(
    items: List[Dict[str, Any]],
    total: int,
    page: int,
    page_size: int,
    base_url: str = "/api/v3",
    collection_type: str = "users"
) -> Dict[str, Any]:
    """
    Format a collection response in HAL+JSON format with pagination.

    Args:
        items: List of items to include
        total: Total number of items
        page: Current page number (1-indexed)
        page_size: Number of items per page
        base_url: Base API URL
        collection_type: Type of collection (e.g., 'users')

    Returns:
        HAL+JSON formatted collection response
    """
    total_pages = (total + page_size - 1) // page_size

    # Build pagination links
    links = {
        "self": {"href": f"{base_url}/{collection_type}?offset={page}&pageSize={page_size}"}
    }

    if page > 1:
        links["first"] = {"href": f"{base_url}/{collection_type}?offset=1&pageSize={page_size}"}
        links["prev"] = {"href": f"{base_url}/{collection_type}?offset={page - 1}&pageSize={page_size}"}

    if page < total_pages:
        links["next"] = {"href": f"{base_url}/{collection_type}?offset={page + 1}&pageSize={page_size}"}
        links["last"] = {"href": f"{base_url}/{collection_type}?offset={total_pages}&pageSize={page_size}"}

    # Format embedded items based on collection type
    if collection_type == "users":
        formatted_items = [format_user_response(item, base_url) for item in items]
    else:
        formatted_items = items

    response = {
        "_type": "Collection",
        "_links": links,
        "total": total,
        "count": len(items),
        "pageSize": page_size,
        "offset": page,
        "_embedded": {
            "elements": formatted_items
        }
    }

    return response


def format_error_response(
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format an error response in HAL+JSON format.

    Args:
        error_type: Type of error
        message: Error message
        details: Optional additional error details

    Returns:
        HAL+JSON formatted error response
    """
    response = {
        "_type": "Error",
        "errorIdentifier": error_type,
        "message": message
    }

    if details:
        response["_embedded"] = {"details": details}

    return response


def format_success_response(message: str) -> Dict[str, Any]:
    """
    Format a success response.

    Args:
        message: Success message

    Returns:
        HAL+JSON formatted success response
    """
    return {
        "_type": "Success",
        "message": message
    }
