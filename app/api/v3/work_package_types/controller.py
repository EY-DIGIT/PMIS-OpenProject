"""
Work Package Type controller.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from ....core.base_controller import BaseController
from ....shared.datetime import iso_ist
from .schemas import WorkPackageTypeListQuery
from . import services


class WorkPackageTypeController:
    @staticmethod
    def _format_type(t, base_url: str = "/api/v3") -> dict:
        """
        Format a WorkPackageType domain object into HAL+JSON primitives.
        Expects a domain entity with attributes: id, name, internal_name,
        is_builtin, is_active, position, created_at, updated_at.
        """
        tid = getattr(t, "id", None)

        # created_at/updated_at should be primitives (ISO strings)
        created = getattr(t, "created_at", None)
        updated = getattr(t, "updated_at", None)
        if hasattr(created, "isoformat"):
            created = iso_ist(created)
        if hasattr(updated, "isoformat"):
            updated = iso_ist(updated)

        resp = {
            "_type": "WorkPackageType",
            "_links": {
                "self": {"href": f"{base_url}/work_package_types/{tid}", "title": getattr(t, "name", None)},
                "workPackages": {"href": f"{base_url}/work_packages?typeId={tid}"}
            },
            "id": tid,
            "name": getattr(t, "name", None),
            "internalName": getattr(t, "internal_name", None),
            "isBuiltin": getattr(t, "is_builtin", False),
            "isActive": getattr(t, "is_active", False),
            "position": getattr(t, "position", None),
            "createdAt": created,
            "updatedAt": updated,
        }

        return resp

    @staticmethod
    def list(request: Request, query: WorkPackageTypeListQuery, db: Session) -> JSONResponse:
        result = services.list_work_package_types(db, offset=query.offset, limit=query.pageSize)
        if not result.is_success():
            return BaseController.error({"message": result.error, "type": result.error_type}, status=400)

        items, total = result.data
        page = query.offset
        page_size = query.pageSize
        total_pages = (total + page_size - 1) // page_size if page_size else 1
        base = f"/api/v3/work_package_types"
        links = {"self": {"href": f"{base}?offset={page}&pageSize={page_size}"}}
        if page > 1:
            links["first"] = {"href": f"{base}?offset=1&pageSize={page_size}"}
            links["prev"] = {"href": f"{base}?offset={page-1}&pageSize={page_size}"}
        if page < total_pages:
            links["next"] = {"href": f"{base}?offset={page+1}&pageSize={page_size}"}
            links["last"] = {"href": f"{base}?offset={total_pages}&pageSize={page_size}"}

        embedded = [WorkPackageTypeController._format_type(i, base_url="/api/v3") for i in items]

        payload = {
            "_type": "Collection",
            "_links": links,
            "total": total,
            "count": len(items),
            "pageSize": page_size,
            "offset": page,
            "_embedded": {"elements": embedded},
        }

        return BaseController.ok(payload)

    @staticmethod
    def get(request: Request, type_id: int, db: Session) -> JSONResponse:
        result = services.get_work_package_type_by_id(db, type_id)
        if not result.is_success():
            return BaseController.error({"message": result.error, "type": result.error_type}, status=404)

        t = result.data
        return BaseController.ok(WorkPackageTypeController._format_type(t, base_url="/api/v3"))

    @staticmethod
    def create(request: Request, data, db: Session) -> JSONResponse:
        result = services.create_work_package_type(
            db=db,
            name=data.name,
            internal_name=data.internalName,
            is_builtin=bool(data.isBuiltin),
            is_active=bool(data.isActive),
            position=int(data.position) if data.position is not None else 0,
        )

        if not result.is_success():
            status = 400
            if result.error_type == "already_exists":
                status = 409
            return BaseController.error({"message": result.error, "type": result.error_type}, status=status)

        t = result.data
        return BaseController.created(WorkPackageTypeController._format_type(t, base_url="/api/v3"))

    @staticmethod
    def update(request: Request, type_id: int, data, db: Session) -> JSONResponse:
        result = services.update_work_package_type(
            db=db,
            type_id=type_id,
            name=data.name,
            is_active=data.isActive,
            position=data.position,
        )

        if not result.is_success():
            status = 400
            if result.error_type == "not_found":
                status = 404
            return BaseController.error({"message": result.error, "type": result.error_type}, status=status)

        t = result.data
        return BaseController.ok(WorkPackageTypeController._format_type(t, base_url="/api/v3"))

    @staticmethod
    def delete(request: Request, type_id: int, db: Session) -> JSONResponse:
        result = services.delete_work_package_type(db, type_id)
        if not result.is_success():
            status = 400
            if result.error_type == "not_found":
                status = 404
            return BaseController.error({"message": result.error, "type": result.error_type}, status=status)

        return BaseController.no_content()
