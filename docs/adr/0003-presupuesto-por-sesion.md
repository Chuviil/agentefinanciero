# ADR-0003: Alcance del presupuesto por sesión

- **Estado:** Aceptado
- **Fecha:** 2026-10-01

## Contexto
El incidente en producción fue de hasta $200 **por sesión**. Un tope solo por request no lo evita: muchas
consultas pequeñas dentro de la misma sesión pueden sumar el mismo gasto.

## Decisión
1. El presupuesto en USD y el presupuesto de tokens (`MAX_TOKENS_BUDGET = 10000`) se acumulan por
   `session_id`.
2. El primer request de una sesión fija el tope en USD con su `max_budget_usd`. En requests posteriores
   se aplica `min(tope_vigente, max_budget_usd)`: un request puede reducir el tope de la sesión, nunca
   ampliarlo.
3. Los límites de ejecución siguen siendo por request: `MAX_STEPS = 8`, timeout global de 45 s y estado
   del circuit breaker.
4. El gasto acumulado se guarda mediante `SessionBudgetRepositoryPort`, con un adaptador en memoria
   (`InMemorySessionBudgetRepository`) por proceso. Cada registro guarda: tope USD, USD gastado,
   tokens usados, último costo observado (ADR-0004) y fecha de último uso.
5. Las sesiones expiran tras `SESSION_TTL_MINUTES` sin actividad (por defecto 60).
6. Si llega un request para una sesión que ya tiene otro request en ejecución, se responde **HTTP 409**
   sin invocar al agente.
7. Si la sesión ya agotó su presupuesto al iniciar el request, se responde sin llamar al LLM con
   `status = partial` y `stop_reason = budget_exceeded`.

## Alternativas consideradas
- **Presupuesto por request.** Más simple, pero no resuelve el problema original.
- **Presupuesto por analista y día.** Útil a futuro, pero fuera del alcance definido.
- **Serializar requests concurrentes de la misma sesión con un lock.** Evita el 409, pero el request en
  espera consume su propio timeout sin hacer nada.

## Consecuencias
- (+) Ninguna sesión puede superar el tope fijado, sin importar cuántas consultas haga.
- (−) Al ser en memoria, un reinicio del proceso reinicia el gasto acumulado. Se acepta porque la
  persistencia en base de datos está fuera de alcance.
- (−) Con varias réplicas, cada proceso lleva su propia cuenta. Para que el tope sea real, los requests de
  una sesión deben llegar al mismo proceso (afinidad por `session_id` en el balanceador o una sola réplica).
- (−) 10 000 tokens por sesión es un presupuesto ajustado; con varias consultas en la misma sesión es
  probable alcanzar respuestas parciales.
- La respuesta de la API reporta el presupuesto con alcance de sesión (`budget.scope = "session"`).

## Relacionados
ADR-0002, ADR-0004, ADR-0005, ADR-0009.
