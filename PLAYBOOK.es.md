# The Bazaar · Manual de juego: probar, observar, mejorar (v1)

Sábado 3 oct 2026 · Equipo 9 · Versión en inglés: `PLAYBOOK.md` · Estrategia: `ONE_SHEET.es.md`

**Regla de cada ciclo: un cambio, un número que mirar, y la regla de decisión escrita ANTES de ver el resultado.**
Los tratos reales cuestan primas: nada de lo siguiente envía algo salvo que ponga LIVE, y LIVE necesita tu aprobación.
**Quién hace qué:** los scripts de dealers (`agent.py`, `bz/haggle.py`: compañera) llevan Abuela, El Chato y Pilar. `trader.py` lleva solo a los otros equipos. Los dos gastan la misma caja, así que hay que avisarse antes de una compra grande.

## 1. Lo que ya está construido (todo de solo lectura, con pruebas)

| Herramienta | Qué hace | Comando |
|---|---|---|
| `observe.py` | Registra nuestras puntuaciones cada vez que cambia una. Guarda la etiqueta del experimento y la puntuación de negociar del líder y de la mediana, para distinguir un cambio nuestro de una deriva de todo el campo. | `python3 observe.py` · `python3 observe.py tag E1` |
| `trader.py` | En cada tick juzga ofertas **solo de otros equipos**, solo por la estructura, con valores del juego (`bz/trade.py`). En sombra por defecto. `--live` acepta ganancias claras y contraoferta. `--live-boards` también acepta ofertas públicas (tope 40 P). Nunca dos ofertas abiertas por una carta, nunca por debajo de la mejor puja reciente. `touch logs/trader.pause` lo para. Cada trato: `TRADES.md`. | `python3 trader.py [--live [--live-boards]]` |
| `duels.py --ab` | Prueba dividida de la apertura en duelos: alterna dos aperturas según el id del duelo. Sin `--ab` se comporta como antes. | `python3 duels.py --ab 0.45,0.25` |
| `analyze_duels.py` | Lee la prueba dividida por brazo y por rol. | `python3 analyze_duels.py --since <primer id de duelo>` |
| Pruebas | 13 comprobaciones de tratos, las del analizador y las antiguas de duelos y precios. | `python3 tests/test_trade.py` y los demás archivos de `tests/` |

Los registros van a `logs/` (puntuación, trader, duelos). No se suben al repositorio.

## 2. Los ciclos

| N.º | Ciclo | Cadencia | Qué observar | Regla de decisión (fijada ahora) | Acción |
|---|---|---|---|---|---|
| L1 | **Puntuación** | siempre activo | `logs/score.jsonl`: nuestros números, la etiqueta, la puntuación del líder y de la mediana | Un experimento se lee solo si nuestro número se movió **y** los del líder y la mediana se movieron menos. Si no, repetirlo. | Poner la etiqueta antes de cada experimento: `observe.py tag E1` |
| L2 | **Ofertas para nosotros** | cada tick | `logs/trader.jsonl`: cuánto valía cada oferta para nosotros | Pasar a LIVE solo tras leer al menos 10 decisiones y estar de acuerdo con todos los ACCEPT. Aun así: una aceptación por tick, solo ganancias claras. | `trader.py` ahora, `--live` después con tu OK |
| L3 | **Apertura en duelos** | cada sesión de duelos | Tasa de tratos, resultado ÷ nuestro límite, rondas, por brazo y rol | Base de la práctica: 34 duelos, 53 % de tratos, resultado 0,185 del límite (comprador 0,137, vendedor 0,233), 3 rondas. Si el brazo 0,25 tiene una tasa de tratos no menor **y** un resultado a menos de 0,01 del brazo 0,45 o mejor → usar 0,25 en la siguiente sesión. Si es peor por más de 0,03 → mantener 0,45. Algo intermedio → dividir de nuevo. | `duels.py --ab 0.45,0.25`, luego `analyze_duels.py` |
| L4 | **Dealers** | por dealer | Registros de hilos, `ladder_points` | Por dealer: teoría → simulación gratis → tu aprobación → una conversación real → comparar con la teoría → actualizar el modelo. Parar con 3 buenos tratos por dealer. | Antes de cada sesión: `python3 -m bz.predict` (modelo por dealer; `agent.py` lo usa por defecto, `--model predict`). Un dealer nuevo: `family_of` elige su familia en cuanto se mueva en algún hilo; hasta entonces, el prior (mensajes antes de su final ≈ 6 × paciencia). |
| L5 | **Market Test** | cada 2 h | `bench_efficiency`, `bench_points`, `market` para nosotros y para el mejor equipo | Test 1: puesto gratis con 0,899 de eficiencia, 0,5 puntos del test, mercado 4,8; mejor equipo 8,01. Si tras el Test 3 el mejor equipo sigue al menos 3 por encima **y** alguien está libre → construir un broker. Si no, mantener el puesto gratis. | Solo lectura |
| L6 | **Palabras** | cuando L2 pueda enviar | Tasa de respuesta y precio logrado, por formulación | Dos formulaciones (directa frente a etiqueta + una pregunta calibrada), alternadas por mensaje, al menos 10 de cada una. Quedarse con la de mayor tasa de respuesta y luego mejor precio. Nunca probar con El Chato (estricto, memoria larga). | Primero tratos con equipos, luego duelos de precio y días |

## 3. Cronograma de hoy (aproximado: el juego va unos 30 minutos por detrás del plan)

| Cuándo | Hacer |
|---|---|
| Ahora | Arrancar `observe.py` y `trader.py` (sombra). Leer juntos las primeras decisiones. |
| ~11:50 | Market Test 2: apuntar los números (L5). |
| ~12:00 | **Duelos I:** arrancar `duels.py --ab 0.45,0.25` y etiquetar `E1`. Después ejecutar `analyze_duels.py` y aplicar la regla de L3. |
| Antes de ~18:30 | Duelos II añade el día de entrega (0–10). Revisar la lógica de días con una prueba en seco. Aplicar el resultado de L3. |
| Todo el día | Dealers nuevos: vigilar `GET /api/levels`. Aplicar L4 a cada uno. |
| Domingo | Ticks de 15 s. Duelos III y Final (10 % por ronda). Los dealers cierran hacia las 14:30. |

## 4. Lista de construcción (en este orden)

1. **Enviar contraofertas y pujas fijas** (con `expires_in_ticks` largo) por las cartas que necesitamos y por los repetidos. Es LIVE, así que necesita tu aprobación. También permite la prueba de palabras (L6).
2. **El Chato:** venderle un poco común repetido como primera conversación real (E3). El agente ahora vuelve a comprobar la propiedad antes de cada venta. Ejecutar antes la simulación (`tests/sim_chato.py`).
3. **Duelos II:** confirmar con una prueba en seco que la lógica de días lee bien `your_days_weight`.
4. **Broker:** solo si L5 lo indica.

## 5. Preguntas abiertas que deben responder los experimentos
- Cómo se reparten los 30 puntos de Negociar entre duelos, dealers y tratos con equipos (E1–E3).
- Si las puntuaciones son relativas: nuestra puntuación de mercado pasó de 4,8 a 5,23 mientras nuestros puntos del test seguían en 0,5 ⚠️.
- Cómo se cuenta el bono de página (hasta saberlo, las ofertas que completan una página van a una persona).
