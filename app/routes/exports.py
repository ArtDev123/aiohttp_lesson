from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, status
from fastapi.responses import FileResponse

from app.celery_app import celery_app
from app.errors import NotFoundError
from app.schemas import ErrorRead, ExportAccepted, ExportStatus
from app.tasks import EXPORT_DIR, export_catalog

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post(
    "",
    response_model=ExportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_export() -> ExportAccepted:
    result = export_catalog.delay()
    return ExportAccepted(task_id=result.id, status=result.status)


@router.get(
    "/{task_id}",
    response_model=ExportStatus,
)
def get_export(task_id: str) -> ExportStatus:
    result = AsyncResult(task_id, app=celery_app)
    payload = ExportStatus(task_id=task_id, status=result.status)

    if result.successful():
        data = result.result or {}
        payload.book_count = data.get("book_count")
        payload.filename = data.get("filename")
    elif result.failed():
        payload.error = str(result.result)

    return payload


@router.get(
    "/{task_id}/file",
    responses={404: {"model": ErrorRead}},
)
def download_export(task_id: str) -> FileResponse:
    path = EXPORT_DIR / f"{task_id}.json"
    if not path.is_file():
        raise NotFoundError("Файл экспорта ещё не готов или не найден")
    return FileResponse(
        path,
        media_type="application/json",
        filename=path.name,
    )