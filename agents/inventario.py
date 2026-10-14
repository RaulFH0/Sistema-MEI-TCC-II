from crewai import Agent, LLM
from dotenv import load_dotenv
import os

load_dotenv()

def criar_agente_inventario():
    llm = LLM(
        model="groq/openai/gpt-oss-20b",
        api_key=os.getenv("GROQ_API_KEY")
    )

    return Agent(
        role="Especialista em Consulta de Estoque",
        goal="Verificar se o produto solicitado está disponível em estoque "
             "na quantidade pedida e informar o preço total do pedido.",
        backstory=(
            "Você é o responsável pelo estoque do comércio. "
            "Conhece todos os produtos, seus preços e quantidades disponíveis. "
            "Antes de confirmar qualquer pedido, sempre verifica se há estoque suficiente. "
            "Quando o estoque está baixo, avisa o dono do negócio."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False
    )