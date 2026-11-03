# Iniciar: desde la raíz del proyecto ejecutar
# python -m uvicorn backend.main:app --reload

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from pwdlib import PasswordHash
from starlette.middleware.sessions import SessionMiddleware

from backend.database.connection import obtener_conexion
from backend.dominio import (
    ErrorDeDominio,
    Usuario,
    validar_contrasena,
    validar_fecha_nacimiento,
)
from backend.repositorios import RepositorioCitas
from backend.servicios import ServicioCitas

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    raise RuntimeError("Define SESSION_SECRET en el archivo .env antes de iniciar la aplicación.")
ES_PRODUCCION = os.getenv("ENTORNO", "desarrollo").lower() == "produccion"

ROLES_CITAS = ["admin", "paciente", "medico"]

app = FastAPI(title="Sistema de Gestión de Citas Médicas", version="1.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=ES_PRODUCCION,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "backend" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "backend" / "templates")
password_hash = PasswordHash.recommended()


# --- Sesión y respuestas ---

def sesion_actual(request: Request) -> dict | None:
    # Se guarda como dict porque las plantillas acceden a usuario.rol y usuario.nombre.
    return request.session.get("usuario")


def usuario_actual(request: Request) -> Usuario | None:
    datos = sesion_actual(request)
    return Usuario.desde_sesion(datos) if datos else None


def pagina(request: Request, nombre: str, estado: int = 200, **context):
    return templates.TemplateResponse(
        request=request,
        name=nombre,
        context={"request": request, "usuario": sesion_actual(request), **context},
        status_code=estado,
    )


def responder_error(request: Request, error: ErrorDeDominio):
    return pagina(request, "mensaje.html", estado=error.estado,
                  titulo=error.titulo, mensaje=str(error))


def redirigir(ruta="/dashboard"):
    return RedirectResponse(ruta, status_code=303)


def exigir_usuario(request: Request, roles=None):
    datos = sesion_actual(request)
    if not datos:
        return redirigir("/login")
    if roles and datos["rol"] not in roles:
        return pagina(request, "mensaje.html", estado=403, titulo="Acceso denegado",
                      mensaje="No tienes permiso para acceder a esta sección.")
    return None


# --- Autenticación ---

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    if sesion_actual(request):
        return redirigir("/dashboard")
    return redirigir("/login")


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return pagina(request, "login.html", error=None)


@app.post("/login")
def login(request: Request, correo: str = Form(...), contrasena: str = Form(...)):
    admin_email = os.getenv("ADMIN_EMAIL", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    # compare_digest sobre bytes: con str lanza TypeError si el texto contiene caracteres no ASCII.
    if admin_email and admin_password \
            and secrets.compare_digest(correo.lower().encode(), admin_email.lower().encode()) \
            and secrets.compare_digest(contrasena.encode(), admin_password.encode()):
        request.session["usuario"] = {"id": 0, "nombre": "Administrador", "correo": correo, "rol": "admin"}
        return redirigir()

    with obtener_conexion() as conexion, conexion.cursor() as cur:
        for tabla, columna_id, rol in (
            ("paciente", "id_paciente", "paciente"),
            ("medico", "id_medico", "medico"),
        ):
            cur.execute(
                f"SELECT {columna_id} AS id, nombre, correo, contrasena "
                f"FROM {tabla} WHERE lower(correo) = lower(%s)",
                (correo,),
            )
            fila = cur.fetchone()
            if fila:
                try:
                    valida = password_hash.verify(contrasena, fila["contrasena"])
                except Exception:
                    valida = False
                if valida:
                    request.session["usuario"] = {
                        "id": fila["id"], "nombre": fila["nombre"],
                        "correo": fila["correo"], "rol": rol,
                    }
                    return redirigir()
    return pagina(request, "login.html", error="Correo o contraseña incorrectos.")


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return redirigir("/login")


@app.get("/registro", response_class=HTMLResponse)
def registro_form(request: Request):
    return pagina(request, "registro.html", error=None)


@app.post("/registro")
def registrar_paciente(
    request: Request,
    nombre: str = Form(...),
    fecha_nacimiento: str = Form(...),
    correo: str = Form(...),
    telefono: str = Form(""),
    contrasena: str = Form(...),
):
    try:
        nacimiento = validar_fecha_nacimiento(fecha_nacimiento)
        validar_contrasena(contrasena)
    except ErrorDeDominio as error:
        return pagina(request, "registro.html", error=str(error))

    try:
        with obtener_conexion() as conexion, conexion.cursor() as cur:
            cur.execute(
                """INSERT INTO paciente (nombre, fecha_nacimiento, correo, contrasena, telefono)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id_paciente""",
                (nombre.strip(), nacimiento, correo.strip().lower(),
                 password_hash.hash(contrasena), telefono.strip() or None),
            )
            nuevo_id = cur.fetchone()["id_paciente"]
    except UniqueViolation:
        return pagina(request, "registro.html", error="Ese correo ya está registrado.")

    request.session["usuario"] = {
        "id": nuevo_id, "nombre": nombre.strip(),
        "correo": correo.strip().lower(), "rol": "paciente",
    }
    return redirigir()


# --- Panel y catálogos ---

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    bloqueo = exigir_usuario(request)
    if bloqueo:
        return bloqueo
    datos = sesion_actual(request)
    with obtener_conexion() as conexion, conexion.cursor() as cur:
        if datos["rol"] == "paciente":
            cur.execute("SELECT COUNT(*) AS total FROM cita WHERE id_paciente = %s", (datos["id"],))
        elif datos["rol"] == "medico":
            cur.execute("SELECT COUNT(*) AS total FROM cita WHERE id_medico = %s", (datos["id"],))
        else:
            cur.execute("SELECT COUNT(*) AS total FROM cita")
        total = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM paciente")
        pacientes = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM medico")
        medicos = cur.fetchone()["total"]
    return pagina(request, "dashboard.html", total=total, pacientes=pacientes, medicos=medicos)


@app.get("/pacientes", response_class=HTMLResponse)
def pacientes(request: Request):
    bloqueo = exigir_usuario(request, ["admin"])
    if bloqueo:
        return bloqueo
    with obtener_conexion() as conexion, conexion.cursor() as cur:
        cur.execute("""SELECT id_paciente, nombre, fecha_nacimiento, correo, telefono
                       FROM paciente ORDER BY nombre""")
        filas = cur.fetchall()
    return pagina(request, "pacientes.html", pacientes=filas)


@app.post("/pacientes/{id_paciente}/eliminar")
def eliminar_paciente(request: Request, id_paciente: int):
    bloqueo = exigir_usuario(request, ["admin"])
    if bloqueo:
        return bloqueo
    try:
        with obtener_conexion() as conexion, conexion.cursor() as cur:
            cur.execute("DELETE FROM paciente WHERE id_paciente = %s", (id_paciente,))
    except ForeignKeyViolation:
        return pagina(request, "mensaje.html", titulo="No se puede eliminar",
                      mensaje="Este paciente tiene citas asociadas. Conserva su registro para mantener el historial.")
    return redirigir("/pacientes")


@app.get("/medicos", response_class=HTMLResponse)
def medicos(request: Request):
    bloqueo = exigir_usuario(request, ROLES_CITAS)
    if bloqueo:
        return bloqueo
    with obtener_conexion() as conexion, conexion.cursor() as cur:
        cur.execute("""SELECT m.id_medico, m.nombre, m.cedula, m.consultorio,
                              m.correo, e.nombre AS especialidad
                       FROM medico m JOIN especialidad e USING (id_especialidad)
                       ORDER BY m.nombre""")
        filas = cur.fetchall()
        cur.execute("SELECT id_especialidad, nombre FROM especialidad ORDER BY nombre")
        especialidades = cur.fetchall()
    return pagina(request, "medicos.html", medicos=filas, especialidades=especialidades)


@app.post("/medicos")
def crear_medico(
    request: Request,
    nombre: str = Form(...),
    cedula: str = Form(...),
    consultorio: str = Form(...),
    correo: str = Form(...),
    contrasena: str = Form(...),
    id_especialidad: int = Form(...),
):
    bloqueo = exigir_usuario(request, ["admin"])
    if bloqueo:
        return bloqueo
    try:
        validar_contrasena(contrasena)
    except ErrorDeDominio as error:
        return responder_error(request, error)
    try:
        with obtener_conexion() as conexion, conexion.cursor() as cur:
            cur.execute(
                """INSERT INTO medico (nombre, cedula, consultorio, correo, contrasena, id_especialidad)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (nombre.strip(), cedula.strip(), consultorio.strip(), correo.strip().lower(),
                 password_hash.hash(contrasena), id_especialidad),
            )
    except UniqueViolation:
        return pagina(request, "mensaje.html", titulo="Datos duplicados",
                      mensaje="La cédula o el correo ya están registrados.")
    except ForeignKeyViolation:
        return pagina(request, "mensaje.html", titulo="Datos inválidos",
                      mensaje="La especialidad seleccionada no existe.")
    return redirigir("/medicos")


@app.post("/especialidades")
def crear_especialidad(request: Request, nombre: str = Form(...)):
    bloqueo = exigir_usuario(request, ["admin"])
    if bloqueo:
        return bloqueo
    try:
        with obtener_conexion() as conexion, conexion.cursor() as cur:
            cur.execute("INSERT INTO especialidad (nombre) VALUES (%s)", (nombre.strip(),))
    except UniqueViolation:
        return pagina(request, "mensaje.html", titulo="Especialidad existente",
                      mensaje="Esa especialidad ya está registrada.")
    return redirigir("/medicos")


# --- Citas ---

@app.get("/citas", response_class=HTMLResponse)
def citas(request: Request):
    bloqueo = exigir_usuario(request, ROLES_CITAS)
    if bloqueo:
        return bloqueo
    datos = sesion_actual(request)
    with obtener_conexion() as conexion, conexion.cursor() as cur:
        cur.execute("SELECT id_medico, nombre FROM medico ORDER BY nombre")
        medicos_lista = cur.fetchall()
        base = """SELECT c.id_cita, c.fecha_hora, c.motivo, ec.nombre AS estado,
                         p.nombre AS paciente, m.nombre AS medico
                  FROM cita c JOIN paciente p USING (id_paciente)
                  JOIN medico m USING (id_medico)
                  JOIN estado_cita ec USING (id_estado)"""
        if datos["rol"] == "paciente":
            cur.execute(base + " WHERE c.id_paciente = %s ORDER BY c.fecha_hora DESC", (datos["id"],))
        elif datos["rol"] == "medico":
            cur.execute(base + " WHERE c.id_medico = %s ORDER BY c.fecha_hora DESC", (datos["id"],))
        else:
            cur.execute(base + " ORDER BY c.fecha_hora DESC")
        filas = cur.fetchall()
        pacientes_lista = []
        if datos["rol"] == "admin":
            cur.execute("SELECT id_paciente, nombre FROM paciente ORDER BY nombre")
            pacientes_lista = cur.fetchall()
    return pagina(request, "citas.html", citas=filas, medicos=medicos_lista,
                  pacientes=pacientes_lista, rol=datos["rol"])


@app.post("/citas")
def crear_cita(
    request: Request,
    id_medico: int = Form(...),
    fecha_hora: str = Form(...),
    motivo: str = Form(...),
    id_paciente: int = Form(0),
):
    bloqueo = exigir_usuario(request, ["admin", "paciente"])
    if bloqueo:
        return bloqueo
    try:
        with obtener_conexion() as conexion, conexion.cursor() as cur:
            ServicioCitas(RepositorioCitas(cur)).agendar(
                usuario_actual(request), id_paciente, id_medico, fecha_hora, motivo)
    except ErrorDeDominio as error:
        return responder_error(request, error)
    return redirigir("/citas")


@app.post("/citas/{id_cita}/cancelar")
def cancelar_cita(request: Request, id_cita: int):
    bloqueo = exigir_usuario(request, ROLES_CITAS)
    if bloqueo:
        return bloqueo
    try:
        with obtener_conexion() as conexion, conexion.cursor() as cur:
            ServicioCitas(RepositorioCitas(cur)).cancelar(usuario_actual(request), id_cita)
    except ErrorDeDominio as error:
        return responder_error(request, error)
    return redirigir("/citas")


# --- Reportes ---

@app.get("/reportes", response_class=HTMLResponse)
def reportes(request: Request):
    bloqueo = exigir_usuario(request, ["admin"])
    if bloqueo:
        return bloqueo
    with obtener_conexion() as conexion, conexion.cursor() as cur:
        cur.execute("""SELECT ec.nombre AS estado, COUNT(c.id_cita) AS total
                       FROM estado_cita ec LEFT JOIN cita c USING (id_estado)
                       GROUP BY ec.nombre ORDER BY ec.nombre""")
        por_estado = cur.fetchall()
        cur.execute("""SELECT m.nombre AS medico, COUNT(c.id_cita) AS total
                       FROM medico m LEFT JOIN cita c USING (id_medico)
                       GROUP BY m.nombre ORDER BY total DESC, m.nombre""")
        por_medico = cur.fetchall()
    return pagina(request, "reportes.html", por_estado=por_estado, por_medico=por_medico)