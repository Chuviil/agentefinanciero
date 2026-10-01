# ADR-0008: Circuit breaker para bucles y errores de tools

- **Estado:** Aceptado (implementado y probado). Con `CB_MAX_REPEATS = 2`, la **segunda** llamada idéntica
  ya abre el circuito (se cuenta la actual). El nodo `agent` registra las llamadas y fija `stop_reason`;
  `route_after_agent` solo lo lee.
- **Fecha:** 2026-10-01

## Contexto
En producción el agente repetía llamadas sin avanzar. Los límites de pasos y presupuesto acotan el daño,
pero no distinguen un bucle de una consulta legítimamente larga.

## Decisión
1. `CircuitBreaker` (dominio) registra una firma por llamada: `(tool_name, args normalizados)`.
2. Si una firma se repite `CB_MAX_REPEATS` veces (por defecto 2), el circuito se abre:
   `route_after_agent` envía a `finalize_partial` **sin ejecutar la tool**, con `stop_reason = loop_detected`.
3. Si hay `CB_MAX_CONSECUTIVE_ERRORS` errores de tool seguidos (por defecto 3), `guard` corta con
   `stop_reason = tool_errors`.
4. El estado del breaker vive en `AgentState` y dura un solo request.

## Alternativas consideradas
- **Detectar bucles por similitud semántica de los mensajes.** Más fino, pero requiere embeddings o
  llamadas extra al LLM, con su costo.
- **Solo depender de `MAX_STEPS`.** Corta tarde: puede gastar 8 pasos en el mismo error.

## Consecuencias
- (+) Corta bucles antes de pagar otra vuelta.
- (−) Una consulta que legítimamente necesite repetir la misma llamada (por ejemplo, tras un error
  transitorio) se cortará. Con mocks deterministas este caso no se presenta.

## Relacionados
ADR-0006, ADR-0009.
