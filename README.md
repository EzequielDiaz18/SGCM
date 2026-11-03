# SGCM - versión inicial funcional

## 1. Preparación
1. Descargar el repositorio
2. Guardar el archivo `.env.example` como `.env`.
3. En `.env`, usa el nombre real de tu base de datos (`SGCM`) y la contraseña local de postgres18. Postgres18 debe estar instalado y se debe crear la base de datos con el nombre SGCM, el script sql está en la carpeta database.
4. Cambiar `SESSION_SECRET`, `ADMIN_EMAIL` y `ADMIN_PASSWORD`. Esta es la cuenta del administrador donde se podrá gestionar el sistema. No subir `.env` a GitHub.

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
