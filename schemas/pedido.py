from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

# ============================================================
# SCHEMAS DE PRODUTO
# ============================================================
class ProdutoBase(BaseModel):
    nome: str = Field(..., min_length=1, description="Nome do produto")
    preco: float = Field(..., gt=0, description="Preço deve ser maior que zero")
    quantidade: int = Field(..., ge=0, description="Quantidade não pode ser negativa")
    descricao: Optional[str] = ""
    categoria: Optional[str] = ""

class ProdutoCreate(ProdutoBase):
    pass

class ProdutoResponse(ProdutoBase):
    id: int
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True


# ============================================================
# SCHEMAS DE PEDIDO
# ============================================================
class PedidoCreate(BaseModel):
    cliente_nome: str = Field(..., min_length=1, description="Nome do cliente")
    produto_nome: str = Field(..., min_length=1, description="Nome do produto")
    quantidade: int = Field(..., gt=0, description="Quantidade deve ser maior que zero")

    @validator("cliente_nome")
    def nome_nao_vazio(cls, v):
        if not v.strip():
            raise ValueError("Nome do cliente não pode ser vazio")
        return v.strip()

    @validator("quantidade")
    def quantidade_valida(cls, v):
        if v > 50:
            raise ValueError("Quantidade máxima por pedido é 50 unidades")
        return v

class PedidoResponse(BaseModel):
    id: int
    cliente_nome: str
    produto_nome: str
    quantidade: int
    valor_total: float
    status: str
    criado_em: datetime

    class Config:
        from_attributes = True


# ============================================================
# SCHEMA DE ENTRADA DO AGENTE
# (o que o usuário digita em linguagem natural)
# ============================================================
class EntradaUsuario(BaseModel):
    mensagem: str = Field(..., min_length=1, description="Mensagem do usuário")
    contexto: Optional[str] = ""

class RespostaAgente(BaseModel):
    resposta: str
    acao_executada: str
    sucesso: bool
    dados: Optional[dict] = None


# ============================================================
# SCHEMAS PARA PEDIDOS COM MÚLTIPLOS PRODUTOS
# ============================================================

from pydantic import ConfigDict, field_validator


class ItemPedido(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produto_nome: str = Field(
        ...,
        min_length=1,
        description="Nome do produto solicitado"
    )

    quantidade: int = Field(
        ...,
        strict=True,
        gt=0,
        le=50,
        description="Quantidade entre 1 e 50 unidades"
    )

    @field_validator("produto_nome")
    @classmethod
    def validar_nome_produto(cls, valor: str):
        nome = valor.strip()

        if not nome:
            raise ValueError(
                "Nome do produto não pode ser vazio"
            )

        return nome


class PedidoMultiploCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cliente_nome: str = Field(
        ...,
        min_length=1,
        description="Nome do cliente"
    )

    itens: list[ItemPedido] = Field(
        ...,
        min_length=1,
        description="Lista de produtos solicitados"
    )

    @field_validator("cliente_nome")
    @classmethod
    def validar_cliente(cls, valor: str):
        nome = valor.strip()

        if not nome:
            raise ValueError(
                "Nome do cliente não pode ser vazio"
            )

        return nome

    @field_validator("itens")
    @classmethod
    def validar_itens(cls, itens: list[ItemPedido]):
        total_por_produto = {}

        for item in itens:
            chave = item.produto_nome.casefold()

            total_por_produto[chave] = (
                total_por_produto.get(chave, 0)
                + item.quantidade
            )

        for quantidade in total_por_produto.values():
            if quantidade > 50:
                raise ValueError(
                    "Quantidade máxima por produto "
                    "é 50 unidades"
                )

        return itens
