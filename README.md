# SGCM - versión inicial funcional

## 1. Preparación
1. Copia esta carpeta dentro de tu proyecto o usa sus archivos para completar tu estructura actual.
2. Conserva tu base de datos PostgreSQL existente y el script SQL original.
3. Copia `.env.example` como `.env`.
4. En `.env`, usa el nombre real de tu base de datos (en la prueba actual respondió `SGCM`) y tu contraseña local.
5. Cambia `SESSION_SECRET`, `ADMIN_EMAIL` y `ADMIN_PASSWORD`. No subas `.env` a GitHub.

## 2. Instalar dependencias
Con el entorno virtual activado, desde la carpeta raíz:

```powershell
python -m pip install -r requirements.txt
```

## 3. Ejecutar
```powershell
python -m uvicorn backend.main:app --reload
```
Abre `http://127.0.0.1:8000`.

## 4. Primer acceso
El administrador se configura con `ADMIN_EMAIL` y `ADMIN_PASSWORD` en `.env`.
Los pacientes se registran desde la pantalla de inicio. El administrador puede registrar médicos y especialidades.

## Alcance y pendientes importantes
Esta es una base de MVP para acelerar el desarrollo, no una versión lista para producción.
- El registro de notificación crea un registro pendiente en la tabla `notificacion`; todavía no envía correos, SMS ni WhatsApp.
- La agenda impide reservar la misma fecha/hora para un médico gracias a la restricción única de PostgreSQL, pero todavía no administra turnos semanales ni bloqueos de horario.
- La reprogramación, edición completa de pacientes/médicos, recuperación de contraseña, protección CSRF, auditoría y pruebas automatizadas deben completarse antes de una entrega final o despliegue.
- Los registros de pacientes con contraseñas en texto plano preexistentes no podrán iniciar sesión con este módulo: las contraseñas nuevas se almacenan con hash Argon2.
- No almacenes datos médicos reales en esta versión de desarrollo.
