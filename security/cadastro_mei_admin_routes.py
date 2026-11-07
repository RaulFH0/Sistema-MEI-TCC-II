from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import get_db
from database.contas_models import Estabelecimento, UsuarioMEI
from database.solicitacoes_models import SolicitacaoCadastroMEI
from database.contas_models import agora_utc

from security.routes import (
    exigir_admin,
    exigir_admin_escrita,
)


router = APIRouter(
    prefix="/admin/solicitacoes-mei",
    tags=["Administracao de cadastros MEI"],
)


class DecisaoRejeicao(BaseModel):
    observacao: str = Field(
        default="",
        max_length=500,
    )


def _resumo(solicitacao):
    # Nunca devolver senha_hash.
    return {
        "id": solicitacao.id,
        "nome_completo": solicitacao.nome_completo,
        "email": solicitacao.email,
        "cnpj": solicitacao.cnpj,
        "telefone": solicitacao.telefone,
        "nome_estabelecimento": solicitacao.nome_estabelecimento,
        "status": solicitacao.status,
        "criado_em": solicitacao.criado_em,
        "analisado_em": solicitacao.analisado_em,
        "analisado_por": solicitacao.analisado_por,
        "observacao_admin": solicitacao.observacao_admin,
    }


@router.get("")
def listar_solicitacoes_mei(
    status: str = "pendente",
    db: Session = Depends(get_db),
    administrador: str = Depends(exigir_admin),
):
    if status not in (
        "pendente",
        "aprovado",
        "rejeitado",
    ):
        raise HTTPException(
            status_code=422,
            detail="Status de consulta invalido.",
        )

    solicitacoes = (
        db.query(SolicitacaoCadastroMEI)
        .filter(SolicitacaoCadastroMEI.status == status)
        .order_by(
            SolicitacaoCadastroMEI.criado_em.asc(),
            SolicitacaoCadastroMEI.id.asc(),
        )
        .all()
    )

    return [_resumo(item) for item in solicitacoes]


@router.post("/{solicitacao_id}/aprovar")
def aprovar_solicitacao_mei(
    solicitacao_id: int,
    db: Session = Depends(get_db),
    administrador: str = Depends(exigir_admin_escrita),
):
    solicitacao = db.get(
        SolicitacaoCadastroMEI,
        solicitacao_id,
    )

    if solicitacao is None:
        raise HTTPException(
            status_code=404,
            detail="Solicitacao nao encontrada.",
        )

    if solicitacao.status != "pendente":
        raise HTTPException(
            status_code=409,
            detail="Solicitacao ja analisada.",
        )

    email = solicitacao.email.strip().lower()

    if (
        db.query(UsuarioMEI.id)
        .filter(UsuarioMEI.email == email)
        .first()
    ):
        raise HTTPException(
            status_code=409,
            detail="Ja existe uma conta com esse e-mail.",
        )

    aprovado_mesmo_cnpj = (
        db.query(SolicitacaoCadastroMEI.id)
        .filter(
            SolicitacaoCadastroMEI.cnpj == solicitacao.cnpj,
            SolicitacaoCadastroMEI.status == "aprovado",
            SolicitacaoCadastroMEI.id != solicitacao_id,
        )
        .first()
    )

    if aprovado_mesmo_cnpj:
        raise HTTPException(
            status_code=409,
            detail="CNPJ ja aprovado anteriormente.",
        )

    slug = f"mei-solicitacao-{solicitacao_id}"

    if (
        db.query(Estabelecimento.id)
        .filter(Estabelecimento.slug == slug)
        .first()
    ):
        raise HTTPException(
            status_code=409,
            detail="Identificador de loja indisponivel.",
        )

    try:
        # A transicao condicional evita aprovar a mesma
        # solicitacao duas vezes em requisicoes concorrentes.
        atualizados = (
            db.query(SolicitacaoCadastroMEI)
            .filter(
                SolicitacaoCadastroMEI.id == solicitacao_id,
                SolicitacaoCadastroMEI.status == "pendente",
            )
            .update(
                {
                    "status": "aprovado",
                    "analisado_em": agora_utc(),
                    "analisado_por": administrador,
                },
                synchronize_session=False,
            )
        )

        if atualizados != 1:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Solicitacao ja analisada.",
            )

        loja = Estabelecimento(
            nome=solicitacao.nome_estabelecimento,
            slug=slug,
            ativo=True,
        )

        db.add(loja)
        db.flush()

        usuario = UsuarioMEI(
            estabelecimento_id=loja.id,
            nome=solicitacao.nome_completo,
            email=email,
            senha_hash=solicitacao.senha_hash,
            ativo=True,
        )

        db.add(usuario)
        db.flush()
        db.commit()

    except HTTPException:
        raise

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflito nos dados do cadastro.",
        ) from None

    except Exception:
        db.rollback()
        raise

    return {
        "mensagem": "Cadastro aprovado.",
        "solicitacao_id": solicitacao_id,
        "estabelecimento_id": loja.id,
        "usuario_mei_id": usuario.id,
        "slug": slug,
    }


@router.post("/{solicitacao_id}/rejeitar")
def rejeitar_solicitacao_mei(
    solicitacao_id: int,
    entrada: DecisaoRejeicao,
    db: Session = Depends(get_db),
    administrador: str = Depends(exigir_admin_escrita),
):
    solicitacao = db.get(
        SolicitacaoCadastroMEI,
        solicitacao_id,
    )

    if solicitacao is None:
        raise HTTPException(
            status_code=404,
            detail="Solicitacao nao encontrada.",
        )

    if solicitacao.status != "pendente":
        raise HTTPException(
            status_code=409,
            detail="Solicitacao ja analisada.",
        )

    try:
        atualizados = (
            db.query(SolicitacaoCadastroMEI)
            .filter(
                SolicitacaoCadastroMEI.id == solicitacao_id,
                SolicitacaoCadastroMEI.status == "pendente",
            )
            .update(
                {
                    "status": "rejeitado",
                    "analisado_em": agora_utc(),
                    "analisado_por": administrador,
                    "observacao_admin": entrada.observacao.strip(),
                },
                synchronize_session=False,
            )
        )

        if atualizados != 1:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Solicitacao ja analisada.",
            )

        db.commit()

    except HTTPException:
        raise

    except Exception:
        db.rollback()
        raise

    return {
        "mensagem": "Solicitacao rejeitada.",
        "solicitacao_id": solicitacao_id,
        "status": "rejeitado",
    }
