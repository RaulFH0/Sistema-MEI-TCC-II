
import { useCallback, useEffect, useMemo, useState } from 'react'

import { listarProdutos, type Produto } from './services/api'
import AtendimentoIA from './components/AtendimentoIA'
import HistoricoCompras from './components/HistoricoCompras'
import GerenciarProdutos from './components/GerenciarProdutos'

import './App.css'

type Pagina = 'estoque' | 'atendimento' | 'historico'
type SituacaoEstoque = 'esgotado' | 'baixo' | 'normal'

const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

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

function App() {
  const [pagina, setPagina] = useState<Pagina>('estoque')
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [busca, setBusca] = useState('')
  const [somenteAlertas, setSomenteAlertas] = useState(false)

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

  useEffect(() => {
    if (pagina === 'estoque') {
      void carregarProdutos()
    }
  }, [pagina, carregarProdutos])

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

  const totalAlertas = produtosSemEstoque + produtosEstoqueBaixo

  const produtosFiltrados = useMemo(() => {
    const termo = busca.trim().toLocaleLowerCase('pt-BR')

    return produtos.filter((produto) => {
      const correspondeBusca =
        `${produto.nome} ${produto.categoria ?? ''}`
          .toLocaleLowerCase('pt-BR')
          .includes(termo)

      const correspondeAlerta =
        !somenteAlertas || situacaoEstoque(produto) !== 'normal'

      return correspondeBusca && correspondeAlerta
    })
  }, [produtos, busca, somenteAlertas])

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
            <header className="page-header">
              <div>
                <p className="eyebrow">VISÃO GERAL</p>
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
                <small>Quantidade zerada</small>
              </article>

              <article className="stat-card">
                <span>Estoque baixo</span>
                <strong>{produtosEstoqueBaixo}</strong>
                <small>Produtos que precisam de reposição</small>
              </article>
            </section>

            {totalAlertas > 0 && !erro && (
              <div className="estoque-alerta" role="status">
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

              {erro && (
                <div className="error-message" role="alert">
                  {erro}
                  <p>
                    Verifique se a FastAPI está em execução
                    na porta 8000.
                  </p>
                </div>
              )}

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
                        const situacao = situacaoEstoque(produto)

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

                            <td>{produto.quantidade}</td>
                            <td>{produto.estoque_minimo}</td>

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
