from flask import Flask, request, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid
import werkzeug
from parser_utils import extract_text
from rag_utils import load_vector_db, retrieve_chunks, chunk_and_store
import shutil
import gc
from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas, BlobSasPermissions
from dotenv import load_dotenv
import openai
from openai import OpenAI, AzureOpenAI
import logging
from sqlalchemy import text
from datetime import datetime, timedelta






load_dotenv()

openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"), 
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
# openai.api_type = "azure"
# openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
# openai.api_key = os.getenv("AZURE_OPENAI_KEY")
# openai.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
# AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = "user-files"

blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

try:
    container_client.create_container()
except Exception:
    pass  # Container already exists


# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = 'your_super_secret_key'  # 🔒 Replace with a secure key
# app.config.update(
#     SESSION_COOKIE_SAMESITE='None',
#     SESSION_COOKIE_SECURE=True
# )
# --- Config ---
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] =  os.getenv("SQLALCHEMY_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB upload limit
app.config["SESSION_COOKIE_DOMAIN"] = "askpro.duckdns.org"
app.config["SESSION_COOKIE_SAMESITE"] = "None"        # ✅ add this
app.config["SESSION_COOKIE_SECURE"] = True 

# --- CORS Setup for React Frontend ---
# CORS(app, origins=["https://blue-cliff-0de6c3b00.2.azurestaticapps.net"], supports_credentials=True)
# Logging to stdout for systemd (Gunicorn compatible)
CORS(
    app,
    origins=["http://localhost:5173", "https://blue-cliff-0de6c3b00.2.azurestaticapps.net"],
    supports_credentials=True
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),  # Output to stdout (captured by systemd)
        # Optional file logging
        # logging.FileHandler("flask-debug.log") 
    ]
)
logger = logging.getLogger(__name__)

# --- DB Setup ---
db = SQLAlchemy(app)

# --- Models ---
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- Initialization ---
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.create_all()

@app.before_request
def log_request_info():
    logger.info("⬅️ Incoming Request: %s %s", request.method, request.path)
    logger.info("🔐 Cookies: %s", request.cookies)
    logger.info("📦 Session: %s", dict(session))
    logger.info("🧾 Headers: %s", dict(request.headers))

# --- Helpers ---
def allowed_file(filename, content_type):
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = ['.pdf', '.docx', '.txt']
    allowed_mimes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
    return ext in allowed_exts and content_type in allowed_mimes

# --- Routes ---
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already registered"}), 400
    user = User(
        email=data['email'],
        password=generate_password_hash(data['password']),  # 🔐 Hashed
        is_org=data.get('is_organization', False),
        uuid=str(uuid.uuid4())
    )
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    session['uuid'] = user.uuid
    return jsonify({"uuid": user.uuid, "message": "Signup successful"})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({"error": "Invalid credentials"}), 401
    session['user_id'] = user.id
    session['uuid'] = user.uuid
    return jsonify({"uuid": user.uuid, "message": "Login successful"})

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})

@app.route('/whoami', methods=['GET'])
def whoami():
    if 'uuid' not in session:
        return jsonify({"loggedIn": False})
    return jsonify({"loggedIn": True, "uuid": session['uuid']})

@app.route('/upload', methods=['POST'])
def upload():
    if "uuid" not in session:
        return jsonify({"error": "Not logged in"}), 401

    user_uuid = session["uuid"]
    user_type = session.get("user_type", "personal")
    try:
        user = User.query.filter_by(uuid=session['uuid']).first()
        file = request.files.get('file')
        if not user or not file:
            return jsonify({"error": "Unauthorized or file missing"}), 400

        # 🔒 Check file count limit
        file_count = File.query.filter_by(user_id=user.id).count()
        max_allowed = 30 if user.is_org else 10
        if file_count >= max_allowed:
            return jsonify({"error": f"Upload limit exceeded. Max allowed: {max_allowed} files."}), 403

        # 🔒 Check file size limit (25MB)
        file.seek(0, os.SEEK_END)
        file_size_mb = file.tell() / (1024 * 1024)
        file.seek(0)
        if file_size_mb > 25:
            return jsonify({"error": "File exceeds 25MB limit"}), 400

        # ✅ Check type
        mimetype = file.mimetype
        if not allowed_file(file.filename, mimetype):
            return jsonify({"error": "Invalid file type"}), 400

        filename = werkzeug.utils.secure_filename(file.filename)
        unique_suffix = uuid.uuid4().hex[:8]
        blob_path = f"{user.uuid}/{unique_suffix}_{filename}"

        # ☁️ Upload to Azure Blob
        try:
            container_client.upload_blob(
                name=blob_path,
                data=file,
                overwrite=True,
                content_settings=ContentSettings(content_type=mimetype)
            )
        except Exception as e:
            print(f"Failed to upload to Blob Storage: {str(e)}")
            return jsonify({"error": f"Failed to upload to Blob Storage: {str(e)}"}), 500

        # 🗃️ Save metadata to DB
        db.session.add(File(filename=filename, path=blob_path, mimetype=mimetype, user_id=user.id))
        db.session.commit()

        # 🧠 Process locally
        os.makedirs("temp", exist_ok=True)
        local_temp_path = os.path.join("temp", filename)
        file.seek(0)
        with open(local_temp_path, "wb") as f:
            f.write(file.read())

        extracted_text = extract_text(local_temp_path, mimetype)
        vector_folder = os.path.join('vectors', user.uuid)
        vector_path = os.path.join(vector_folder, f"{filename}.faiss")
        chunk_and_store(extracted_text, vector_path, metadata={"filename": filename})
        # print("Extracted text:", extracted_text[:500])  # dev check

        os.remove(local_temp_path)
        return jsonify({"message": "Upload successful"})
    
    except Exception as e:
        print("❌ Upload route error:", e)
        return jsonify({"error": str(e)}), 500
@app.route('/query', methods=['POST'])
def query():
    print("🧪 Model from ENV:", os.getenv("AZURE_OPENAI_DEPLOYMENT"))
    if "uuid" not in session:
        return jsonify({"error": "Not logged in"}), 401

    uuid = session["uuid"]
    user_type = session.get("user_type", "personal")
    try:
        data = request.json
        query_text = data.get('query')

        user = User.query.filter_by(uuid=session['uuid']).first()
        if not user:
            return jsonify({"error": "Invalid user"}), 400

        vector_folder = os.path.join('vectors', user.uuid)
        if not os.path.exists(vector_folder):
            return jsonify({"error": "No vectors found"}), 400

        results = []
        for vec_file in os.listdir(vector_folder):
            if vec_file.endswith(".faiss"):
                vec_path = os.path.join(vector_folder, vec_file)
                try:
                    vectordb = load_vector_db(vec_path)
                    chunk_tuples = retrieve_chunks(vectordb, query_text)
                    results.extend(chunk_tuples)
                except Exception as e:
                    print(f"Error loading vector DB from {vec_path}: {e}")
                    continue

        results = sorted(results, key=lambda x: x[1])
        top_chunks = [doc.page_content for doc, score in results[:10]]
        context = "\n\n".join(top_chunks)

        messages = [
            {"role": "system", "content": "You are a helpful assistant that gives accurate answers based on document context."},
            {"role": "user", "content": f"""Use the following context to answer the question. If not found, say so.

### Context:
{context}

### Question:
{query_text}

### Answer:"""}
        ]

        response = openai_client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),  
            messages=messages,
            temperature=0.2,
            max_tokens=8192
        )

        answer = response.choices[0].message.content.strip()
        return jsonify({"answer": answer, "chunks": top_chunks})

    except Exception as e:
        print(f"❌ OpenAI query failed: {e}")
        return jsonify({"error": "Failed to generate response"}), 500


@app.route('/list-files', methods=['GET'])
def list_files():
    if 'uuid' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user = User.query.filter_by(uuid=session['uuid']).first()
    files = File.query.filter_by(user_id=user.id).all()
    return jsonify([{"id": f.id, "filename": f.filename} for f in files])


@app.route('/delete-file', methods=['POST'])
def delete_file():
    if 'uuid' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    file_id = data.get("file_id")
    user = User.query.filter_by(uuid=session['uuid']).first()
    file = File.query.filter_by(id=file_id, user_id=user.id).first()
    if not file:
        return jsonify({"error": "File not found"}), 404

    try:
        # 1. Delete file from Azure Blob Storage
        container_client.delete_blob(file.path)
        # print(f"[✓] Deleted blob: {file.path}")

        # 2. Delete vector index
        vector_folder = os.path.join('vectors', user.uuid)
        vector_file = os.path.join(vector_folder, f"{os.path.basename(file.path)}.faiss")

        if os.path.exists(vector_file):
            shutil.rmtree(vector_file)
            # print(f"[✓] Deleted vector folder: {vector_file}")

        # 3. Clean from DB
        db.session.delete(file)
        db.session.commit()

    except Exception as e:
        print(f"[!] Delete error: {e}")
        return jsonify({"error": "Delete operation failed"}), 500

    return jsonify({"message": "File and vector index deleted"})

# --- Serve React Static Build (Optional) ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(f"frontend/build/{path}"):
        return send_from_directory('frontend/build', path)
    else:
        return send_from_directory('frontend/build', 'index.html')
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

@app.route('/keep-alive')
def keep_alive():
    try:
        db.session.execute(text("SELECT 1"))
        return "✅ DB alive", 200
    except Exception as e:
        return f"❌ DB error: {str(e)}", 500

@app.route("/view-file/<int:file_id>")
def view_file(file_id):
    if "uuid" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user = User.query.filter_by(uuid=session["uuid"]).first()
    file = File.query.filter_by(id=file_id, user_id=user.id).first()
    if not file:
        return jsonify({"error": "File not found"}), 404

    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=AZURE_CONTAINER_NAME,
        blob_name=file.path,
        account_key=os.getenv("AZURE_STORAGE_ACCOUNT_KEY"),
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(minutes=15)
    )
    blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{file.path}?{sas_token}"
    return jsonify({"url": blob_url})

# --- Run ---
if __name__ == "__main__":
    app.run(debug=True)
