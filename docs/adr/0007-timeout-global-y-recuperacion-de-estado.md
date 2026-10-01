# ADR-0007: Timeout global y recuperación de estado

- **Estado:** Aceptado (implementado y probado). El checkpointer registra explícitamente los tipos de
  dominio que guarda en el estado (`build_checkpointer`), porque LangGraph bloqueará en el futuro la
  deserialización de tipos no registrados.
- **Fecha:** 2026-10-01

## Contexto
El requisito es un timeout global de 45 s por consulta. Cada llamada a `search_financial_data` tarda 2 s,
así que 8 pasos con tools más la latencia del LLM se acercan al límite. Al cortar por tiempo hay que
devolver lo obtenido, no un error.

## Decisión
1. `LangGraphAnalysisEngine` envuelve `graph.ainvoke` con `asyncio.wait_for(..., TIMEOUT_GLOBAL_S = 45)`.
2. El grafo se compila con un checkpointer en memoria (`InMemorySaver`).
3. `thread_id = f"{session_id}:{request_id}"`, con `request_id` generado por request, para que los
   requests de una misma sesión no compartan mensajes ni pasos.
4. Ante `asyncio.TimeoutError` o `GraphRecursionError`, el engine recupera el último estado con
   `graph.get_state(config)` y construye una respuesta parcial (`stop_reason = timeout` o `max_steps_reached`).
5. El costo de las llamadas ya completadas antes del corte se registra en el presupuesto de la sesión.

## Alternativas consideradas
- **Timeout por llamada al LLM únicamente.** No limita la duración total de la consulta.
- **Sin checkpointer.** Más simple, pero el timeout terminaría en error sin datos.

## Consecuencias
- (+) Ninguna consulta supera 45 s y siempre devuelve lo obtenido.
- (−) Una llamada al LLM cancelada a mitad de camino puede haberse cobrado sin que se reciba su
  `usage_metadata`; ese costo no queda registrado. Se documenta como desvío conocido.
- (−) Los checkpoints en memoria deben liberarse al terminar cada request.

## Relacionados
ADR-0005, ADR-0006, ADR-0009.
