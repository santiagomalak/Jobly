"""Ícono de la app (una "J" verde) generado como PNG sin librerías de imágenes."""
from __future__ import annotations

import struct
import zlib
from functools import lru_cache

_FONDO = (11, 13, 18)
_VERDE = (34, 197, 94)
_TINTA = (4, 20, 10)


def _en_rect(x: float, y: float, x0: float, y0: float, x1: float, y1: float) -> bool:
    return x0 <= x <= x1 and y0 <= y <= y1


def _pixel(x: float, y: float) -> tuple[int, int, int]:
    """x, y en [0, 1]. Cuadrado verde redondeado con una J."""
    m, r = 0.08, 0.22  # margen y radio de las esquinas
    dentro = m <= x <= 1 - m and m <= y <= 1 - m
    if dentro:
        for cx, cy in ((m + r, m + r), (1 - m - r, m + r), (m + r, 1 - m - r), (1 - m - r, 1 - m - r)):
            en_esquina = (x < m + r or x > 1 - m - r) and (y < m + r or y > 1 - m - r)
            if en_esquina and (x - cx) ** 2 + (y - cy) ** 2 > r**2 and abs(x - cx) < r + 1e-9 and abs(y - cy) < r + 1e-9:
                if (x < 0.5) == (cx < 0.5) and (y < 0.5) == (cy < 0.5):
                    dentro = False
    if not dentro:
        return _FONDO
    es_j = (
        _en_rect(x, y, 0.50, 0.24, 0.65, 0.70)  # palo
        or _en_rect(x, y, 0.33, 0.58, 0.65, 0.72)  # base
        or _en_rect(x, y, 0.33, 0.50, 0.44, 0.72)  # gancho
        or _en_rect(x, y, 0.42, 0.24, 0.72, 0.34)  # travesaño superior
    )
    return _TINTA if es_j else _VERDE


@lru_cache(maxsize=4)
def png(lado: int) -> bytes:
    filas = bytearray()
    for j in range(lado):
        filas.append(0)  # filtro "none" de la fila
        for i in range(lado):
            filas.extend(_pixel((i + 0.5) / lado, (j + 0.5) / lado))

    def chunk(tipo: bytes, datos: bytes) -> bytes:
        cuerpo = tipo + datos
        return struct.pack(">I", len(datos)) + cuerpo + struct.pack(">I", zlib.crc32(cuerpo) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", lado, lado, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(filas), 9))
        + chunk(b"IEND", b"")
    )
