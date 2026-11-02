import os
import secrets
from datetime import datetime
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pwdlib import PasswordHash
from psycopg.errors import UniqueViolation, ForeignKeyViolation
from backend.database.connection import obtener_conexion
from dotenv import load_dotenv

load_dotenv()

#iniciar la app: en main.py ctrl+ ñ y pegar en la terminal
# python -m uvicorn backend.main:app --reload
# 



app = FastAPI(title="Sistema de Gestión de Citas Médicas", version="1.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "CAMBIAR-ESTA-CLAVE-ANTES-DE-USAR"),
    same_site="lax",
    https_only=False
)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")
templates = Jinja2Templates(directory="backend/templates")
password_hash = PasswordHash.recommended()

def usuario_actual(request: Request):
    return request.session.get("usuario")

def pagina(request: Request, nombre: str, **context):
    return templates.TemplateResponse(
        request=request,
        name=nombre,
        context={"request": request, "usuario": usuario_actual(request), **context}
    )

def redirigir(ruta="/dashboard"):
    return RedirectResponse(ruta, status_code=303)

def exigir_usuario(request: Request, roles=None):
    user = usuario_actual(request)
    if not user:
        return redirigir("/login")
    if roles and user["rol"] not in roles:
        return pagina(request, "mensaje.html", titulo="Acceso denegado",
                      mensaje="No tienes permiso para acceder a esta sección.")
    return None

def registrar_notificacion(cursor, id_cita):
    # Registra la notificación pendiente. El envío real por correo/SMS se integra después.
    cursor.execute(
        """INSERT INTO notificacion (canal, estado_envio, id_cita)
           VALUES ('Correo', 'Pendiente', %s)""",
        (id_cita,)
    )

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    if usuario_actual(request):
        return redirigir("/dashboard")
    return redirigir("/login")

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return pagina(request, "login.html", error=None)

@app.post("/login")
def login(request: Request, correo: str = Form(...), contrasena: str = Form(...)):
    admin_email = os.getenv("ADMIN_EMAIL", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if admin_email and secrets.compare_digest(correo.lower(), admin_email.lower()) \
            and admin_password and secrets.compare_digest(contrasena, admin_password):
        request.session["usuario"] = {"id": 0, "nombre": "Administrador", "correo": correo, "rol": "admin"}
        return redirigir()

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            for tabla, columna_id, rol in (
                ("paciente", "id_paciente", "paciente"),
                ("medico", "id_medico", "medico")
            ):
                cur.execute(
                    f"SELECT {columna_id} AS id, nombre, correo, contrasena FROM {tabla} WHERE lower(correo)=lower(%s)",
                    (correo,)
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
                            "correo": fila["correo"], "rol": rol
                        }
                        return redirigir()
        return pagina(request, "login.html", error="Correo o contraseña incorrectos.")
    finally:
        conexion.close()

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
    contrasena: str = Form(...)
):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            cur.execute(
                """INSERT INTO paciente (nombre, fecha_nacimiento, correo, contrasena, telefono)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id_paciente""",
                (nombre.strip(), fecha_nacimiento, correo.strip().lower(),
                 password_hash.hash(contrasena), telefono.strip() or None)
            )
            nuevo_id = cur.fetchone()["id_paciente"]
        conexion.commit()
        request.session["usuario"] = {
            "id": nuevo_id, "nombre": nombre.strip(),
            "correo": correo.strip().lower(), "rol": "paciente"
        }
        return redirigir()
    except UniqueViolation:
        conexion.rollback()
        return pagina(request, "registro.html", error="Ese correo ya está registrado.")
    finally:
        conexion.close()

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    bloqueo = exigir_usuario(request)
    if bloqueo: return bloqueo
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            if usuario_actual(request)["rol"] == "paciente":
                cur.execute("SELECT COUNT(*) AS total FROM cita WHERE id_paciente=%s", (usuario_actual(request)["id"],))
            elif usuario_actual(request)["rol"] == "medico":
                cur.execute("SELECT COUNT(*) AS total FROM cita WHERE id_medico=%s", (usuario_actual(request)["id"],))
            else:
                cur.execute("SELECT COUNT(*) AS total FROM cita")
            total = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS total FROM paciente")
            pacientes = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS total FROM medico")
            medicos = cur.fetchone()["total"]
        return pagina(request, "dashboard.html", total=total, pacientes=pacientes, medicos=medicos)
    finally:
        conexion.close()

@app.get("/pacientes", response_class=HTMLResponse)
def pacientes(request: Request):
    bloqueo = exigir_usuario(request, ["admin"])
    if bloqueo: return bloqueo
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            cur.execute("""SELECT id_paciente, nombre, fecha_nacimiento, correo, telefono
                           FROM paciente ORDER BY nombre""")
            filas = cur.fetchall()
        return pagina(request, "pacientes.html", pacientes=filas)
    finally:
        conexion.close()

@app.post("/pacientes/{id_paciente}/eliminar")
def eliminar_paciente(request: Request, id_paciente: int):
    bloqueo = exigir_usuario(request, ["admin"])
    if bloqueo: return bloqueo
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            cur.execute("DELETE FROM paciente WHERE id_paciente=%s", (id_paciente,))
        conexion.commit()
        return redirigir("/pacientes")
    except ForeignKeyViolation:
        conexion.rollback()
        return pagina(request, "mensaje.html", titulo="No se puede eliminar",
                      mensaje="Este paciente tiene citas asociadas. Conserva su registro para mantener el historial.")
    finally:
        conexion.close()

@app.get("/medicos", response_class=HTMLResponse)
def medicos(request: Request):
    bloqueo = exigir_usuario(request, ["admin", "paciente", "medico"])
    if bloqueo: return bloqueo
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            cur.execute("""SELECT m.id_medico, m.nombre, m.cedula, m.consultorio,
                                  m.correo, e.nombre AS especialidad
                           FROM medico m JOIN especialidad e USING (id_especialidad)
                           ORDER BY m.nombre""")
            filas = cur.fetchall()
            cur.execute("SELECT id_especialidad, nombre FROM especialidad ORDER BY nombre")
            especialidades = cur.fetchall()
        return pagina(request, "medicos.html", medicos=filas, especialidades=especialidades)
    finally:
        conexion.close()

@app.post("/medicos")
def crear_medico(
    request: Request,
    nombre: str = Form(...),
    cedula: str = Form(...),
    consultorio: str = Form(...),
    correo: str = Form(...),
    contrasena: str = Form(...),
    id_especialidad: int = Form(...)
):
    bloqueo = exigir_usuario(request, ["admin"])
    if bloqueo: return bloqueo
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            cur.execute(
                """INSERT INTO medico (nombre, cedula, consultorio, correo, contrasena, id_especialidad)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (nombre.strip(), cedula.strip(), consultorio.strip(), correo.strip().lower(),
                 password_hash.hash(contrasena), id_especialidad)
            )
        conexion.commit()
        return redirigir("/medicos")
    except UniqueViolation:
        conexion.rollback()
        return pagina(request, "mensaje.html", titulo="Datos duplicados",
                      mensaje="La cédula o el correo ya están registrados.")
    finally:
        conexion.close()

@app.post("/especialidades")
def crear_especialidad(request: Request, nombre: str = Form(...)):
    bloqueo = exigir_usuario(request, ["admin"])
    if bloqueo: return bloqueo
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            cur.execute("INSERT INTO especialidad (nombre) VALUES (%s)", (nombre.strip(),))
        conexion.commit()
        return redirigir("/medicos")
    except UniqueViolation:
        conexion.rollback()
        return pagina(request, "mensaje.html", titulo="Especialidad existente",
                      mensaje="Esa especialidad ya está registrada.")
    finally:
        conexion.close()

@app.get("/citas", response_class=HTMLResponse)
def citas(request: Request):
    bloqueo = exigir_usuario(request, ["admin", "paciente", "medico"])
    if bloqueo: return bloqueo
    user = usuario_actual(request)
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            cur.execute("SELECT id_medico, nombre FROM medico ORDER BY nombre")
            medicos_lista = cur.fetchall()
            base = """SELECT c.id_cita, c.fecha_hora, c.motivo, ec.nombre AS estado,
                             p.nombre AS paciente, m.nombre AS medico
                      FROM cita c JOIN paciente p USING (id_paciente)
                      JOIN medico m USING (id_medico)
                      JOIN estado_cita ec USING (id_estado)"""
            if user["rol"] == "paciente":
                cur.execute(base + " WHERE c.id_paciente=%s ORDER BY c.fecha_hora DESC", (user["id"],))
            elif user["rol"] == "medico":
                cur.execute(base + " WHERE c.id_medico=%s ORDER BY c.fecha_hora DESC", (user["id"],))
            else:
                cur.execute(base + " ORDER BY c.fecha_hora DESC")
            filas = cur.fetchall()
            pacientes_lista = []
            if user["rol"] == "admin":
                cur.execute("SELECT id_paciente, nombre FROM paciente ORDER BY nombre")
                pacientes_lista = cur.fetchall()
        return pagina(request, "citas.html", citas=filas, medicos=medicos_lista,
                      pacientes=pacientes_lista, rol=user["rol"])
    finally:
        conexion.close()

@app.post("/citas")
def crear_cita(
    request: Request,
    id_medico: int = Form(...),
    fecha_hora: str = Form(...),
    motivo: str = Form(...),
    id_paciente: int = Form(0)
):
    bloqueo = exigir_usuario(request, ["admin", "paciente"])
    if bloqueo: return bloqueo
    user = usuario_actual(request)
    paciente_id = user["id"] if user["rol"] == "paciente" else id_paciente
    if not paciente_id:
        return pagina(request, "mensaje.html", titulo="Falta paciente",
                      mensaje="Selecciona un paciente para registrar la cita.")
    try:
        fecha = datetime.fromisoformat(fecha_hora)
        if fecha <= datetime.now():
            return pagina(request, "mensaje.html", titulo="Fecha inválida",
                          mensaje="La cita debe programarse en una fecha futura.")
    except ValueError:
        return pagina(request, "mensaje.html", titulo="Fecha inválida",
                      mensaje="Revisa la fecha y hora seleccionadas.")
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            cur.execute(
                """INSERT INTO cita (fecha_hora, motivo, id_paciente, id_medico, id_estado)
                   VALUES (%s, %s, %s, %s,
                     (SELECT id_estado FROM estado_cita WHERE nombre='Pendiente'))
                   RETURNING id_cita""",
                (fecha, motivo.strip(), paciente_id, id_medico)
            )
            id_cita = cur.fetchone()["id_cita"]
            registrar_notificacion(cur, id_cita)
        conexion.commit()
        return redirigir("/citas")
    except UniqueViolation:
        conexion.rollback()
        return pagina(request, "mensaje.html", titulo="Horario ocupado",
                      mensaje="Ese médico ya tiene una cita registrada en esa fecha y hora.")
    except ForeignKeyViolation:
        conexion.rollback()
        return pagina(request, "mensaje.html", titulo="Datos inválidos",
                      mensaje="El paciente o médico seleccionado no existe.")
    finally:
        conexion.close()

@app.post("/citas/{id_cita}/cancelar")
def cancelar_cita(request: Request, id_cita: int):
    bloqueo = exigir_usuario(request, ["admin", "paciente", "medico"])
    if bloqueo: return bloqueo
    user = usuario_actual(request)
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            cur.execute("SELECT id_paciente, id_medico FROM cita WHERE id_cita=%s", (id_cita,))
            cita = cur.fetchone()
            if not cita or (user["rol"] == "paciente" and cita["id_paciente"] != user["id"]) \
                    or (user["rol"] == "medico" and cita["id_medico"] != user["id"]):
                return pagina(request, "mensaje.html", titulo="Acceso denegado",
                              mensaje="No puedes modificar esta cita.")
            cur.execute("""UPDATE cita SET id_estado =
                           (SELECT id_estado FROM estado_cita WHERE nombre='Cancelada')
                           WHERE id_cita=%s""", (id_cita,))
            registrar_notificacion(cur, id_cita)
        conexion.commit()
        return redirigir("/citas")
    finally:
        conexion.close()

@app.get("/reportes", response_class=HTMLResponse)
def reportes(request: Request):
    bloqueo = exigir_usuario(request, ["admin"])
    if bloqueo: return bloqueo
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cur:
            cur.execute("""SELECT ec.nombre AS estado, COUNT(c.id_cita) AS total
                           FROM estado_cita ec LEFT JOIN cita c USING (id_estado)
                           GROUP BY ec.nombre ORDER BY ec.nombre""")
            por_estado = cur.fetchall()
            cur.execute("""SELECT m.nombre AS medico, COUNT(c.id_cita) AS total
                           FROM medico m LEFT JOIN cita c USING (id_medico)
                           GROUP BY m.nombre ORDER BY total DESC, m.nombre""")
            por_medico = cur.fetchall()
        return pagina(request, "reportes.html", por_estado=por_estado, por_medico=por_medico)
    finally:
        conexion.close()


