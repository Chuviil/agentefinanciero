# ADR-0002: Modelo LLM gpt-5-mini en Azure AI Foundry y tabla de precios

- **Estado:** Aceptado
- **Fecha:** 2026-10-01

## Contexto
Sin modelo ni precios definidos no es posible calcular `cumulative_cost`, comparar contra
`max_budget_usd` ni estimar el costo de la siguiente llamada. El banco consume modelos a través de
Azure AI Foundry.

## Decisión
1. Se usa **gpt-5-mini** desplegado en **Azure AI Foundry**, vía `AzureChatOpenAI` de `langchain-openai`.
2. Precios de referencia, tomados de la página oficial del modelo en OpenAI
   (https://developers.openai.com/api/docs/models/gpt-5-mini), consultada el 2026-10-01:

   | Tipo de token | USD por 1M tokens |
   |---|---|
   | Input | 0.25 |
   | Cached input | 0.025 |
   | Output (incluye tokens de razonamiento) | 2.00 |

3. Los precios viven en configuración (`PRICE_INPUT_PER_MTOK`, `PRICE_CACHED_INPUT_PER_MTOK`,
   `PRICE_OUTPUT_PER_MTOK`), nunca en código.
4. `TokenPricing` calcula:
   `costo = (input − cached) × P_input + cached × P_cached + output × P_output`, todo dividido entre 1e6,
   usando `usage_metadata` (`input_tokens`, `output_tokens`, `input_token_details.cache_read`).
5. Parámetros del modelo:
   - El límite de salida se envía como tokens de completado (`max_completion_tokens` en la API), porque
     gpt-5-mini es un modelo de razonamiento.
   - No se fija `temperature`; se usa el valor por defecto del modelo.
   - `reasoning_effort` configurable (`LLM_REASONING_EFFORT`), por defecto `low`.

Variables: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `OPENAI_API_VERSION`.

## Alternativas consideradas
- **gpt-5 completo.** Unas 5 veces más caro por token de entrada; innecesario para consultas acotadas
  con herramientas.
- **gpt-5-nano.** Más barato, pero con mayor riesgo de razonamiento insuficiente en consultas de varios
  periodos.

## Consecuencias
- (+) Costo calculable y auditable por paso.
- (−) **El precio de referencia es el de OpenAI, pero la factura llega de Azure.** Azure puede variar según
  el tipo de despliegue (Global, Data Zone, Regional). Se debe validar contra la página de precios de Azure
  OpenAI para el despliegue real y actualizar la configuración si difiere.
- (−) Los tokens de razonamiento se cobran como salida y no se ven en la respuesta. Con un presupuesto de
  10 000 tokens por sesión (ADR-0003), un `reasoning_effort` alto puede agotarlo en pocas llamadas; por eso
  el valor por defecto es `low`.
- (−) Si `max_completion_tokens` se agota durante el razonamiento, la respuesta puede llegar vacía
  (`finish_reason = length`). Ese caso se trata como corte parcial con `token_budget_exceeded`.
- Nota de magnitud: 10 000 tokens cuestan como máximo $0.02 (todo salida). Con `max_budget_usd = 0.50`,
  el límite de tokens se alcanza antes que el de USD. Se mantienen ambos: el de tokens protege la ejecución
  y el de USD es la garantía visible para negocio si cambian modelo o precios.

## Relacionados
ADR-0003, ADR-0004, ADR-0010.
