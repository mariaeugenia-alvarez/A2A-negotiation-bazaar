# The Bazaar · Hoja de negociación (maestra, v4)

Sábado 3 oct 2026 · Equipo 9 · Versión en inglés: `ONE_SHEET.md`
Las cinco secciones están rellenas. Las secciones II–IV son borradores sin probar. Los ciclos y experimentos están en `PLAYBOOK.es.md`.
Fuentes: `RULES.md`, diapositivas del kickoff, **Pistas del Día 2**, el mostrador, nuestros datos y registros.
✅ = comprobado en una fuente o en nuestros datos · ⚠️ = inferencia mía · ❓ = no sabemos

---

## I. LA META

**Meta de hoy: descubrir cuál de los tres sitios nos da más puntos y poner ahí nuestro esfuerzo. Mientras tanto, no perder los puntos seguros.**

### Qué ha cambiado desde el primer borrador (leer primero)
- **Corregido:** los dealers no se limitan a unos 6 tratos. Hoy llegan más dealers (niveles 3–5), los niveles altos pesan más, y tres buenos tratos con un dealer desbloquean el siguiente antes.
- **Corregido:** «ningún mercado ha hecho un trato» solo significaba que los mercados de equipos aún no habían abierto. Abrieron en la hora de juego 3,0.
- **Explicado:** cada día es su propia ronda y **hoy empieza en 0**. Por eso nuestros `neg_points` y `ladder_points` bajaron a 0,0. Los experimentos de hoy son limpios.
- **Confirmado:** el mostrador dijo que un rival callado en un duelo significa cero para los dos. No quiso decirnos cómo se reparten los 30 puntos. Lo descubrimos con experimentos.
- **Nuevo en las pistas:** un trato por encima de tu propio valor cuesta puntos. Abrir los duelos con una oferta que la otra parte pueda aceptar. Leer `GET /api/me/offers` en cada tick. Publicar pujas y cambios con `expires_in_ticks`.
- **Nuevo en nuestros datos:** tenemos un puesto gratis (`v12`). El Market Test 1 le dio un 89,9 % de eficiencia y una puntuación de mercado de 4,8. El juego va unos 30 minutos por detrás del plan.

### 1. Dónde están los puntos ✅
- 100 puntos: **Negociar 30**, **Mercado 30**, **Jurado 40**.
- Negociar sale de tres sitios: **duelos**, **dealers** (Abuela, El Chato y otros nuevos), **tratos con otros equipos**.
- El viernes cuenta la mitad, el sábado y el domingo cuentan completos. Los tratos del viernes no ayudan a la ronda de hoy.
- **No sabemos cómo se reparten los 30 puntos entre los tres.**
- Nunca puntúa: número de tratos, número de anuncios, comisiones, suerte en los sobres, regalos.
- **Las puntuaciones pueden ser relativas a los demás equipos** ⚠️ (líder cerca de 30, último en 0).

### 2. Los tres sitios ✅

| Sitio | Hechos |
|---|---|
| **Duelos** | Práctica: 32 duelos, cerramos los 15 en que el rival contestó. Los 12 con rival callado puntuaron cero. Menos de la mitad de los duelos de práctica acabaron en trato (pistas). Cada ronda de conversación encoge el trato: 6 % (Duelos I), 8 % (II), 10 % (III y Final). Comprobado con nuestros datos: 26 × 0,94³ = 21,6. Duelos II añaden un día de entrega (0–10): descubrir a quién le importa más el tiempo. |
| **Dealers** | Solo cuentan los 3 mejores tratos por dealer, y un hueco vacío es cero. Un trato al precio de apertura no cuenta. La ronda de hoy empieza vacía también con Abuela. Con El Chato tenemos 0. Los dealers notan el spam. El mismo precio no es un movimiento, 20 → 21 → 22 sí. Los precios de los dealers salen de sus propias reglas. |
| **Tratos con equipos** | Las ofertas hechas para nosotros duran unos 2 ticks. Anoche los equipos 13, 10 y 12 quisieron comprar nuestra rara MAL-10 por 45, 75 y 82 P. Para nosotros vale 63 P. **No contestamos.** También podemos publicar pujas por cualquier copia de una carta, o cambios, con `expires_in_ticks` hasta 120. |

### 3. Valor de las cartas: las reglas que usamos ✅
- **Valor de una carta** = precio de catálogo × nuestro multiplicador del set × factor de copia. Comprobado con MAL-10: 70 × 0,9 = 63, y una segunda copia 70 × 0,9 × 0,25 = 15,75.
- **Precios de catálogo:** común 10, poco común 25, rara 70, épica 180, legendaria 450.
- **Factor de copia:** 1.ª copia 1,0, 2.ª 0,25, 3.ª y siguientes 0,1. Por eso los repetidos nos valen poco y a un equipo al que le falta la carta le valen mucho.
- **Nuestros multiplicadores privados:** Lavapiés 1,6, El Retiro 1,3, Salamanca 1,1, Malasaña 0,9, Chamberí 0,7, La Latina 0,5. Nuestra mejor página para completar es Lavapiés.
- **Nunca pagar por encima de tu propio valor.** Vender primero los repetidos, nunca por debajo de lo que vale la copia para nosotros.
- ❓ El **bono de página** (25 % en el catálogo, 10 % el de maestro) **no** está en `your_value`. No sabemos cómo se cuenta. Hasta medirlo, una carta que completa una página va a una persona, no a las reglas automáticas.
- ✅ **Comisiones:** quien acepta una oferta paga la comisión del mercado (SDK). El Rastro cobra 5 % + 1 P por carta. Publicar nuestra oferta y dejar que la acepten puede ahorrarnos la comisión ⚠️.

### 4. Los experimentos (una acción, un número que mirar)
Todas nuestras puntuaciones están ahora a 0,0, así que cualquier cambio de hoy es limpio. Nuestros números están en `GET /api/me` → `score` y se actualizan cada 5 ticks más o menos. Apuntar el número **antes** y **después**.

| N.º | Hacer esto | Mirar esto | Nos dice |
|---|---|---|---|
| E1 | Terminar el primer duelo con puntuación (Duelos I) | `duel_points` | ¿Los duelos dan puntos? ¿Cuántos por trato? |
| E2 | Un trato pequeño con otro equipo | `neg_points` | ¿Los tratos con equipos dan puntos? ¿Coincide con el valor que ganamos? |
| E3 | Un trato con El Chato (lo aprobamos antes) | `ladder_points` | ¿Los dealers dan puntos? ¿Qué precio cuenta como bueno? |

- **Una cosa cada vez.** Dos acciones juntas esconden cuál movió el número.
- **Los tratos reales cuestan primas.** Primero teoría, luego simulación gratis, y los tratos reales **solo con tu aprobación.**

### 5. El negociador automático para ofertas que nos llegan (plan, aún sin construir)
- **Lee solo la estructura** (`give` y `want`), nunca las palabras. Las reglas dicen: mirar la oferta, no el mensaje.
- **Comprar:** aceptar solo si (valor que recibimos) − (dinero que pagamos) − (comisión) supera un margen.
- **Vender:** nunca por debajo del valor de la copia que damos. Primero los repetidos.
- **Antes de cada aceptación:** seguimos teniendo la carta, tenemos el dinero, la oferta no ha caducado, y solo una aceptación por tick (la mejor). Nuestro primer hilo con El Chato acabó en `not_owner` porque la carta ya estaba vendida.
- **También publicar pujas fijas** por las cartas que necesitamos, por debajo de nuestro valor, y ofertas de venta de repetidos, por encima, con caducidad larga.
- **Leer `GET /api/me/offers` en cada tick.** Usar `next_tick_in` de `GET /api/clock` o el stream de eventos. Un 429 significa «espera al siguiente tick», no es un error.
- **Caso de prueba de hoy:** el equipo 5 ofrece una copia de LAV-02 por 10 P. Ya tenemos una, así que otra copia nos vale 4 P (16 × 0,25). Las reglas la rechazarían. También habrían rechazado la puja de 45 P por MAL-10 y aceptado las de 75 P y 82 P.
- **Primero en modo sombra:** muestra lo que aceptaría o contraofertaría y no envía nada. Las aceptaciones automáticas llegan después, solo para ganancias claras, con tu aprobación.

### 6. La parte verbal (etiquetas, espejo, preguntas): lo que de verdad sabemos
- ✅ Los precios de los dealers salen de sus propias reglas. La inyección de prompts cambia lo que dicen, nunca sus precios.
- ✅ Todo mensaje que mandamos a un dealer fue una plantilla amable fija con un precio. Nunca probamos etiquetas, espejo ni preguntas, ni mandamos un mensaje seco de control. **No hay ninguna prueba de si el tono cambia un precio.** En 11 intercambios con Abuela bajó unos 1 P por cada subida, con cualquier plantilla (muy pocos para demostrar nada).
- ✅ Las palabras sí dan **información**. Abuela nos dijo «una página completa vale mucho más», «tu repetida vale oro para quien le falta», y que a El Chato «le gusta la gente que trata sin rodeos».
- ✅ Los dealers usan estas técnicas con nosotros. El Chato repitió nuestro precio («Veintidós, dices… trece primas») y nos etiquetó («Yo no me muevo si tú apenas te mueves»).
- ✅ Otros equipos también. El equipo 13 escribió: «It looks like Malasaña is not your focus, while it is ours.»
- ⚠️ **Hipótesis para probar luego:** las palabras pueden rendir donde la otra parte es un agente con deseos ocultos: tratos con equipos y duelos de precio y días. Probar un cambio cada vez.

### 7. Reloj (hora de Madrid) ✅⚠️
**El juego va unos 30 minutos por detrás del plan.** El Market Test 1 estaba previsto a las 09:21 y empezó hacia las 09:50 (tick 201).

| Plan de las pistas | Hora real probable |
|---|---|
| 09:21 abren mercados de equipos + Market Test 1, luego cada 2 h | empezó ≈ 09:50 |
| 11:30 Duelos I puntúan | ≈ 12:00 |
| 18:00 Duelos II (precio + día) | ≈ 18:30 |
| todo el día: llegan dealers nuevos (pantalla grande, `GET /api/levels`) | |
| 23:00 cierran las puertas | 23:00 |

Mirar `GET /api/schedule` para las horas reales. Mañana: ticks de 15 s, Duelos III y duelos de la Final (10 % por ronda), cierran los dealers, se congelan las puntuaciones.

### 8. Mercados (30 puntos) ✅
- **Tres tipos de mercado:** la casa (El Rastro: 5 % + 1 P por carta, ofertas publicadas, sin broker), un mercado `board` (el broker de su dueño empareja ofertas: hay que mantenerlo en marcha) y un mercado `auto` (el motor empareja la mejor compra y la mejor venta en cada tick).
- **Las comisiones nunca puntúan.** Lo que puntúa: el Market Test (el mismo libro sintético para todos, cada 2 h) y el valor creado entre otros equipos en tu mercado.
- **Ya tenemos un puesto gratis:** `v12`, auto, 3 % de comisión, sin fianza, abierto en el tick 201. Los puntos completos van a la media de los tres mejores mercados.
- **Resultado del Market Test 1 (ticks 201–217) ✅:** nuestro puesto realizó el **89,9 %** de las ganancias posibles y recibió **0,5 puntos del test**. Tras la actualización de puntuación (tick 220), nuestra puntuación de mercado es **4,8**. Los equipos 14 y 18 muestran el mismo 4,8, como se espera de puestos gratis idénticos.
- **La mejor puntuación de mercado es la del equipo 12 con 8,01** (un mercado `board`, 0 % de comisión). Son unos **+3,2 sobre el puesto gratis** tras una sesión ⚠️. Hizo 1 trato de 7 P, así que casi todo será del Market Test, no de tratos. No sabemos cómo emparejó. Cada sesión siguiente cuenta por separado y la ronda hace la media.
- **Hay 18 mercados abiertos,** 7 abiertos por equipos, casi todos con 0 % de comisión. Nuestro propio agente no puede tratar en nuestro propio mercado.
- **Coste de abrir uno propio:** 250 P de fianza (vuelve tras un periodo de espera) + 20 P. Sustituye al puesto gratis. Solo compensa con un broker que estime los límites ocultos mejor que el puesto. Aún no tenemos ese broker.
- **Decisión (propuesta):** mantener el puesto gratis por ahora. El puesto gratis ya puntúa 4,8, y el extra de un broker más listo parece de unos 3 puntos. Revisarlo tras el Market Test 2 (hacia las 11:50), y solo si alguien del equipo tiene tiempo para construir el broker. Abrir un mercado con el broker de ejemplo solo repetiría la puntuación del puesto gratis.

### 9. Decisiones del equipo para hoy
1. **¿Aprobar el negociador en modo sombra?** Solo lee ofertas y muestra decisiones.
2. **Apertura en duelos:** nuestro código abre al 45 % de nuestro límite (`bz/duel.py`, ajustado solo en simulación). La pista dice abrir con una oferta que la otra parte pueda aceptar. Revisarlo antes de Duelos I (hacia las 12:00).
3. **El Chato:** aprobar la teoría y la simulación gratis, y luego un trato real cada vez (E3). Sus tres huecos están vacíos, y tres buenos tratos desbloquean el siguiente dealer antes.
4. **Mercado:** mantener el puesto gratis (4,8 ahora) o construir un broker mejor (el mejor equipo tiene 8,01). Decidir tras el Market Test 2.
5. **Quién vigila los números de puntuación** antes y después de cada experimento.

---

## II. RESUMEN (hechos a los que queremos que cada parte responda «eso es») ⚠️ aún sin probar

| Contraparte | Resumen |
|---|---|
| Otros equipos | Las páginas valen más para el equipo al que le falta una carta. Las ofertas para nosotros duran unos 2 ticks, así que necesitáis respuestas rápidas. Tenemos repetidos y alguna rara, y las valoramos con nuestros propios multiplicadores. |
| Rival de duelo | Cada ronda de conversación encoge el trato para los dos, y si nadie contesta puntuamos cero los dos. Quieres un trato rápido a un reparto justo, y nosotros también. |
| Abuela | Eres paciente, te gustan los clientes amables y solo te mueves cuando nos movemos. Una página completa importa más que las cartas sueltas. |
| El Chato | Tratas sin rodeos, no te mueves por pasos pequeños y tu paciencia es corta (unos 3 mensajes antes de tu última palabra). |

## III. ETIQUETAS / AUDITORÍA DE ACUSACIONES ⚠️ todas sin probar

| Quién | Acusación probable | Etiquetas (3 cada uno) |
|---|---|---|
| Otros equipos | «Ignoráis las ofertas» / «ofrecéis muy poco» | Parece que esta carta completa vuestra página. · Parece que la rapidez os importa, porque las ofertas desaparecen enseguida. · Parece que os han ignorado ofertas antes. |
| Rival de duelo | «Abres demasiado bajo» | Parece que el tiempo es valioso para ti. · Parece que prefieres cerrar rápido. · Parece que un reparto justo te importa. |
| Abuela | «Regateas duro» (sus propias palabras) | Parece que has conocido a muchos clientes duros. · Parece que valoras a los clientes amables. · Parece que una página completa te importa. |
| El Chato | «Intentas ser listo» (memoria larga, estricto) | Parece que valoras el trato sin rodeos. · Parece que no te gustan los juegos. · Parece que los pasos pequeños no te impresionan. |

Los precios de los dealers siguen sus propias reglas. Con ellos, las etiquetas sirven para información y relación, no para el precio.

## IV. PREGUNTAS CALIBRADAS ⚠️ todas sin probar

| Quién | Preguntas |
|---|---|
| Otros equipos | ¿Qué haría que este trato os funcionara? · ¿Cómo encaja esta carta en vuestra página? · ¿Qué presión de tiempo tenéis? |
| Duelos II–III–Final (precio y día) | ¿Qué importancia tiene para ti el día de entrega? · ¿Qué cambiaría para ti una entrega más corta o más larga? (descubre a quién le importa más el tiempo) |
| Abuela (perdona: memoria 0,15, rigor 0,1) | ¿Qué buscas en un cliente? · ¿Cómo decides quién recibe tu mejor precio? |
| El Chato (estricto 0,85, memoria 0,9) | **No preguntar todavía.** Reglas: algunos dealers tratan las mismas palabras sin un precio nuevo como spam. Todo mensaje a él lleva un precio nuevo. |

## V. OFERTAS SIN DINERO

| Quién | Qué podrían dar además de dinero |
|---|---|
| Abuela ✅ | Regalos: nos dio una carta («un pequeño regalo de mi parte», hilo 108) y regaló cartas a los equipos 7 y 17. También da consejos: «una página completa vale mucho más», «cambia tus repes». |
| El Chato | ❓ Desconocido. Compra cartas poco comunes y raras. Tres buenos tratos con él desbloquean antes el siguiente dealer ✅. |
| Otros equipos | Cambios carta por carta en lugar de dinero ✅ (pistas). Sus huecos de página, que nos dicen cuánto valen nuestros repetidos para ellos. Ofertas con larga vida. Ahorro de comisión si aceptan nuestra oferta, porque paga quien acepta ⚠️. |
| Rival de duelo | El día de entrega (0–10): cambiar el día que menos nos importa por precio ✅. |

Manual con los ciclos, experimentos y reglas de decisión: `PLAYBOOK.es.md`.
