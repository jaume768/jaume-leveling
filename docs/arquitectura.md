core/
  Profile         nivel, xp_total, rango(FK), fecha_inicio, altura, peso_objetivo
  Rank            nombre, orden, nivel_min, nivel_max, objetivo, criterio_ascenso, jefe
  Attribute       nombre, slug, valor(1-100), categoria
  AttributeLog    attribute(FK), fecha, valor, nota

missions/
  Mission         titulo, tipo(DIARIA|SEMANAL|MENSUAL|ANUAL|PRINCIPAL), descripcion,
                  definicion_terminada, tiempo_estimado_min, xp, attribute(FK),
                  motivo, evidencia_requerida, activa, orden, es_minima
  MissionLog      mission(FK), fecha, completada, evidencia_texto, evidencia_url,
                  xp_otorgado, notas

progression/
  XPRule          accion_slug, nombre, xp, tope_semanal, categoria, activa
  XPEvent         fecha, categoria(RESULTADO|SOPORTE|CONSUMO|PENALIZACION),
                  accion_slug, descripcion, xp_bruto, xp_neto, tope_aplicado,
                  multiplicador_racha, fuente(MISION|MANUAL|AUTO), objeto_relacionado
  Penalty         fecha, regla_slug, descripcion, xp, correccion_exigida, resuelta
  Reward          nivel_requerido | rango(FK), titulo, descripcion, desbloqueada, fecha

business/
  Client          nombre, sector, url, estado, mrr, fecha_alta, notas
  Deal            negocio, contacto, canal, sector, estado(CONTACTADO|CONVERSANDO|
                  PROPUESTA|GANADO|PERDIDO), valor_potencial, fecha_primer_contacto,
                  ultimo_toque, proximo_paso, fecha_proximo_paso, motivo_perdida
  Invoice         client(FK), concepto, importe, fecha_emision, vencimiento,
                  cobrada, fecha_cobro, notas
  Project         client(FK), nombre, precio, horas_estimadas, horas_reales,
                  estado(ACTIVO|ENTREGADO|CONGELADO), fecha_inicio, fecha_entrega

review/
  WeeklyReview    semana_iso, anio, m1..m10 (métricas del panel), xp_semana,
                  funciono, no_funciono, decision, objetivo_1, objetivo_2, objetivo_3
  HealthLog       fecha, peso, cintura, sueno_horas, energia(1-5), entreno, tipo_entreno

wisdom/
  Maxim           numero, libro, titulo, principio, texto, aplicacion, tags
  SystemPrompt    slug, nombre, contenido, activo, version
  AdviceSession   fecha, pregunta, contexto_json, respuesta, modelo, tokens_in,
                  tokens_out, coste_estimado