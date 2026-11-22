
import os
import time
import json

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

# Workaround temporario para CrewAI + Groq
import crewai.llms.cache as crew_cache
crew_cache.mark_cache_breakpoint = lambda msg: msg

from crewai import Crew, Task, Process

from agents.triagem import criar_agente_triagem
from agents.inventario import criar_agente_inventario
from agents.escrita import criar_agente_escrita

from rag.retriever import buscar_contexto
from database.models import init_db, SessionLocal
from database import crud
from schemas.pedido import PedidoMultiploCreate
from pydantic import ValidationError
from security.atendimento_conversacional import (
    esclarecimento_triagem,
)


# ============================================================
# ORQUESTRADOR DE ATENDIMENTO - MULTI-MEI
# ============================================================

def processar_pedido(
    mensagem_usuario: str,
    chave_idempotencia: str,
    *,
    estabelecimento_id: int = 1,
) -> dict:

    inicio = time.perf_counter()
    db = None
    resultado_compra = None

    def tempo_decorrido():
        return int(
            (time.perf_counter() - inicio) * 1000
        )

    try:
        # ====================================================
        # ETAPA 0 - VALIDACAO DE ENTRADA
        # ====================================================

        if (
            type(estabelecimento_id) is not int
            or estabelecimento_id < 1
        ):
            raise ValueError(
                "Identificador do estabelecimento invalido."
            )

        if not isinstance(mensagem_usuario, str):
            raise ValueError("Mensagem invalida.")

        if not mensagem_usuario.strip():
            raise ValueError("Mensagem vazia.")

        if not isinstance(chave_idempotencia, str):
            raise ValueError(
                "Chave de idempotencia invalida."
            )

        chave = chave_idempotencia.strip()

        if not 1 <= len(chave) <= 128:
            raise ValueError(
                "Chave de idempotencia invalida."
            )

        init_db()

        # ====================================================
        # ETAPA 1 - CONSULTA ANTECIPADA DE IDEMPOTENCIA
        # ====================================================

        db = SessionLocal()

        compra_existente = (
            crud.consultar_compra_por_mensagem(
                db=db,
                chave_idempotencia=chave,
                mensagem_original=mensagem_usuario,
                estabelecimento_id=estabelecimento_id,
            )
        )

        if compra_existente is not None:
            return {
                "sucesso": True,
                "resultado": compra_existente,
                "resposta": (
                    f"Compra {compra_existente['compra_id']} "
                    "ja registrada anteriormente."
                ),
                "tempo_ms": tempo_decorrido(),
            }

        # Liberar a conexao antes de executar os agentes.
        db.close()
        db = None

        # ====================================================
        # ETAPA 2 - RECUPERACAO DE CONTEXTO RAG ISOLADO
        # ====================================================

        contexto_rag = buscar_contexto(
            mensagem_usuario,
            estabelecimento_id=estabelecimento_id,
        )

        agente_triagem = criar_agente_triagem()

        # ====================================================
        # ETAPA 3 - TRIAGEM
        # ====================================================

        tarefa_triagem = Task(
            description=(
                "Interprete a mensagem do cliente e extraia "
                "o nome e todos os produtos solicitados.\n\n"
                f"Mensagem:\n{mensagem_usuario}\n\n"
                "Retorne exclusivamente JSON no formato:\n"
                '{"cliente_nome":"João","itens":['
                '{"produto_nome":"Arroz","quantidade":2},'
                '{"produto_nome":"Feijão","quantidade":1}'
                ']}\n\n'
                "O JSON é somente um exemplo de estrutura. "
                "Utilize os dados reais da mensagem. "
                "Nao invente informacoes e nao confirme vendas."
            ),
            expected_output=(
                "JSON com cliente_nome e lista de itens."
            ),
            agent=agente_triagem,
        )

        crew_triagem = Crew(
            agents=[agente_triagem],
            tasks=[tarefa_triagem],
            process=Process.sequential,
            verbose=True,
            cache=False,
        )

        saida = crew_triagem.kickoff()
        texto_triagem = saida.tasks_output[0].raw

        try:
            dados = json.loads(texto_triagem)
        except json.JSONDecodeError:
            dados = None

        resposta_esclarecimento = esclarecimento_triagem(
            dados
        )

        if resposta_esclarecimento is not None:
            return {
                "sucesso": False,
                "tipo": "esclarecimento",
                "resposta": resposta_esclarecimento,
                "tempo_ms": tempo_decorrido(),
            }

        try:
            pedido = PedidoMultiploCreate.model_validate(
                dados
            )
        except ValidationError:
            return {
                "sucesso": False,
                "tipo": "esclarecimento",
                "resposta": (
                    "Nao consegui identificar todos os "
                    "dados necessarios para o pedido. "
                    "Informe seu nome, os produtos e "
                    "as quantidades desejadas."
                ),
                "tempo_ms": tempo_decorrido(),
            }

        # ====================================================
        # ETAPA 4 - INVENTARIO CONSULTIVO
        # ====================================================

        agente_inventario = criar_agente_inventario()

        tarefa_inventario = Task(
            description=(
                "Analise o pedido estruturado:\n"
                f"{pedido.model_dump_json()}\n\n"
                f"Contexto do negocio:\n{contexto_rag}\n\n"
                "Este atendimento pertence exclusivamente "
                f"ao estabelecimento ID {estabelecimento_id}. "
                "Identifique possiveis inconsistencias. "
                "Nao confirme estoque nem invente precos. "
                "O banco SQLite fara a verificacao definitiva."
            ),
            expected_output=(
                "Analise consultiva das informacoes do pedido."
            ),
            agent=agente_inventario,
        )

        crew_inventario = Crew(
            agents=[agente_inventario],
            tasks=[tarefa_inventario],
            process=Process.sequential,
            verbose=True,
            cache=False,
        )

        crew_inventario.kickoff()

        # ====================================================
        # ETAPA 5 - PERSISTENCIA REAL DA COMPRA MULTI-MEI
        # ====================================================

        db = SessionLocal()

        resultado_compra = crud.registrar_compra_segura(
            db=db,
            cliente_nome=pedido.cliente_nome,
            itens=[
                item.model_dump()
                for item in pedido.itens
            ],
            chave_idempotencia=chave,
            mensagem_original=mensagem_usuario,
            estabelecimento_id=estabelecimento_id,
        )

        # O CRUD retorna somente apos o commit.
        # A compra ja esta persistida neste ponto.

        # ====================================================
        # ETAPA 6 - CONFIRMACAO AO CLIENTE
        # ====================================================

        resumo = (
            f"Compra {resultado_compra['compra_id']} "
            f"registrada para {pedido.cliente_nome}. "
            f"Valor total: "
            f"R$ {resultado_compra['valor_total']:.2f}."
        )

        # Nao executar novamente o agente de escrita
        # se a requisicao ja foi registrada.
        if not resultado_compra["requisicao_repetida"]:
            try:
                agente_escrita = criar_agente_escrita()

                tarefa_escrita = Task(
                    description=(
                        "Escreva uma mensagem curta de confirmacao "
                        "de uma compra ja registrada.\n\n"
                        f"Dados: {json.dumps(resultado_compra, ensure_ascii=False)}\n\n"
                        "Nao modifique valores nem quantidades. "
                        "Nao execute operacoes no banco."
                    ),
                    expected_output=(
                        "Mensagem curta em portugues."
                    ),
                    agent=agente_escrita,
                )

                crew_escrita = Crew(
                    agents=[agente_escrita],
                    tasks=[tarefa_escrita],
                    process=Process.sequential,
                    verbose=True,
                    cache=False,
                )

                crew_escrita.kickoff()

                # A resposta oficial continua sendo o resumo
                # deterministico produzido com dados do banco.

            except Exception:
                # Falha na redacao nao cancela compra gravada.
                pass

        # ====================================================
        # ETAPA 7 - REGISTRO DE LOG
        # ====================================================

        try:
            crud.registrar_log(
                db=db,
                acao=(
                    "compra_repetida"
                    if resultado_compra["requisicao_repetida"]
                    else "compra_confirmada"
                ),
                entrada=mensagem_usuario,
                resposta=json.dumps(
                    resultado_compra,
                    ensure_ascii=False,
                ),
                tempo_ms=tempo_decorrido(),
                sucesso="sim",
            )

        except Exception:
            db.rollback()

        return {
            "sucesso": True,
            "resultado": resultado_compra,
            "resposta": resumo,
            "tempo_ms": tempo_decorrido(),
        }

    except Exception as erro:
        if db is not None:
            db.rollback()

        # Se ja houve commit, nao informar que
        # a compra falhou.
        if resultado_compra is not None:
            return {
                "sucesso": True,
                "resultado": resultado_compra,
                "resposta": "Compra registrada com sucesso.",
                "tempo_ms": tempo_decorrido(),
            }

        return {
            "sucesso": False,
            "erro": str(erro),
            "tempo_ms": tempo_decorrido(),
        }

    finally:
        if db is not None:
            db.close()
