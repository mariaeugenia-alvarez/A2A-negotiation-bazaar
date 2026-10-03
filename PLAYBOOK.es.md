# The Bazaar · Manual de juego: probar, observar, mejorar (v2)

Sábado 3 oct 2026, 13:05 (tick 583) · Equipo 9 · Versión en inglés: `PLAYBOOK.md` · Estrategia y fuente de verdad: `ONE_SHEET.es.md`

**Regla de cada ciclo: un cambio, un número que mirar, y la regla de decisión escrita ANTES de ver el resultado.**
Los tratos reales cuestan primas: nada de lo siguiente envía algo salvo que ponga EN VIVO, y EN VIVO necesita el visto
bueno de Thameur.
**Quién hace qué en nuestra clave compartida:** dealers = scripts de Maru (`agent.py`, `bz/haggle.py`, `bz/predict.py`).
Tratos con equipos = `trader.py` (sesión del trader). Duelos = `duels.py` bajo `duels_watch.py`, en **una sola
máquina**. Todos gastan la misma caja, así que hay que avisarse antes de una compra grande o de publicar ofertas.

## 1. Lo que ya está construido

| Herramienta | Qué hace | Comando |
|---|---|---|
| `observe.py` | Guarda nuestra puntuación cada vez que cambia, con la etiqueta del experimento y la puntuación de negociación del líder y de la mediana | `python3 observe.py` · `python3 observe.py tag D2` |
| `trader.py` | Juzga las ofertas de **otros equipos solamente**, por su estructura, con los valores del juego. En sombra por defecto. `touch logs/trader.pause` lo para. Cada trato va a `TRADES.md` | `python3 trader.py [--live [--live-boards]]` |
| `trader.py --quotes` | **Quoter:** pujas fijas por cartas que nos faltan para una página y ofertas de venta de repetidas, vigiladas por un guardián. Avisos en `logs/alerts.jsonl` (STOP, UP, WIN, PAGE, OUTBID, STALE, FOREIGN). Solo publica con `--live` | `python3 trader.py --quotes [--quote-budget 180] [--live]` |
| `duels.py` | Juega cada duelo en vivo. Decide el código; las palabras lo transmiten | `python3 duels.py [--dry]` |
| `duels_watch.py` | **Supervisor:** arranca `duels.py` cuando hay duelos en vivo, lo reinicia si se cae o si un duelo lleva 3 ticks esperándonos. Avisos DUEL_START, DUEL_SILENT, DUEL_CRASH | `python3 duels_watch.py [--silent 3] [-- <args de duels.py>]` |
| `analyze_duels.py` | Tasa de tratos, resultado ÷ límite, rondas, por papel y por brazo | `python3 analyze_duels.py --since <primer id de duelo>` |
| `bz.predict` (Maru) | Un modelo por dealer y tipo de trato. `agent.py` lo usa por defecto | `python3 agent.py learn && python3 -m bz.predict` |
| `broker.py` (Maru) | Broker para un puesto propio: registra el libro y casa tratos. Sin usar | ver el archivo |
| Pruebas | tratos, quotes, reglas, duelos, modelos de dealers | `python3 tests/test_trade.py`, `tests/test_quotes.py`, `tests/test_rules.py`, `tests/test_predict.py` … |

## 2. Los ciclos

| # | Ciclo | Ritmo | Qué mirar | Regla de decisión (fijada ya) | Acción |
|---|---|---|---|---|---|
| L1 | **Puntuación** | siempre | `logs/score.jsonl`: nuestros números, la etiqueta, el líder y la mediana | Un experimento solo se lee si nuestro número se movió **y** el líder y la mediana se movieron menos. La negociación es relativa ✅: comparar siempre con la mediana | Poner la etiqueta antes de cada experimento |
| L2 | **Ofertas que nos hacen** | cada tick | `logs/trader.jsonl` | Cada aceptación debe ganar valor. Nunca vender por debajo de nuestro valor ni una carta que nos falte para una página | `trader.py`; EN VIVO solo con tu visto bueno (`logs/trader.pause` existe desde las 11:09, así que está en pausa) |
| L3 | **Duelos** | cada sesión | Tasa de tratos, resultado por trato, rondas, duelos sin respuesta | **Base de Duelos I:** 18 tratos de 30, 13,3 por trato; tratos en ≤ 2 rondas 20,4 frente a ≥ 4 rondas 5,7; **8 duelos perdidos por nuestro silencio**. Objetivo Duelos II: 0 sin respuesta, ≥ 80 % de tratos, mediana ≤ 2 rondas, ≥ 18 por trato. Si con menos rondas el resultado por trato baja → volver a la lógica de Duelos I para el domingo | `duels_watch.py` en una máquina, `observe.py tag D2`, luego `analyze_duels.py` |
| L4 | **Quoter** | cada tick cuando esté EN VIVO | Ventas/compras llenadas, `neg_points`, avisos | Cada compra o venta llenada debe subir `neg_points`. Si una lo baja, o aparece un aviso STALE / FOREIGN, pausar (`touch logs/trader.pause`) y mirar | `trader.py --quotes --live` tras tu visto bueno |
| L5 | **Dealers** | por dealer | Hilos, `ladder_points`, `neg_points` | Los dealers dan muy poca puntuación (0,14). Tratar solo por valor: cartas de página por debajo de su valor, repetidas por encima. **Ninguna venta por debajo de nuestro valor, ninguna carta de página** | Scripts de Maru, `--model predict` |
| L6 | **Market Test** | cada 2 h | `bench_efficiency`, `market` nuestro y del mejor equipo | El puesto gratis dio 0,933 → mercado 7,5. **Desde el tick 575 lo sustituye nuestro puesto propio v21** (sin broker visto aún). Si v21 saca menos de 7,5 en el Market Test 3 → ponerle un broker pasa a ser la primera tarea de mercado | Solo lectura |
| L7 | **Palabras** | primero en tratos con equipos | Tasa de respuesta y precio logrado, por redacción | Dos redacciones (simple frente a etiqueta + una pregunta calibrada), alternadas, al menos 10 de cada. Quedarse con la de más respuestas y luego mejor precio. Nunca con El Chato | Cuando L2 envíe contraofertas |

## 3. Calendario (Madrid, estimado desde `/api/schedule` en el tick 583, a las 13:03)

| ≈ Cuándo | Qué hacer |
|---|---|
| 13:50 · 15:50 · 17:50 | Market Tests: apuntar nuestros números y los del mejor equipo (L6) |
| **16:00–18:00** | **Fiebre de Salamanca de Pilar (+25 % sobre catálogo).** Antes, el equipo decide: vender Salamanca o completar la página |
| **18:00** | Ensayo en seco `python3 duels.py --dry` en un duelo de dos temas: comprobar `days` y el signo de `days_meaning`. Elegir la máquina de `duels_watch.py` |
| **18:30** | **Duelos II** (8 % por ronda, 16 ticks, hasta 6 a la vez). `observe.py tag D2`. Después `analyze_duels.py` y aplicar L3 |
| 19:50 · **21:30 (duro)** · 21:50 | Market Tests |
| 23:00 | Cierran las puertas |
| **Domingo** | 09:00 abre (ticks de 15 s). ≈09:30 ronda 3 desde cero, sale Chamberí, +150 P. **≈11:30 Duelos III** (10 %, 12 ticks = 3 min). ≈14:30 cierran los dealers + **Gran Final** (10 %, 12 ticks). ≈15:30 se congela la puntuación |

## 4. Lista de trabajo (en este orden)

1. **Lógica de decisión de los Duelos II** (`bz/duel.py`, sesión del trader, aprobada a las 13:35): sección VI de `ONE_SHEET.es.md`. Límite firme, primera oferta ambiciosa que el rival pueda aceptar, leer al bot y adaptarse (callar mientras cede solo), aceptar cuando una ronda más no pueda superar el decaimiento, como mucho 2 contraofertas reales. Día de entrega: solo hipótesis. Probar en simulación antes de las 18:00.
2. **Guardián de dealers** (Maru): rechazar cualquier venta por debajo de nuestro valor y cualquier carta que nos falte para una página.
3. **Quoter EN VIVO** con tu visto bueno (180 P en pujas, +79 de valor si todo se llena).
4. **Broker:** solo si L6 lo pide.

## 5. Preguntas abiertas que deben responder los experimentos
- La fórmula exacta de `neg_points`, `duel_points` y `ladder_points` a los 30 puntos de negociación.
- Por qué bajó `neg_points` en el tick 567 (¿ventas a Pilar por debajo de su valor?).
- El bono de maestro.
- Si las palabras cambian el precio de un rival LLM (L7).
