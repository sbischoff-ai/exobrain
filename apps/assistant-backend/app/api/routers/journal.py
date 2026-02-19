from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.dependencies.auth import get_required_auth_context
from app.api.schemas.auth import UnifiedPrincipal
from app.api.schemas.journal import JournalEntryResponse, JournalMessageResponse
from app.services.journal_service import JournalService

router = APIRouter(prefix="/journal", tags=["journal"])


def _entry_from_record(record) -> JournalEntryResponse:
    return JournalEntryResponse(
        id=record["id"],
        reference=record["reference"],
        created_at=record["created_at"],
        updated_at=record["updated_at"],
        last_message_at=record["last_message_at"],
        message_count=record["message_count"],
        status=record["status"],
    )


@router.get("", response_model=list[JournalEntryResponse])
async def list_journal_entries(
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> list[JournalEntryResponse]:
    service: JournalService = request.app.state.journal_service
    rows = await service.list_journals(principal.user_id, limit=limit, before=cursor)
    return [_entry_from_record(row) for row in rows]


@router.get("/today", response_model=JournalEntryResponse)
async def get_today_journal(
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
    create: bool = False,
) -> JournalEntryResponse:
    service: JournalService = request.app.state.journal_service
    reference = service.today_reference()
    if create:
        await service.ensure_conversation(principal.user_id, reference)
    row = await service.get_journal(principal.user_id, reference)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="journal entry not found")
    return _entry_from_record(row)


@router.get("/today/messages", response_model=list[JournalMessageResponse])
async def get_today_messages(
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[JournalMessageResponse]:
    service: JournalService = request.app.state.journal_service
    rows = await service.list_messages(principal.user_id, service.today_reference(), limit)
    return [
        JournalMessageResponse(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
            metadata=row["metadata"],
        )
        for row in rows
    ]


@router.get("/search", response_model=list[JournalEntryResponse])
async def search_journal_entries(
    q: str,
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[JournalEntryResponse]:
    rows = await request.app.state.database_service.fetch(
        """
        SELECT DISTINCT
          c.id::text AS id,
          c.reference,
          c.created_at,
          c.updated_at,
          MAX(m.created_at) AS last_message_at,
          COUNT(m.id)::int AS message_count,
          'open'::text AS status
        FROM conversations c
        LEFT JOIN messages m ON m.conversation_id = c.id
        WHERE c.user_id = $1::uuid
          AND (m.content ILIKE ('%' || $2 || '%') OR c.reference ILIKE ('%' || $2 || '%'))
        GROUP BY c.id
        ORDER BY c.reference DESC
        LIMIT $3
        """,
        principal.user_id,
        q,
        limit,
    )
    return [_entry_from_record(row) for row in rows]



@router.get("/{reference:path}/messages", response_model=list[JournalMessageResponse])
async def get_journal_messages(
    reference: str,
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[JournalMessageResponse]:
    service: JournalService = request.app.state.journal_service
    rows = await service.list_messages(principal.user_id, reference, limit)
    return [
        JournalMessageResponse(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
            metadata=row["metadata"],
        )
        for row in rows
    ]


@router.get("/{reference:path}/summary", response_model=JournalEntryResponse)
async def get_journal_summary(
    reference: str,
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
) -> JournalEntryResponse:
    return await get_journal_by_reference(reference, request, principal)

@router.get("/{reference:path}", response_model=JournalEntryResponse)
async def get_journal_by_reference(
    reference: str,
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
) -> JournalEntryResponse:
    service: JournalService = request.app.state.journal_service
    row = await service.get_journal(principal.user_id, reference)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="journal entry not found")
    return _entry_from_record(row)

