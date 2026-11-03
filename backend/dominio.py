from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar

ESTADOS_NO_CANCELABLES = frozenset({"Cancelada", "Atendida"})
LONGITUD_MINIMA_CONTRASENA = 8


class ErrorDeDominio(Exception):
    """Violación de una regla de negocio. El mensaje está pensado para el usuario final."""

    def __init__(self, mensaje: str, titulo: str = "Operación no permitida", estado: int = 400):
        super().__init__(mensaje)
        self.titulo = titulo
        self.estado = estado


class CitaNoEncontrada(ErrorDeDominio):
    def __init__(self):
        super().__init__("La cita no existe.", titulo="Cita no encontrada", estado=404)


@dataclass(frozen=True)
class Cita:
    """Entidad inmutable. Su única regla de comportamiento vive dentro de la propia entidad."""

    id_cita: int
    id_paciente: int
    id_medico: int
    estado: str

    def puede_cancelarse(self) -> bool:
        return self.estado not in ESTADOS_NO_CANCELABLES


@dataclass(frozen=True)
class Usuario:
    """Usuario autenticado. Cada rol concreta su política de acceso (polimorfismo)."""

    id: int
    nombre: str
    correo: str

    rol: ClassVar[str] = "base"

    def puede_gestionar(self, cita: Cita) -> bool:
        return False

    def id_paciente_para(self, id_formulario: int | None) -> int:
        raise ErrorDeDominio("Tu rol no puede agendar citas.", titulo="Acceso denegado", estado=403)

    def a_sesion(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "correo": self.correo, "rol": self.rol}

    @classmethod
    def desde_sesion(cls, datos: dict) -> "Usuario":
        clase = CLASES_USUARIO[datos["rol"]]
        return clase(id=datos["id"], nombre=datos["nombre"], correo=datos["correo"])


@dataclass(frozen=True)
class Administrador(Usuario):
    rol: ClassVar[str] = "admin"

    def puede_gestionar(self, cita: Cita) -> bool:
        return True

    def id_paciente_para(self, id_formulario: int | None) -> int:
        if not id_formulario:
            raise ErrorDeDominio("Selecciona un paciente para registrar la cita.", titulo="Falta paciente")
        return id_formulario


@dataclass(frozen=True)
class Paciente(Usuario):
    rol: ClassVar[str] = "paciente"

    def puede_gestionar(self, cita: Cita) -> bool:
        return cita.id_paciente == self.id

    def id_paciente_para(self, id_formulario: int | None) -> int:
        return self.id


@dataclass(frozen=True)
class Medico(Usuario):
    rol: ClassVar[str] = "medico"

    def puede_gestionar(self, cita: Cita) -> bool:
        return cita.id_medico == self.id


CLASES_USUARIO: dict[str, type[Usuario]] = {
    "admin": Administrador,
    "paciente": Paciente,
    "medico": Medico,
}


# --- Validaciones: funciones puras, sin efectos secundarios ---

def validar_fecha_nacimiento(texto: str, hoy: date | None = None) -> date:
    hoy = hoy or date.today()
    try:
        fecha = date.fromisoformat(texto)
    except ValueError:
        raise ErrorDeDominio("La fecha de nacimiento no es válida.", titulo="Fecha inválida")
    if fecha > hoy:
        raise ErrorDeDominio("La fecha de nacimiento no puede ser futura.", titulo="Fecha inválida")
    return fecha


def validar_contrasena(texto: str) -> str:
    if len(texto) < LONGITUD_MINIMA_CONTRASENA:
        raise ErrorDeDominio(
            f"La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres.",
            titulo="Contraseña insegura",
        )
    return texto


def validar_fecha_cita(texto: str, ahora: datetime | None = None) -> datetime:
    ahora = ahora or datetime.now()
    try:
        fecha = datetime.fromisoformat(texto)
    except ValueError:
        raise ErrorDeDominio("Revisa la fecha y hora seleccionadas.", titulo="Fecha inválida")
    if fecha <= ahora:
        raise ErrorDeDominio("La cita debe programarse en una fecha futura.", titulo="Fecha inválida")
    return fecha