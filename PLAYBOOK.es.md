# The Bazaar · Manual de juego: probar, observar, mejorar (v2)

Sábado 3 oct 2026, 13:05 (tick 583) · Equipo 9 · Versión en inglés: `PLAYBOOK.md` · Estrategia y fuente de verdad: `ONE_SHEET.es.md`

**Regla de cada ciclo: un cambio, un número que mirar, y la regla de decisión escrita ANTES de ver el resultado.**
Los tratos reales cuestan primas: nada de lo siguiente envía algo salvo que ponga EN VIVO, y EN VIVO necesita visto
bueno: **duelos, de Thameur; cartas (dealers, tratos con equipos, quoter), de Maru**.
**Quién hace qué en nuestra clave compartida:** dealers = scripts de Maru (`agent.py`, `bz/haggle.py`, `bz/predict.py`).
Tratos con equipos = `trader.py` (sesión del trader). Duelos = `duels.py` bajo `duels_watch.py`, **solo en la
máquina de Thameur**. Todos gastan la misma caja, así que hay que avisarse antes de una compra grande o de publicar ofertas.

## 1. Lo que ya está construido

| Herramienta | Qué hace | Comando |
|---|---|---|
| `observe.py` | Guarda nuestra puntuación cada vez que cambia, con la etiqueta del experimento y la puntuación de negociación del líder y de la mediana | `python3 observe.py` · `python3 observe.py tag D2` |
| `trader.py` | Juzga las ofertas de **otros equipos solamente**, por su estructura, con los valores del juego. En sombra por defecto. `touch logs/trader.pause` lo para. Cada trato va a `TRADES.md` | `python3 trader.py [--live [--live-boards]]` |
| `trader.py --quotes` | **Quoter:** pujas fijas por cartas que nos faltan para una página y ofertas de venta de repetidas, vigiladas por un guardián. Suelo de caja 15 P reservado para aceptar; compras en tableros con tope de 40 P por hora; sin contraofertas de sondeo; `--hands-off RET-09` (Maru la compra a mano: ni puja, ni acepta, ni contraoferta); `--earmark REF:CANTIDAD` apagado por defecto. Los tiempos se ajustan a la duración del tick (domingo 15 s). Guardián: STOP si una operación pierde valor, si baja la puntuación en 15 ticks tras un trato nuestro, o por gasto o errores; SCORE-DROP es solo un aviso. Borrar `logs/trader.pause` lo reinicia. Avisos en `logs/alerts.jsonl`. Solo publica con `--live`. Escribe `logs/trader.heartbeat` | `python3 trader.py --quotes --live-boards [--quote-budget 180] [--live]` |
| `trader_review.py` | **Bucle de revisión:** informe de solo lectura sobre salud, puesto frente al campo, aceptaciones previstas frente a reales, contraofertas, pujas llenadas por precio, ganancias claras perdidas (`logs/trader_blocked.jsonl`) y señales; como máximo 3 propuestas con su prueba. Corre solo cada 2 h (09:17-23:17) mientras la sesión de Claude esté abierta. Una persona aprueba cualquier cambio | `python3 trader_review.py [--hours 2]` |
| `duels.py` | Juega cada duelo en vivo. Decide el código; las palabras lo transmiten. **Por defecto `--policy v2`: la jugada de esperar** (`ONE_SHEET.es.md` §VI). `--policy v1` = lógica antigua, el interruptor de seguridad. Los movimientos del rival se leen en nuestro valor total U (precio + día); cada oferta es un paquete (precio, día) con U ≥ 1; los textos son bilingües ES/EN según la situación | `python3 duels.py [--dry] [--policy v1]` |
| `duels_watch.py` | **Supervisor:** arranca `duels.py` cuando hay duelos en vivo, lo reinicia si se cae o si un duelo lleva 3 ticks esperándonos. Avisos DUEL_START, DUEL_SILENT, DUEL_CRASH | `python3 duels_watch.py [--silent 3] [-- <args de duels.py>]` |
| `analyze_duels.py` | Tasa de tratos, resultado ÷ límite, rondas, por papel y por brazo | `python3 analyze_duels.py --since <primer id de duelo>` |
| `bz.predict` (Maru) | Un modelo por dealer y tipo de trato. `agent.py` lo usa por defecto | `python3 agent.py learn && python3 -m bz.predict` |
| `broker.py` (Maru) | Broker para un puesto propio: registra el libro y casa tratos. Sin usar | ver el archivo |
| Pruebas | tratos, quotes, reglas, duelos, modelos de dealers | `python3 tests/test_trade.py`, `tests/test_quotes.py`, `tests/test_rules.py`, `tests/test_predict.py` … |

## 2. Los ciclos

| # | Ciclo | Ritmo | Qué mirar | Regla de decisión (fijada ya) | Acción |
|---|---|---|---|---|---|
| L1 | **Puntuación** | siempre | `logs/score.jsonl`: nuestros números, la etiqueta, el líder y la mediana | Un experimento solo se lee si nuestro número se movió **y** el líder y la mediana se movieron menos. La negociación es relativa ✅: comparar siempre con la mediana | Poner la etiqueta antes de cada experimento |
| L2 | **Ofertas que nos hacen** | cada tick | `logs/trader.jsonl` | Cada aceptación debe ganar valor. Nunca vender por debajo de nuestro valor ni una carta que nos falte para una página | `trader.py`; EN VIVO solo con el visto bueno de Maru (`logs/trader.pause` existe desde las 11:09, así que está en pausa) |
| L3 | **Duelos** | cada sesión | Tasa de tratos, resultado por trato, rondas, duelos sin respuesta, cuántos bots ceden solos | **Base de Duelos I:** 18 tratos de 34, 13,3 por trato; tratos en ≤ 2 rondas 20,4 frente a ≥ 4 rondas 5,7; **8 duelos perdidos por nuestro silencio**. Objetivo Duelos II: 0 sin respuesta, ≥ 80 % de tratos, mediana ≤ 2 rondas, ≥ 18 por trato. **Interruptor de seguridad:** ≥ 2 no-tratos evitables (sin trato aunque el rival ofreció dentro de nuestro límite con U ≥ 1), o el agente falla y el vigilante no puede reiniciarlo → reiniciar con `--policy v1` (`analyze_duels.py` los cuenta) | `duels_watch.py` en la máquina de Thameur, `observe.py tag D2`, luego `analyze_duels.py` |
| L4 | **Quoter** | cada tick cuando esté EN VIVO | Ventas/compras llenadas, `neg_points`, avisos | Cada compra o venta llenada debe subir `neg_points`. Si una lo baja, o aparece un aviso STALE / FOREIGN, pausar (`touch logs/trader.pause`) y mirar | `trader.py --quotes --live` tras el visto bueno de Maru |
| L5 | **Dealers** | por dealer | Hilos, `ladder_points`, `neg_points` | Los dealers dan muy poca puntuación (0,14). Tratar solo por valor: cartas de página por debajo de su valor, repetidas por encima. **Ninguna venta por debajo de nuestro valor, ninguna carta de página** | Scripts de Maru, `--model predict` |
| L6 | **Market Test** | cada 2 h | `bench_efficiency`, `market` nuestro y del mejor equipo | El puesto gratis dio 0,933 → mercado 7,5. **Desde el tick 575 lo sustituye nuestro puesto propio v21** (sin broker visto aún). Si v21 saca menos de 7,5 en el Market Test 3 → ponerle un broker pasa a ser la primera tarea de mercado | Solo lectura |
| L7 | **Palabras** | primero en tratos con equipos | Tasa de respuesta y precio logrado, por redacción | Dos redacciones (simple frente a etiqueta + una pregunta calibrada), alternadas, al menos 10 de cada. Quedarse con la de más respuestas y luego mejor precio. Nunca con El Chato | Cuando L2 envíe contraofertas |

## 3. Calendario (Madrid, estimado desde `/api/schedule` en el tick 583, a las 13:03)

| ≈ Cuándo | Qué hacer |
|---|---|
| 17:55 · 19:55 · 21:55 | Market Tests: apuntar nuestros números y los del mejor equipo (L6) |
| **18:05–20:05** | **Fiebre de Salamanca de Pilar (+25 % sobre catálogo).** Antes, el equipo decide: vender Salamanca o completar la página |
| **ya en marcha** | `python3 duels_watch.py` corre en la máquina de Thameur desde las 15:52 (v2, la jugada de esperar) |
| **≈20:35** | **Duelos II** (8 % por ronda, 16 ticks, hasta 6 a la vez). `observe.py tag D2`. Comprobación de la lectura del día al abrir. Revisión a las 21:00, luego `analyze_duels.py` y aplicar L3 |
| 23:00 | Cierran las puertas |
| **Domingo** | 09:00 abre (ticks de 15 s). ≈09:35 Market Test duro. ≈11:35 ronda 3 desde cero, sale Chamberí, +150 P. **≈13:35 Duelos III** (10 %, 12 ticks = 3 min). 15:00 cierre. Gran Final / congelación ❓ (después de las 15:00 en el calendario actual) |

## 4. Lista de trabajo (en este orden)

1. ✅ **Lógica de duelos para Duelos II** (`bz/duel.py` v2, terminal del trader, también dueña de `duels.py`): doctrina aprobada a las 13:35, jugada de esperar aprobada a las 14:00 (`ONE_SHEET.es.md` §VI). Por defecto `--policy v2`; `--policy v1` es el interruptor de seguridad. Día de entrega: reglas de paquetes (precio + día desde una U objetivo; un movimiento de día hacia él se paga en precio) y la regla dura **toda oferta tiene U ≥ 1**; los números aún no tienen datos reales (`ONE_SHEET.es.md` §VI).
2. **Guardián de dealers** (Maru): `sell-spares` solo vende repetidas, nunca por debajo de `sell_floor`; `--limit` limitado a `sell_floor`/`buy_cap` (15:36). **Hecho.**
3. **Quoter EN VIVO** con el visto bueno de Maru (180 P en pujas, +79 de valor si todo se llena). La caja tiene 48 P tras la fianza de v21: poner `--quote-budget` a lo que haya.
4. **Broker:** v21 está abierto sin broker. Leer L6 en el próximo Market Test y decidir entonces, no en el test duro.

## 5. Preguntas abiertas que deben responder los experimentos
- La fórmula exacta de `neg_points`, `duel_points` y `ladder_points` a los 30 puntos de negociación.
- Por qué bajó `neg_points` en el tick 567 (¿ventas a Pilar por debajo de su valor?).
- El bono de maestro.
- Si las palabras cambian el precio de un rival LLM (L7).
