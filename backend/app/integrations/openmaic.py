"""The only module that talks to OpenMAIC.

Everything about OpenMAIC's wire format is contained here so that when it
changes -- and it ships releases roughly monthly -- exactly one file breaks.

VERIFIED against the OpenMAIC source (THU-MAIC/OpenMAIC, v1.5.0, Nov 2026):

  POST /api/materials
      Raw file bytes in the body. `Content-Type` is the MIME type and
      `x-material-filename` the display name. 201 -> {"materialId", "originalName",
      "bytes", "mime", "mediaKind", "extraction"}.
      Accepted formats: pdf pptx docx xlsx png jpeg webp txt markdown csv
      mp4 mov webm mp3 wav m4a aac. Anything else -> 415.

  POST /api/generate-classroom      {"requirement", "materialIds"?} -> 202 job
  GET  /api/generate-classroom/{id}                                 -> job
      Job fields: jobId, runId, runState, status, step, progress, message,
      pollUrl, pollIntervalMs, scenesGenerated, totalScenes, result
      {classroomId, url, scenesCount, warning?}, error, retryable, done.
      status in queued|running|succeeded|failed.
      429 ACTIVE_RUN_LIMIT when the owner is at their concurrent-run cap.

  POST /api/generation-runs/{runId}/retry   {"commandId": "<new id>"}
  GET  /api/classroom-media/{classroomId}/{media|audio}/{path...}

ALSO VERIFIED (storage contract + route sources):

  GET  /api/persistence/documents/{stageId}      the full MaicDocument (raw body)
  GET  /api/persistence/assets/{assetId}/content asset bytes
  POST /api/access-code/verify  {"code"}         sets the `openmaic_access` cookie

  `result.classroomId` of a finished job is the stage id. A document holds stage,
  scenes and outline; media is stored separately and referenced by `ast_...` ids.

Authentication (VERIFIED in lib/server/identity and middleware.ts): with
OWNER_SINGLE_USER=true and ACCESS_CODE unset, Minet sends no credential at all.
If ACCESS_CODE is set, it is exchanged once for the `openmaic_access` cookie; it
is never sent as a header. `OPENMAIC_COOKIE` remains only for an OpenMAIC left in
its default per-browser owner mode.

STILL UNVERIFIED (needs a live instance; see tests/test_live_openmaic.py):
  * whether job responses are wrapped in {"success":true,"data":{...}}
    (`_unwrap` accepts both);
  * that cookie-less document and asset reads succeed in single-user mode;
  * the exact QuizOption shape, PBL project schema and discussion payload.

There is NO server route that builds the .maic.zip / HTML / PPTX exports (the
builder is a browser hook), so Minet imports from the document and asset routes.
The manual export upload remains as a fallback.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from .. import config

log = logging.getLogger("minet.openmaic")

# Formats OpenMAIC's material-upload policy accepts, by extension.
SUPPORTED_MATERIAL_EXTENSIONS = {
    "pdf", "pptx", "docx", "xlsx", "png", "jpg", "jpeg", "webp", "txt", "md",
    "markdown", "csv", "mp4", "mov", "webm", "mp3", "wav", "m4a", "aac",
}

TERMINAL_STATUSES = {"succeeded", "failed"}

# base_url -> openmaic_access cookie value, so the code is exchanged once.
_ACCESS_TOKENS: dict[str, str] = {}


class OpenMAICError(RuntimeError):
    """Base class. `retryable` tells the worker whether to try again."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False,
                 code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.code = code


class OpenMAICNotConfigured(OpenMAICError):
    def __init__(self) -> None:
        super().__init__(
            "OpenMAIC is not configured. Set OPENMAIC_BASE_URL in backend/.env.",
            retryable=False, code="NOT_CONFIGURED")


class OpenMAICAuthError(OpenMAICError):
    pass


class OpenMAICBusy(OpenMAICError):
    """429 ACTIVE_RUN_LIMIT -- the instance is busy, the job itself is fine."""

    def __init__(self, message: str = "OpenMAIC is at its concurrent generation limit.") -> None:
        super().__init__(message, status=429, retryable=True, code="ACTIVE_RUN_LIMIT")


class OpenMAICUnsupported(OpenMAICError):
    """A capability this OpenMAIC build does not expose."""


@dataclass
class MaterialUpload:
    material_id: str
    original_name: str
    bytes_: int
    mime: str
    media_kind: Optional[str] = None
    extraction: Any = None


@dataclass
class GenerationJobView:
    """Normalised view of an OpenMAIC job. Minet's own vocabulary stays separate."""
    job_id: str
    status: str                     # queued | running | succeeded | failed
    step: Optional[str] = None
    progress: int = 0
    message: Optional[str] = None
    done: bool = False
    retryable: bool = False
    error: Optional[str] = None
    classroom_id: Optional[str] = None
    classroom_url: Optional[str] = None
    scenes_count: Optional[int] = None
    warning: Optional[str] = None
    raw: dict = field(default_factory=dict)


def _unwrap(payload: Any) -> dict:
    """Accept both a bare object and an {"success":true,"data":{...}} envelope."""
    if not isinstance(payload, dict):
        raise OpenMAICError(f"Unexpected response from OpenMAIC: {type(payload).__name__}")
    if "data" in payload and isinstance(payload["data"], dict) and (
            "success" in payload or "error" not in payload):
        inner = payload["data"]
        if inner:
            return inner
    return payload


def _error_text(payload: Any, fallback: str) -> tuple[str, Optional[str]]:
    """Pull (message, code) out of OpenMAIC's several error shapes."""
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or fallback), err.get("code")
        if isinstance(err, str):
            return err, payload.get("errorCode")
        if payload.get("message"):
            return str(payload["message"]), payload.get("errorCode")
    return fallback, None


class OpenMAICClient:
    """Thin, synchronous client. One instance per worker iteration is fine."""

    def __init__(self, base_url: Optional[str] = None, cookie: Optional[str] = None,
                 access_code: Optional[str] = None, timeout: Optional[int] = None) -> None:
        self.base_url = (base_url if base_url is not None else config.OPENMAIC_BASE_URL).rstrip("/")
        self.cookie = cookie if cookie is not None else config.OPENMAIC_COOKIE
        self.access_code = access_code if access_code is not None else config.OPENMAIC_ACCESS_CODE
        self.timeout = timeout or config.OPENMAIC_TIMEOUT_SECONDS

    # -- plumbing -----------------------------------------------------------

    def _cookie_header(self, force: bool = False) -> str:
        """Owner cookie (optional) plus, when ACCESS_CODE is set on OpenMAIC, the
        `openmaic_access` cookie obtained from POST /api/access-code/verify.

        VERIFIED in OpenMAIC's middleware.ts: the access code is carried only by
        that cookie -- there is no header. In OWNER_SINGLE_USER mode with
        ACCESS_CODE unset, neither is needed and this returns "".
        """
        parts = [self.cookie] if self.cookie else []
        token = self._access_token(force)
        if token:
            parts.append(f"openmaic_access={token}")
        return "; ".join(parts)

    def _access_token(self, force: bool = False) -> str:
        if not self.access_code:
            return ""
        if not force and self.base_url in _ACCESS_TOKENS:
            return _ACCESS_TOKENS[self.base_url]
        self._require()
        try:
            response = httpx.post(f"{self.base_url}/api/access-code/verify",
                                  json={"code": self.access_code}, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise OpenMAICError(f"Cannot reach OpenMAIC at {self.base_url}: {exc}",
                                retryable=True, code="UNREACHABLE") from exc
        if response.status_code == 429:
            raise OpenMAICError("OpenMAIC is rate limiting access-code attempts.",
                                status=429, retryable=True, code="RATE_LIMITED")
        if response.status_code in (400, 401, 403):
            raise OpenMAICAuthError(
                "OpenMAIC rejected OPENMAIC_ACCESS_CODE. Check it matches ACCESS_CODE on "
                "the OpenMAIC server.", status=response.status_code, code="INVALID_ACCESS_CODE")
        token = response.cookies.get("openmaic_access") or ""
        _ACCESS_TOKENS[self.base_url] = token   # empty when the gate is disabled
        return token

    def _headers(self, extra: Optional[dict] = None) -> dict:
        headers = {"accept": "application/json"}
        cookie = self._cookie_header()
        if cookie:
            headers["cookie"] = cookie
        if extra:
            headers.update(extra)
        return headers

    def _require(self) -> None:
        if not self.base_url:
            raise OpenMAICNotConfigured()

    def _request(self, method: str, path: str, *, timeout: Optional[int] = None,
                 _retried: bool = False, **kwargs) -> Any:
        self._require()
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=timeout or self.timeout, follow_redirects=False) as http:
                response = http.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise OpenMAICError(f"OpenMAIC timed out calling {path}.",
                                retryable=True, code="TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise OpenMAICError(f"Cannot reach OpenMAIC at {self.base_url}: {exc}",
                                retryable=True, code="UNREACHABLE") from exc

        if response.status_code == 204:
            return {}
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"message": response.text[:500]}

        if response.is_success:
            return payload

        if (response.status_code == 401 and self.access_code and not _retried
                and "access code" in str(payload).lower()):
            _ACCESS_TOKENS.pop(self.base_url, None)
            headers = dict(kwargs.get("headers") or {})
            headers["cookie"] = self._cookie_header(force=True)
            kwargs["headers"] = headers
            return self._request(method, path, timeout=timeout, _retried=True, **kwargs)

        message, code = _error_text(payload, f"OpenMAIC returned {response.status_code}")
        if response.status_code in (401, 403):
            raise OpenMAICAuthError(
                "OpenMAIC rejected Minet's credentials. OPENMAIC_COOKIE may have expired; "
                "OpenMAIC has no documented server-to-server API key. "
                f"({message})", status=response.status_code, retryable=False, code=code)
        if response.status_code == 429:
            raise OpenMAICBusy(message)
        if response.status_code == 404:
            raise OpenMAICUnsupported(
                f"OpenMAIC has no route {path} in this build. ({message})",
                status=404, retryable=False, code=code)
        if response.status_code in (415, 413, 400, 422):
            raise OpenMAICError(message, status=response.status_code, retryable=False, code=code)
        raise OpenMAICError(message, status=response.status_code, retryable=True, code=code)

    # -- capability probe ---------------------------------------------------

    def health(self) -> dict:
        """Best-effort reachability check for the admin UI."""
        try:
            self._request("GET", "/api/health", timeout=10)
            return {"reachable": True, "detail": "OpenMAIC responded."}
        except OpenMAICNotConfigured:
            return {"reachable": False, "detail": "OPENMAIC_BASE_URL is not set."}
        except OpenMAICUnsupported:
            # No /api/health in this build; the host is still up.
            return {"reachable": True, "detail": "Reachable (no /api/health route)."}
        except OpenMAICError as exc:
            return {"reachable": False, "detail": str(exc)}

    # -- materials ----------------------------------------------------------

    def upload_material(self, *, filename: str, mime_type: str, payload: bytes) -> MaterialUpload:
        """POST /api/materials -- raw bytes, filename in a header."""
        data = _unwrap(self._request(
            "POST", "/api/materials",
            content=payload,
            headers=self._headers({
                "content-type": mime_type or "application/octet-stream",
                "x-material-filename": filename,
                "x-request-id": uuid.uuid4().hex,
            }),
            timeout=config.OPENMAIC_UPLOAD_TIMEOUT_SECONDS,
        ))
        material_id = data.get("materialId")
        if not material_id:
            raise OpenMAICError(
                "OpenMAIC accepted the upload but returned no materialId. "
                f"Response keys: {sorted(data)}")
        return MaterialUpload(
            material_id=str(material_id),
            original_name=str(data.get("originalName") or filename),
            bytes_=int(data.get("bytes") or len(payload)),
            mime=str(data.get("mime") or mime_type),
            media_kind=data.get("mediaKind"),
            extraction=data.get("extraction"),
        )

    # -- generation ---------------------------------------------------------

    def start_generation(self, *, requirement: str,
                         material_ids: Optional[list[str]] = None) -> GenerationJobView:
        body: dict[str, Any] = {"requirement": requirement}
        if material_ids:
            body["materialIds"] = list(material_ids)
        payload = self._request("POST", "/api/generate-classroom", json=body,
                                headers=self._headers({"content-type": "application/json"}))
        return self._to_job(payload)

    def get_job(self, job_id: str) -> GenerationJobView:
        payload = self._request("GET", f"/api/generate-classroom/{job_id}",
                                headers=self._headers())
        return self._to_job(payload)

    def retry_run(self, run_id: str) -> dict:
        """POST /api/generation-runs/{runId}/retry. Verified only via its error text."""
        return _unwrap(self._request(
            "POST", f"/api/generation-runs/{run_id}/retry",
            json={"commandId": uuid.uuid4().hex},
            headers=self._headers({"content-type": "application/json"})))

    @staticmethod
    def _to_job(payload: Any) -> GenerationJobView:
        data = _unwrap(payload)
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        status = str(data.get("status") or "queued")
        job_id = data.get("jobId") or data.get("runId")
        if not job_id:
            raise OpenMAICError(f"OpenMAIC job response has no jobId. Keys: {sorted(data)}")
        error = data.get("error")
        if isinstance(error, dict):
            error = error.get("message")
        return GenerationJobView(
            job_id=str(job_id),
            status=status,
            step=data.get("step"),
            progress=int(data.get("progress") or 0),
            message=data.get("message"),
            done=bool(data.get("done") or status in TERMINAL_STATUSES),
            retryable=bool(data.get("retryable")),
            error=str(error) if error else None,
            classroom_id=result.get("classroomId"),
            classroom_url=result.get("url"),
            scenes_count=result.get("scenesCount"),
            warning=result.get("warning"),
            raw=data if isinstance(data, dict) else {},
        )

    # -- content retrieval (VERIFIED routes) --------------------------------

    def fetch_classroom_document(self, classroom_id: str) -> Optional[dict]:
        """GET /api/persistence/documents/{stageId} -> the full MaicDocument.

        VERIFIED: the job result's `classroomId` is the stage id, and this is the
        storage package's document route (packages/@openmaic/storage/docs/
        document-http-contract.md) mounted under /api/persistence. The body is the
        document itself (stage + scenes + outline), not an apiSuccess envelope, so
        it is returned as-is. Returns None only for a 404.
        """
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,190}", classroom_id or ""):
            raise OpenMAICError(f"Refusing an unsafe classroom id: {classroom_id!r}")
        try:
            payload = self._request(
                "GET", f"/api/persistence/documents/{classroom_id}", headers=self._headers())
        except OpenMAICUnsupported:
            log.info("Document %s was not found on OpenMAIC.", classroom_id)
            return None
        return payload if isinstance(payload, dict) and payload else None

    def fetch_asset(self, asset_id: str) -> tuple[bytes, Optional[str]]:
        """GET /api/persistence/assets/{id}/content -> (bytes, content type).

        VERIFIED contract (asset-http-contract.md); the mount prefix is verified in
        app/api/persistence/[...path]/route.ts. Streams with a size cap and follows
        the optional redirect to a signed URL that the asset contract allows.
        """
        if not re.fullmatch(r"ast_[A-Za-z0-9_-]{8,128}", asset_id or ""):
            raise OpenMAICError(f"Refusing a malformed asset id: {asset_id!r}")
        self._require()
        url = f"{self.base_url}/api/persistence/assets/{asset_id}/content"
        limit = config.MAX_UPLOAD_BYTES
        try:
            with httpx.Client(timeout=config.OPENMAIC_UPLOAD_TIMEOUT_SECONDS,
                              follow_redirects=True) as http:
                with http.stream("GET", url, headers=self._headers({"accept": "*/*"})) as response:
                    if response.status_code == 404:
                        raise OpenMAICUnsupported(f"Asset {asset_id} was not found.", status=404)
                    if response.status_code in (401, 403):
                        raise OpenMAICAuthError("OpenMAIC refused the asset download.",
                                                status=response.status_code)
                    if response.status_code != 200:
                        raise OpenMAICError(f"Asset download returned {response.status_code}.",
                                            status=response.status_code, retryable=True)
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > limit:
                            raise OpenMAICError(f"Asset {asset_id} exceeds the {limit} byte limit.")
                        chunks.append(chunk)
                    return b"".join(chunks), response.headers.get("content-type")
        except httpx.TimeoutException as exc:
            raise OpenMAICError(f"Timed out downloading asset {asset_id}.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise OpenMAICError(f"Cannot download asset {asset_id}: {exc}", retryable=True) from exc


def material_extension_supported(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in SUPPORTED_MATERIAL_EXTENSIONS
