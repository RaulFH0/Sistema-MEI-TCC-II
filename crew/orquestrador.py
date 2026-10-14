
import os
import time
import json

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

# Compatibilidade temporária CrewAI + Groq
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


def processar_pedido(mensagem_usuario: str) -> dict:
    inicio = time.time()

    db = None
    pedido_persistido = False

    try:
        init_db()

        if not mensagem_usuario.strip():
            raise ValueError("Mensagem não pode ser vazia.")

        # ====================================================
        # 1. CONTEXTO RAG
        # ====================================================

        contexto_rag = buscar_contexto(mensagem_usuario)

        # ====================================================
        # 2. AGENTES
        # ====================================================

        agente_triagem = criar_agente_triagem()
        agente_inventario = criar_agente_inventario()
        agente_escrita = criar_agente_escrita()

        # ====================================================
        # 3. TRIAGEM
        # ====================================================

        tarefa_triagem = Task(
            description=(
                "Extraia fielmente os dados do pedido.\n\n"
                f"Mensagem: {mensagem_usuario}\n\n"
                "Retorne somente JSON com esta estrutura:\n"
                '{'
                '"cliente_nome": "João", '
                '"itens": ['
                '{"produto_nome": "Arroz", "quantidade": 2}, '
                '{"produto_nome": "Feijão", "quantidade": 1}'
                ']'
                '}\n\n'
                "O JSON acima é apenas um exemplo de formato. "
                "Use exclusivamente os dados da mensagem real. "
                "Não invente informações. "
                "Não confirme vendas."
            ),
            expected_output=(
                "JSON válido contendo cliente_nome e itens."
            ),
            agent=agente_triagem
        )

        crew_triagem = Crew(
            agents=[agente_triagem],
            tasks=[tarefa_triagem],
            process=Process.sequential,
            verbose=True,
            cache=False
        )

        resultado_triagem = crew_triagem.kickoff()

        # ====================================================
        # 4. VALIDAÇÃO PYDANTIC
        # ====================================================

        try:
            dados = json.loads(
                resultado_triagem.tasks_output[0].raw
            )
        except (json.JSONDecodeError, IndexError) as exc:
            raise ValueError(
                "Triagem não retornou JSON válido."
            ) from exc

        pedido = PedidoMultiploCreate.model_validate(dados)

        # ====================================================
        # 5. AGENTE DE INVENTÁRIO
        # ====================================================
        # Análise consultiva. Não autoriza vendas.
        # A verificação definitiva ocorre no SQLite.

        tarefa_inventario = Task(
            description=(
                "Analise o pedido estruturado a seguir:\n"
                f"{pedido.model_dump_json()}\n\n"
                f"Contexto RAG:\n{contexto_rag}\n\n"
                "Identifique possíveis inconsistências "
                "ou informações ausentes. "
                "Não invente preços nem quantidades. "
                "Não confirme disponibilidade. "
                "A verificação definitiva será feita "
                "pelo banco de dados."
            ),
            expected_output=(
                "Relatório consultivo sobre o pedido."
            ),
            agent=agente_inventario
        )

        crew_inventario = Crew(
            agents=[agente_inventario],
            tasks=[tarefa_inventario],
            process=Process.sequential,
            verbose=True,
            cache=False
        )

        crew_inventario.kickoff()

        # ====================================================
        # 6. REGISTRO REAL NO SQLITE
        # ====================================================

        db = SessionLocal()

        resultado_pedido = crud.registrar_pedido_seguro(
            db=db,
            cliente_nome=pedido.cliente_nome,
            itens=[
                item.model_dump()
                for item in pedido.itens
            ]
        )

        # O commit ocorreu dentro da função CRUD.
        pedido_persistido = True

        # ====================================================
        # 7. ESCRITA APÓS O REGISTRO
        # ====================================================

        resumo_padrao = (
            f"Pedido registrado para "
            f"{pedido.cliente_nome}. "
            f"Valor total: "
            f"R$ {resultado_pedido['valor_total']:.2f}."
        )

        resumo_final = resumo_padrao

        try:
            tarefa_escrita = Task(
                description=(
                    "Produza uma mensagem curta e clara "
                    "para o cliente sobre um pedido "
                    "JÁ REGISTRADO no banco.\n\n"
                    "Dados confirmados:\n"
                    f"{json.dumps(resultado_pedido, ensure_ascii=False)}\n\n"
                    "Não altere preços, quantidades "
                    "ou informações do pedido. "
                    "Não solicite nova gravação."
                ),
                expected_output=(
                    "Mensagem de confirmação em português."
                ),
                agent=agente_escrita
            )

            crew_escrita = Crew(
                agents=[agente_escrita],
                tasks=[tarefa_escrita],
                process=Process.sequential,
                verbose=True,
                cache=False
            )

            resultado_escrita = crew_escrita.kickoff()

            if resultado_escrita.tasks_output:
                texto = resultado_escrita.tasks_output[0].raw
                if texto and texto.strip():
                    # Texto gerado não substitui os dados
                    # estruturados e confirmados pelo banco.
                    resumo_final = texto.strip()

        except Exception:
            # Uma falha de escrita não desfaz uma venda
            # que já foi gravada com sucesso.
            resumo_final = resumo_padrao

        # ====================================================
        # 8. LOG
        # ====================================================

        tempo_ms = int((time.time() - inicio) * 1000)

        try:
            crud.registrar_log(
                db=db,
                acao="pedido_completo",
                entrada=mensagem_usuario,
                resposta=json.dumps(
                    resultado_pedido,
                    ensure_ascii=False
                ),
                tempo_ms=tempo_ms,
                sucesso="sim"
            )
        except Exception:
            db.rollback()
            # O pedido já foi confirmado no banco.
            # Falha de log não altera seu resultado.

        return {
            "sucesso": True,
            "resultado": resultado_pedido,
            "resposta": resumo_final,
            "tempo_ms": tempo_ms
        }

    except Exception as e:
        tempo_ms = int((time.time() - inicio) * 1000)

        if db is not None:
            db.rollback()

        # Não registrar como venda concluída se o
        # commit da operação ainda não ocorreu.
        return {
            "sucesso": pedido_persistido,
            "erro": str(e),
            "tempo_ms": tempo_ms
        }

    finally:
        if db is not None:
            db.close()
