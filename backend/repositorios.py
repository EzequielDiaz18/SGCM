from datetime import datetime

from psycopg.errors import ForeignKeyViolation, UniqueViolation

from backend.dominio import Cita, ErrorDeDominio


class RepositorioCitas:
    def __init__(self, cursor):
        self._cur = cursor

    def obtener_para_actualizar(self, id_cita: int) -> Cita | None:
        # FOR UPDATE bloquea la fila: dos cancelaciones simultáneas no pueden pasar ambas la validación.
        self._cur.execute(
            """SELECT c.id_cita, c.id_paciente, c.id_medico, ec.nombre AS estado
               FROM cita c JOIN estado_cita ec USING (id_estado)
               WHERE c.id_cita = %s
               FOR UPDATE OF c""",
            (id_cita,),
        )
        fila = self._cur.fetchone()
        return Cita(**fila) if fila else None

    def cambiar_estado(self, id_cita: int, nombre_estado: str) -> None:
        # El estado se resuelve por nombre, no por un identificador fijo del catálogo.
        self._cur.execute(
            """UPDATE cita
               SET id_estado = (SELECT id_estado FROM estado_cita WHERE nombre = %s)
               WHERE id_cita = %s""",
            (nombre_estado, id_cita),
        )

    def insertar(self, fecha: datetime, motivo: str, id_paciente: int, id_medico: int) -> int:
        try:
            self._cur.execute(
                """INSERT INTO cita (fecha_hora, motivo, id_paciente, id_medico, id_estado)
                   VALUES (%s, %s, %s, %s,
                           (SELECT id_estado FROM estado_cita WHERE nombre = 'Pendiente'))
                   RETURNING id_cita""",
                (fecha, motivo, id_paciente, id_medico),
            )
        except UniqueViolation:
            raise ErrorDeDominio(
                "Ese médico ya tiene una cita registrada en esa fecha y hora.",
                titulo="Horario ocupado",
                estado=409,
            )
        except ForeignKeyViolation:
            raise ErrorDeDominio("El paciente o médico seleccionado no existe.", titulo="Datos inválidos")
        return self._cur.fetchone()["id_cita"]

    def registrar_notificacion(self, id_cita: int, canal: str = "Correo") -> None:
        self._cur.execute(
            """INSERT INTO notificacion (canal, estado_envio, id_cita)
               VALUES (%s, 'Pendiente', %s)""",
            (canal, id_cita),
        )