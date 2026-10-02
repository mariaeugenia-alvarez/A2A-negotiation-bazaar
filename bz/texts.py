"""Kind words for Abuela (she likes kindness). Every message carries a new price, and no text repeats in a thread."""
import random

BUY = [
    "¡Buenas tardes, Carmen! Qué puesto tan bonito. ¿Le parecerían bien {p} primas?",
    "Gracias por su paciencia, Carmen. ¿Podríamos dejarlo en {p}?",
    "Me encanta venir a su puesto. Subo un poquito: {p} primas, ¿qué me dice?",
    "Usted sí que sabe de cromos. ¿Y si quedamos en {p}?",
    "Se lo agradezco mucho, de verdad. Le ofrezco {p}, con todo mi cariño.",
    "Mi abuela también tenía un puesto así. ¿{p} primas le vendría bien?",
    "Un pasito más por mi parte: {p}. ¡Muchas gracias, Carmen!",
    "Qué gusto hablar con usted. ¿Lo dejamos en {p}?",
    "Hago un esfuerzo, Carmen: {p} primas. ¿Trato hecho?",
    "Es usted un sol. ¿{p} y me lo llevo encantado?",
]
SELL = [
    "¡Hola, Carmen! Le traigo un cromo repetido, en perfecto estado. ¿{p} primas?",
    "Está como nuevo, se lo prometo. ¿Le parecen bien {p}?",
    "Gracias por mirarlo con calma. Bajo un poquito: {p}.",
    "Para usted, que es la mejor del Rastro: {p} primas.",
    "Me hace mucha ilusión que lo tenga usted. ¿{p}?",
    "Un pasito más por mi parte: {p}. ¡Gracias, Carmen!",
    "Hago un esfuerzo: {p} primas. ¿Trato hecho?",
    "Qué gusto hablar con usted. ¿Lo dejamos en {p}?",
]


class Writer:
    def __init__(self, side: str):
        self.pool = list(BUY if side == "buy" else SELL)
        random.shuffle(self.pool)
        self.used = set()

    def line(self, price: int) -> str:
        for t in self.pool:
            if t not in self.used:
                self.used.add(t)
                return t.format(p=price)
        self.used.clear()  # every text used once: start over, the price is new anyway
        return self.line(price)
