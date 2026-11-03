from backend.dominio import CitaNoEncontrada, ErrorDeDominio, Usuario, validar_fecha_cita
from backend.repositorios import RepositorioCitas


class ServicioCitas:
    def __init__(self, repositorio: RepositorioCitas):
        self._repo = repositorio

    def agendar(self, usuario: Usuario, id_formulario: int | None,
                id_medico: int, texto_fecha: str, motivo: str) -> int:
        id_paciente = usuario.id_paciente_para(id_formulario)
        fecha = validar_fecha_cita(texto_fecha)
        id_cita = self._repo.insertar(fecha, motivo.strip(), id_paciente, id_medico)
        self._repo.registrar_notificacion(id_cita)
        return id_cita

    def cancelar(self, usuario: Usuario, id_cita: int) -> None:
        cita = self._repo.obtener_para_actualizar(id_cita)
        if cita is None:
            raise CitaNoEncontrada()
        if not usuario.puede_gestionar(cita):
            raise ErrorDeDominio("No puedes modificar esta cita.", titulo="Acceso denegado", estado=403)
        if not cita.puede_cancelarse():
            raise ErrorDeDominio(
                f"La cita ya está {cita.estado.lower()}.",
                titulo="No se puede cancelar",
            )
        self._repo.cambiar_estado(id_cita, "Cancelada")
        self._repo.registrar_notificacion(id_cita)