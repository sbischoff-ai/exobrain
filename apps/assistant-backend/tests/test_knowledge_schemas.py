from app.api.schemas.knowledge import (
    KnowledgeCategoryPageListItem,
    KnowledgeCategoryPagesListResponse,
    KnowledgePageDetailResponse,
)


def test_category_pages_list_item_uses_compact_fields() -> None:
    item = KnowledgeCategoryPageListItem.model_validate(
        {
            "id": "page-1",
            "title": "Page One",
            "summary": "Summary One",
            "metadata": {
                "created_at": "2026-02-18T10:00:00Z",
                "updated_at": "2026-02-19T10:00:00Z",
            },
        }
    )

    assert item.id == "page-1"
    assert item.title == "Page One"
    assert item.summary == "Summary One"
    assert item.metadata.created_at == "2026-02-18T10:00:00Z"


def test_category_pages_list_response_preserves_pagination() -> None:
    response = KnowledgeCategoryPagesListResponse.model_validate(
        {
            "knowledge_pages": [
                {
                    "id": "page-1",
                    "title": "Page One",
                    "summary": "Summary One",
                    "metadata": {"created_at": "", "updated_at": ""},
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
    assert response.knowledge_pages[0].id == "page-1"


def test_page_detail_response_maps_aliases_and_context_markdown() -> None:
    response = KnowledgePageDetailResponse.model_validate(
        {
            "id": "page-42",
            "category_id": "node.note",
            "title": "Meaning",
            "summary": "All about meaning",
            "metadata": {
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-02-01T00:00:00Z",
            },
            "links": [{"page_id": "page-8", "title": "Linked", "summary": "Neighbor"}],
            "content_markdown": "# Meaning",
        }
    )

    assert response.id == "page-42"
    assert response.category_id == "node.note"
    assert response.title == "Meaning"
    assert response.summary == "All about meaning"
    assert response.metadata.created_at == "2026-01-01T00:00:00Z"
    assert response.metadata.updated_at == "2026-02-01T00:00:00Z"
    assert response.links[0]["page_id"] == "page-8"
    assert response.content_markdown == "# Meaning"
    assert "entity" not in response.model_dump()
