# Sistema MEI ? TCC II

**Sistema inteligente de apoio ? gest?o de microempreendedores individuais**

**Autor:** Raul Ferreira Holanda
**Orientador:** Prof. Me. Ronildo Oliveira da Silva
**Curso:** Sistemas de Informa??o
**Institui??o:** Centro Universit?rio Cat?lica de Quixad? (UniCat?lica)
**Ano:** 2026

## Sobre o projeto

O Sistema MEI ? um prot?tipo acad?mico de aplica??o web
para apoio ? gest?o de microempreendedores individuais.

O sistema integra funcionalidades de gest?o comercial,
controle de estoque, atendimento em linguagem natural
e componentes baseados em agentes de intelig?ncia
artificial.

O trabalho foi desenvolvido no contexto do TCC II:

**Desenvolvimento e Valida??o T?cnica de um Sistema
Baseado em Agentes de Intelig?ncia Artificial para
Apoio ? Gest?o de Microempreendedores Individuais.**

## Objetivo

Desenvolver e validar tecnicamente um prot?tipo que
integre atendimento em linguagem natural e opera??es
comerciais, com mecanismos de valida??o, autentica??o
e isolamento dos registros por estabelecimento.

## Funcionalidades

- Cadastro e gerenciamento de produtos.
- Controle de estoque e estoque m?nimo.
- Consultas ao cat?logo, pre?os e disponibilidade.
- Atendimento em linguagem natural com apoio de IA.
- Solicita??o de esclarecimentos para mensagens incompletas.
- Processamento de pedidos com valida??es comerciais.
- Prote??o contra registros duplicados de compras.
- Autentica??o e controle de sess?es.
- Separa??o de registros entre diferentes estabelecimentos.
- Interfaces administrativas e ?rea p?blica da loja.

As funcionalidades representam o escopo do prot?tipo
desenvolvido, n?o uma plataforma comercial homologada.

## Tecnologias

| Camada | Tecnologia |
| --- | --- |
| Backend | Python, FastAPI |
| Banco de dados | SQLite, SQLAlchemy |
| Valida??o | Pydantic |
| Frontend | React, TypeScript, Vite |
| Intelig?ncia artificial | Modelos de linguagem, CrewAI |
| Testes automatizados | pytest |
| Versionamento | Git e GitHub |

A opera??o dos componentes externos de IA pode exigir
configura??o de credenciais e servi?os espec?ficos.

## Arquitetura

```text
Cliente / Administrador MEI
           |
           v
    Frontend React
           |
           v
       API FastAPI
           |
       +---+----------------+
       |                    |
       v                    v
 Regras comerciais     Componentes de IA
       |                    |
       v                    v
 SQLAlchemy / SQLite   Interpretacao de mensagens
       |
       v
 Produtos, estoque e pedidos
```

A representa??o acima e simplificada.

A interpreta??o de mensagens n?o equivale, por si s?,
? autoriza??o para registrar uma compra. Opera??es
comerciais dependem das regras de valida??o do sistema.

## Estrutura principal

```text
Sistema-MEI/
|-- main.py
|-- database/
|-- security/
|-- crew/
|-- frontend/
|   |-- src/
|   `-- package.json
|-- tests/
|-- requirements.txt
`-- README.md
```

A estrutura pode conter outros m?dulos e arquivos
de apoio, conforme a vers?o do projeto.

## Requisitos de execu??o

- Python compat?vel com as depend?ncias do projeto.
- Node.js e npm compat?veis com o frontend.
- Git.
- Configura??o local das vari?veis de ambiente exigidas.
- Credenciais v?lidas para integra??es externas, quando
  essas funcionalidades forem utilizadas.

Nenhuma credencial deve ser publicada neste reposit?rio.

## Execu??o local ? Windows PowerShell

### 1. Clonar o projeto

```powershell
git clone https://github.com/RaulFH0/Sistema-MEI-TCC-II.git
cd Sistema-MEI-TCC-II
```

### 2. Preparar o ambiente Python

```powershell
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

A instala??o depende das vers?es de Python e das
bibliotecas utilizadas no projeto.

### 3. Configurar as integra??es

Configure as vari?veis de ambiente exigidas pela
aplica??o em seu ambiente local.

N?o copie arquivos com credenciais reais para o GitHub.

### 4. Executar o backend

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

Por padr?o, o servi?o poder? ser acessado em:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

A disponibilidade das rotas depende da configura??o
local e das inicializa??es exigidas pela aplica??o.

### 5. Executar o frontend

Abra outro terminal:

```powershell
cd frontend
npm install
npm run dev
```

O Vite apresentar? no terminal o endere?o local da
interface.

## Testes automatizados

Para executar a su?te completa:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

### Evid?ncia apresentada no TCC II

Na regress?o geral registrada em **19/11/2026**:

| Indicador | Resultado |
| --- | ---: |
| Testes aprovados | 400 |
| Testes com falha | 0 |
| Avisos | 1 |
| Dura??o | 162,88 segundos |

Esses valores pertencem ? execu??o documentada naquela
data. A quantidade de testes e os resultados podem
mudar em vers?es posteriores do c?digo.

A aprova??o dos testes n?o garante aus?ncia total de
defeitos, seguran?a absoluta ou cobertura integral.

## Metodologia acad?mica

A pesquisa possui natureza aplicada, com objetivos
explorat?rios e descritivos.

A avalia??o foi baseada no desenvolvimento do
prot?tipo, testes automatizados e ensaios t?cnicos
em ambientes controlados.

N?o foram realizadas avalia??es de produtividade ou
usabilidade com microempreendedores participantes
nesta etapa.

Portanto, os resultados n?o demonstram ganhos reais
de produtividade, receita ou satisfa??o dos usu?rios.

## Limita??es

- Depend?ncia de servi?os externos para recursos de IA.
- Custo de inicializa??o de componentes inteligentes.
- Limita??es de interpreta??o de mensagens ambiguas.
- Aus?ncia de avalia??o de uso com o p?blico-alvo.
- Aus?ncia de auditoria independente completa de seguran?a.
- Resultados t?cnicos limitados aos cen?rios avaliados.

## Seguran?a e privacidade

Este projeto ? disponibilizado para fins acad?micos.

N?o devem ser versionados:

- Credenciais e chaves de API.
- Senhas, tokens e segredos de autentica??o.
- Bancos de dados contendo registros privados.
- Arquivos `.env` com valores reais.
- Ambientes virtuais e depend?ncias instaladas.
- Backups e arquivos de execu??o locais.

Antes de publicar atualiza??es, verifique tamb?m o
historico de commits, pois o `.gitignore` n?o remove
arquivos sens?veis j? versionados.

## Refer?ncia acad?mica

HOLANDA, Raul Ferreira. **Desenvolvimento e valida??o
t?cnica de um sistema baseado em agentes de intelig?ncia
artificial para apoio ? gest?o de microempreendedores
individuais**. Trabalho de Conclus?o de Curso.
Sistemas de Informa??o, Centro Universit?rio Cat?lica
de Quixad?, Quixad?, 2026.

## Autor

**Raul Ferreira Holanda**

Trabalho de Conclus?o de Curso II ? 2026.

## Observa??o

Este reposit?rio apresenta um prot?tipo desenvolvido
para estudo acad?mico e valida??o t?cnica.

N?o h? declara??o de homologa??o para uso em produ??o
ou garantia de adequa??o a opera??es comerciais reais.
