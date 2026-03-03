from app.api.schemas.knowledge import (
    KnowledgeCategoryPageListItem,
    KnowledgeCategoryPagesListResponse,
    KnowledgePageDetailResponse,
)


def test_category_pages_list_item_maps_aliases_from_entity() -> None:
    item = KnowledgeCategoryPageListItem.model_validate(
        {
            "entity": {
                "id": "page-1",
                "name": "Page One",
                "description": "Summary One",
                "updated_at": "2026-02-19T10:00:00Z",
            }
        }
    )

    assert item.page_id == "page-1"
    assert item.page_title == "Page One"
    assert item.page_summary == "Summary One"


def test_category_pages_list_response_preserves_pagination() -> None:
    response = KnowledgeCategoryPagesListResponse.model_validate(
        {
            "pages": [
                {
                    "entity": {
                        "id": "page-1",
                        "name": "Page One",
                        "description": "Summary One",
                    }
                }
            ],
            "page_size": 20,
            "next_page_token": "cursor-2",
            "total_count": 101,
        }
    )

    assert response.page_size == 20
    assert response.next_page_token == "cursor-2"
    assert response.total_count == 101
    assert response.pages[0].entity.id == "page-1"


def test_page_detail_response_maps_aliases_and_context_markdown() -> None:
    response = KnowledgePageDetailResponse.model_validate(
        {
            "entity": {
                "id": "page-42",
                "name": "Meaning",
                "description": "All about meaning",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-02-01T00:00:00Z",
            },
            "links": ["https://example.com/doc"],
            "prompt_context_markdown": "# Meaning",
        }
    )

    assert response.page_id == "page-42"
    assert response.title == "Meaning"
    assert response.summary == "All about meaning"
    assert response.created_at == "2026-01-01T00:00:00Z"
    assert response.updated_at == "2026-02-01T00:00:00Z"
    assert response.content_markdown == "# Meaning"
