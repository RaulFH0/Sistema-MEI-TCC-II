
import hashlib
import json

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from sqlalchemy import update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import (
    Produto,
    Pedido,
    LogSistema,
    Compra,
    ItemCompra,
)


# ============================================================
# CONFIGURAÇÕES E FUNÇÕES AUXILIARES
# ============================================================

LIMITE_POR_PRODUTO = 50


def _validar_quantidade(quantidade):
    if type(quantidade) is not int:
        raise ValueError(
            "Quantidade deve ser um número inteiro."
        )

    if not 1 <= quantidade <= LIMITE_POR_PRODUTO:
        raise ValueError(
            "Quantidade por produto deve estar entre 1 e 50."
        )

    return quantidade


def _validar_nome(nome, campo="Nome"):
    if not isinstance(nome, str) or not nome.strip():
        raise ValueError(
            f"{campo} é obrigatório."
        )

    return nome.strip()


def _valor_decimal(valor):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(
            "Valor monetário inválido."
        )

    if not numero.is_finite():
        raise ValueError(
            "Valor monetário inválido."
        )

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
    nome = _validar_nome(
        nome,
        "Nome do produto"
    )

    if type(quantidade) is not int or quantidade < 0:
        raise ValueError(
            "Estoque inicial inválido."
        )

    preco_validado = _valor_decimal(preco)

    if preco_validado <= 0:
        raise ValueError(
            "Preço deve ser maior que zero."
        )

    existente = (
        db.query(Produto)
        .filter(
            func.lower(func.trim(Produto.nome))
            == nome.casefold()
        )
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


def buscar_produto_por_nome(
    db: Session,
    nome: str
):
    nome = _validar_nome(
        nome,
        "Nome do produto"
    )

    return (
        db.query(Produto)
        .filter(Produto.nome.ilike(f"%{nome}%"))
        .first()
    )


def listar_produtos(db: Session):
    return (
        db.query(Produto)
        .order_by(Produto.id)
        .all()
    )


def atualizar_estoque(
    db: Session,
    produto_id: int,
    nova_quantidade: int
):
    if (
        type(nova_quantidade) is not int
        or nova_quantidade < 0
    ):
        raise ValueError(
            "Estoque não pode ser negativo."
        )

    try:
        produto = db.get(
            Produto,
            produto_id
        )

        if produto is None:
            raise ValueError(
                "Produto não encontrado."
            )

        produto.quantidade = nova_quantidade
        produto.atualizado_em = datetime.now()

        db.commit()
        db.refresh(produto)

        return produto

    except Exception:
        db.rollback()
        raise


# ============================================================
# CRUD DE PEDIDOS - MODELO ANTERIOR
# ============================================================

def registrar_pedido_seguro(
    db: Session,
    cliente_nome: str,
    itens: list[dict]
):
    """
    Registra um ou vários produtos de maneira atômica.

    Cada item é salvo como um registro na tabela
    anterior de pedidos.

    Não há um identificador único compartilhado
    entre todos os itens dessa compra.
    """

    cliente_nome = _validar_nome(
        cliente_nome,
        "Nome do cliente"
    )

    if not isinstance(itens, list) or not itens:
        raise ValueError(
            "Pedido sem produtos."
        )

    quantidades = {}

    # --------------------------------------------------------
    # 1. VALIDAR E CONSOLIDAR ITENS
    # --------------------------------------------------------

    for item in itens:
        if not isinstance(item, dict):
            raise ValueError(
                "Formato de item inválido."
            )

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
                    quantidade=(
                        Produto.quantidade - quantidade
                    ),
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
            ).quantize(
                Decimal("0.01")
            )

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

    produto = db.get(
        Produto,
        produto_id
    )

    if produto is None:
        raise ValueError(
            "Produto não encontrado."
        )

    if (
        produto.nome.strip().casefold()
        != produto_nome.strip().casefold()
    ):
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

    return db.get(
        Pedido,
        pedido_id
    )


def listar_pedidos(db: Session):
    return (
        db.query(Pedido)
        .order_by(Pedido.id)
        .all()
    )


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
    chave_idempotencia: str,
    mensagem_original: str | None = None,
    total_aprovado_centavos: int | None = None,
    identificar_por_id: bool = False
):
    """
    Registra uma compra V2 de maneira transacional.

    O total_aprovado_centavos é opcional para preservar
    a compatibilidade com o atendimento IA existente.

    Quando informado pelo portal do cliente, o valor
    é comparado com o total calculado pelo banco.

    Se o valor tiver mudado, a compra é cancelada
    e a transação é revertida.
    """

    cliente = _validar_nome(
        cliente_nome,
        "Nome do cliente"
    )

    chave = _validar_nome(
        chave_idempotencia,
        "Chave de idempotencia"
    )

    if len(chave) > 128:
        raise ValueError(
            "Chave de idempotencia muito longa."
        )

    # --------------------------------------------------------
    # VALIDAR O TOTAL APROVADO PELO CLIENTE
    # --------------------------------------------------------

    if total_aprovado_centavos is not None:
        if (
            type(total_aprovado_centavos) is not int
            or total_aprovado_centavos <= 0
        ):
            raise ValueError(
                "Total aprovado invalido."
            )

    # --------------------------------------------------------
    # VALIDAR A MENSAGEM ORIGINAL
    # --------------------------------------------------------

    hash_mensagem = None

    if mensagem_original is not None:
        if not isinstance(mensagem_original, str):
            raise ValueError(
                "Mensagem original invalida."
            )

        if not mensagem_original.strip():
            raise ValueError(
                "Mensagem original vazia."
            )

        hash_mensagem = hashlib.sha256(
            mensagem_original.encode("utf-8")
        ).hexdigest()

    if not isinstance(itens, list) or not itens:
        raise ValueError(
            "Compra sem produtos."
        )

    # --------------------------------------------------------
    # 1. NORMALIZAR E CONSOLIDAR ITENS
    # --------------------------------------------------------

    
    normalizados = {}

    for item in itens:
        if not isinstance(item, dict):
            raise ValueError("Item invalido.")

        quantidade = _validar_quantidade(
            item.get("quantidade")
        )

        if identificar_por_id:
            produto_id = item.get("produto_id")

            if type(produto_id) is not int or produto_id < 1:
                raise ValueError("ID do produto invalido.")

            chave_produto = produto_id
        else:
            nome = _validar_nome(
                item.get("produto_nome"),
                "Produto"
            )
            chave_produto = nome.casefold()

        normalizados[chave_produto] = (
            normalizados.get(chave_produto, 0)
            + quantidade
        )

    for identificador, quantidade in normalizados.items():
        if quantidade > LIMITE_POR_PRODUTO:
            raise ValueError(
                f"Limite de 50 unidades excedido: {identificador}"
            )

    # --------------------------------------------------------
    # 2. GERAR HASH CANONICO DA COMPRA
    # --------------------------------------------------------

    assinatura = {
    "cliente": cliente.casefold(),
    "itens": sorted(normalizados.items())
}

    if identificar_por_id:
        assinatura["identificacao"] = "produto_id"
        assinatura["total_aprovado_centavos"] = (
            total_aprovado_centavos
        )

    conteudo = json.dumps(
        assinatura,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":")
    )

    hash_solicitacao = hashlib.sha256(
        conteudo.encode("utf-8")
    ).hexdigest()

    # --------------------------------------------------------
    # APRESENTAR RESULTADO
    # --------------------------------------------------------

    def apresentar(compra, repetida=False):
        return {
            "pedido_confirmado": True,
            "compra_id": compra.id,
            "cliente_nome": compra.cliente_nome,
            "itens": [
                {
                    "produto_nome": item.produto_nome,
                    "quantidade": item.quantidade,
                    "preco_unitario": (
                        item.preco_unitario / 100
                    ),
                    "subtotal": item.subtotal / 100
                }
                for item in sorted(
                    compra.itens,
                    key=lambda x: x.id
                )
            ],
            "valor_total": compra.valor_total / 100,
            "requisicao_repetida": repetida
        }

    # --------------------------------------------------------
    # VERIFICAR COMPRA EXISTENTE
    # --------------------------------------------------------

    def verificar_existente(compra):
        if compra.hash_solicitacao != hash_solicitacao:
            raise ValueError(
                "Chave de idempotencia ja utilizada "
                "com dados diferentes."
            )

        if compra.hash_mensagem is not None:
            if hash_mensagem is None:
                raise ValueError(
                    "Mensagem original obrigatoria "
                    "para reutilizar esta chave."
                )

            if compra.hash_mensagem != hash_mensagem:
                raise ValueError(
                    "Chave de idempotencia utilizada "
                    "com mensagem diferente."
                )

        # Se um total aprovado foi fornecido,
        # ele também deve corresponder à compra
        # registrada anteriormente.
        if (
            total_aprovado_centavos is not None
            and compra.valor_total
            != total_aprovado_centavos
        ):
            raise ValueError(
                "Chave de idempotencia ja utilizada "
                "com valor aprovado diferente."
            )

        return apresentar(
            compra,
            repetida=True
        )

    # --------------------------------------------------------
    # 3. CONSULTAR COMPRA EXISTENTE
    # --------------------------------------------------------

    existente = (
        db.query(Compra)
        .filter(
            Compra.chave_idempotencia == chave
        )
        .first()
    )

    if existente:
        return verificar_existente(existente)

    try:
        # ----------------------------------------------------
        # 4. RESERVAR CHAVE ANTES DE BAIXAR ESTOQUE
        # ----------------------------------------------------

        compra = Compra(
            cliente_nome=cliente,
            chave_idempotencia=chave,
            hash_solicitacao=hash_solicitacao,
            hash_mensagem=hash_mensagem,
            valor_total=0,
            status="confirmado"
        )

        db.add(compra)
        db.flush()

        total_centavos = 0

        # ----------------------------------------------------
        # 5. CONSULTAR PRODUTOS E ATUALIZAR ESTOQUE
        # ----------------------------------------------------

        
        for identificador, qtd in sorted(normalizados.items()):

            # Portal do cliente: identificar pelo ID.
            if identificar_por_id:
                produto = db.get(Produto, identificador)

                if produto is None:
                    raise ValueError(
                        f"Produto ID {identificador} nao cadastrado."
                    )

            # Atendimento IA: identificar pelo nome.
            else:
                produtos = (
                    db.query(Produto)
                    .filter(
                        func.lower(func.trim(Produto.nome))
                        == identificador
                    )
                    .all()
                )

                if not produtos:
                    raise ValueError(
                        f"Produto '{identificador}' nao cadastrado."
                    )

                if len(produtos) > 1:
                    raise ValueError(
                        f"Produto '{identificador}' duplicado."
                    )

                produto = produtos[0]

            # A partir daqui, os dois caminhos utilizam
            # a mesma variavel 'produto'.
            preco = _valor_decimal(produto.preco)


            if preco <= 0:
                raise ValueError(
                    "Preco invalido."
                )

            preco_centavos = int(
                preco * 100
            )

            subtotal = (
                preco_centavos * qtd
            )

            # Atualização condicional de estoque.
            # Se não houver quantidade suficiente,
            # a operação é rejeitada.
            atualizacao = db.execute(
                update(Produto)
                .where(
                    Produto.id == produto.id,
                    Produto.quantidade >= qtd
                )
                .values(
                    quantidade=(
                        Produto.quantidade - qtd
                    ),
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

            db.add(
                ItemCompra(
                    compra_id=compra.id,
                    produto_id=produto.id,
                    produto_nome=produto.nome,
                    quantidade=qtd,
                    preco_unitario=preco_centavos,
                    subtotal=subtotal
                )
            )

            total_centavos += subtotal

        # ----------------------------------------------------
        # 6. CONFERIR TOTAL APROVADO PELO CLIENTE
        # ----------------------------------------------------

        if (
            total_aprovado_centavos is not None
            and total_centavos != total_aprovado_centavos
        ):
            raise ValueError(
                "O valor do pedido mudou desde o orcamento. "
                "Solicite um novo orcamento antes de confirmar."
            )

        # ----------------------------------------------------
        # 7. FINALIZAR A COMPRA
        # ----------------------------------------------------

        compra.valor_total = total_centavos

        db.flush()

        resultado = apresentar(
            compra
        )

        # Compra, itens e estoque na mesma transação.
        db.commit()

        return resultado

    except IntegrityError:
        db.rollback()

        # Outra chamada pode ter registrado a mesma chave.
        existente = (
            db.query(Compra)
            .filter(
                Compra.chave_idempotencia == chave
            )
            .first()
        )

        if existente:
            return verificar_existente(existente)

        raise

    except Exception:
        db.rollback()
        raise


# ============================================================
# CONSULTAR COMPRA EXISTENTE ANTES DA IA
# ============================================================

def consultar_compra_por_mensagem(
    db: Session,
    chave_idempotencia: str,
    mensagem_original: str
) -> dict | None:
    """
    Consulta uma compra existente antes de executar a IA.

    Retorna:
    - None: chave ainda nao utilizada;
    - dict: compra existente com mensagem identica;
    - ValueError: chave reutilizada com mensagem diferente.

    Compras antigas sem hash_mensagem nao sao
    retornadas antecipadamente.
    """

    chave = _validar_nome(
        chave_idempotencia,
        "Chave de idempotencia"
    )

    if len(chave) > 128:
        raise ValueError(
            "Chave de idempotencia muito longa."
        )

    if (
        not isinstance(mensagem_original, str)
        or not mensagem_original.strip()
    ):
        raise ValueError(
            "Mensagem original invalida."
        )

    hash_atual = hashlib.sha256(
        mensagem_original.encode("utf-8")
    ).hexdigest()

    compra = (
        db.query(Compra)
        .filter(
            Compra.chave_idempotencia == chave
        )
        .first()
    )

    if compra is None:
        return None

    # Compras anteriores à V2.2 precisam passar
    # pela validação estruturada completa.
    if compra.hash_mensagem is None:
        return None

    if compra.hash_mensagem != hash_atual:
        raise ValueError(
            "Chave de idempotencia utilizada "
            "com mensagem diferente."
        )

    return {
        "pedido_confirmado": True,
        "compra_id": compra.id,
        "cliente_nome": compra.cliente_nome,
        "itens": [
            {
                "produto_nome": item.produto_nome,
                "quantidade": item.quantidade,
                "preco_unitario": (
                    item.preco_unitario / 100
                ),
                "subtotal": (
                    item.subtotal / 100
                )
            }
            for item in sorted(
                compra.itens,
                key=lambda item: item.id
            )
        ],
        "valor_total": (
            compra.valor_total / 100
        ),
        "requisicao_repetida": True
    }
