import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import get_db
from database.contas_models import UsuarioMEI
from database.solicitacoes_models import SolicitacaoCadastroMEI
from security.auth import gerar_hash_senha


router = APIRouter(
    prefix="/cadastro-mei",
    tags=["Cadastro MEI"],
)


class SolicitacaoEntrada(BaseModel):
    nome_completo: str = Field(min_length=3, max_length=150)
    email: str = Field(min_length=5, max_length=254)
    cnpj: str = Field(min_length=14, max_length=18)
    telefone: str = Field(min_length=8, max_length=20)
    nome_estabelecimento: str = Field(
        min_length=2,
        max_length=150,
    )
    senha: SecretStr


def normalizar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def cnpj_valido(cnpj: str) -> bool:
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    numeros = [int(digito) for digito in cnpj]

    def verificar(pesos, posicao):
        soma = sum(
            numero * peso
            for numero, peso in zip(numeros, pesos)
        )
        resto = soma % 11
        esperado = 0 if resto < 2 else 11 - resto
        return numeros[posicao] == esperado

    return (
        verificar(
            [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
            12,
        )
        and verificar(
            [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
            13,
        )
    )


@router.post("/solicitar", status_code=status.HTTP_202_ACCEPTED)
def solicitar_cadastro_mei(
    entrada: SolicitacaoEntrada,
    db: Session = Depends(get_db),
):
    nome = entrada.nome_completo.strip()
    email = entrada.email.strip().lower()
    cnpj = normalizar_cnpj(entrada.cnpj)
    telefone = entrada.telefone.strip()
    estabelecimento = entrada.nome_estabelecimento.strip()
    senha = entrada.senha.get_secret_value()

    if (
        len(nome) < 3
        or len(estabelecimento) < 2
        or len(telefone) < 8
    ):
        raise HTTPException(
            status_code=422,
            detail="Dados cadastrais incompletos.",
        )

    if not re.fullmatch(
        r"[^\s@]+@[^\s@]+\.[^\s@]+",
        email,
    ):
        raise HTTPException(
            status_code=422,
            detail="E-mail invalido.",
        )

    if not cnpj_valido(cnpj):
        raise HTTPException(
            status_code=422,
            detail="CNPJ invalido.",
        )

    if not 10 <= len(senha) <= 128:
        raise HTTPException(
            status_code=422,
            detail="A senha deve ter entre 10 e 128 caracteres.",
        )

    usuario_existente = (
        db.query(UsuarioMEI.id)
        .filter(func.lower(UsuarioMEI.email) == email)
        .first()
    )

    pendente = (
        db.query(SolicitacaoCadastroMEI.id)
        .filter(
            SolicitacaoCadastroMEI.status == "pendente",
            or_(
                func.lower(SolicitacaoCadastroMEI.email) == email,
                SolicitacaoCadastroMEI.cnpj == cnpj,
            ),
        )
        .first()
    )

    cnpj_aprovado = (
        db.query(SolicitacaoCadastroMEI.id)
        .filter(
            SolicitacaoCadastroMEI.cnpj == cnpj,
            SolicitacaoCadastroMEI.status == "aprovado",
        )
        .first()
    )

    if usuario_existente or pendente or cnpj_aprovado:
        raise HTTPException(
            status_code=409,
            detail=(
                "Ja existe uma conta ou solicitacao "
                "associada aos dados informados."
            ),
        )

    solicitacao = SolicitacaoCadastroMEI(
        nome_completo=nome,
        email=email,
        cnpj=cnpj,
        telefone=telefone,
        nome_estabelecimento=estabelecimento,
        senha_hash=gerar_hash_senha(senha),
        status="pendente",
    )

    try:
        db.add(solicitacao)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Ja existe uma solicitacao pendente "
                "com os dados informados."
            ),
        ) from None

    except Exception:
        db.rollback()
        raise

    return {
        "mensagem": (
            "Solicitacao recebida. "
            "Aguarde a analise do administrador."
        ),
        "status": "pendente",
    }
