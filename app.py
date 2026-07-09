import logging
import os
import time
import secrets
import shutil
import uuid as uuid_module
from datetime import datetime, timedelta

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file, send_from_directory, session, url_for
from flask_cors import CORS, cross_origin
from flask_sqlalchemy import SQLAlchemy
from openai import AzureOpenAI
from parser_utils import extract_document_parts
from rag_utils import chunk_and_store, load_vector_db, retrieve_ranked_chunks
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_csv(name, default):
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def coerce_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()
LOCAL_STORAGE_ROOT = os.path.abspath(
    os.getenv("LOCAL_STORAGE_ROOT", os.path.join(BASE_DIR, "uploads"))
)
VECTOR_ROOT = os.path.abspath(os.getenv("VECTOR_ROOT", os.path.join(BASE_DIR, "vectors")))
TEMP_ROOT = os.path.abspath(os.getenv("TEMP_ROOT", os.path.join(BASE_DIR, "temp")))
FRONTEND_DIST_DIR = os.path.abspath(
    os.getenv("FRONTEND_DIST_DIR", os.path.join(BASE_DIR, "frontend", "dist"))
)
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "user-files")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
DEFAULT_ORG_SYSTEM_PROMPT = (
    "You are a helpful assistant for this organization's document corpus. "
    "Answer using only the retrieved context. If the answer is not present, say so."
)
DEFAULT_CHAT_TITLE = "AskPro Chat"
DATABASE_URI = os.getenv("ASKPRO_DATABASE_URI")
if not DATABASE_URI:
    if env_bool("USE_REMOTE_DATABASE", False):
        DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    else:
        DATABASE_URI = "sqlite:///askpro_local.db"
if not DATABASE_URI:
    raise RuntimeError("Database URI is not configured")


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["UPLOAD_FOLDER"] = TEMP_ROOT
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = int(
    os.getenv("MAX_UPLOAD_MB", "50")
) * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
app.config["SESSION_COOKIE_SECURE"] = env_bool("SESSION_COOKIE_SECURE", False)

cookie_domain = os.getenv("SESSION_COOKIE_DOMAIN")
if cookie_domain:
    app.config["SESSION_COOKIE_DOMAIN"] = cookie_domain

CORS(
    app,
    origins=env_csv(
        "CORS_ORIGINS",
        [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "https://blue-cliff-0de6c3b00.2.azurestaticapps.net",
        ],
    ),
    supports_credentials=True,
)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
db = SQLAlchemy(app)

blob_service_client = None
container_client = None
openai_client = None
RATE_LIMIT_BUCKETS = {}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_org = db.Column(db.Boolean, default=False)
    uuid = db.Column(db.String(36), unique=True, nullable=False)


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    path = db.Column(db.String(300), nullable=False)
    mimetype = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class OrganizationSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    system_prompt = db.Column(db.Text, nullable=False, default=DEFAULT_ORG_SYSTEM_PROMPT)
    api_key = db.Column(db.String(120), unique=True, nullable=False)
    public_id = db.Column(db.String(48), unique=True, nullable=False)
    chat_title = db.Column(db.String(120), nullable=False, default=DEFAULT_CHAT_TITLE)
    api_enabled = db.Column(db.Boolean, nullable=False, default=True)
    public_enabled = db.Column(db.Boolean, nullable=False, default=True)
    allowed_origins = db.Column(db.Text, nullable=False, default="*")


def init_storage():
    global blob_service_client, container_client

    os.makedirs(TEMP_ROOT, exist_ok=True)
    os.makedirs(VECTOR_ROOT, exist_ok=True)

    if STORAGE_BACKEND == "local":
        os.makedirs(LOCAL_STORAGE_ROOT, exist_ok=True)
        logger.info("Using local file storage at %s", LOCAL_STORAGE_ROOT)
        return

    if STORAGE_BACKEND != "azure":
        raise RuntimeError(f"Unsupported STORAGE_BACKEND: {STORAGE_BACKEND}")

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required for Azure storage")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
    try:
        container_client.create_container()
    except Exception:
        pass
    logger.info("Using Azure Blob storage container %s", AZURE_CONTAINER_NAME)


def safe_local_path(root, relative_path):
    normalized = os.path.normpath(relative_path).replace("\\", os.sep)
    if os.path.isabs(normalized) or normalized.startswith(".."):
        raise ValueError("Invalid storage path")

    root_abs = os.path.abspath(root)
    target = os.path.abspath(os.path.join(root_abs, normalized))
    if os.path.commonpath([root_abs, target]) != root_abs:
        raise ValueError("Invalid storage path")
    return target


def make_storage_key(user_uuid, filename):
    suffix = uuid_module.uuid4().hex[:8]
    return f"{user_uuid}/{suffix}_{filename}"


def vector_path_for(user_uuid, storage_key):
    vector_name = f"{os.path.basename(storage_key)}.faiss"
    return os.path.join(VECTOR_ROOT, user_uuid, vector_name)


def generate_api_key():
    return f"askpro_{secrets.token_urlsafe(32)}"


def generate_public_id():
    return secrets.token_urlsafe(18).replace("-", "_")


def get_org_settings(user, create=True):
    if not user or not user.is_org:
        return None

    settings = OrganizationSettings.query.filter_by(user_id=user.id).first()
    if settings or not create:
        return settings

    settings = OrganizationSettings(
        user_id=user.id,
        system_prompt=DEFAULT_ORG_SYSTEM_PROMPT,
        api_key=generate_api_key(),
        public_id=generate_public_id(),
        chat_title=DEFAULT_CHAT_TITLE,
        api_enabled=True,
        public_enabled=True,
        allowed_origins="*",
    )
    db.session.add(settings)
    db.session.commit()
    return settings


def get_api_key_from_request():
    api_key = request.headers.get("X-API-Key", "").strip()
    auth_header = request.headers.get("Authorization", "").strip()
    if not api_key and auth_header.lower().startswith("bearer "):
        api_key = auth_header[7:].strip()
    return api_key


def normalize_allowed_origins(value):
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value or "*").replace(",", "\n").splitlines()

    origins = []
    for item in raw_items:
        origin = str(item).strip().rstrip("/")
        if origin and origin not in origins:
            origins.append(origin)
    return "\n".join(origins) if origins else "*"


def api_origin_allowed(settings):
    origin = request.headers.get("Origin", "").strip().rstrip("/")
    if not origin:
        return True

    allowed = normalize_allowed_origins(settings.allowed_origins).splitlines()
    return "*" in allowed or origin in allowed


def validate_api_access(settings):
    if not settings.api_enabled:
        return jsonify({"error": "API access is disabled"}), 403
    if not api_origin_allowed(settings):
        return jsonify({"error": "Origin is not allowed for this API key"}), 403
    return None



def request_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit_config(scope):
    upper = scope.upper()
    return {
        "enabled": env_bool("RATE_LIMIT_ENABLED", True),
        "window_seconds": env_int(f"RATE_LIMIT_{upper}_WINDOW_SECONDS", env_int("RATE_LIMIT_WINDOW_SECONDS", 60)),
        "max_requests": env_int(f"RATE_LIMIT_{upper}_MAX_REQUESTS", env_int("RATE_LIMIT_MAX_REQUESTS", 60)),
    }


def check_rate_limit(scope, identity):
    config = rate_limit_config(scope)
    if not config["enabled"] or config["max_requests"] <= 0:
        return None

    now = time.time()
    window = max(config["window_seconds"], 1)
    max_requests = config["max_requests"]
    bucket_key = f"{scope}:{identity}"
    bucket = RATE_LIMIT_BUCKETS.setdefault(bucket_key, [])
    cutoff = now - window
    bucket[:] = [timestamp for timestamp in bucket if timestamp > cutoff]

    if len(bucket) >= max_requests:
        retry_after = max(1, int(window - (now - bucket[0])))
        response = jsonify(
            {
                "error": "Rate limit exceeded",
                "scope": scope,
                "retry_after_seconds": retry_after,
            }
        )
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response

    bucket.append(now)
    return None


def rate_limit_identity(prefix, unique_id=None):
    return f"{prefix}:{unique_id or 'anonymous'}:{request_ip()}"


def save_to_storage(local_path, storage_key, mimetype):
    if STORAGE_BACKEND == "local":
        destination = safe_local_path(LOCAL_STORAGE_ROOT, storage_key)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(local_path, destination)
        return

    with open(local_path, "rb") as handle:
        container_client.upload_blob(
            name=storage_key,
            data=handle,
            overwrite=True,
            content_settings=ContentSettings(content_type=mimetype),
        )


def delete_from_storage(storage_key):
    if STORAGE_BACKEND == "local":
        path = safe_local_path(LOCAL_STORAGE_ROOT, storage_key)
        if os.path.exists(path):
            os.remove(path)
        return

    container_client.delete_blob(storage_key)


def get_azure_openai_client():
    global openai_client
    if openai_client:
        return openai_client

    required = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_DEPLOYMENT",
    ]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError("Missing Azure OpenAI env vars: " + ", ".join(missing))

    openai_client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )
    return openai_client


def allowed_file(filename, content_type):
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = {".pdf", ".docx", ".txt"}
    allowed_mimes = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    }
    return ext in allowed_exts and content_type in allowed_mimes


def current_user():
    if "uuid" not in session:
        return None
    return User.query.filter_by(uuid=session["uuid"]).first()


def require_user():
    user = current_user()
    if not user:
        return None, (jsonify({"error": "Not logged in"}), 401)
    return user, None


def require_org_user():
    user, error = require_user()
    if error:
        return None, error
    if not user.is_org:
        return None, (jsonify({"error": "Organization account required"}), 403)
    get_org_settings(user)
    return user, None


def rounded_score(value):
    if value is None:
        return None
    return round(float(value), 6)


def citation_snippet(text, limit=850):
    snippet = " ".join((text or "").split())
    if len(snippet) > limit:
        return snippet[:limit].rstrip() + "..."
    return snippet


def source_location(metadata):
    if metadata.get("page"):
        page_label = metadata.get("page_label") or metadata.get("page")
        page_count = metadata.get("page_count")
        if page_count:
            return f"page {page_label} of {page_count}"
        return f"page {page_label}"
    if metadata.get("paragraph_start"):
        start = metadata.get("paragraph_start")
        end = metadata.get("paragraph_end") or start
        return f"paragraphs {start}-{end}" if end != start else f"paragraph {start}"
    if metadata.get("line_start"):
        start = metadata.get("line_start")
        end = metadata.get("line_end") or start
        return f"lines {start}-{end}" if end != start else f"line {start}"
    if metadata.get("section_heading"):
        return f"section: {metadata.get('section_heading')}"
    return ""


def source_display_name(metadata):
    filename = metadata.get("filename") or "uploaded document"
    location = source_location(metadata)
    return f"{filename}, {location}" if location else filename


def build_citation(item, index):
    doc = item["doc"]
    metadata = doc.metadata or {}
    citation_id = f"S{index}"
    return {
        "id": citation_id,
        "label": f"[{citation_id}]",
        "display_name": source_display_name(metadata),
        "filename": metadata.get("filename"),
        "storage_key": metadata.get("storage_key"),
        "source_type": metadata.get("source_type"),
        "location": source_location(metadata),
        "source_label": metadata.get("source_label") or source_display_name(metadata),
        "page": metadata.get("page"),
        "page_label": metadata.get("page_label"),
        "page_count": metadata.get("page_count"),
        "section_heading": metadata.get("section_heading"),
        "section_index": metadata.get("section_index"),
        "paragraph_start": metadata.get("paragraph_start"),
        "paragraph_end": metadata.get("paragraph_end"),
        "line_start": metadata.get("line_start"),
        "line_end": metadata.get("line_end"),
        "part_index": metadata.get("part_index"),
        "part_id": metadata.get("part_id"),
        "chunk_id": metadata.get("chunk_id"),
        "chunk_index": metadata.get("chunk_index"),
        "chunk_keywords": metadata.get("chunk_keywords"),
        "token_count": metadata.get("token_count"),
        "char_count": metadata.get("char_count"),
        "start_index": metadata.get("start_index"),
        "snippet": citation_snippet(doc.page_content),
        "score": rounded_score(item.get("score")),
        "semantic_score": rounded_score(item.get("semantic_score")),
        "keyword_score": rounded_score(item.get("keyword_score")),
        "metadata_score": rounded_score(item.get("metadata_score")),
        "phrase_score": rounded_score(item.get("phrase_score")),
        "cross_encoder_score": rounded_score(item.get("cross_encoder_score")),
        "cross_encoder_score_raw": rounded_score(item.get("cross_encoder_score_raw")),
        "matched_terms": item.get("matched_terms", []),
    }


def format_context_block(item, citation):
    return f"{citation['label']} {citation['display_name']}\n{item['doc'].page_content}"


def format_retrieval_answer(citations):
    if not citations:
        return "No matching document chunks were found."

    lines = [
        "LLM generation is disabled in this local mode. Here are the most relevant retrieved passages with citations:"
    ]
    for citation in citations[:5]:
        score = citation.get("score") or 0
        lines.append(
            f"\n**{citation['label']} {citation['display_name']}** "
            f"(score {score:.4f})\n\n{citation['snippet']}"
        )
    return "\n".join(lines)


def get_retrieval_results(user, query_text):
    vector_folder = os.path.join(VECTOR_ROOT, user.uuid)
    if not os.path.exists(vector_folder):
        raise FileNotFoundError("No vectors found")

    results = []
    for entry in os.scandir(vector_folder):
        if not entry.is_dir() or not entry.name.endswith(".faiss"):
            continue
        try:
            vectordb = load_vector_db(entry.path)
            results.extend(
                retrieve_ranked_chunks(
                    vectordb,
                    query_text,
                    semantic_k=env_int("RAG_SEMANTIC_CANDIDATES", 30),
                    keyword_k=env_int("RAG_KEYWORD_CANDIDATES", 30),
                    final_k=env_int("RAG_PER_INDEX_FINAL_K", 12),
                )
            )
        except Exception:
            logger.exception("Error loading vector DB from %s", entry.path)

    return sorted(results, key=lambda item: item["score"], reverse=True)


def build_rag_payload(user, query_text, system_prompt=None):
    results = get_retrieval_results(user, query_text)
    top_results = results[: env_int("RAG_CONTEXT_CHUNKS", 10)]
    citations = [build_citation(item, index) for index, item in enumerate(top_results, start=1)]
    top_chunks = [item["doc"].page_content for item in top_results]

    if LLM_PROVIDER not in {"azure", "azure-openai"}:
        return {
            "answer": format_retrieval_answer(citations),
            "chunks": top_chunks,
            "sources": citations,
            "citations": citations,
            "mode": "retrieval-only",
            "retrieval_strategy": "hybrid-semantic-keyword-rerank",
        }

    context = "\n\n".join(
        format_context_block(item, citation)
        for item, citation in zip(top_results, citations)
    )
    org_prompt = (system_prompt or DEFAULT_ORG_SYSTEM_PROMPT).strip()
    response = get_azure_openai_client().chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {
                "role": "system",
                "content": (
                    f"{org_prompt}\n\n"
                    "Use only the supplied document context. If the answer is not in the context, say so. "
                    "Cite every factual claim with the source labels provided, such as [S1] or [S2]."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"### Context:\n{context}\n\n"
                    f"### Question:\n{query_text}\n\n### Answer with citations:"
                ),
            },
        ],
        temperature=float(os.getenv("AZURE_OPENAI_TEMPERATURE", "0.2")),
        max_tokens=int(os.getenv("AZURE_OPENAI_MAX_TOKENS", "2048")),
    )
    return {
        "answer": response.choices[0].message.content.strip(),
        "chunks": top_chunks,
        "sources": citations,
        "citations": citations,
        "mode": "llm",
        "retrieval_strategy": "hybrid-semantic-keyword-rerank",
    }


def rag_response_for_user(user, query_text, system_prompt=None):
    try:
        return jsonify(build_rag_payload(user, query_text, system_prompt))
    except FileNotFoundError:
        return jsonify({"error": "No vectors found"}), 400
    except Exception:
        logger.exception("RAG query failed")
        return jsonify({"error": "Failed to generate response"}), 500


def ensure_organization_settings_schema():
    if db.engine.dialect.name != "sqlite":
        return

    columns = {
        row[1]
        for row in db.session.execute(text("PRAGMA table_info(organization_settings)"))
    }
    migrations = {
        "chat_title": "ALTER TABLE organization_settings ADD COLUMN chat_title VARCHAR(120) NOT NULL DEFAULT 'AskPro Chat'",
        "api_enabled": "ALTER TABLE organization_settings ADD COLUMN api_enabled BOOLEAN NOT NULL DEFAULT 1",
        "public_enabled": "ALTER TABLE organization_settings ADD COLUMN public_enabled BOOLEAN NOT NULL DEFAULT 1",
        "allowed_origins": "ALTER TABLE organization_settings ADD COLUMN allowed_origins TEXT NOT NULL DEFAULT '*'",
    }
    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(text(statement))
    db.session.commit()


with app.app_context():
    init_storage()
    db.create_all()
    ensure_organization_settings_schema()


@app.before_request
def log_request_info():
    logger.info("Incoming request: %s %s", request.method, request.path)


@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400

    user = User(
        email=email,
        password=generate_password_hash(password),
        is_org=data.get("is_organization", False),
        uuid=str(uuid_module.uuid4()),
    )
    db.session.add(user)
    db.session.flush()
    if user.is_org:
        db.session.add(
            OrganizationSettings(
                user_id=user.id,
                system_prompt=DEFAULT_ORG_SYSTEM_PROMPT,
                api_key=generate_api_key(),
                public_id=generate_public_id(),
                chat_title=DEFAULT_CHAT_TITLE,
                api_enabled=True,
                public_enabled=True,
                allowed_origins="*",
            )
        )
    db.session.commit()
    session["user_id"] = user.id
    session["uuid"] = user.uuid
    return jsonify({"uuid": user.uuid, "is_org": user.is_org, "message": "Signup successful"})


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = user.id
    session["uuid"] = user.uuid
    if user.is_org:
        get_org_settings(user)
    return jsonify({"uuid": user.uuid, "is_org": user.is_org, "message": "Login successful"})


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@app.route("/whoami", methods=["GET"])
def whoami():
    user = current_user()
    if not user:
        return jsonify({"loggedIn": False})
    return jsonify({"loggedIn": True, "uuid": user.uuid, "is_org": user.is_org})


@app.route("/upload", methods=["POST"])
def upload():
    user, error = require_user()
    if error:
        return error

    uploaded_file = request.files.get("file")
    if not uploaded_file:
        return jsonify({"error": "File missing"}), 400

    file_count = File.query.filter_by(user_id=user.id).count()
    max_allowed = 30 if user.is_org else 10
    if file_count >= max_allowed:
        return jsonify({"error": f"Upload limit exceeded. Max allowed: {max_allowed} files."}), 403

    uploaded_file.seek(0, os.SEEK_END)
    file_size_mb = uploaded_file.tell() / (1024 * 1024)
    uploaded_file.seek(0)
    if file_size_mb > int(os.getenv("PER_FILE_UPLOAD_LIMIT_MB", "25")):
        return jsonify({"error": "File exceeds 25MB limit"}), 400

    mimetype = uploaded_file.mimetype
    if not allowed_file(uploaded_file.filename, mimetype):
        return jsonify({"error": "Invalid file type"}), 400

    filename = secure_filename(uploaded_file.filename) or "upload.txt"
    storage_key = make_storage_key(user.uuid, filename)
    temp_path = safe_local_path(TEMP_ROOT, os.path.basename(storage_key))
    vector_path = vector_path_for(user.uuid, storage_key)
    storage_saved = False

    try:
        uploaded_file.save(temp_path)
        save_to_storage(temp_path, storage_key, mimetype)
        storage_saved = True

        document_parts = extract_document_parts(temp_path, mimetype)
        chunk_and_store(
            document_parts,
            vector_path,
            metadata={"filename": filename, "storage_key": storage_key},
        )

        file_record = File(
            filename=filename,
            path=storage_key,
            mimetype=mimetype,
            user_id=user.id,
        )
        db.session.add(file_record)
        db.session.commit()
        return jsonify({"message": "Upload successful"})
    except Exception as exc:
        db.session.rollback()
        if storage_saved:
            try:
                delete_from_storage(storage_key)
            except Exception:
                logger.exception("Failed to clean storage after upload error")
        if os.path.exists(vector_path):
            shutil.rmtree(vector_path, ignore_errors=True)
        logger.exception("Upload failed")
        return jsonify({"error": str(exc)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route("/query", methods=["POST"])
def query():
    user, error = require_user()
    if error:
        return error

    rate_error = check_rate_limit("SESSION_CHAT", rate_limit_identity("user", user.uuid))
    if rate_error:
        return rate_error

    data = request.get_json(silent=True) or {}
    query_text = data.get("query", "").strip()
    if not query_text:
        return jsonify({"error": "Query is required"}), 400

    settings = get_org_settings(user, create=False)
    system_prompt = settings.system_prompt if settings else None
    return rag_response_for_user(user, query_text, system_prompt)


@app.route("/admin/config", methods=["GET"])
def get_admin_config():
    user, error = require_org_user()
    if error:
        return error

    settings = get_org_settings(user)
    files = File.query.filter_by(user_id=user.id).all()
    return jsonify(
        {
            "email": user.email,
            "is_org": user.is_org,
            "system_prompt": settings.system_prompt,
            "api_key": settings.api_key,
            "public_id": settings.public_id,
            "public_path": f"/public/{settings.public_id}",
            "api_endpoint": "/api/chat",
            "chat_title": settings.chat_title,
            "api_enabled": settings.api_enabled,
            "public_enabled": settings.public_enabled,
            "allowed_origins": settings.allowed_origins,
            "files": [{"id": item.id, "filename": item.filename} for item in files],
        }
    )


@app.route("/admin/config", methods=["POST"])
def update_admin_config():
    user, error = require_org_user()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    settings = get_org_settings(user)
    settings.system_prompt = data.get("system_prompt", DEFAULT_ORG_SYSTEM_PROMPT).strip() or DEFAULT_ORG_SYSTEM_PROMPT
    settings.chat_title = data.get("chat_title", settings.chat_title or DEFAULT_CHAT_TITLE).strip() or DEFAULT_CHAT_TITLE
    settings.api_enabled = coerce_bool(data.get("api_enabled"), settings.api_enabled)
    settings.public_enabled = coerce_bool(data.get("public_enabled"), settings.public_enabled)
    settings.allowed_origins = normalize_allowed_origins(data.get("allowed_origins", settings.allowed_origins))
    db.session.commit()
    return jsonify(
        {
            "message": "Configuration saved",
            "system_prompt": settings.system_prompt,
            "chat_title": settings.chat_title,
            "api_enabled": settings.api_enabled,
            "public_enabled": settings.public_enabled,
            "allowed_origins": settings.allowed_origins,
        }
    )


@app.route("/admin/regenerate-api-key", methods=["POST"])
def regenerate_api_key():
    user, error = require_org_user()
    if error:
        return error

    settings = get_org_settings(user)
    settings.api_key = generate_api_key()
    db.session.commit()
    return jsonify({"message": "API key regenerated", "api_key": settings.api_key})


@app.route("/api/chat", methods=["POST"])
@cross_origin(origins="*")
def api_chat():
    api_key = get_api_key_from_request()
    if not api_key:
        return jsonify({"error": "API key required"}), 401

    settings = OrganizationSettings.query.filter_by(api_key=api_key).first()
    if not settings:
        return jsonify({"error": "Invalid API key"}), 401

    access_error = validate_api_access(settings)
    if access_error:
        return access_error

    rate_error = check_rate_limit("API_CHAT", rate_limit_identity("api", settings.id))
    if rate_error:
        return rate_error

    data = request.get_json(silent=True) or {}
    query_text = (data.get("message") or data.get("query") or "").strip()
    if not query_text:
        return jsonify({"error": "Message is required"}), 400

    user = db.session.get(User, settings.user_id)
    if not user:
        return jsonify({"error": "Organization not found"}), 404
    return rag_response_for_user(user, query_text, settings.system_prompt)


@app.route("/public-chat/<public_id>/meta", methods=["GET"])
@cross_origin(origins="*")
def public_chat_meta(public_id):
    settings = OrganizationSettings.query.filter_by(public_id=public_id).first()
    if not settings or not settings.public_enabled:
        return jsonify({"error": "Chat link not found"}), 404
    return jsonify({"chat_title": settings.chat_title, "public_id": settings.public_id})


@app.route("/public-chat/<public_id>", methods=["POST"])
@cross_origin(origins="*")
def public_chat(public_id):
    settings = OrganizationSettings.query.filter_by(public_id=public_id).first()
    if not settings or not settings.public_enabled:
        return jsonify({"error": "Chat link not found"}), 404

    rate_error = check_rate_limit("PUBLIC_CHAT", rate_limit_identity("public", settings.public_id))
    if rate_error:
        return rate_error

    data = request.get_json(silent=True) or {}
    query_text = (data.get("message") or data.get("query") or "").strip()
    if not query_text:
        return jsonify({"error": "Message is required"}), 400

    user = db.session.get(User, settings.user_id)
    if not user:
        return jsonify({"error": "Organization not found"}), 404
    return rag_response_for_user(user, query_text, settings.system_prompt)


@app.route("/list-files", methods=["GET"])
def list_files():
    user, error = require_user()
    if error:
        return error

    files = File.query.filter_by(user_id=user.id).all()
    return jsonify([{"id": item.id, "filename": item.filename} for item in files])


@app.route("/delete-file", methods=["POST"])
def delete_file():
    user, error = require_user()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    file_id = data.get("file_id")
    file_record = File.query.filter_by(id=file_id, user_id=user.id).first()
    if not file_record:
        return jsonify({"error": "File not found"}), 404

    try:
        delete_from_storage(file_record.path)
        vector_path = vector_path_for(user.uuid, file_record.path)
        if os.path.exists(vector_path):
            shutil.rmtree(vector_path)
        db.session.delete(file_record)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Delete failed")
        return jsonify({"error": "Delete operation failed"}), 500

    return jsonify({"message": "File and vector index deleted"})


@app.route("/keep-alive")
def keep_alive():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(
            {
                "status": "ok",
                "storage_backend": STORAGE_BACKEND,
                "embedding_provider": os.getenv("RAG_EMBEDDING_PROVIDER", "local"),
                "llm_provider": LLM_PROVIDER,
            }
        )
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500


@app.route("/view-file/<int:file_id>")
def view_file(file_id):
    user, error = require_user()
    if error:
        return error

    file_record = File.query.filter_by(id=file_id, user_id=user.id).first()
    if not file_record:
        return jsonify({"error": "File not found"}), 404

    if STORAGE_BACKEND == "local":
        return jsonify({"url": url_for("download_file", file_id=file_id, _external=True)})

    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    if not account_key:
        return jsonify({"error": "AZURE_STORAGE_ACCOUNT_KEY is required to view files"}), 500

    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=AZURE_CONTAINER_NAME,
        blob_name=file_record.path,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(minutes=15),
    )
    blob_url = (
        f"https://{blob_service_client.account_name}.blob.core.windows.net/"
        f"{AZURE_CONTAINER_NAME}/{file_record.path}?{sas_token}"
    )
    return jsonify({"url": blob_url})


@app.route("/download-file/<int:file_id>")
def download_file(file_id):
    if STORAGE_BACKEND != "local":
        return jsonify({"error": "Local downloads are only available in local storage mode"}), 400

    user, error = require_user()
    if error:
        return error

    file_record = File.query.filter_by(id=file_id, user_id=user.id).first()
    if not file_record:
        return jsonify({"error": "File not found"}), 404

    path = safe_local_path(LOCAL_STORAGE_ROOT, file_record.path)
    return send_file(
        path,
        mimetype=file_record.mimetype,
        as_attachment=False,
        download_name=file_record.filename,
    )


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path:
        asset_path = os.path.join(FRONTEND_DIST_DIR, path)
        if os.path.exists(asset_path):
            return send_from_directory(FRONTEND_DIST_DIR, path)

    index_path = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(FRONTEND_DIST_DIR, "index.html")

    status = {
        "message": "AskPro API is running. Build the frontend or use Vite for the UI.",
        "frontend_dist": FRONTEND_DIST_DIR,
    }
    return jsonify(status), 200 if not path else 404


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_RUN_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_RUN_PORT", "5000")),
        debug=env_bool("FLASK_DEBUG", False),
    )
