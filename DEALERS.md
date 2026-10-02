# Dealers · lo que hemos aprendido

Memoria del equipo entre sesiones (skill `abuela-learner`). Datos: `logs/threads/`, modelo: `logs/dealer_model.json`.

## Abuela Carmen (nivel 1)

Rasgos publicados: paciencia 0.85, generosidad 0.8, astucia 0.2. Habla en inglés con cariño («cariño», «hijo»),
regala consejos («a full page is worth much more») y a veces un detalle («a little present from me»).
Frases de cierre: «Let's meet in the middle», «Venga, X P», y la final: «I can't go lower. This is my last offer.»

### Vender poco común · hilos 42, 54 (viernes)
- Abre en 12, su tope ha sido 13 las dos veces (una como oferta final, otra aceptando nuestro 13).
- Final tras ~5 mensajes nuestros. **Patrón fiable**: 13 P. Nos valían 2,2 → +10,8 P cada una.

### Vender común · hilo 96 (viernes)
- Abre en 5, final en 6 tras ~5 mensajes. Una sola muestra: hipótesis.

### Comprar sobre de barrio · hilos 19, 66, 108, 121 (viernes)
| Hilo | Ticks | Su apertura | Cierre | Cómo |
|---|---|---|---|---|
| 19 | 1–2 | 17 | 17 | aceptado sin regatear (starter): **no cuenta** |
| 66 | 35–41 | 30 | **19** | aceptó nuestro 19 («Venga, 19 P») |
| 108 | 60–67 | 30 | 21 | su final |
| 121 | 68–74 | 30 | 23 | su final |

- Concede ~4 P al principio y luego 1 P por mensaje; final tras ~6–7 mensajes nuestros.
- Su apertura fue 17 al empezar la partida («Made for beginners») y 30 después.
- ~~Hipótesis del cupo por hora~~: descartada con el feed (otros equipos chocan con un final de 23 en su primer
  sobre de la hora; la hora es de juego, por ticks: 0–59, 60–119, ...).
- **H1**: cada conversación tiene un límite secreto L; Abuela acepta NUESTRA oferta en cuanto llega a L, y aparte
  baja su precio por su cuenta (30 → 26 → 25 → 24 → 23) hasta dar su final (casi siempre 23) tras 4–7 mensajes.
  Feed, ticks 60–81: t06 cerró aceptando su 22 (#137), t06 su 24 (#109, su 22 rechazado), finales de 23 para
  t03/t04/t12/t13 con ofertas de 14–20.
- **H2**: L sube con el tiempo de juego (19 en el tick 40; nadie por debajo de 21 desde el tick 60).

### Sondeo · hilo 165 (ticks 88–92, viernes 21:48)
- Abrimos en 18 y subimos 1 a 1 hasta un tope de 21; ella: 30 → 27 → 26 → 25. **No aceptó 19, 20 ni 21: L > 21.**
- Al llegar a nuestro tope y dejar de movernos, ella tampoco se movió: no llegó a dar su final. Cerramos: 0 P.
- `neg_points` no cambió (−8,2): control correcto, un hilo sin trato no puntúa.
- Lectura: con datos de los ticks 60–92, L suele estar en 22–23 → pesa más H2 (o una L alta casi siempre) que
  la idea de que empezar bajo nos costaba el precio. Ofrecer menos de 22 ahora mismo no consigue sobre.
- Pendiente: medir L por equipo y tick con `logs/feed.jsonl` (registrador del feed en marcha desde las 21:51).

### Cambios aplicados
- `bz/learn.py`: `target` = su mejor precio histórico (antes la mediana); horizonte de ritmo = paciencia − 2.
  Motivo: con «meet in the middle» importa dónde estamos cuando se le acaba la paciencia. No demostrado aún.
- `bz/learn.py`: el precio del trato cuenta como «su mejor precio» (acepta a veces NUESTRA oferta).

### Revisión con el feed completo (106 hilos, ticks 60–122; deep-dive del viernes 22:30)
- **Su final es un suelo oculto F por conversación** (20–25, media 22,3), independiente de nuestra trayectoria:
  corr(nº de mensajes, final) −0,16, corr(nuestro último precio, final) −0,10. «Meet in the middle» y «N concesiones»
  descartados (85 %).
- **Su primera bajada delata F**: F ≈ 30 − 2·d1, con ±1 en 16 de 17 hilos (75 %). Ej.: hilo 165, d1 = 3 → F ≈ 24 > nuestro
  límite 21; hilo 166, d1 = 5 → F = 20 (no fue por abrir en 8).
- Solo concede cuando subimos (~1 P por subida, sea cual sea el paso). Repetir precio no la mueve.
- Acepta nuestra oferta cuando llega a F (a veces F − 1) (60 %).
- **H2 descartada** (final de 20 en el tick 95). `best_ever = 19` (tick 35) está caducado: `accept_at` nunca dispara.
- Mejoras pendientes: límite 25 en vez de 23 (con 23 perdemos ~18 % de tratos), pujar F − 1 y luego F tras su primera bajada.

## El Chato (nivel 2)
- **Activo para nosotros desde el tick 98** (desbloqueado con 4 tratos con Abuela); abre a todos en t = 2,63 h.
- Vende: comunes/poco comunes desde 33, raras desde 97 (−1 por subida nuestra, final ~91), sobre_plata 188.
- Compra poco comunes a 13 sin moverse; una rara: de 39 a 46 (final).
- Aún no hemos abierto ningún hilo con él: sus 3 mejores tratos llenan los huecos del nivel 2, que pesa más.

### Teoría, simulación y primer hilo (rama `price-limits`)
Rasgos publicados: paciencia 0.35 (Abuela 0.85), astucia 0.85, memoria 0.9, rigor 0.85. Silver pack: lista 150, apertura 188.
Simulaciones: `tests/sim_chato.py` (dealer simulado con paciencia baja; todos los supuestos están en su docstring).

**Primer hilo, 294 (ticks 148-151): vender MAL-08 (poco común), nuestro suelo 13. Sin trato:** otra sesión vendió
esa carta a Abuela en el tick 155 y el hilo cerró con `not_owner`.

| Tick | Quién | Precio |
|---|---|---|
| 148 | nosotros | 22 |
| 149 | El Chato | 13 («Veintidós, dices... trece primas») |
| 149 | nosotros | 18 |
| 150 | El Chato | 13 |
| 150 | nosotros | 14 |
| 151 | El Chato | 13 («Yo no me muevo si tú apenas te mueves. Lo tomas o te lo quedas.») |

- Su puja por un poco común empieza en 13 (50 % de la lista) y no se movió con pasos pequeños.
- Nombró su última oferta **solo con palabras**, tras 3 mensajes nuestros (sin `final: true`). El agente ya lo lee
  (`bz/texts.py: says_final`), y `learn` saca su paciencia de ese texto.
- Su puja por un poco común es la misma que la de Abuela (13): con nuestra apertura no mejora a Abuela.
- Mala coordinación: dos sesiones eligieron la misma carta. El agente ahora relee nuestras cartas antes de cada venta.

**Cruzando con los datos del feed de arriba:** vende poco comunes desde 33 (no desde 26, la lista) y casi no se mueve
(−1 por subida nuestra; una rara de 97 a 91). Dos consecuencias:
- Comprarle un poco común a nuestro límite actual (26, su lista) no cerrará: su rango real queda por encima.
- Para comprar, nuestro BATNA es Abuela (compramos LAV-08 a 21 allí). A El Chato solo le compramos si baja de lo
  que ya conseguimos con ella. Hay que reescribir los escenarios de compra del simulador con apertura 33 y paso ≈ 1.

**Prior para dealers nuevos (agrupado, aparte de los datos de cada dealer):** mensajes antes de su final ≈ 6 × rasgo de
paciencia (Abuela 0,85 → 5-7; El Chato 0,35 → 3 observado, 2 con el prior). `learn.messages_per_trait` lo calcula con
los dealers que ya conocemos, y un hilo real sustituye al prior.

## Puntuación: experimentos con `neg_points` (viernes 22:00–22:22)
La clasificación (y el `score` de `/api/me`) se recalcula cada 5 ticks (`snapshot_tick`, `next_refresh_tick`).

| Experimento | Valor ganado (privado) | Liquidado | `neg_points` | `ladder_points` | `negotiating` |
|---|---|---|---|---|---|
| Vender LAT-02 a 6 P (nos valía 0,5) | +5,5 | tick 106 | −8,2 → −8,2 | 0,066 → 0,066 | 12,5 → 12,5 |
| Comprar LAV-08 a 21 P (nos vale 40) | +19 | tick 117 | −8,2 → −8,2 | 0,066 → 0,066 | 12,5 → 12,31 |

- Conclusión: los tratos con dealers **no mueven `neg_points`** (ni ventas ni compras, con valor a favor).
  Lo más probable es que sea el valor ganado en tratos con otros equipos; el −8,2 no lo explican los datos que
  tenemos (sin ofertas ni tratos entre equipos desde el tick 60; antes no hay registro).
- `ladder_points` tampoco se movió con ninguno de los dos tratos.
- `negotiating` bajó sin que cambiara nada nuestro: parece normalizado (fase de la ronda o relativo al resto).
- Pendiente: preguntar en el mostrador qué miden `neg_points` y `ladder_points`.
