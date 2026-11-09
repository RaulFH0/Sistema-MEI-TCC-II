from fastapi.testclient import TestClient

import security.cadastro_mei_routes as cadastro
from security.limite_cadastro import LimitadorCadastro
from main import app


DADOS_INVALIDOS = {
    "nome_completo": "Teste de Limite",
    "email": "limite@example.com",
    "cnpj": "00.000.000/0000-00",
    "telefone": "85999999999",
    "nome_estabelecimento": "Loja Teste Limite",
    "senha": "SenhaForteTeste!2026",
}


def test_sexta_tentativa_retorna_http_429(monkeypatch):
    tempo = [100.0]

    limitador = LimitadorCadastro(
        limite=5,
        janela_segundos=900,
        relogio=lambda: tempo[0],
    )

    monkeypatch.setattr(
        cadastro,
        "limitador_cadastro",
        limitador,
    )

    cliente = TestClient(app)

    try:
        for _ in range(5):
            resposta = cliente.post(
                "/cadastro-mei/solicitar",
                json=DADOS_INVALIDOS,
            )

            assert resposta.status_code == 422, resposta.text

        bloqueada = cliente.post(
            "/cadastro-mei/solicitar",
            json=DADOS_INVALIDOS,
        )

        assert bloqueada.status_code == 429, bloqueada.text
        assert bloqueada.headers["retry-after"] == "900"

        tempo[0] += 900

        liberada = cliente.post(
            "/cadastro-mei/solicitar",
            json=DADOS_INVALIDOS,
        )

        assert liberada.status_code == 422, liberada.text

    finally:
        cliente.close()


def test_limite_nao_exige_login(monkeypatch):
    limitador = LimitadorCadastro(
        limite=5,
        janela_segundos=900,
        relogio=lambda: 100.0,
    )

    monkeypatch.setattr(
        cadastro,
        "limitador_cadastro",
        limitador,
    )

    cliente = TestClient(app)

    try:
        resposta = cliente.post(
            "/cadastro-mei/solicitar",
            json=DADOS_INVALIDOS,
        )

        # Rejeicao pelo CNPJ, nao por falta de login.
        assert resposta.status_code == 422, resposta.text

    finally:
        cliente.close()
