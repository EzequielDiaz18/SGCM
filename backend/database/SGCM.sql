-- ------------------------------------------------------------
-- ESPECIALIDAD
-- ------------------------------------------------------------
CREATE TABLE especialidad (
  id_especialidad INTEGER GENERATED ALWAYS AS IDENTITY,
  nombre          VARCHAR(100) NOT NULL,
  CONSTRAINT pk_especialidad PRIMARY KEY (id_especialidad),
  CONSTRAINT uq_especialidad_nombre UNIQUE (nombre)
);
 
-- ------------------------------------------------------------
-- MEDICO  
-- ------------------------------------------------------------
CREATE TABLE medico (
  id_medico       INTEGER GENERATED ALWAYS AS IDENTITY,
  nombre          VARCHAR(120) NOT NULL,
  cedula          VARCHAR(20)  NOT NULL,
  consultorio     VARCHAR(20)  NOT NULL,
  correo          VARCHAR(120) NOT NULL,
  contrasena      VARCHAR(255) NOT NULL,          
  id_especialidad INTEGER      NOT NULL,
  CONSTRAINT pk_medico PRIMARY KEY (id_medico),
  CONSTRAINT uq_medico_cedula UNIQUE (cedula),
  CONSTRAINT uq_medico_correo UNIQUE (correo),
  CONSTRAINT fk_medico_especialidad
    FOREIGN KEY (id_especialidad) REFERENCES especialidad (id_especialidad)
    ON UPDATE CASCADE ON DELETE RESTRICT
);
 
CREATE INDEX idx_medico_especialidad ON medico (id_especialidad);
 
-- ------------------------------------------------------------
-- PACIENTE
-- ------------------------------------------------------------
CREATE TABLE paciente (
  id_paciente      INTEGER GENERATED ALWAYS AS IDENTITY,
  nombre           VARCHAR(120) NOT NULL,
  fecha_nacimiento DATE         NOT NULL,
  correo           VARCHAR(120) NOT NULL,
  contrasena       VARCHAR(255) NOT NULL,        
  telefono         VARCHAR(15),
  CONSTRAINT pk_paciente PRIMARY KEY (id_paciente),
  CONSTRAINT uq_paciente_correo UNIQUE (correo),
  CONSTRAINT ck_paciente_fecha_nac CHECK (fecha_nacimiento <= CURRENT_DATE)
);
 
-- ------------------------------------------------------------
-- ESTADO_CITA  (catálogo)
-- ------------------------------------------------------------
CREATE TABLE estado_cita (
  id_estado INTEGER GENERATED ALWAYS AS IDENTITY,
  nombre    VARCHAR(30) NOT NULL,
  CONSTRAINT pk_estado_cita PRIMARY KEY (id_estado),
  CONSTRAINT uq_estado_nombre UNIQUE (nombre)
);
 
INSERT INTO estado_cita (nombre) VALUES
  ('Pendiente'), ('Confirmada'), ('Cancelada'), ('Reprogramada'), ('Atendida');
 
-- ------------------------------------------------------------
-- CITA
-- ------------------------------------------------------------
CREATE TABLE cita (
  id_cita     INTEGER GENERATED ALWAYS AS IDENTITY,
  fecha_hora  TIMESTAMP    NOT NULL,
  motivo      VARCHAR(255) NOT NULL,
  id_paciente INTEGER      NOT NULL,
  id_medico   INTEGER      NOT NULL,
  id_estado   INTEGER      NOT NULL DEFAULT 1,     -- 1 = Pendiente
  CONSTRAINT pk_cita PRIMARY KEY (id_cita),
  CONSTRAINT fk_cita_paciente
    FOREIGN KEY (id_paciente) REFERENCES paciente (id_paciente)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_cita_medico
    FOREIGN KEY (id_medico) REFERENCES medico (id_medico)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_cita_estado
    FOREIGN KEY (id_estado) REFERENCES estado_cita (id_estado)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  -- Un médico no puede tener dos citas a la misma hora
  CONSTRAINT uq_cita_medico_fecha UNIQUE (id_medico, fecha_hora)
);
 
CREATE INDEX idx_cita_paciente ON cita (id_paciente);
CREATE INDEX idx_cita_estado   ON cita (id_estado);
CREATE INDEX idx_cita_fecha    ON cita (fecha_hora);
 
-- ------------------------------------------------------------
-- NOTIFICACION  
-- ------------------------------------------------------------
CREATE TABLE notificacion (
  id_notificacion INTEGER GENERATED ALWAYS AS IDENTITY,
  canal           VARCHAR(20) NOT NULL,            -- Correo, SMS, WhatsApp
  estado_envio    VARCHAR(20) NOT NULL DEFAULT 'Pendiente',
  id_cita         INTEGER     NOT NULL,
  CONSTRAINT pk_notificacion PRIMARY KEY (id_notificacion),
  CONSTRAINT fk_notificacion_cita
    FOREIGN KEY (id_cita) REFERENCES cita (id_cita)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT ck_notificacion_canal
    CHECK (canal IN ('Correo', 'SMS', 'WhatsApp')),
  CONSTRAINT ck_notificacion_estado
    CHECK (estado_envio IN ('Pendiente', 'Enviado', 'Fallido'))
);
 
CREATE INDEX idx_notificacion_cita ON notificacion (id_cita);