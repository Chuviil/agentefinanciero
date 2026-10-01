# Agente de Análisis Financiero (FinOps-aware)

Agente de IA que asiste a analistas financieros en la evaluación de indicadores, ratios y tendencias.
Reemplaza una versión en producción que llegó a costar $200 por sesión sin registrar métricas.
Objetivo: **respuestas útiles con costo acotado, ejecución acotada y trazabilidad total.**

- Endpoint: `POST /api/v1/analysis/query`
- Grafo LangGraph: `guard` → `agent` ↔ `tool_caller`, con salidas `END` (completed) y `finalize_partial` (partial)
- Modelo: gpt-5-mini en Azure AI Foundry (ADR-0002). Herramientas mockeadas (ADR-0011).
- Arquitectura hexagonal: ver [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) y [`docs/adr/`](docs/adr/).

## Puesta en marcha

```bash
uv sync                       # instala dependencias (Python 3.13+)
cp .env.example .env          # y completar las variables
uv run uvicorn agentefinanciero.main:app --reload
uv run pytest -q
```

> Si el proyecto está dentro de OneDrive y `uv sync` falla con "Access is denied" al reinstalar el
> paquete, usar `uv sync --inexact --no-install-project` y `uv run --no-sync ...`.

La app falla al arrancar, con un mensaje que nombra las variables faltantes, si no están definidos los
precios (`PRICE_*`) o las variables de Azure (`AZURE_OPENAI_*`, `OPENAI_API_VERSION`).

## Ejemplo

```bash
curl -X POST http://localhost:8000/api/v1/analysis/query \
  -H "Content-Type: application/json" \
  -d '{"analyst_id":"A01","session_id":"S001","query":"¿Cuál fue el margen neto de 2024?","max_budget_usd":0.50}'
```

La respuesta es HTTP 200 siempre que el agente se haya ejecutado, aunque sea parcial
(`status: "partial"` con `warning` y `stop_reason`). HTTP 422 solo para requests inválidos.

## Límites

| Límite | Default | Variable |
|---|---|---|
| Pasos (llamadas al LLM) | 8 | `MAX_STEPS` |
| Tokens por request | 10000 | `MAX_TOKENS_BUDGET` |
| Presupuesto USD | del request | `max_budget_usd` |
| Timeout global | 45 s | `TIMEOUT_GLOBAL_S` |
| Rate limiter (por proceso) | sin límite si está vacío | `RATE_LIMIT_RPS` |
| Llamada repetida (circuit breaker) | 2 | `CB_MAX_REPEATS` |
| Errores de tool consecutivos | 3 | `CB_MAX_CONSECUTIVE_ERRORS` |
| Estimación de la siguiente llamada | 2000 tokens | `INITIAL_CALL_ESTIMATE_TOKENS` |

`RATE_LIMIT_RPS = cuota_RPM_del_despliegue / (60 × número_de_procesos)` (ADR-0005).
Los precios (`PRICE_INPUT_PER_MTOK`, `PRICE_CACHED_INPUT_PER_MTOK`, `PRICE_OUTPUT_PER_MTOK`) son de
referencia de OpenAI; hay que validarlos contra la tarifa de Azure del despliegue real (ADR-0002).

## Observabilidad

- Logs JSON a stdout: un evento `analysis_step` por paso y un `analysis_completed` al final.
- LangSmith: tracing nativo, con `analyst_id`, `session_id` y `request_id` como metadata y tags.
  Si `LANGSMITH_API_KEY` no está definida, el tracing se desactiva. Si LangSmith falla, el log JSON se mantiene.
- `elapsed_time` de cada paso es acumulado desde el inicio del request, medido al terminar la llamada
  al LLM de ese paso.

## Alcance del presupuesto

El presupuesto (USD y tokens) es **por request**. El acumulado por sesión de los ADR 0003/0004
(repositorio de sesión, HTTP 409, `overshoot_*`, `budget.scope`) está **diferido**.

## Estructura

```
src/agentefinanciero/
  domain/        reglas puras: Budget, ExecutionGuard, CircuitBreaker, TokenPricing, ratio
  application/   puertos (Protocol) y RunAnalysisService
  adapters/      FastAPI, LangGraph, datos mock y métricas (único lugar con frameworks)
  config/        settings y container (único que instancia adaptadores)
tests/
  unit/          dominio, aplicación, adaptadores simples y regla de dependencias
  integration/   grafo completo con chat model falso
  api/           endpoint con httpx
```

Ninguna prueba automatizada llama al LLM real (ADR-0012).
