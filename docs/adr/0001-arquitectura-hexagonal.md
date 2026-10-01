# ADR-0001: Arquitectura hexagonal con LangGraph como adaptador de salida

- **Estado:** Propuesto
- **Fecha:** 2026-10-01

## Contexto
La versión en producción mezclaba orquestación del agente, llamadas al LLM y lógica de control en un mismo
bloque. Eso hizo imposible probar los límites de costo de forma aislada, y el resultado fueron sesiones de
hasta $200 sin métricas. Las reglas que más importan al negocio (cuánto se puede gastar, cuándo cortar,
qué es un bucle) no deben depender del framework de orquestación.

## Decisión
Se adopta arquitectura hexagonal (puertos y adaptadores):

- **Dominio** (`app/domain`): `Budget`, `StepMetric`, `AnalysisResult`, `StopReason`, `ExecutionLimits`,
  `ExecutionGuard`, `CircuitBreaker`, `TokenPricing` y el cálculo puro de ratio. No importa frameworks.
- **Aplicación** (`app/application`): puerto de entrada `AnalyzeQueryUseCase`, puertos de salida
  `AnalysisEnginePort`, `FinancialDataPort`, `MetricsPort`, `SessionBudgetRepositoryPort`, y el servicio
  `RunAnalysisService`. Importa solo dominio. Puertos definidos como `typing.Protocol`.
- **Adaptadores** (`app/adapters`): FastAPI como entrada; `LangGraphAnalysisEngine`,
  `MockFinancialDataAdapter`, `InMemorySessionBudgetRepository` y `CompositeMetricsAdapter` como salida.
- **Composición** (`app/config/container.py`): único punto que instancia adaptadores.

LangGraph es un **adaptador de salida**. Sus nodos son delgados: leen el estado y delegan las decisiones en
el dominio.

## Nota de implementación
- `SessionBudgetRepositoryPort` e `InMemorySessionBudgetRepository` están **diferidos** (ver ADR-0003): hoy
  el presupuesto es por request.
- El paquete vive en `src/agentefinanciero/` en lugar de `app/`. La regla de dependencias se verifica con
  `tests/unit/test_architecture.py`.

## Alternativas consideradas
- **Arquitectura por capas con el grafo en el centro.** Más rápida de escribir, pero acopla las políticas
  de presupuesto a la API de LangGraph y obliga a probarlas a través del grafo.
- **Agente prearmado de LangChain con middlewares de límite.** Reduce código, pero los límites quedan
  definidos por la librería y no cubren presupuesto en USD por sesión.

## Consecuencias
- (+) Las políticas de costo se prueban con tests unitarios puros, rápidos y sin LLM.
- (+) Cambiar de motor de orquestación o de proveedor LLM no toca las reglas de negocio.
- (−) Más archivos y mapeos entre modelos Pydantic, estado del grafo y objetos de dominio.
- (−) Requiere disciplina en code review para que no se filtren imports de frameworks al dominio.

## Relacionados
ADR-0006, `docs/ARCHITECTURE.md`.
