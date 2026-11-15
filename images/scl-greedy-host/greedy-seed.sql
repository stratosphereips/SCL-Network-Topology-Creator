-- Idempotent demo dataset for the Strato Cyber Lab Greedy Cars host.
-- Fixed IDs make the script safe to execute on every container start.
START TRANSACTION;

INSERT IGNORE INTO pais (id, eliminado, nombre) VALUES
  (1001, 0, 'Argentina');

INSERT IGNORE INTO provincia (id, eliminado, nombre, pais_id) VALUES
  (1001, 0, 'Mendoza', 1001);

INSERT IGNORE INTO departamento (id, eliminado, nombre, provincia_id) VALUES
  (1001, 0, 'Capital', 1001),
  (1002, 0, 'Godoy Cruz', 1001);

INSERT IGNORE INTO localidad (id, eliminado, codigo_postal, nombre, departamento_id) VALUES
  (1001, 0, 'M5500', 'Ciudad de Mendoza', 1001),
  (1002, 0, 'M5501', 'Godoy Cruz', 1002);

INSERT IGNORE INTO nacionalidad (id, eliminado, nombre) VALUES
  ('10000000-0000-4000-8000-000000000001', 0, 'Argentina');

INSERT IGNORE INTO empresa (id, eliminado, nombre) VALUES
  ('20000000-0000-4000-8000-000000000001', 0, 'Greedy Cars Mendoza');

INSERT IGNORE INTO direccion
  (id, eliminado, barrio, calle, numeracion, observacion, piso_casa, puerta_manzana, localidad_id)
VALUES
  (1001, 0, 'Centro', 'Avenida San Martin', '1250', 'Casa central del laboratorio', NULL, NULL, 1001),
  (1002, 0, 'Bombal', 'Belgrano', '742', 'Domicilio de Ana Torres', NULL, NULL, 1001),
  (1003, 0, 'Centro', 'Rivadavia', '315', 'Domicilio de Bruno Diaz', '2', 'B', 1002),
  (1004, 0, 'Centro', 'Patricias Mendocinas', '880', 'Domicilio de Carla Suarez', NULL, NULL, 1001),
  (1005, 0, 'Villa Hipodromo', 'Paso de los Andes', '2140', 'Domicilio de Diego Ramirez', NULL, NULL, 1002),
  (1006, 0, 'Bombal', 'Colon', '640', 'Domicilio de Sofia Castro', '4', 'A', 1001),
  (1007, 0, 'Centro', 'Necochea', '455', 'Domicilio temporal de Martin Herrera', NULL, NULL, 1001),
  (1008, 0, 'Trapiche', 'Los Alamos', '1780', 'Domicilio de Valentina Romero', NULL, NULL, 1002),
  (1009, 0, 'Centro', 'Mitre', '925', 'Domicilio de Jorge Nunez', '6', 'C', 1001);

INSERT IGNORE INTO contacto
  (id, eliminado, observacion, tipo_contacto)
VALUES
  ('30000000-0000-4000-8000-000000000001', 0, 'Correo comercial', 'EMPRESA'),
  ('30000000-0000-4000-8000-000000000002', 0, 'Telefono comercial', 'EMPRESA'),
  ('30000000-0000-4000-8000-000000000003', 0, 'Correo personal', 'PERSONAL'),
  ('30000000-0000-4000-8000-000000000004', 0, 'Correo personal', 'PERSONAL'),
  ('30000000-0000-4000-8000-000000000005', 0, 'Correo laboral de gerencia', 'LABORAL'),
  ('30000000-0000-4000-8000-000000000006', 0, 'Correo laboral de administracion', 'LABORAL'),
  ('30000000-0000-4000-8000-000000000007', 0, 'Correo laboral de administracion', 'LABORAL'),
  ('30000000-0000-4000-8000-000000000008', 0, 'Correo personal', 'PERSONAL'),
  ('30000000-0000-4000-8000-000000000009', 0, 'Correo personal', 'PERSONAL'),
  ('30000000-0000-4000-8000-000000000010', 0, 'Correo personal', 'PERSONAL');

INSERT IGNORE INTO contacto_correo_electronico (mail, id) VALUES
  ('ventas@greedy-cars.test', '30000000-0000-4000-8000-000000000001'),
  ('ana.torres@greedy-cars.test', '30000000-0000-4000-8000-000000000003'),
  ('bruno.diaz@greedy-cars.test', '30000000-0000-4000-8000-000000000004'),
  ('carla.suarez@greedy-cars.test', '30000000-0000-4000-8000-000000000005'),
  ('diego.ramirez@greedy-cars.test', '30000000-0000-4000-8000-000000000006'),
  ('sofia.castro@greedy-cars.test', '30000000-0000-4000-8000-000000000007'),
  ('martin.herrera@greedy-cars.test', '30000000-0000-4000-8000-000000000008'),
  ('valentina.romero@greedy-cars.test', '30000000-0000-4000-8000-000000000009'),
  ('jorge.nunez@greedy-cars.test', '30000000-0000-4000-8000-000000000010');

INSERT IGNORE INTO contacto_telefonico (telefono, tipo_telefono, id) VALUES
  ('+542615550100', 'FIJO', '30000000-0000-4000-8000-000000000002');

INSERT IGNORE INTO persona
  (tipo_persona, id, eliminado, apellido, fecha_nacimiento, nombre, numero_documento, tipo_documento)
VALUES
  ('CLIENTE', '40000000-0000-4000-8000-000000000001', 0, 'Torres', '1991-04-12', 'Ana', '30111222', 'DNI'),
  ('CLIENTE', '40000000-0000-4000-8000-000000000002', 0, 'Diaz', '1987-09-28', 'Bruno', '28999888', 'DNI'),
  ('EMPLEADO', '40000000-0000-4000-8000-000000000003', 0, 'Suarez', '1985-02-18', 'Carla', '27123456', 'DNI'),
  ('EMPLEADO', '40000000-0000-4000-8000-000000000004', 0, 'Ramirez', '1980-11-03', 'Diego', '25000111', 'DNI'),
  ('EMPLEADO', '40000000-0000-4000-8000-000000000005', 0, 'Castro', '1983-07-21', 'Sofia', '26000222', 'DNI'),
  ('CLIENTE', '40000000-0000-4000-8000-000000000006', 0, 'Herrera', '1993-05-09', 'Martin', '32000333', 'DNI'),
  ('CLIENTE', '40000000-0000-4000-8000-000000000007', 0, 'Romero', '1995-12-14', 'Valentina', '33000444', 'DNI'),
  ('CLIENTE', '40000000-0000-4000-8000-000000000008', 0, 'Nunez', '1989-08-30', 'Jorge', '34000555', 'DNI');

-- Demo client users reuse the bootstrap admin BCrypt hash. Their password is
-- therefore the documented lab password without storing another plaintext or
-- fixed hash in this seed file.
INSERT IGNORE INTO usuario
  (id, eliminado, clave, email, email_verified, external_id, is_external,
   nombre_usuario, provider, rol, persona_id)
SELECT
  '50000000-0000-4000-8000-000000000001', 0, clave,
  'ana.torres@greedy-cars.test', 1, NULL, 0,
  'demo.ana', 'local', 'CLIENTE',
  '40000000-0000-4000-8000-000000000001'
FROM usuario
WHERE nombre_usuario = 'admin'
LIMIT 1;

-- Fixed BCrypt hashes were generated and verified with the application's
-- BCryptPasswordEncoder. Plaintext credentials are documented for instructors.
INSERT IGNORE INTO usuario
  (id, eliminado, clave, email, email_verified, external_id, is_external,
   nombre_usuario, provider, rol, persona_id)
VALUES
  ('50000000-0000-4000-8000-000000000003', 0, '$2a$10$RSAK8i6OkE/J7.GDWYaLkunXM7y6mAgXMiURyFv7xkwrq7Q7h1LNe', 'carla.suarez@greedy-cars.test', b'1', NULL, b'0', 'carla.suarez', 'local', 'JEFE', NULL),
  ('50000000-0000-4000-8000-000000000004', 0, '$2a$10$as3GVS5w8A1I7HDnkhAlGu7jzfrhfW8NpxP8uV86HLguNFEKshm9i', 'diego.ramirez@greedy-cars.test', b'1', NULL, b'0', 'diego.ramirez', 'local', 'ADMINISTRATIVO', '40000000-0000-4000-8000-000000000004'),
  ('50000000-0000-4000-8000-000000000005', 0, '$2a$10$dIdkLXBTNPAkNZTmQKurU.EQu6B7FOetiISoqGeviUUaxuEZLDYIS', 'sofia.castro@greedy-cars.test', b'1', NULL, b'0', 'sofia.castro', 'local', 'ADMINISTRATIVO', '40000000-0000-4000-8000-000000000005'),
  ('50000000-0000-4000-8000-000000000006', 0, '$2a$10$C3ISGvq/TbYzqgteaigG1eQexqmvoi1qID4h.XLK45nGEE1XL3Kwu', 'martin.herrera@greedy-cars.test', b'1', NULL, b'0', 'martin.herrera', 'local', 'CLIENTE', '40000000-0000-4000-8000-000000000006'),
  ('50000000-0000-4000-8000-000000000007', 0, '$2a$10$.2OVwWVlCpfKoBNmmIjDtOsWctY6SqajAXOQUpekGNCrxviTEAO9K', 'valentina.romero@greedy-cars.test', b'1', NULL, b'0', 'valentina.romero', 'local', 'CLIENTE', '40000000-0000-4000-8000-000000000007'),
  ('50000000-0000-4000-8000-000000000008', 0, '$2a$10$nZXSOjVGt.MejwEYOq3hi.EFzU6pdcbXm5ks.tYeKY/sJuPlSLyTq', 'jorge.nunez@greedy-cars.test', b'1', NULL, b'0', 'jorge.nunez', 'local', 'CLIENTE', '40000000-0000-4000-8000-000000000008');

INSERT IGNORE INTO usuario
  (id, eliminado, clave, email, email_verified, external_id, is_external,
   nombre_usuario, provider, rol, persona_id)
SELECT
  '50000000-0000-4000-8000-000000000002', 0, clave,
  'bruno.diaz@greedy-cars.test', 1, NULL, 0,
  'demo.bruno', 'local', 'CLIENTE',
  '40000000-0000-4000-8000-000000000002'
FROM usuario
WHERE nombre_usuario = 'admin'
LIMIT 1;

INSERT IGNORE INTO clientes (direccion_estadia, recibir_promociones, id, usuario_id) VALUES
  ('Avenida Las Heras 550, Mendoza', b'1', '40000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001'),
  ('San Rafael 221, Mendoza', b'1', '40000000-0000-4000-8000-000000000002', '50000000-0000-4000-8000-000000000002'),
  ('Hotel Mendoza, Avenida Espana 1210', b'1', '40000000-0000-4000-8000-000000000006', '50000000-0000-4000-8000-000000000006'),
  ('Los Alamos 1780, Godoy Cruz', b'0', '40000000-0000-4000-8000-000000000007', '50000000-0000-4000-8000-000000000007'),
  ('Mitre 925, Ciudad de Mendoza', b'1', '40000000-0000-4000-8000-000000000008', '50000000-0000-4000-8000-000000000008');

INSERT IGNORE INTO empleados (tipo_empleado, id) VALUES
  ('JEFE', '40000000-0000-4000-8000-000000000003'),
  ('ADMINISTRATIVO', '40000000-0000-4000-8000-000000000004'),
  ('ADMINISTRATIVO', '40000000-0000-4000-8000-000000000005');

INSERT INTO cliente_nacionalidad (cliente_id, nacionalidad_id)
SELECT '40000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001'
WHERE NOT EXISTS (
  SELECT 1 FROM cliente_nacionalidad
  WHERE cliente_id = '40000000-0000-4000-8000-000000000001'
    AND nacionalidad_id = '10000000-0000-4000-8000-000000000001'
);

INSERT INTO cliente_nacionalidad (cliente_id, nacionalidad_id)
SELECT '40000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001'
WHERE NOT EXISTS (
  SELECT 1 FROM cliente_nacionalidad
  WHERE cliente_id = '40000000-0000-4000-8000-000000000002'
    AND nacionalidad_id = '10000000-0000-4000-8000-000000000001'
);

INSERT INTO empresa_direccion (empresa_id, direccion_id)
SELECT '20000000-0000-4000-8000-000000000001', 1001
WHERE NOT EXISTS (
  SELECT 1 FROM empresa_direccion
  WHERE empresa_id = '20000000-0000-4000-8000-000000000001' AND direccion_id = 1001
);

INSERT INTO empresa_contacto (empresa_id, contacto_id)
SELECT '20000000-0000-4000-8000-000000000001', '30000000-0000-4000-8000-000000000001'
WHERE NOT EXISTS (
  SELECT 1 FROM empresa_contacto
  WHERE empresa_id = '20000000-0000-4000-8000-000000000001'
    AND contacto_id = '30000000-0000-4000-8000-000000000001'
);

INSERT INTO empresa_contacto (empresa_id, contacto_id)
SELECT '20000000-0000-4000-8000-000000000001', '30000000-0000-4000-8000-000000000002'
WHERE NOT EXISTS (
  SELECT 1 FROM empresa_contacto
  WHERE empresa_id = '20000000-0000-4000-8000-000000000001'
    AND contacto_id = '30000000-0000-4000-8000-000000000002'
);

INSERT INTO persona_direccion (persona_id, direccion_id)
SELECT '40000000-0000-4000-8000-000000000001', 1002
WHERE NOT EXISTS (
  SELECT 1 FROM persona_direccion
  WHERE persona_id = '40000000-0000-4000-8000-000000000001' AND direccion_id = 1002
);

INSERT INTO persona_direccion (persona_id, direccion_id)
SELECT '40000000-0000-4000-8000-000000000002', 1003
WHERE NOT EXISTS (
  SELECT 1 FROM persona_direccion
  WHERE persona_id = '40000000-0000-4000-8000-000000000002' AND direccion_id = 1003
);

INSERT INTO persona_contacto (persona_id, contacto_id)
SELECT '40000000-0000-4000-8000-000000000001', '30000000-0000-4000-8000-000000000003'
WHERE NOT EXISTS (
  SELECT 1 FROM persona_contacto
  WHERE persona_id = '40000000-0000-4000-8000-000000000001'
    AND contacto_id = '30000000-0000-4000-8000-000000000003'
);

INSERT INTO persona_contacto (persona_id, contacto_id)
SELECT '40000000-0000-4000-8000-000000000002', '30000000-0000-4000-8000-000000000004'
WHERE NOT EXISTS (
  SELECT 1 FROM persona_contacto
  WHERE persona_id = '40000000-0000-4000-8000-000000000002'
    AND contacto_id = '30000000-0000-4000-8000-000000000004'
);

INSERT IGNORE INTO caracteristica_vehiculo
  (id, eliminado, anio, cantidad_asiento, cantidad_puerta, cantidad_total_vehiculo,
   cantidad_vehiculo_alquilado, marca, modelo)
VALUES
  ('60000000-0000-4000-8000-000000000001', 0, 2024, 5, 5, 2, 1, 'Toyota', 'Corolla Cross'),
  ('60000000-0000-4000-8000-000000000002', 0, 2023, 5, 5, 1, 0, 'Volkswagen', 'Taos'),
  ('60000000-0000-4000-8000-000000000003', 0, 2022, 4, 3, 1, 0, 'Renault', 'Kwid'),
  ('60000000-0000-4000-8000-000000000004', 0, 2023, 5, 5, 2, 0, 'Ford', 'EcoSport'),
  ('60000000-0000-4000-8000-000000000005', 0, 2024, 5, 5, 2, 1, 'Chevrolet', 'Onix'),
  ('60000000-0000-4000-8000-000000000006', 0, 2022, 5, 5, 1, 0, 'Peugeot', '208');

INSERT IGNORE INTO vehiculo
  (id, eliminado, estado_vehiculo, patente, caracteristica_vehiculo_id)
VALUES
  ('70000000-0000-4000-8000-000000000001', 0, 'ALQUILADO', 'AG123AA', '60000000-0000-4000-8000-000000000001'),
  ('70000000-0000-4000-8000-000000000002', 0, 'DISPONIBLE', 'AG456BB', '60000000-0000-4000-8000-000000000001'),
  ('70000000-0000-4000-8000-000000000003', 0, 'DISPONIBLE', 'AF789CC', '60000000-0000-4000-8000-000000000002'),
  ('70000000-0000-4000-8000-000000000004', 0, 'DISPONIBLE', 'AE321DD', '60000000-0000-4000-8000-000000000003'),
  ('70000000-0000-4000-8000-000000000005', 0, 'DISPONIBLE', 'AB456DE', '60000000-0000-4000-8000-000000000004'),
  ('70000000-0000-4000-8000-000000000006', 0, 'DISPONIBLE', 'AC789EF', '60000000-0000-4000-8000-000000000004'),
  ('70000000-0000-4000-8000-000000000007', 0, 'ALQUILADO', 'AD012FG', '60000000-0000-4000-8000-000000000005'),
  ('70000000-0000-4000-8000-000000000008', 0, 'DISPONIBLE', 'AE345GH', '60000000-0000-4000-8000-000000000005'),
  ('70000000-0000-4000-8000-000000000009', 0, 'DISPONIBLE', 'AF678HJ', '60000000-0000-4000-8000-000000000006');

INSERT IGNORE INTO costo_vehiculo
  (id, eliminado, costo, fecha_desde, fecha_hasta, caracteristica_vehiculo_id)
VALUES
  ('80000000-0000-4000-8000-000000000001', 0, 65000, CURDATE() - INTERVAL 30 DAY, CURDATE() + INTERVAL 335 DAY, '60000000-0000-4000-8000-000000000001'),
  ('80000000-0000-4000-8000-000000000002', 0, 72000, CURDATE() - INTERVAL 30 DAY, CURDATE() + INTERVAL 335 DAY, '60000000-0000-4000-8000-000000000002'),
  ('80000000-0000-4000-8000-000000000003', 0, 48000, CURDATE() - INTERVAL 30 DAY, CURDATE() + INTERVAL 335 DAY, '60000000-0000-4000-8000-000000000003'),
  ('80000000-0000-4000-8000-000000000004', 0, 59000, CURDATE() - INTERVAL 30 DAY, CURDATE() + INTERVAL 335 DAY, '60000000-0000-4000-8000-000000000004'),
  ('80000000-0000-4000-8000-000000000005', 0, 55000, CURDATE() - INTERVAL 30 DAY, CURDATE() + INTERVAL 335 DAY, '60000000-0000-4000-8000-000000000005'),
  ('80000000-0000-4000-8000-000000000006', 0, 52000, CURDATE() - INTERVAL 30 DAY, CURDATE() + INTERVAL 335 DAY, '60000000-0000-4000-8000-000000000006');

INSERT IGNORE INTO promocion
  (id, eliminado, aplica_a_todos, codigo_descuento, descripcion_descuento,
   fecha_fin_promocion, fecha_inicio_promocion, porcentaje_descuento)
VALUES
  ('90000000-0000-4000-8000-000000000001', 0, b'1', 'SCL20',
   'Descuento de bienvenida para el laboratorio', CURDATE() + INTERVAL 90 DAY,
   CURDATE() - INTERVAL 1 DAY, 20),
  ('90000000-0000-4000-8000-000000000002', 0, b'0', 'CLIENTE10',
   'Promocion destinada a clientes demo', CURDATE() + INTERVAL 60 DAY,
   CURDATE() - INTERVAL 1 DAY, 10);

INSERT IGNORE INTO promocion_cliente_destino (promocion_id, cliente_id) VALUES
  ('90000000-0000-4000-8000-000000000002', '40000000-0000-4000-8000-000000000001'),
  ('90000000-0000-4000-8000-000000000002', '40000000-0000-4000-8000-000000000002');

INSERT IGNORE INTO alquiler
  (id, eliminado, fecha_desde, fecha_hasta, cliente_id, vehiculo_id)
VALUES
  ('a0000000-0000-4000-8000-000000000001', 0, CURDATE() - INTERVAL 1 DAY, CURDATE() + INTERVAL 4 DAY,
   '40000000-0000-4000-8000-000000000001', '70000000-0000-4000-8000-000000000001'),
  ('a0000000-0000-4000-8000-000000000002', 0, CURDATE() - INTERVAL 20 DAY, CURDATE() - INTERVAL 17 DAY,
   '40000000-0000-4000-8000-000000000002', '70000000-0000-4000-8000-000000000003'),
  ('a0000000-0000-4000-8000-000000000003', 0, CURDATE() - INTERVAL 45 DAY, CURDATE() - INTERVAL 40 DAY,
   '40000000-0000-4000-8000-000000000006', '70000000-0000-4000-8000-000000000005'),
  ('a0000000-0000-4000-8000-000000000004', 0, CURDATE() - INTERVAL 12 DAY, CURDATE() - INTERVAL 9 DAY,
   '40000000-0000-4000-8000-000000000007', '70000000-0000-4000-8000-000000000009'),
  ('a0000000-0000-4000-8000-000000000005', 0, CURDATE() - INTERVAL 2 DAY, CURDATE() + INTERVAL 5 DAY,
   '40000000-0000-4000-8000-000000000008', '70000000-0000-4000-8000-000000000007');

INSERT IGNORE INTO factura
  (id, eliminado, estado, fecha_factura, numero_factura, total_pagado, cliente_id)
VALUES
  ('b0000000-0000-4000-8000-000000000001', 0, 'PAGADA', CURDATE() - INTERVAL 17 DAY,
   10001, 216000, '40000000-0000-4000-8000-000000000002'),
  ('b0000000-0000-4000-8000-000000000002', 0, 'SIN_DEFINIR', CURDATE(),
   10002, 0, '40000000-0000-4000-8000-000000000001'),
  ('b0000000-0000-4000-8000-000000000003', 0, 'PAGADA', CURDATE() - INTERVAL 40 DAY,
   10003, 295000, '40000000-0000-4000-8000-000000000006'),
  ('b0000000-0000-4000-8000-000000000004', 0, 'PAGADA', CURDATE() - INTERVAL 9 DAY,
   10004, 156000, '40000000-0000-4000-8000-000000000007'),
  ('b0000000-0000-4000-8000-000000000005', 0, 'SIN_DEFINIR', CURDATE(),
   10005, 0, '40000000-0000-4000-8000-000000000008');

INSERT IGNORE INTO detalle_factura
  (id, eliminado, cantidad, subtotal, alquiler_id, factura_id, promocion_id)
VALUES
  ('c0000000-0000-4000-8000-000000000001', 0, 3, 216000,
   'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', NULL),
  ('c0000000-0000-4000-8000-000000000002', 0, 5, 260000,
   'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000002',
   '90000000-0000-4000-8000-000000000001'),
  ('c0000000-0000-4000-8000-000000000003', 0, 5, 295000,
   'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000003', NULL),
  ('c0000000-0000-4000-8000-000000000004', 0, 3, 156000,
   'a0000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000004', NULL),
  ('c0000000-0000-4000-8000-000000000005', 0, 7, 308000,
   'a0000000-0000-4000-8000-000000000005', 'b0000000-0000-4000-8000-000000000005',
   '90000000-0000-4000-8000-000000000001');

INSERT IGNORE INTO forma_pago
  (id, eliminado, observacion, tipo_pago, factura_id)
VALUES
  ('d0000000-0000-4000-8000-000000000001', 0, 'Pago demo confirmado', 'TRANSFERENCIA',
   'b0000000-0000-4000-8000-000000000001'),
  ('d0000000-0000-4000-8000-000000000002', 0, 'Transferencia bancaria confirmada', 'TRANSFERENCIA',
   'b0000000-0000-4000-8000-000000000003'),
  ('d0000000-0000-4000-8000-000000000003', 0, 'Pago en mostrador', 'EFECTIVO',
   'b0000000-0000-4000-8000-000000000004');

COMMIT;
