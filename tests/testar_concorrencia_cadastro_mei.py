from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from main import app
from database.models import Base, get_db
from database.contas_models import Estabelecimento, UsuarioMEI
from database.solicitacoes_models import SolicitacaoCadastroMEI
from security.routes import exigir_admin_escrita
from security.auth import gerar_hash_senha
from security.limite_cadastro import LimitadorCadastro
import security.cadastro_mei_routes as cadastro_routes


CNPJ_TESTE = "11222333000181"


@pytest.fixture
def ambiente_concorrente(tmp_path, monkeypatch):
    caminho = tmp_path / "concorrencia_mei.db"

    engine = create_engine(
        f"sqlite:///{caminho.as_posix()}",
        connect_args={
            "check_same_thread": False,
            "timeout": 20,
        },
    )

    @event.listens_for(engine, "connect")
    def configurar_sqlite(conexao, registro):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=20000")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    Sessao = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def obter_db():
        with Sessao() as db:
            yield db

    anteriores = dict(app.dependency_overrides)

    app.dependency_overrides[get_db] = obter_db
    app.dependency_overrides[exigir_admin_escrita] = (
        lambda: "admin_teste_concorrencia"
    )

    monkeypatch.setattr(
        cadastro_routes,
        "limitador_cadastro",
        LimitadorCadastro(limite=5, janela_segundos=900),
    )

    try:
        yield Sessao
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)
        engine.dispose()


def test_duas_aprovacoes_da_mesma_solicitacao(
    ambiente_concorrente,
):
    Sessao = ambiente_concorrente

    with Sessao.begin() as db:
        pedido = SolicitacaoCadastroMEI(
            nome_completo="Empreendedor Concorrencia",
            email="concorrencia@example.com",
            cnpj=CNPJ_TESTE,
            telefone="85999999999",
            nome_estabelecimento="Loja Concorrencia",
            senha_hash=gerar_hash_senha(
                "SenhaSeguraConcorrencia!2026"
            ),
            status="pendente",
        )
        db.add(pedido)
        db.flush()
        pedido_id = pedido.id

    barreira = Barrier(2)

    def aprovar():
        with TestClient(app) as cliente:
            barreira.wait(timeout=20)
            resposta = cliente.post(
                f"/admin/solicitacoes-mei/{pedido_id}/aprovar"
            )
            return resposta.status_code, resposta.text

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [
            executor.submit(aprovar)
            for _ in range(2)
        ]
        resultados = [f.result(timeout=45) for f in futuros]

    codigos = sorted(codigo for codigo, _ in resultados)

    assert codigos == [200, 409], resultados

    with Sessao() as db:
        assert db.query(Estabelecimento).filter_by(
            slug=f"mei-solicitacao-{pedido_id}"
        ).count() == 1

        assert db.query(UsuarioMEI).filter_by(
            email="concorrencia@example.com"
        ).count() == 1

        pedido = db.get(SolicitacaoCadastroMEI, pedido_id)
        assert pedido.status == "aprovado"


def test_duas_solicitacoes_com_mesmo_cnpj(
    ambiente_concorrente,
):
    Sessao = ambiente_concorrente
    barreira = Barrier(2)

    def solicitar(numero):
        dados = {
            "nome_completo": f"Empreendedor {numero}",
            "email": f"simultaneo{numero}@example.com",
            "cnpj": CNPJ_TESTE,
            "telefone": "85999999999",
            "nome_estabelecimento": f"Loja Simultanea {numero}",
            "senha": "SenhaSeguraConcorrencia!2026",
        }

        with TestClient(app) as cliente:
            barreira.wait(timeout=20)
            resposta = cliente.post(
                "/cadastro-mei/solicitar",
                json=dados,
            )
            return resposta.status_code, resposta.text

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [
            executor.submit(solicitar, numero)
            for numero in (1, 2)
        ]
        resultados = [f.result(timeout=45) for f in futuros]

    codigos = sorted(codigo for codigo, _ in resultados)

    assert codigos == [202, 409], resultados

    with Sessao() as db:
        assert db.query(SolicitacaoCadastroMEI).filter_by(
            cnpj=CNPJ_TESTE,
            status="pendente",
        ).count() == 1
