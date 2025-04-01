from flask import Flask, render_template, request, redirect, send_file, url_for, session, make_response
import os
import datetime
import csv
import sqlite3
import psycopg2

app = Flask(__name__, static_folder="static")
app.secret_key = "supersecretkey" 


# 🔹 URL de la base de datos en Render
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:Bxz0y99K2FItHZGk8E8a8TCbmSke01kX@dpg-cvm5k8qdbo4c73c8kl2g-a.oregon-postgres.render.com/queries_929r")

# 🔹 Conectar a PostgreSQL
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

# 🔹 Crear tabla si no existe
cur.execute("""
    CREATE TABLE IF NOT EXISTS queries (
        id SERIAL PRIMARY KEY,
        query TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")
conn.commit()


# HEADERS 
@app.before_request
def log_headers():
    print("DEBUG: Headers de la solicitud")
    for header, value in request.headers.items():
        print(f"{header}: {value}")

#@app.before_request
#def block_if_no_security_header():
#    if "X-WAF-Token" not in request.headers:
#        return "Acceso denegado: Falta header X-WAF-Token", 403

@app.after_request
def add_headers(response):
    response.headers["X-Security-Test"] = "Passed"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# ✅ Función para agregar headers guardados en sesión
@app.after_request
def add_persistent_headers(response):
    if "custom_headers" in session:
        for key, value in session["custom_headers"].items():
            response.headers[key] = value
    return response

# ✅ Función para agregar un nuevo header a la sesión
def add_header_to_session(header_name, header_value):
    if "custom_headers" not in session:
        session["custom_headers"] = {}
    session["custom_headers"][header_name] = header_value

UPLOAD_FOLDER = "uploads"
DOWNLOAD_FOLDER = "downloads"
QUERY_FOLDER = "queries"
# ✅ Ensure Flask is always using the correct base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ✅ Define paths for folders
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
QUERY_FOLDER = os.path.join(BASE_DIR, "queries")
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "downloads")

# ✅ Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QUERY_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["QUERY_FOLDER"] = QUERY_FOLDER
app.config["DOWNLOAD_FOLDER"] = DOWNLOAD_FOLDER

# ✅ Define query CSV file path
QUERY_FILE = os.path.join(QUERY_FOLDER, "queries.csv")




# ✅ Ensure the CSV file exists with proper headers
if not os.path.exists(QUERY_FILE):
    with open(QUERY_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Query"])  # Column headers


# ✅ Login Route
@app.route("/", methods=["GET", "POST"])
def home():
    if "logged_in" in session and session["logged_in"]:
        return render_template("query.html")  # Redirect to query page if already logged in

    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        print(f"DEBUG: Received username={username}, password={password}")  # Debugging

        if username == "admin" and password == "password":
            session["logged_in"] = True
            #print("DEBUG: Login successful!")  # Debugging
            add_header_to_session("X-Login-Status", "Successful")  # ✅ Guardar header en sesión
            return redirect(url_for("query_page"))
        else:
            error = "Invalid username or password."
            #print("DEBUG: Login failed!")  # Debugging

    return render_template("index.html", error=error)  # Show error if login fails

# ✅ Query Page - Save Query Output
@app.route("/query", methods=["GET", "POST"])
def query_page():
    if not session.get("logged_in"):
        return render_template("403.html"), 403  # Restrict access

    with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT query, timestamp FROM queries ORDER BY timestamp DESC")
            return cur.fetchall()

    if request.method == "POST":
        query_text = request.form.get("query")
        if query_text:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"DEBUG: Saving query with timestamp {timestamp}")

             # ✅ Append query to `queries.csv`
            #with open(QUERY_FILE, "a", newline="") as f:
             #   writer = csv.writer(f)
              #  writer.writerow([timestamp, query_text])

            # ✅ Guardar query en la base de datos
            with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO queries (query) VALUES (%s)", (query_text,))
                    conn.commit()

            response = make_response(render_template("query.html", success="Query saved!"))
            add_header_to_session("X-Query-Submission", "Success") # ✅ Guardar en sesión
            return response

    return render_template("query.html")


# ✅ Upload Page (Requires Login)
@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    if not session.get("logged_in"):
        return render_template("403.html"), 403  # Restringir acceso

    if request.method == "POST":
        file = request.files.get("file")
        if file:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)  # ✅ Guardar archivo

            add_header_to_session("X-File-Upload", "Completed")  # ✅ Guardar en sesión
            return render_template("upload_success.html", filename=file.filename)

    return render_template("upload.html")


@app.route("/download")
def download_page():
    if not session.get("logged_in"):
        return render_template("403.html"), 403  # Restrict access

    # ✅ Ensure `downloads/` exists
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)

    # ✅ Get list of files in `downloads/`
    files = os.listdir(DOWNLOAD_FOLDER)

    # ✅ Debugging: Print files Flask sees
    #print(f"DEBUG: Files in downloads/: {files}")

    # ✅ Include `queries.csv`
    files.append("queries.csv")

    # ✅ Agregar opción de descarga para las queries en la base de datos
    #files.append("queries_db.csv")  # Nuevo nombre para diferenciarlo

    return render_template("download.html", files=files)


@app.route("/download/<filename>")
def download_file(filename):
    if not session.get("logged_in"):
        return render_template("403.html"), 403  # Restringir acceso

    # ✅ Si el usuario pide descargar las queries desde la base de datos
    if filename == "queries_db.csv":
        conn = sqlite3.connect("queries.db")
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, query FROM queries ORDER BY id DESC")
        queries = cursor.fetchall()
        conn.close()

        # ✅ Generar el contenido CSV en memoria
        csv_content = "Timestamp, Query\n"
        for query in queries:
            csv_content += f"{query[0]}, {query[1]}\n"

        response = make_response(csv_content)
        response.headers["Content-Disposition"] = "attachment; filename=queries_db.csv"
        response.headers["Content-Type"] = "text/csv"
        add_header_to_session("X-File-Download", "QueriesDB")  # ✅ Guardar en sesión
        return response

    file_path_downloads = os.path.join(DOWNLOAD_FOLDER, filename)
    file_path_queries = os.path.join(QUERY_FOLDER, filename)

    if os.path.exists(file_path_downloads):
        add_header_to_session("X-File-Download", "Success")  # ✅ Guardar en sesión
        return send_file(file_path_downloads, as_attachment=True)

    elif os.path.exists(file_path_queries):
        add_header_to_session("X-File-Download", "Success")  # ✅ Guardar en sesión
        return send_file(file_path_queries, as_attachment=True)
    
    add_header_to_session("X-File-Download", "NotFound")  # ✅ Guardar en sesión
    return "File not found", 404  # ✅ Return 404 if the file is missing

# ✅ Logout Route
@app.route("/logout")
def logout():
    session.clear()  # Clears the session
    return render_template("index.html")  # Show login page again

if __name__ == "__main__":
    app.run(debug=True)


