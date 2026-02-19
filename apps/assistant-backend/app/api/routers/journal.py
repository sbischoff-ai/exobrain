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


def _messages_from_records(rows) -> list[JournalMessageResponse]:
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


@router.get("", response_model=list[JournalEntryResponse])
async def list_journal_entries(
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
) -> list[JournalEntryResponse]:
    service: JournalService = request.app.state.journal_service
    rows = await service.list_journals(user_id=principal.user_id, limit=limit, before=cursor)
    return [_entry_from_record(row) for row in rows]


@router.get("/today", response_model=JournalEntryResponse)
async def get_today_journal(
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
    create: bool = False,
) -> JournalEntryResponse:
    service: JournalService = request.app.state.journal_service
    row = await service.get_today_journal(user_id=principal.user_id, create=create)
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
    rows = await service.list_today_messages(user_id=principal.user_id, limit=limit)
    return _messages_from_records(rows)


@router.get("/search", response_model=list[JournalEntryResponse])
async def search_journal_entries(
    q: str,
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[JournalEntryResponse]:
    service: JournalService = request.app.state.journal_service
    rows = await service.search_journals(user_id=principal.user_id, query=q, limit=limit)
    return [_entry_from_record(row) for row in rows]


@router.get("/{reference:path}/messages", response_model=list[JournalMessageResponse])
async def get_journal_messages(
    reference: str,
    request: Request,
    principal: UnifiedPrincipal = Depends(get_required_auth_context),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[JournalMessageResponse]:
    service: JournalService = request.app.state.journal_service
    rows = await service.list_messages(user_id=principal.user_id, reference=reference, limit=limit)
    return _messages_from_records(rows)


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
    row = await service.get_journal(user_id=principal.user_id, reference=reference)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="journal entry not found")
    return _entry_from_record(row)
