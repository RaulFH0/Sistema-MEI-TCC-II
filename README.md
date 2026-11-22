# Sistema MEI — TCC II

**Sistema inteligente de apoio à gestão de microempreendedores individuais**

**Autor:** Raul Ferreira Holanda

**Orientador:** Prof. Me. Ronildo Oliveira da Silva

**Curso:** Sistemas de Informação

**Instituição:** Centro Universitário Católica de Quixadá (UniCatólica)

**Ano:** 2026

## Sobre o projeto

O Sistema MEI é um protótipo acadêmico de aplicação web desenvolvido para apoiar a gestão de microempreendedores individuais (MEIs).

A aplicação integra funcionalidades de gestão comercial, controle de estoque, atendimento em linguagem natural e componentes baseados em agentes de inteligência artificial.

### Título do TCC II

**Desenvolvimento e Validação Técnica de um Sistema Baseado em Agentes de Inteligência Artificial para Apoio à Gestão de Microempreendedores Individuais**

## Objetivo

Desenvolver e validar tecnicamente um protótipo web que integre atendimento em linguagem natural e operações comerciais, com mecanismos de validação, autenticação e isolamento dos registros por estabelecimento.

## Funcionalidades

- Cadastro, consulta e gerenciamento de produtos.
- Controle de estoque e estoque mínimo.
- Consulta de catálogo, preços e disponibilidade.
- Atendimento em linguagem natural com apoio de IA.
- Tratamento de solicitações incompletas e ambíguas.
- Registro de pedidos e compras com validações comerciais.
- Proteção contra registros duplicados.
- Autenticação e gerenciamento de sessões.
- Isolamento de informações entre estabelecimentos.
- Interfaces administrativas e área pública da loja.

As funcionalidades fazem parte de um protótipo acadêmico e não representam homologação para uso comercial em produção.

## Tecnologias utilizadas

| Componente | Tecnologias |
| --- | --- |
| Backend | Python e FastAPI |
| Banco de dados | SQLite e SQLAlchemy |
| Validação de dados | Pydantic |
| Frontend | React, TypeScript e Vite |
| Inteligência artificial | Modelos de linguagem e CrewAI |
| Testes | pytest |
| Versionamento | Git e GitHub |

## Arquitetura simplificada

```text
Usuário / Administrador MEI
           |
           v
     Interface React
           |
           v
       API FastAPI
           |
    +------+-----------+
    |                  |
    v                  v
Regras comerciais   Componentes de IA
    |                  |
    v                  v
SQLAlchemy/SQLite  Interpretação
    |              de mensagens
    v
Produtos, estoque
e pedidos
```

As operações comerciais dependem das regras de validação do sistema. A interpretação de uma mensagem pela IA não constitui, isoladamente, autorização para registrar uma compra.

## Requisitos para execução

- Python compatível com as dependências.
- Node.js e npm para a interface.
- Git para clonagem e versionamento.
- Configuração local das variáveis de ambiente necessárias.
- Credenciais válidas para as integrações externas utilizadas.

## Instalação e execução

### 1. Clonar o repositório

```powershell
git clone https://github.com/RaulFH0/Sistema-MEI-TCC-II.git
cd Sistema-MEI-TCC-II
```

### 2. Criar o ambiente Python

```powershell
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Configurar o ambiente

Configure localmente as variáveis de ambiente exigidas pela aplicação e pelos serviços externos de inteligência artificial.

**Nunca publique chaves de API, senhas ou tokens reais.**

### 4. Iniciar o backend

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

Endereços locais esperados:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

### 5. Iniciar o frontend

Em outro terminal:

```powershell
cd frontend
npm install
npm run dev
```

O endereço local da interface será exibido pelo Vite.

## Testes automatizados

Execute a suíte com:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

### Resultados da versão publicada

Na execução de 22 de novembro de 2026, antes da publicação do commit `c24f124`, foram obtidos:

| Indicador | Resultado |
| --- | ---: |
| Testes aprovados | 400 |
| Testes com falha | 0 |
| Avisos | 1 |
| Duração da regressão | 97,38 segundos |
| Compilação do frontend | Aprovada |

O aviso registrado está relacionado à inspeção de um índice do banco de dados SQLite pelo SQLAlchemy.

Os resultados representam a execução registrada, não uma garantia de ausência de defeitos ou de cobertura integral do código.

**Versão de referência:** `c24f124`

## Metodologia acadêmica

A pesquisa é aplicada, exploratória e descritiva, concentrada no desenvolvimento e na validação técnica do protótipo.

Foram utilizadas verificações automatizadas e ensaios técnicos em cenários controlados.

Não foram realizadas avaliações de produtividade ou usabilidade com microempreendedores participantes nesta etapa.

Portanto, os resultados não comprovam aumento de produtividade, receita ou satisfação de usuários reais.

## Limitações

- Dependência de serviços externos para funcionalidades de IA.
- Custo de inicialização de componentes inteligentes.
- Possíveis dificuldades na interpretação de mensagens ambíguas.
- Ausência de validação com microempreendedores participantes.
- Ausência de auditoria independente e abrangente de segurança.
- Resultados restritos aos cenários técnicos avaliados.

## Segurança e privacidade

Este projeto é disponibilizado para fins acadêmicos.

Não devem ser publicados:

- Arquivos `.env` com credenciais reais.
- Chaves de API, senhas e tokens.
- Bancos de dados com informações privadas.
- Ambientes virtuais Python.
- Dependências instaladas do frontend.
- Backups contendo informações sensíveis.

O `.gitignore` ajuda a evitar novos arquivos indevidos, mas não remove informações já existentes no histórico do Git.

## Referência acadêmica

HOLANDA, Raul Ferreira. **Desenvolvimento e validação técnica de um sistema baseado em agentes de inteligência artificial para apoio à gestão de microempreendedores individuais**. Trabalho de Conclusão de Curso. Sistemas de Informação, Centro Universitário Católica de Quixadá, Quixadá, 2026.

## Autor

**Raul Ferreira Holanda**

Trabalho de Conclusão de Curso II — UniCatólica — 2026.

## Observação

O Sistema MEI é um protótipo de pesquisa. Sua disponibilização não implica homologação, certificação de segurança ou garantia de adequação para operações comerciais em produção.
