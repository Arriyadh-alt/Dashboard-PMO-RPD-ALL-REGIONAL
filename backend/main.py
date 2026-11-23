"""Same-origin private service. Start with one worker behind an HTTPS reverse proxy."""

import base64
import hashlib
import json
import os
import secrets
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analytics import (DEFAULT_RULES, area_key, build_analysis, coordinator, label, matches, period_bounds,
                        prepare, quality, record_view, scoped_rows, target_ref)
from .auth import Sessions, SessionCapacity, user_key
from .source import RotationRequired, SourceCache
from .exports import TITLES, make_report
from .store import Store, now_iso

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / 'web'


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictModel):
    account: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class MappingChange(StrictModel):
    version: int = Field(ge=0)
    values: dict[str, dict]


class Scope(StrictModel):
    m0: int = Field(default=0, ge=0)
    m1: int | None = Field(default=None, ge=0)
    reg: str = Field(default="", max_length=100)
    ab: int = Field(default=-1, ge=-1)
    kel: int = Field(default=-1, ge=-1)
    coordinator: str = Field(default="", max_length=150)
    statuses: list[str] = Field(default_factory=list, max_length=30)
    start: date | None = None
    end: date | None = None


class Search(StrictModel):
    scope: Scope = Field(default_factory=Scope)
    pam: str = Field(default="", max_length=30)
    kelurahan: str = Field(default="", max_length=100)
    surveyor: str = Field(default="", max_length=150)
    canvassing: int = Field(default=0, ge=0)
    installation: int = Field(default=0, ge=0)
    potential: int = Field(default=0, ge=0)
    outstanding_only: bool = False
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


class Followup(StrictModel):
    pic: str = Field(min_length=1, max_length=150)
    status: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=2000)
    target_date: date | None = None
    resolution_notes: str = Field(default="", max_length=2000)
    case_started: date | None = None
    pause_days: int = Field(default=0, ge=0, le=36500)
    pause_reason: str = Field(default="", max_length=500)


class Target(StrictModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    region: str = Field(default="", max_length=100)
    area: int = Field(default=-1, ge=-1)
    target: int = Field(gt=0, le=10000000)
    evidence: str = Field(min_length=1, max_length=1000)


class Rules(StrictModel):
    minimum_sample: int = Field(default=20, ge=1, le=100000)
    high_backlog_rate: float = Field(default=.30, gt=0, le=1)
    cooling_interest_rate: float = Field(default=.10, ge=0, le=1)


class AreaContext(StrictModel):
    area: int = Field(ge=0)
    supply: Literal["unknown", "ready", "constrained"]
    readiness: Literal["unknown", "ready", "blocked"]
    evidence: str = Field(min_length=1, max_length=1000)


def create_app(source_path=None, state_dir=None, origin=None, dev=None):
    dev = (os.environ.get("RPD_DEV") == "1") if dev is None else dev
    origin = origin or os.environ.get("RPD_PUBLIC_ORIGIN") or ("http://127.0.0.1:8765" if dev else "")
    source_path = Path(source_path or os.environ.get("RPD_DATA_PATH", "/nonexistent/rpd-data.enc.json"))
    state_dir = Path(state_dir or os.environ.get("RPD_STATE_DIR", str(Path.home() / ".local/share/rpd")))
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_dir.chmod(0o700)
    store = Store(state_dir / "operations.sqlite3")
    (state_dir / "operations.sqlite3").chmod(0o600)
    sessions = Sessions()
    source_cache=SourceCache()
    app = FastAPI(title="Private RPD service", docs_url=None, redoc_url=None, openapi_url=None)
    host = urlsplit(origin).hostname
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[host] if host else ["localhost", "127.0.0.1"])
    app.state.store, app.state.sessions = store, sessions

    def source_stamp():
        try:
            stat = source_path.stat()
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not origin or request.headers.get("origin") != origin:
                return JSONResponse({"detail": "Origin tidak diizinkan."}, status_code=403)
            try:
                too_large = int(request.headers.get("content-length", "0")) > 32768
            except ValueError:
                too_large = True
            if too_large:
                return JSONResponse({"detail": "Permintaan terlalu besar."}, status_code=413)
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 32768:
                    return JSONResponse({"detail": "Permintaan terlalu besar."}, status_code=413)
                chunks.append(chunk)
            # Starlette's cached request replays this bounded body to the endpoint.
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        if not dev:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(ValidationError)
    @app.exception_handler(RequestValidationError)
    async def invalid_model(request, error):
        return JSONResponse({"detail": "Filter atau nilai tidak valid."}, status_code=422)

    def authenticated(request: Request):
        token = request.cookies.get("rpd_session", "")
        session = sessions.get(token, source_stamp())
        if not session:
            raise HTTPException(401, "Sesi berakhir. Silakan masuk kembali.")
        if request.method not in ("GET", "HEAD") and not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf):
            raise HTTPException(403, "Token permintaan tidak valid.")
        return session

    def administrator(session=Depends(authenticated)):
        if session.role != "owner":
            raise HTTPException(403, "Akses administrator diperlukan.")
        return session

    def scope_dict(scope, session):
        values = scope.model_dump(mode="json", exclude_none=True)
        source=session.data['source']
        for field,dimension in [('ab','abs'),('kel','kels')]:
            if values[field]>=len(source[dimension]):
                raise HTTPException(422,'Filter wilayah tidak tersedia pada sumber aktif. Muat ulang atau simpan ulang preset.')
        values.setdefault("m1", len(session.data["source"]["months"]) - 1)
        try:
            period_bounds(session.data["source"], values)
        except (ValueError, IndexError):
            raise HTTPException(422, "Periode tidak valid.")
        return values

    def query_scope(request: Request, session):
        raw = {key: request.query_params[key] for key in Scope.model_fields if key != "statuses" and key in request.query_params}
        raw["statuses"] = request.query_params.getlist("status")
        return scope_dict(Scope(**raw), session)

    @app.get("/health")
    def health():
        return {"service": "rpd", "configured": bool(origin and source_path.is_file() and (dev or origin.startswith("https://")))}

    @app.post("/api/login")
    def login(body: Login, request: Request, response: Response):
        if not origin or not source_path.is_file() or (not dev and not origin.startswith("https://")):
            raise HTTPException(503, "Backend privat belum dikonfigurasi. GitHub Pages tidak menyediakan akses data.")
        client=request.client.host if request.client else 'unknown'
        peer = (client,user_key(body.account))
        if sessions.limited(peer) or sessions.limited(client,100) or not sessions.login_slots.acquire(blocking=False):
            raise HTTPException(429, "Terlalu banyak percobaan. Coba kembali setelah 15 menit.")
        try:
            stamp = source_stamp()
            data,role=source_cache.authenticate(source_path,body.account,body.password,stamp,allow_legacy=dev)
            token = sessions.create(user_key(body.account), role, data, stamp)
        except RotationRequired:
            raise HTTPException(503,'Rotasi kredensial dan kunci sumber legacy diperlukan sebelum akses produksi. Lihat panduan cutover.')
        except SessionCapacity:
            raise HTTPException(503,'Kapasitas sesi sementara penuh. Coba kembali nanti.')
        except (OSError, json.JSONDecodeError):
            raise HTTPException(503, "Sumber data privat tidak tersedia.")
        except Exception:
            sessions.failed(peer)
            sessions.failed(client)
            raise HTTPException(401, "ID atau kata sandi tidak valid, atau kontrak data belum tervalidasi.")
        finally:
            sessions.login_slots.release()
        response.set_cookie("rpd_session", token, httponly=True, secure=not dev, samesite="strict", max_age=3600, path="/")
        store.append("session", "login", user_key(body.account), {"role": role})
        return {"role": role}

    @app.post("/api/logout")
    def logout(request: Request, response: Response, session=Depends(authenticated)):
        sessions.remove(request.cookies.get("rpd_session", ""))
        response.delete_cookie("rpd_session", path="/", secure=not dev, httponly=True, samesite="strict")
        return {"ok": True}

    @app.get("/api/bootstrap")
    def bootstrap(session=Depends(authenticated)):
        source = session.data["source"]
        safe = {key: source[key] for key in ("months", "abs", "reg", "kels", "svs", "st", "kl", "A", "S", "E", "P", "W", "dic")}
        safe["meta"] = {key: source["meta"].get(key, [] if key == "korlaps" else {} if key == "sync" else 0)
                        for key in ("tmin", "tmax", "rows", "uniq", "sync", "korlaps", "rt_bad")}
        if session.role != "owner":
            safe["svs"] = [f"Surveyor {index + 1}" for index in range(len(source["svs"]))]
        mapping_events=store.history('mapping','all',limit=1)
        overrides=mapping_events[0]['payload'] if mapping_events else {}
        indexed = {str(index): overrides[name] for index, name in enumerate(source["svs"]) if name in overrides}
        pairs={(row['ab'],row['kel']) for row in session.data['prepared']['rows'] if row['valid_location']}
        pairs.update((row[0],row[1]) for row in [*source['P'],*source['W']] if len(row)>=2 and type(row[0]) is int and type(row[1]) is int and 0<=row[0]<len(source['abs']) and 0<=row[1]<len(source['kels']))
        geography=sorted(pairs)
        return {"data": safe, "overrides": indexed, 'mapping_version':mapping_events[0]['id'] if mapping_events else 0, "role": session.role, "geography": geography,
                'area_keys':[area_key(source,index) for index in range(len(source['abs']))],
                "data_owner": os.environ.get("RPD_DATA_OWNER", ""),
                "csrf": session.csrf, "source": session.data["info"],
                "capabilities": {"customer_detail": session.role == "owner", "attendance": False,
                                 "geographic_boundaries": False, "historical_snapshots": False}}

    @app.get("/api/analysis")
    def analysis(request: Request, session=Depends(authenticated)):
        filters = query_scope(request, session)
        return build_analysis(session.data["source"], session.data["prepared"], filters, store, session.role)

    @app.get("/api/quality")
    def data_quality(session=Depends(authenticated)):
        return {**quality(session.data["source"], session.data["prepared"]), "source": session.data["info"]}

    @app.post("/api/records/search")
    def search(body: Search, session=Depends(administrator)):
        source, prepared = session.data["source"], session.data["prepared"]
        filters = scope_dict(body.scope, session)
        overrides = store.latest("mapping").get("all", {})
        actions = store.latest("followup")
        selected, total = [], 0
        for row in scoped_rows(source, prepared, filters, overrides):
            if (body.pam and not row["pam"].startswith(body.pam.strip().lstrip("0"))) or (body.kelurahan and body.kelurahan.casefold() not in source["kels"][row["kel"]].casefold()) or (body.surveyor and body.surveyor.casefold() not in source["svs"][row["sv"]].casefold()):
                continue
            if any(value and row[key] != value for key, value in (("c1", body.canvassing), ("kf", body.installation), ("pr", body.potential))):
                continue
            if body.outstanding_only and not (row["interest"] and not row["installed"] and not row["cancelled"]):
                continue
            if body.offset <= total < body.offset + body.limit:
                selected.append(record_view(source, prepared, row, overrides, actions.get(row["ref"])))
            total += 1
        return {"rows": selected, "total": total, "offset": body.offset, "limit": body.limit}

    def known_case(ref, session):
        if not any(row["valid"] and row["ref"] == ref for row in session.data["prepared"]["rows"]):
            raise HTTPException(404, "Referensi kasus tidak ditemukan pada sumber aktif.")

    @app.get("/api/followups/{ref}")
    def followup_history(ref: str, limit: int = Query(100, ge=1, le=1000), before: int | None = Query(None, ge=1), session=Depends(administrator)):
        known_case(ref, session)
        events = store.history("followup", ref, limit, before)
        return {"events": events, "next_before": events[-1]["id"] if len(events) == limit else None}

    @app.post("/api/followups/{ref}")
    def append_followup(ref: str, body: Followup, session=Depends(administrator)):
        known_case(ref, session)
        source = session.data["source"]
        if body.status not in source["dic"]["kf"] and body.status != "Tidak tercatat":
            raise HTTPException(422, "Gunakan status operasional sumber; status sumber tidak ditimpa.")
        if body.case_started:
            elapsed = (date.today() - body.case_started).days
            if elapsed < 0 or body.pause_days > elapsed:
                raise HTTPException(422, "Tanggal awal atau durasi jeda tidak valid.")
        if body.pause_days and (not body.case_started or not body.pause_reason.strip()):
            raise HTTPException(422, "Hari jeda memerlukan tanggal awal dan alasan terverifikasi.")
        payload = body.model_dump(mode="json")
        payload["updated_at"] = now_iso()
        event_id = store.append("followup", ref, session.actor, payload)
        return {"event_id": event_id, "ok": True}

    @app.put("/api/admin/mappings")
    def mappings(body: MappingChange, session=Depends(administrator)):
        source = session.data["source"]
        allowed = [*source["meta"].get("korlaps", []), "PENGAWAS", "BELUM TERDAFTAR", "AKUN GENERIK"]
        converted = {}
        if len(body.values) > len(source["svs"]):
            raise HTTPException(422, "Pemetaan tidak valid.")
        for index, value in body.values.items():
            if not str(index).isdigit() or not 0 <= int(index) < len(source["svs"]) or not isinstance(value, dict) or set(value) - {"kl", "st"}:
                raise HTTPException(422, "Pemetaan tidak valid.")
            if ("kl" in value and value["kl"] not in allowed) or ("st" in value and (type(value["st"]) is not int or value["st"] not in (0, 1, 2))):
                raise HTTPException(422, "Koordinator/status pemetaan tidak valid.")
            converted[source["svs"][int(index)]] = value
        try:
            version=store.append_if_current('mapping','all',session.actor,converted,body.version)
        except ValueError:
            raise HTTPException(409,'Pemetaan telah diubah administrator lain. Muat versi terbaru lalu ulangi perubahan Anda.')
        return {"ok": True,'version':version}

    @app.post("/api/admin/targets")
    def targets(body: Target, session=Depends(administrator)):
        source = session.data["source"]
        if body.month not in source["months"] or (body.region and body.region not in source["reg"]) or body.area >= len(source["abs"]):
            raise HTTPException(422, "Bulan/regional/area target tidak valid.")
        if body.area >= 0 and source["reg"][body.area] != body.region:
            raise HTTPException(422, "Regional target harus cocok dengan area bisnis.")
        payload={**body.model_dump(), 'area_name':source['abs'][body.area] if body.area >= 0 else ''}
        store.append("target", target_ref(body.month, body.region, body.area, source), session.actor, payload)
        return {"ok": True}

    @app.put("/api/admin/rules")
    def rules(body: Rules, session=Depends(administrator)):
        store.append("rules", "all", session.actor, body.model_dump())
        return {"ok": True}

    @app.post("/api/admin/area-context")
    def area_context(body: AreaContext, session=Depends(administrator)):
        if body.area >= len(session.data["source"]["abs"]):
            raise HTTPException(422, "Area tidak valid.")
        source=session.data['source']
        store.append("area_context", area_key(source, body.area), session.actor, {**body.model_dump(), 'area_name':source['abs'][body.area], 'region':source['reg'][body.area]})
        return {"ok": True}

    @app.get("/api/admin/audit")
    def audit(limit: int = Query(100, ge=1, le=1000), before: int | None = Query(None, ge=1), session=Depends(administrator)):
        events = store.history(limit=limit, before=before)
        contexts=store.latest('area_context')
        current={str(index):contexts[area_key(session.data['source'],index)] for index in range(len(session.data['source']['abs'])) if area_key(session.data['source'],index) in contexts}
        return {"events": events, "next_before": events[-1]["id"] if len(events) == limit else None, "targets": store.latest("target"),
                "area_context": current, "rules": {**DEFAULT_RULES, **store.latest("rules").get("all", {})}}

    @app.get("/api/reports/{kind}.{extension}")
    def export(kind: str, extension: str, request: Request, session=Depends(authenticated)):
        if kind not in TITLES or extension not in ("csv", "xlsx", "pdf"):
            raise HTTPException(404)
        filters = query_scope(request, session)
        source, prepared = session.data["source"], session.data["prepared"]
        analysis = build_analysis(source, prepared, filters, store, session.role)
        try:
            content, media_type = make_report(kind, extension, analysis, source, prepared, filters, store, session.role, session.data["info"])
        except ValueError as error:
            raise HTTPException(422, str(error))
        return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="RPD-{kind}.{extension}"'})

    @app.get("/api/legacy-report.pdf")
    def legacy_pdf(session=Depends(administrator)):
        content = session.data["source"].get("pdf")
        if not content:
            raise HTTPException(404, "PDF lama tidak tersedia pada sumber.")
        return Response(base64.b64decode(content), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="RPD-all-surveyors-unfiltered.pdf"'})

    @app.get("/")
    def index():
        return FileResponse(PUBLIC / "index.html")

    @app.get("/{asset}")
    def asset(asset: str):
        if asset not in ("app.js", "command-center.js", "styles.css", "command-center.css"):
            raise HTTPException(404)
        return FileResponse(PUBLIC / asset)

    return app


app = create_app()
