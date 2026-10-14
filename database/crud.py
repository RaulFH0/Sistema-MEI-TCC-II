import hashlib
import json
from sqlalchemy.exc import IntegrityError
from database.models import Compra, ItemCompra

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from sqlalchemy import update, func
from sqlalchemy.orm import Session

from database.models import Produto, Pedido, LogSistema


# ============================================================
# CONFIGURAÇÕES E FUNÇÕES AUXILIARES
# ============================================================

LIMITE_POR_PRODUTO = 50


def _validar_quantidade(quantidade):
    if type(quantidade) is not int:
        raise ValueError("Quantidade deve ser um número inteiro.")

    if not 1 <= quantidade <= LIMITE_POR_PRODUTO:
        raise ValueError(
            "Quantidade por produto deve estar entre 1 e 50."
        )

    return quantidade


def _validar_nome(nome, campo="Nome"):
    if not isinstance(nome, str) or not nome.strip():
        raise ValueError(f"{campo} é obrigatório.")

    return nome.strip()


def _valor_decimal(valor):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Valor monetário inválido.")

    if not numero.is_finite():
        raise ValueError("Valor monetário inválido.")

    return numero.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


# ============================================================
# CRUD DE PRODUTOS
# ============================================================

def criar_produto(
    db: Session,
    nome: str,
    preco: float,
    quantidade: int,
    descricao: str = "",
    categoria: str = ""
):
    nome = _validar_nome(nome, "Nome do produto")

    if type(quantidade) is not int or quantidade < 0:
        raise ValueError("Estoque inicial inválido.")

    preco_validado = _valor_decimal(preco)

    if preco_validado <= 0:
        raise ValueError("Preço deve ser maior que zero.")

    existente = (
        db.query(Produto)
        .filter(func.lower(func.trim(Produto.nome)) == nome.casefold())
        .first()
    )

    if existente:
        raise ValueError(
            f"Produto '{nome}' já está cadastrado."
        )

    produto = Produto(
        nome=nome,
        preco=float(preco_validado),
        quantidade=quantidade,
        descricao=descricao,
        categoria=categoria
    )

    try:
        db.add(produto)
        db.commit()
        db.refresh(produto)
        return produto

    except Exception:
        db.rollback()
        raise


def buscar_produto_por_nome(db: Session, nome: str):
    nome = _validar_nome(nome, "Nome do produto")

    return (
        db.query(Produto)
        .filter(Produto.nome.ilike(f"%{nome}%"))
        .first()
    )


def listar_produtos(db: Session):
    return db.query(Produto).order_by(Produto.id).all()


def atualizar_estoque(
    db: Session,
    produto_id: int,
    nova_quantidade: int
):
    if type(nova_quantidade) is not int or nova_quantidade < 0:
        raise ValueError("Estoque não pode ser negativo.")

    try:
        produto = db.get(Produto, produto_id)

        if produto is None:
            raise ValueError("Produto não encontrado.")

        produto.quantidade = nova_quantidade
        produto.atualizado_em = datetime.now()

        db.commit()
        db.refresh(produto)

        return produto

    except Exception:
        db.rollback()
        raise


# ============================================================
# CRUD DE PEDIDOS
# ============================================================

def registrar_pedido_seguro(
    db: Session,
    cliente_nome: str,
    itens: list[dict]
):
    """
    Registra um ou vários produtos de maneira atômica.

    Cada item é salvo como um registro na tabela atual
    de pedidos. Não há ainda um identificador único
    compartilhado entre todos os itens da compra.
    """

    cliente_nome = _validar_nome(
        cliente_nome,
        "Nome do cliente"
    )

    if not isinstance(itens, list) or not itens:
        raise ValueError("Pedido sem produtos.")

    quantidades = {}

    # --------------------------------------------------------
    # 1. VALIDAR E CONSOLIDAR ITENS
    # --------------------------------------------------------

    for item in itens:
        if not isinstance(item, dict):
            raise ValueError("Formato de item inválido.")

        nome = _validar_nome(
            item.get("produto_nome"),
            "Nome do produto"
        )

        quantidade = _validar_quantidade(
            item.get("quantidade")
        )

        chave = nome.casefold()

        if chave not in quantidades:
            quantidades[chave] = {
                "nome": nome,
                "quantidade": 0
            }

        quantidades[chave]["quantidade"] += quantidade

    for item in quantidades.values():
        if item["quantidade"] > LIMITE_POR_PRODUTO:
            raise ValueError(
                f"Quantidade máxima de 50 unidades "
                f"excedida para '{item['nome']}'."
            )

    # --------------------------------------------------------
    # 2. VALIDAR PRODUTOS, ESTOQUE E PREÇOS
    # --------------------------------------------------------

    pedidos_criados = []
    total_geral = Decimal("0.00")

    try:
        for item in quantidades.values():
            nome = item["nome"]
            quantidade = item["quantidade"]

            produtos = (
                db.query(Produto)
                .filter(
                    func.lower(func.trim(Produto.nome))
                    == nome.lower()
                )
                .all()
            )

            if not produtos:
                raise ValueError(
                    f"Produto '{nome}' não cadastrado."
                )

            if len(produtos) > 1:
                raise ValueError(
                    f"Produto '{nome}' duplicado no cadastro."
                )

            produto = produtos[0]

            preco = _valor_decimal(produto.preco)

            if preco <= 0:
                raise ValueError(
                    f"Preço inválido para '{nome}'."
                )

            # ------------------------------------------------
            # 3. REDUZIR ESTOQUE COM VERIFICAÇÃO ATÔMICA
            # ------------------------------------------------

            atualizacao = db.execute(
                update(Produto)
                .where(
                    Produto.id == produto.id,
                    Produto.quantidade >= quantidade
                )
                .values(
                    quantidade=Produto.quantidade - quantidade,
                    atualizado_em=datetime.now()
                )
                .execution_options(
                    synchronize_session=False
                )
            )

            if atualizacao.rowcount != 1:
                raise ValueError(
                    f"Estoque insuficiente para '{nome}'."
                )

            subtotal = (
                preco * Decimal(quantidade)
            ).quantize(Decimal("0.01"))

            pedido = Pedido(
                cliente_nome=cliente_nome,
                produto_id=produto.id,
                produto_nome=produto.nome,
                quantidade=quantidade,
                valor_total=float(subtotal),
                status="confirmado"
            )

            db.add(pedido)
            pedidos_criados.append(pedido)

            total_geral += subtotal

        # ----------------------------------------------------
        # 4. GRAVAR TUDO NA MESMA TRANSAÇÃO
        # ----------------------------------------------------

        db.flush()

        resultado = {
            "pedido_confirmado": True,
            "cliente_nome": cliente_nome,
            "itens": [
                {
                    "pedido_id": pedido.id,
                    "produto_nome": pedido.produto_nome,
                    "quantidade": pedido.quantidade,
                    "valor_total": pedido.valor_total
                }
                for pedido in pedidos_criados
            ],
            "valor_total": float(total_geral)
        }

        db.commit()

        return resultado

    except Exception:
        db.rollback()
        raise


def criar_pedido(
    db: Session,
    cliente_nome: str,
    produto_id: int,
    produto_nome: str,
    quantidade: int,
    valor_total: float
):
    """
    Interface antiga mantida por compatibilidade.

    As informações comerciais são obtidas do banco,
    independentemente dos valores informados pelo agente.
    """

    produto = db.get(Produto, produto_id)

    if produto is None:
        raise ValueError("Produto não encontrado.")

    if produto.nome.strip().casefold() != produto_nome.strip().casefold():
        raise ValueError(
            "O nome informado não corresponde ao produto."
        )

    resultado = registrar_pedido_seguro(
        db=db,
        cliente_nome=cliente_nome,
        itens=[
            {
                "produto_nome": produto.nome,
                "quantidade": quantidade
            }
        ]
    )

    pedido_id = resultado["itens"][0]["pedido_id"]

    return db.get(Pedido, pedido_id)


def listar_pedidos(db: Session):
    return db.query(Pedido).order_by(Pedido.id).all()


# ============================================================
# LOGS DO SISTEMA
# ============================================================

def registrar_log(
    db: Session,
    acao: str,
    entrada: str,
    resposta: str,
    tempo_ms: int,
    sucesso: str = "sim",
    erro: str = ""
):
    log = LogSistema(
        acao=acao,
        entrada_usuario=entrada,
        resposta_agente=resposta,
        tempo_ms=tempo_ms,
        sucesso=sucesso,
        erro=erro
    )

    try:
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    except Exception:
        db.rollback()
        raise


# ============================================================
# COMPRAS V2 - MULTIPLOS ITENS E IDEMPOTENCIA
# ============================================================

def registrar_compra_segura(
    db: Session,
    cliente_nome: str,
    itens: list[dict],
    chave_idempotencia: str
):
    cliente = _validar_nome(
        cliente_nome, "Nome do cliente"
    )

    chave = _validar_nome(
        chave_idempotencia, "Chave de idempotencia"
    )

    if len(chave) > 128:
        raise ValueError("Chave de idempotencia muito longa.")

    if not isinstance(itens, list) or not itens:
        raise ValueError("Compra sem produtos.")

    # 1. Normalizar e consolidar itens
    normalizados = {}

    for item in itens:
        if not isinstance(item, dict):
            raise ValueError("Item invalido.")

        nome = _validar_nome(
            item.get("produto_nome"), "Produto"
        )
        qtd = _validar_quantidade(
            item.get("quantidade")
        )

        nome_normalizado = nome.casefold()

        normalizados[nome_normalizado] = (
            normalizados.get(nome_normalizado, 0) + qtd
        )

    for nome, qtd in normalizados.items():
        if qtd > LIMITE_POR_PRODUTO:
            raise ValueError(
                f"Limite de 50 unidades excedido: {nome}"
            )

    # 2. Hash canonico do conteudo da compra
    assinatura = {
        "cliente": cliente.casefold(),
        "itens": sorted(normalizados.items())
    }

    conteudo = json.dumps(
        assinatura,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":")
    )

    hash_solicitacao = hashlib.sha256(
        conteudo.encode("utf-8")
    ).hexdigest()

    def apresentar(compra, repetida=False):
        return {
            "pedido_confirmado": True,
            "compra_id": compra.id,
            "cliente_nome": compra.cliente_nome,
            "itens": [
                {
                    "produto_nome": item.produto_nome,
                    "quantidade": item.quantidade,
                    "preco_unitario": item.preco_unitario / 100,
                    "subtotal": item.subtotal / 100
                }
                for item in sorted(
                    compra.itens, key=lambda x: x.id
                )
            ],
            "valor_total": compra.valor_total / 100,
            "requisicao_repetida": repetida
        }

    def verificar_existente(compra):
        if compra.hash_solicitacao != hash_solicitacao:
            raise ValueError(
                "Chave de idempotencia ja utilizada "
                "com dados diferentes."
            )
        return apresentar(compra, repetida=True)

    # 3. Verificar compra previamente confirmada
    existente = (
        db.query(Compra)
        .filter(Compra.chave_idempotencia == chave)
        .first()
    )

    if existente:
        return verificar_existente(existente)

    try:
        # 4. Reservar a chave antes de baixar estoque
        compra = Compra(
            cliente_nome=cliente,
            chave_idempotencia=chave,
            hash_solicitacao=hash_solicitacao,
            valor_total=0,
            status="confirmado"
        )

        db.add(compra)
        db.flush()

        total_centavos = 0

        # 5. Consultar produtos e atualizar estoque
        for nome, qtd in sorted(normalizados.items()):
            produtos = (
                db.query(Produto)
                .filter(
                    func.lower(func.trim(Produto.nome))
                    == nome
                )
                .all()
            )

            if not produtos:
                raise ValueError(
                    f"Produto '{nome}' nao cadastrado."
                )

            if len(produtos) > 1:
                raise ValueError(
                    f"Produto '{nome}' duplicado."
                )

            produto = produtos[0]
            preco = _valor_decimal(produto.preco)

            if preco <= 0:
                raise ValueError("Preco invalido.")

            preco_centavos = int(preco * 100)
            subtotal = preco_centavos * qtd

            atualizacao = db.execute(
                update(Produto)
                .where(
                    Produto.id == produto.id,
                    Produto.quantidade >= qtd
                )
                .values(
                    quantidade=Produto.quantidade - qtd,
                    atualizado_em=datetime.now()
                )
                .execution_options(
                    synchronize_session=False
                )
            )

            if atualizacao.rowcount != 1:
                raise ValueError(
                    f"Estoque insuficiente: {produto.nome}"
                )

            db.add(ItemCompra(
                compra_id=compra.id,
                produto_id=produto.id,
                produto_nome=produto.nome,
                quantidade=qtd,
                preco_unitario=preco_centavos,
                subtotal=subtotal
            ))

            total_centavos += subtotal

        compra.valor_total = total_centavos

        db.flush()
        resultado = apresentar(compra)

        # Uma transacao para compra, itens e estoque
        db.commit()

        return resultado

    except IntegrityError:
        db.rollback()

        # Outra chamada pode ter gravado a mesma chave.
        existente = (
            db.query(Compra)
            .filter(Compra.chave_idempotencia == chave)
            .first()
        )

        if existente:
            return verificar_existente(existente)

        raise

    except Exception:
        db.rollback()
        raise
