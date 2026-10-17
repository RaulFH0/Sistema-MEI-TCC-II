from security.auth import gerar_hash_senha


SENHA_ADMIN_TESTE = "SenhaForteExclusivaTeste!2026"


def autenticar_cliente_admin(cliente, monkeypatch):
    """
    Configura uma conta administrativa de teste
    e autentica o TestClient usando as rotas reais.

    Deve ser utilizado apenas nos testes automatizados.
    """

    monkeypatch.setenv(
        "ADMIN_USERNAME",
        "admin"
    )

    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH",
        gerar_hash_senha(SENHA_ADMIN_TESTE)
    )

    monkeypatch.setenv(
        "SESSION_SECRET",
        "segredo-exclusivo-para-testes-2026"
    )

    monkeypatch.setenv(
        "COOKIE_SECURE",
        "false"
    )

    resposta = cliente.post(
        "/auth/login",
        json={
            "usuario": "admin",
            "senha": SENHA_ADMIN_TESTE
        }
    )

    assert resposta.status_code == 200, resposta.text

    csrf_token = resposta.json()["csrf_token"]

    # Todas as requisicoes subsequentes deste cliente
    # enviarao o CSRF; o cookie de sessao e gerenciado
    # automaticamente pelo TestClient.
    cliente.headers.update({
        "X-CSRF-Token": csrf_token
    })

    return cliente