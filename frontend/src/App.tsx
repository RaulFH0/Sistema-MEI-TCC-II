
import { useCallback, useEffect, useMemo, useState } from 'react'

import { listarProdutos, type Produto } from './services/api'
import AtendimentoIA from './components/AtendimentoIA'
import HistoricoCompras from './components/HistoricoCompras'
import GerenciarProdutos from './components/GerenciarProdutos'

import './App.css'

type Pagina = 'estoque' | 'atendimento' | 'historico'

const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

function App() {
  // ============================================================
  // ESTADOS DA APLICACAO
  // ============================================================

  const [pagina, setPagina] = useState<Pagina>('estoque')
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [busca, setBusca] = useState('')

  // ============================================================
  // CONSULTA DE PRODUTOS
  // ============================================================

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

  // Atualiza os dados quando o usuario abre o estoque.
  useEffect(() => {
    if (pagina === 'estoque') {
      void carregarProdutos()
    }
  }, [pagina, carregarProdutos])

  // ============================================================
  // FILTROS E INDICADORES
  // ============================================================

  const produtosFiltrados = useMemo(() => {
    const termo = busca.trim().toLocaleLowerCase('pt-BR')

    return produtos.filter((produto) =>
      `${produto.nome} ${produto.categoria ?? ''}`
        .toLocaleLowerCase('pt-BR')
        .includes(termo)
    )
  }, [produtos, busca])

  const totalUnidades = produtos.reduce(
    (total, produto) => total + produto.quantidade,
    0
  )

  const produtosSemEstoque = produtos.filter(
    (produto) => produto.quantidade === 0
  ).length

  // ============================================================
  // INTERFACE
  // ============================================================

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">M</div>

          <div>
            <strong>Sistema MEI</strong>
            <span>Gestão inteligente</span>
          </div>
        </div>

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

        <div className="sidebar-footer">
          Protótipo acadêmico — TCC II
        </div>
      </aside>

      <main className="main">
        {pagina === 'historico' ? (
          <HistoricoCompras />
        ) : pagina === 'atendimento' ? (
          <AtendimentoIA />
        ) : (
          <>
            {/* CABECALHO */}
            <header className="page-header">
              <div>
                <p className="eyebrow">VISÃO GERAL</p>
                <h1>Produtos e estoque</h1>
                <p className="subtitle">
                  Acompanhe e gerencie os produtos
                  cadastrados no seu negócio.
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

            {/* INDICADORES */}
            <section
              className="stats"
              aria-label="Indicadores de estoque"
            >
              <article className="stat-card">
                <span>Produtos cadastrados</span>
                <strong>{produtos.length}</strong>
                <small>Tipos de produtos</small>
              </article>

              <article className="stat-card">
                <span>Unidades em estoque</span>
                <strong>{totalUnidades}</strong>
                <small>Total disponível</small>
              </article>

              <article className="stat-card">
                <span>Produtos sem estoque</span>
                <strong>{produtosSemEstoque}</strong>
                <small>Precisam de reposição</small>
              </article>
            </section>

            {/* INVENTARIO */}
            <section className="content-card">
              <div className="section-header">
                <div>
                  <h2>Inventário</h2>
                  <p>
                    Consulta de preços e quantidades
                    disponíveis.
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

              {erro && (
                <div
                  className="error-message"
                  role="alert"
                >
                  {erro}
                  <p>
                    Verifique se o FastAPI está
                    em execução na porta 8000.
                  </p>
                </div>
              )}

              {carregando ? (
                <p className="empty-message">
                  Carregando produtos...
                </p>
              ) : produtosFiltrados.length === 0 ? (
                <p className="empty-message">
                  {erro
                    ? 'Não foi possível consultar o estoque.'
                    : 'Nenhum produto encontrado.'}
                </p>
              ) : (
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Produto</th>
                        <th>Categoria</th>
                        <th>Preço</th>
                        <th>Estoque</th>
                        <th>Situação</th>
                      </tr>
                    </thead>

                    <tbody>
                      {produtosFiltrados.map((produto) => (
                        <tr key={produto.id}>
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

                          <td>{produto.quantidade}</td>

                          <td>
                            <span
                              className={
                                produto.quantidade === 0
                                  ? 'status empty'
                                  : 'status available'
                              }
                            >
                              {produto.quantidade === 0
                                ? 'Sem estoque'
                                : 'Disponível'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* CADASTRO E ATUALIZACAO DE ESTOQUE */}
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

export default App
