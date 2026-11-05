import { useCallback, useEffect, useMemo, useState } from 'react'

import { listarProdutos, type Produto } from './services/api'

import AtendimentoIA from './components/AtendimentoIA'
import HistoricoCompras from './components/HistoricoCompras'
import GerenciarProdutos from './components/GerenciarProdutos'
import LoginAdmin from './components/LoginAdmin'
import LojaCliente from './components/LojaCliente'

import {
  consultarSessao,
  realizarLogout,
  type SessaoAdmin,
} from './services/auth'

import './App.css'

// ============================================================
// TIPOS
// ============================================================

type Pagina = 'estoque' | 'atendimento' | 'historico'

type SituacaoEstoque = 'esgotado' | 'baixo' | 'normal'

// ============================================================
// FORMATACAO DE MOEDA
// ============================================================

const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

// ============================================================
// SITUACAO DO ESTOQUE
// ============================================================

function situacaoEstoque(produto: Produto): SituacaoEstoque {
  if (produto.quantidade === 0) {
    return 'esgotado'
  }

  if (
    produto.estoque_minimo > 0 &&
    produto.quantidade <= produto.estoque_minimo
  ) {
    return 'baixo'
  }

  return 'normal'
}

// ============================================================
// COMPONENTE PRINCIPAL
// ============================================================

function PainelAdmin() {
  // ----------------------------------------------------------
  // NAVEGACAO
  // ----------------------------------------------------------

  const [pagina, setPagina] = useState<Pagina>('estoque')

  // ----------------------------------------------------------
  // AUTENTICACAO ADMINISTRATIVA
  // ----------------------------------------------------------

  const [sessao, setSessao] = useState<SessaoAdmin | null>(
    null
  )

  const [verificandoSessao, setVerificandoSessao] =
    useState(true)

  const [encerrandoSessao, setEncerrandoSessao] =
    useState(false)

  const [erroAutenticacao, setErroAutenticacao] =
    useState('')

  // ----------------------------------------------------------
  // ESTADOS DO ESTOQUE
  // ----------------------------------------------------------

  const [produtos, setProdutos] = useState<Produto[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [busca, setBusca] = useState('')
  const [somenteAlertas, setSomenteAlertas] = useState(false)

  // ==========================================================
  // VERIFICAR SESSAO AO INICIAR A APLICACAO
  // ==========================================================

  useEffect(() => {
    let ativo = true

    async function verificarAutenticacao() {
      try {
        const resultado = await consultarSessao()

        if (ativo) {
          setSessao(resultado)
          setErroAutenticacao('')
        }
      } catch (falha) {
        if (ativo) {
          setErroAutenticacao(
            falha instanceof Error
              ? falha.message
              : 'Erro ao verificar autenticação.'
          )
        }
      } finally {
        if (ativo) {
          setVerificandoSessao(false)
        }
      }
    }

    void verificarAutenticacao()

    return () => {
      ativo = false
    }
  }, [])

  // ==========================================================
  // ENCERRAR SESSAO ADMINISTRATIVA
  // ==========================================================

  async function sairDoPainel() {
    if (encerrandoSessao) {
      return
    }

    setEncerrandoSessao(true)
    setErroAutenticacao('')

    try {
      await realizarLogout()

      setSessao(null)
      setPagina('estoque')
      setProdutos([])
      setBusca('')
      setSomenteAlertas(false)
      setErro('')
    } catch (falha) {
      setErroAutenticacao(
        falha instanceof Error
          ? falha.message
          : 'Não foi possível encerrar a sessão.'
      )
    } finally {
      setEncerrandoSessao(false)
    }
  }

  // ==========================================================
  // CARREGAR PRODUTOS
  // ==========================================================

  const carregarProdutos = useCallback(async () => {
    setCarregando(true)
    setErro('')

    try {
      const dados = await listarProdutos()
      setProdutos(dados)
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : 'Erro ao carregar produtos.'
      )
    } finally {
      setCarregando(false)
    }
  }, [])

  // ==========================================================
  // ATUALIZAR ESTOQUE AO ENTRAR NO PAINEL
  // ==========================================================

  useEffect(() => {
    if (sessao && pagina === 'estoque') {
      void carregarProdutos()
    }
  }, [sessao, pagina, carregarProdutos])

  // ==========================================================
  // INDICADORES DO ESTOQUE
  // ==========================================================

  const totalUnidades = produtos.reduce(
    (total, produto) => total + produto.quantidade,
    0
  )

  const produtosSemEstoque = produtos.filter(
    (produto) => situacaoEstoque(produto) === 'esgotado'
  ).length

  const produtosEstoqueBaixo = produtos.filter(
    (produto) => situacaoEstoque(produto) === 'baixo'
  ).length

  const totalAlertas =
    produtosSemEstoque + produtosEstoqueBaixo

  // ==========================================================
  // FILTRAGEM DOS PRODUTOS
  // ==========================================================

  const produtosFiltrados = useMemo(() => {
    const termo = busca.trim().toLocaleLowerCase('pt-BR')

    return produtos.filter((produto) => {
      const correspondeBusca =
        `${produto.nome} ${produto.categoria ?? ''}`
          .toLocaleLowerCase('pt-BR')
          .includes(termo)

      const correspondeAlerta =
        !somenteAlertas ||
        situacaoEstoque(produto) !== 'normal'

      return correspondeBusca && correspondeAlerta
    })
  }, [produtos, busca, somenteAlertas])

  // ==========================================================
  // TELA DE VERIFICACAO DE SESSAO
  // ==========================================================

  if (verificandoSessao) {
    return (
      <div className="login-page" role="status">
        <p>Verificando sessão administrativa...</p>
      </div>
    )
  }

  // ==========================================================
  // TELA DE LOGIN
  // ==========================================================

  if (!sessao) {
    return (
      <LoginAdmin
        aoAutenticar={(novaSessao) => {
          setSessao(novaSessao)
          setErroAutenticacao('')
          setPagina('estoque')
        }}
      />
    )
  }

  // ==========================================================
  // PAINEL ADMINISTRATIVO AUTENTICADO
  // ==========================================================

  return (
    <div className="app">

      {/* =====================================================
          MENU LATERAL
      ===================================================== */}

      <aside className="sidebar">

        <div className="brand">
          <div className="brand-icon">M</div>

          <div>
            <strong>Sistema MEI</strong>
            <span>Gestão inteligente</span>
          </div>
        </div>

        {/* ---------------------------------------------------
            NAVEGACAO
        --------------------------------------------------- */}

        <nav
          className="navigation"
          aria-label="Menu principal"
        >
          <button
            type="button"
            className={`nav-item ${
              pagina === 'estoque' ? 'active' : ''
            }`}
            onClick={() => setPagina('estoque')}
            aria-current={
              pagina === 'estoque' ? 'page' : undefined
            }
          >
            ▦ Painel de estoque
          </button>

          <button
            type="button"
            className={`nav-item ${
              pagina === 'atendimento' ? 'active' : ''
            }`}
            onClick={() => setPagina('atendimento')}
            aria-current={
              pagina === 'atendimento' ? 'page' : undefined
            }
          >
            ◉ Atendimento IA
          </button>

          <button
            type="button"
            className={`nav-item ${
              pagina === 'historico' ? 'active' : ''
            }`}
            onClick={() => setPagina('historico')}
            aria-current={
              pagina === 'historico' ? 'page' : undefined
            }
          >
            ▤ Histórico de compras
          </button>
        </nav>

        {/* ---------------------------------------------------
            USUARIO AUTENTICADO E LOGOUT
        --------------------------------------------------- */}

        <div className="sidebar-footer">

          <div style={{ marginBottom: 12 }}>
            <strong>Administrador</strong>

            <p style={{ margin: '4px 0' }}>
              {sessao.usuario}
            </p>
          </div>

          {erroAutenticacao && (
            <p role="alert">
              {erroAutenticacao}
            </p>
          )}

          <button
            type="button"
            onClick={() => void sairDoPainel()}
            disabled={encerrandoSessao}
            style={{
              width: '100%',
              padding: '10px',
              cursor: encerrandoSessao
                ? 'not-allowed'
                : 'pointer',
              borderRadius: '8px',
            }}
          >
            {encerrandoSessao
              ? 'Saindo...'
              : 'Sair do painel'}
          </button>

          <p style={{ marginTop: 16 }}>
            Protótipo acadêmico — TCC II
          </p>

        </div>

      </aside>

      {/* =====================================================
          CONTEUDO PRINCIPAL
      ===================================================== */}

      <main className="main">

        {pagina === 'historico' ? (

          <HistoricoCompras />

        ) : pagina === 'atendimento' ? (

          <AtendimentoIA />

        ) : (

          <>
            {/* ================================================
                CABECALHO DO ESTOQUE
            ================================================ */}

            <header className="page-header">

              <div>
                <p className="eyebrow">
                  VISÃO GERAL
                </p>

                <h1>Produtos e estoque</h1>

                <p className="subtitle">
                  Controle os produtos e acompanhe as necessidades
                  de reposição do empreendimento.
                </p>
              </div>

              <button
                type="button"
                className="refresh-button"
                onClick={() => void carregarProdutos()}
                disabled={carregando}
              >
                ↻ Atualizar
              </button>

            </header>

            {/* ================================================
                INDICADORES DO ESTOQUE
            ================================================ */}

            <section
              className="stats"
              aria-label="Indicadores de estoque"
            >

              <article className="stat-card">
                <span>Produtos cadastrados</span>

                <strong>
                  {produtos.length}
                </strong>

                <small>Tipos de produtos</small>
              </article>

              <article className="stat-card">
                <span>Unidades em estoque</span>

                <strong>
                  {totalUnidades}
                </strong>

                <small>Total disponível</small>
              </article>

              <article className="stat-card">
                <span>Produtos sem estoque</span>

                <strong>
                  {produtosSemEstoque}
                </strong>

                <small>Quantidade zerada</small>
              </article>

              <article className="stat-card">
                <span>Estoque baixo</span>

                <strong>
                  {produtosEstoqueBaixo}
                </strong>

                <small>
                  Produtos que precisam de reposição
                </small>
              </article>

            </section>

            {/* ================================================
                ALERTAS DE ESTOQUE
            ================================================ */}

            {totalAlertas > 0 && !erro && (
              <div
                className="estoque-alerta"
                role="status"
              >
                <strong>
                  Atenção: {totalAlertas}{' '}

                  {totalAlertas === 1
                    ? 'produto precisa'
                    : 'produtos precisam'}{' '}

                  de atenção.
                </strong>

                <span>
                  {produtosEstoqueBaixo} com estoque baixo e{' '}
                  {produtosSemEstoque} sem estoque.
                </span>
              </div>
            )}

            {/* ================================================
                LISTAGEM DO INVENTARIO
            ================================================ */}

            <section className="content-card">

              <div className="section-header">

                <div>
                  <h2>Inventário</h2>

                  <p>
                    Consulte quantidades, preços e limites mínimos.
                  </p>
                </div>

                <input
                  type="search"
                  placeholder="Pesquisar produto..."
                  aria-label="Pesquisar produto"
                  value={busca}
                  onChange={(evento) =>
                    setBusca(evento.target.value)
                  }
                />

              </div>

              {/* ---------------------------------------------
                  FILTRO DE ALERTAS
              --------------------------------------------- */}

              <label className="estoque-filtro">

                <input
                  type="checkbox"
                  checked={somenteAlertas}
                  onChange={(evento) =>
                    setSomenteAlertas(evento.target.checked)
                  }
                />

                Mostrar somente produtos que precisam de atenção

              </label>

              {/* ---------------------------------------------
                  MENSAGENS DE ERRO
              --------------------------------------------- */}

              {erro && (
                <div
                  className="error-message"
                  role="alert"
                >
                  {erro}

                  <p>
                    Verifique se a FastAPI está em execução
                    na porta 8000.
                  </p>
                </div>
              )}

              {/* ---------------------------------------------
                  ESTADOS DA LISTAGEM
              --------------------------------------------- */}

              {carregando ? (

                <p className="empty-message">
                  Carregando produtos...
                </p>

              ) : erro ? (

                <p className="empty-message">
                  Não foi possível consultar o estoque.
                </p>

              ) : produtosFiltrados.length === 0 ? (

                <p className="empty-message">
                  Nenhum produto encontrado para os filtros atuais.
                </p>

              ) : (

                <div className="table-wrapper">

                  <table>

                    <thead>
                      <tr>
                        <th>Produto</th>
                        <th>Categoria</th>
                        <th>Preço</th>
                        <th>Estoque atual</th>
                        <th>Estoque mínimo</th>
                        <th>Situação</th>
                      </tr>
                    </thead>

                    <tbody>

                      {produtosFiltrados.map((produto) => {

                        const situacao =
                          situacaoEstoque(produto)

                        return (
                          <tr
                            key={produto.id}
                            className={
                              situacao === 'normal'
                                ? ''
                                : 'estoque-linha-alerta'
                            }
                          >
                            <td className="product-name">
                              {produto.nome}
                            </td>

                            <td>
                              {produto.categoria ||
                                'Não informada'}
                            </td>

                            <td>
                              {moeda.format(produto.preco)}
                            </td>

                            <td>
                              {produto.quantidade}
                            </td>

                            <td>
                              {produto.estoque_minimo}
                            </td>

                            <td>
                              <span
                                className={`status ${
                                  situacao === 'esgotado'
                                    ? 'empty'
                                    : situacao === 'baixo'
                                      ? 'low'
                                      : 'available'
                                }`}
                              >
                                {situacao === 'esgotado'
                                  ? 'Sem estoque'
                                  : situacao === 'baixo'
                                    ? 'Estoque baixo'
                                    : 'Disponível'}
                              </span>
                            </td>

                          </tr>
                        )
                      })}

                    </tbody>

                  </table>

                </div>

              )}

            </section>

            {/* ================================================
                GERENCIAMENTO DE PRODUTOS
            ================================================ */}

            <GerenciarProdutos
              produtos={produtos}
              aoAtualizar={carregarProdutos}
            />

          </>

        )}

      </main>

    </div>
  )
}


/* ============================================================
   NAVEGACAO PUBLICA MULTI-MEI
   ============================================================ */


function App() {
  // ============================================================
  // IDENTIFICACAO DO CAMINHO
  // ============================================================

  // pathname nao inclui parametros como ?utm_source=...
  // Remove barras extras no final do endereco.
  const caminho =
    window.location.pathname.replace(/\/+$/, '') || '/'

  const partes = caminho
    .split('/')
    .filter(Boolean)

  // ============================================================
  // PAINEL ADMINISTRATIVO
  // ============================================================

  if (caminho === '/') {
    return <PainelAdmin />
  }

  // ============================================================
  // PORTAL PUBLICO MULTI-MEI
  // ============================================================

  if (partes[0] === 'lojas') {
    const slug = partes[1] ?? ''

    // Identificador publico da loja.
    const slugValido =
      /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)

    const paginaCatalogo =
      partes.length === 2

    const paginaAtendimento =
      partes.length === 3 &&
      partes[2] === 'atendimento'

    // Enderecos desconhecidos nao devem
    // carregar automaticamente outra loja.
    if (
      !slugValido ||
      (!paginaCatalogo && !paginaAtendimento)
    ) {
      return (
        <main style={{ padding: 32 }}>
          <h1>Página não encontrada</h1>
          <p>Verifique o endereço da loja.</p>
        </main>
      )
    }

    const enderecoLoja =
      `/lojas/${encodeURIComponent(slug)}`

    // ==========================================================
    // NAVEGACAO DO CLIENTE
    // ==========================================================

    return (
      <div>
        <nav
          aria-label="Navegação da loja"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 16,
            alignItems: 'center',
            padding: '14px 24px',
            background: '#ffffff',
            borderBottom: '1px solid #e5e7eb',
          }}
        >
          <strong>Sistema MEI</strong>

          <a
            href={enderecoLoja}
            aria-current={
              paginaCatalogo ? 'page' : undefined
            }
          >
            Produtos e compras
          </a>

          <a
            href={`${enderecoLoja}/atendimento`}
            aria-current={
              paginaAtendimento ? 'page' : undefined
            }
          >
            Atendimento com IA
          </a>
        </nav>

        {/* ======================================================
            PAGINAS PUBLICAS ISOLADAS POR ESTABELECIMENTO
        ====================================================== */}

        {paginaAtendimento ? (
          <AtendimentoIA
            key={`atendimento:${slug}`}
            slug={slug}
          />
        ) : (
          <LojaCliente
            key={`catalogo:${slug}`}
            slug={slug}
          />
        )}
      </div>
    )
  }

  // ============================================================
  // ENDERECO DESCONHECIDO
  // ============================================================

  return (
    <main style={{ padding: 32 }}>
      <h1>Página não encontrada</h1>
      <p>Verifique o endereço informado.</p>
    </main>
  )
}


export default App