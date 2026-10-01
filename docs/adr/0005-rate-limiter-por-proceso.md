# ADR-0005: Rate limiter por proceso

- **Estado:** Aceptado
- **Fecha:** 2026-10-01

## Contexto
El despliegue de gpt-5-mini en Azure AI Foundry tiene cuota de requests y tokens por minuto. Superarla
genera errores 429 y reintentos que alargan la ejecución y consumen el timeout global.

## Decisión
1. Se usa `InMemoryRateLimiter` de `langchain_core`, pasado al chat model mediante `rate_limiter`.
2. El alcance es **por proceso**: una instancia compartida por todos los requests del proceso.
3. Su valor se deriva de la cuota del despliegue:
   `RATE_LIMIT_RPS = cuota_RPM_del_despliegue / (60 × número_de_procesos)`.
   El valor final se configura por variable de entorno según la cuota asignada en Azure.
4. El cliente LLM usa `max_retries` bajo (por defecto 2); los reintentos cuentan dentro del timeout global.
5. El rate limiter solo aplica a llamadas al LLM. Las tools son mocks y no lo necesitan.

## Alternativas consideradas
- **Rate limiter global distribuido.** Exacto entre réplicas, pero requiere almacenamiento compartido,
  fuera de alcance.
- **Por analista.** Más justo entre usuarios, pero no protege la cuota del despliegue, que es el recurso
  compartido real.

## Consecuencias
- (+) Implementación nativa y sin infraestructura adicional.
- (−) Si cambia el número de procesos o réplicas, hay que recalcular `RATE_LIMIT_RPS`.
- (−) No limita tokens por minuto; un pico de consultas largas aún puede recibir 429 por TPM.
- Es coherente con ADR-0003: tanto el presupuesto de sesión como el rate limiter viven en el proceso.

## Relacionados
ADR-0003, ADR-0007.
