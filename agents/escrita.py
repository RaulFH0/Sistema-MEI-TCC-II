from crewai import Agent, LLM
from dotenv import load_dotenv
import os

load_dotenv()

def criar_agente_escrita():
    llm = LLM(
        model="groq/openai/gpt-oss-20b",
        api_key=os.getenv("GROQ_API_KEY")
    )

    return Agent(
        role="Especialista em Registro de Pedidos",
        goal="Registrar pedidos confirmados no banco de dados com precisão, "
             "garantindo que todas as informações estejam corretas antes de salvar.",
        backstory=(
            "Você é o responsável pela parte administrativa do comércio. "
            "Registra todos os pedidos com cuidado e atenção aos detalhes. "
            "Nunca registra um pedido sem confirmar que os dados estão completos "
            "e que o estoque foi verificado pelo seu colega responsável pelo estoque."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False
    )