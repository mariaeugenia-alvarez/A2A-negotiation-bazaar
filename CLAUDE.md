# bazaar-kit · instrucciones para cada sesión

Equipo t09 en The Bazaar. Varias sesiones comparten la misma clave: antes de abrir un hilo, `python3 agent.py status`.

## Negociar con dealers (Abuela, El Chato, Pilar y los que vengan)

1. **Antes de negociar**, refresca y lee el modelo de cada dealer (solo lectura, 0 P):
   ```bash
   python3 agent.py learn && python3 -m bz.predict
   ```
   `bz/predict.py` reconstruye todos los hilos con dealers de todos los equipos (feed + `logs/threads/`), ajusta un
   modelo por dealer y tipo de trato, e imprime su precisión, el límite que delata cada primera respuesta y los pasos
   que conviene dar. Las reglas, en `DEALERS.md`.
2. **Negocia con `agent.py`**: por defecto `--model predict` (el modelo pone cada precio; `bz/haggle.py` lo recibe con
   `advise=`). `--model learn` vuelve al ritmo antiguo, que también es el de reserva para dealers sin modelo.
   No escribas bucles de regateo a mano: usa `agent.py` o `bz.predict.advise()`.
3. **Jugada de cada dealer:**
   - Abuela («midpoint»): su 1ª respuesta delata su límite (L = A − 2·d1 o una más). Abrir lejos, +1 P por mensaje sin
     repetir, ofrecer L cuando solo pueda decir L, aceptar su final.
   - El Chato («boulware»): su calendario a·k² limita lo que cede, y nunca cede más que nuestro paso. Pasos crecientes
     (rara: 1, 2, 2, 4, 4, 5) y el punto medio al final. Poco comunes: comprárselas a Abuela, no a él.
   - Pilar («linear»): no se mueve en su primera respuesta, luego +1 P por movimiento sea cual sea el paso. Abrir alto,
     bajar 1 P sin repetir, aceptar su final (17-21; 24-25 si la carta es de SAL/RET). Las poco comunes sobrantes, a ella;
     nunca una carta de página. En la fiebre de Salamanca (≈16-18 h) el equipo decide antes: vender SAL o completar la página.
   - Dealer nuevo: `bz.predict.family_of()` elige entre las tres familias en cuanto se ha movido en 3 hilos; hasta
     entonces no hay modelo y `agent.py` lo avisa. Para usarlo, añádelo a `MODELS` en `bz/predict.py`.
4. **Después de negociar**: `python3 -m bz.predict` otra vez. Si la precisión de un dealer baja o un tipo de trato
   nuevo aparece sin modelo, revisa con la skill `abuela-learner` y anota en `DEALERS.md`.
5. **Antes de tocar `bz/predict.py`, `bz/haggle.py` o `agent.py`**: `python3 tests/test_predict.py`,
   `python3 tests/test_haggle_model.py`, `python3 tests/sim_chato.py`, `python3 tests/sim_haggle.py`.

## Reglas

- Analizar es gratis; negociar gasta primas reales: nada LIVE sin el visto bueno de Maru.
- **Manda lo que nos vale la carta** (`your_value`, `b.value(ref)`): nunca vender por debajo de `price.sell_floor(valor)`
  ni comprar por encima de `price.buy_cap(valor)`. Vale también para `--limit`, `--force` y scripts a medida. Si la
  escalera de dealers justifica cruzar ese límite, antes se pregunta a Maru diciendo cuántas primas perdemos.
- Las palabras del dealer no mueven su precio; lo deciden el código y el modelo.
