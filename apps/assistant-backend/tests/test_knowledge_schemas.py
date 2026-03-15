from app.api.schemas.knowledge import (
    KnowledgeCategoryPageListItem,
    KnowledgeCategoryPagesListResponse,
    KnowledgePageBlocksUpdateRequest,
    KnowledgePageBlocksUpdateResponse,
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


def test_page_detail_response_maps_aliases_and_content_blocks() -> None:
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
            "properties": {"status": "active", "owner": "alice"},
            "links": [{"page_id": "page-8", "title": "Linked", "summary": "Neighbor"}],
            "content_blocks": [
                {"block_id": "block-1", "markdown": "# Meaning"},
                {"block_id": "block-1-1", "markdown": "Supporting detail"},
            ],
        }
    )

    assert response.id == "page-42"
    assert response.category_id == "node.note"
    assert response.title == "Meaning"
    assert response.summary == "All about meaning"
    assert response.metadata.created_at == "2026-01-01T00:00:00Z"
    assert response.metadata.updated_at == "2026-02-01T00:00:00Z"
    assert response.properties == {"status": "active", "owner": "alice"}
    assert response.links[0]["page_id"] == "page-8"
    assert response.content_blocks[0].block_id == "block-1"
    assert response.content_blocks[0].markdown == "# Meaning"
    assert response.content_blocks[1].block_id == "block-1-1"
    assert response.content_blocks[1].markdown == "Supporting detail"
    assert "entity" not in response.model_dump()



def test_page_blocks_update_request_requires_non_empty_block_list() -> None:
    request = KnowledgePageBlocksUpdateRequest.model_validate(
        {
            "content_blocks": [
                {"block_id": "b-1", "markdown_content": "# Updated"},
            ]
        }
    )

    assert request.content_blocks[0].block_id == "b-1"
    assert request.content_blocks[0].markdown_content == "# Updated"


def test_page_blocks_update_response_defaults_status() -> None:
    response = KnowledgePageBlocksUpdateResponse.model_validate(
        {
            "page_id": "page-1",
            "updated_block_ids": ["b-1"],
            "updated_block_count": 1,
        }
    )

    assert response.status == "updated"
