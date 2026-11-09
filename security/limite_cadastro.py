import math
import time

from collections import deque
from threading import Lock
from typing import Callable


class LimitadorCadastro:
    """
    Limitador por chave, com janela deslizante.

    Armazena somente horarios de tentativas.
    Nao armazena senhas, CNPJs ou outros dados cadastrais.
    """

    def __init__(
        self,
        limite: int = 5,
        janela_segundos: int = 900,
        capacidade: int = 10000,
        relogio: Callable[[], float] = time.monotonic,
    ):
        if limite < 1 or janela_segundos < 1 or capacidade < 1:
            raise ValueError("Configuracao do limitador invalida.")

        self.limite = limite
        self.janela = janela_segundos
        self.capacidade = capacidade
        self.relogio = relogio
        self._tentativas: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _limpar_expirados(self, agora: float) -> None:
        for chave in list(self._tentativas):
            registros = self._tentativas[chave]

            while registros and agora - registros[0] >= self.janela:
                registros.popleft()

            if not registros:
                del self._tentativas[chave]

    def consumir(self, chave: str) -> int | None:
        """
        Retorna None quando permitido.

        Retorna segundos de espera quando bloqueado.
        """
        if not isinstance(chave, str) or not chave.strip():
            raise ValueError("Chave de limitacao invalida.")

        with self._lock:
            agora = self.relogio()

            self._limpar_expirados(agora)

            registros = self._tentativas.get(chave)

            if registros is None:
                if len(self._tentativas) >= self.capacidade:
                    return self.janela

                registros = deque()
                self._tentativas[chave] = registros

            if len(registros) >= self.limite:
                restante = self.janela - (agora - registros[0])
                return max(1, math.ceil(restante))

            registros.append(agora)
            return None


# Instancia para o processo local do FastAPI.
limitador_cadastro = LimitadorCadastro(
    limite=5,
    janela_segundos=15 * 60,
)
