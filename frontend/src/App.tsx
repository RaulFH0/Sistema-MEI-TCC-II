
import { useEffect, useMemo, useState } from 'react'
import { listarProdutos, type Produto } from './services/api'
import './App.css'

function App() {
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [busca, setBusca] = useState('')

  async function carregarProdutos() {
    setCarregando(true)
    setErro('')

    try {
      const dados = await listarProdutos()
      setProdutos(dados)
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : 'Erro ao carregar produtos.'
      )
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    void carregarProdutos()
  }, [])

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

  const moeda = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })

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

        <nav className="navigation" aria-label="Menu principal">
          <span className="nav-item active">▦ Painel de estoque</span>
          <span className="nav-item disabled">◉ Atendimento IA</span>
          <span className="nav-item disabled">▤ Histórico de compras</span>
        </nav>

        <div className="sidebar-footer">
          Protótipo acadêmico — TCC II
        </div>
      </aside>

      <main className="main">
        <header className="page-header">
          <div>
            <p className="eyebrow">VISÃO GERAL</p>
            <h1>Produtos e estoque</h1>
            <p className="subtitle">
              Acompanhe os produtos cadastrados no seu negócio.
            </p>
          </div>

          <button
            className="refresh-button"
            onClick={() => void carregarProdutos()}
            disabled={carregando}
          >
            ↻ Atualizar
          </button>
        </header>

        <section className="stats" aria-label="Indicadores">
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

        <section className="content-card">
          <div className="section-header">
            <div>
              <h2>Inventário</h2>
              <p>Consulta de preços e quantidades disponíveis.</p>
            </div>

            <input
              type="search"
              placeholder="Pesquisar produto..."
              aria-label="Pesquisar produto"
              value={busca}
              onChange={(evento) => setBusca(evento.target.value)}
            />
          </div>

          {erro && (
            <div className="error-message" role="alert">
              {erro}
              <p>
                Verifique se o FastAPI está em execução
                na porta 8000.
              </p>
            </div>
          )}

          {carregando ? (
            <p className="empty-message">Carregando produtos...</p>
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
                      <td className="product-name">{produto.nome}</td>
                      <td>{produto.categoria || 'Não informada'}</td>
                      <td>{moeda.format(produto.preco)}</td>
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
      </main>
    </div>
  )
}

export default App
