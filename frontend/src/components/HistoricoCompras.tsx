
import { useEffect, useMemo, useState } from 'react'
import {
  listarCompras,
  type CompraHistorico,
} from '../services/api'

import './HistoricoCompras.css'

const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

function formatarData(valor: string): string {
  const data = new Date(valor)

  if (Number.isNaN(data.getTime())) {
    return valor
  }

  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(data)
}

export default function HistoricoCompras() {
  const [compras, setCompras] = useState<CompraHistorico[]>([])
  const [busca, setBusca] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [expandida, setExpandida] = useState<number | null>(null)

  async function carregar() {
    setCarregando(true)
    setErro('')

    try {
      const dados = await listarCompras()
      setCompras(dados)
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : 'Erro ao consultar compras.'
      )
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    void carregar()
  }, [])

  const comprasFiltradas = useMemo(() => {
    const termo = busca.trim().toLocaleLowerCase('pt-BR')

    if (!termo) return compras

    return compras.filter((compra) => {
      const texto = [
        compra.id.toString(),
        compra.cliente_nome,
        compra.status,
        ...compra.itens.map((item) => item.produto_nome),
      ]
        .join(' ')
        .toLocaleLowerCase('pt-BR')

      return texto.includes(termo)
    })
  }, [compras, busca])

  const valorTotal = compras.reduce(
    (total, compra) => total + compra.valor_total,
    0
  )

  return (
    <section className="historico">
      <header className="page-header">
        <div>
          <p className="eyebrow">GESTÃO DE VENDAS</p>
          <h1>Histórico de compras</h1>
          <p className="subtitle">
            Consulte as compras registradas pelo Sistema MEI.
          </p>
        </div>

        <button
          type="button"
          className="refresh-button"
          onClick={() => void carregar()}
          disabled={carregando}
        >
          ↻ Atualizar
        </button>
      </header>

      <div className="historico-indicadores">
        <article className="stat-card">
          <span>Compras carregadas</span>
          <strong>{compras.length}</strong>
          <small>Até 50 registros recentes</small>
        </article>

        <article className="stat-card">
          <span>Valor das compras carregadas</span>
          <strong className="historico-valor">
            {moeda.format(valorTotal / 100)}
          </strong>
          <small>Não representa o faturamento total do negócio</small>
        </article>
      </div>

      <section className="content-card">
        <div className="section-header">
          <div>
            <h2>Compras registradas</h2>
            <p>
              Clique em uma compra para visualizar seus produtos.
            </p>
          </div>

          <input
            type="search"
            placeholder="Buscar cliente ou produto..."
            aria-label="Pesquisar compras"
            value={busca}
            onChange={(evento) => setBusca(evento.target.value)}
          />
        </div>

        {erro && (
          <div className="error-message" role="alert">
            {erro}
          </div>
        )}

        {carregando ? (
          <p className="empty-message">Carregando compras...</p>
        ) : comprasFiltradas.length === 0 ? (
          <p className="empty-message">
            {erro
              ? 'Não foi possível consultar o histórico.'
              : 'Nenhuma compra encontrada.'}
          </p>
        ) : (
          <div className="historico-lista">
            {comprasFiltradas.map((compra) => {
              const aberta = expandida === compra.id

              return (
                <article
                  className="historico-compra"
                  key={compra.id}
                >
                  <button
                    type="button"
                    className="historico-compra-botao"
                    onClick={() =>
                      setExpandida(aberta ? null : compra.id)
                    }
                    aria-expanded={aberta}
                  >
                    <span className="historico-identificacao">
                      <strong>Compra #{compra.id}</strong>
                      <span>{compra.cliente_nome}</span>
                    </span>

                    <span className="historico-data">
                      {formatarData(compra.criado_em)}
                    </span>

                    <span className="historico-status">
                      {compra.status}
                    </span>

                    <strong className="historico-preco">
                      {moeda.format(compra.valor_total / 100)}
                    </strong>

                    <span aria-hidden="true">
                      {aberta ? '⌃' : '⌄'}
                    </span>
                  </button>

                  {aberta && (
                    <div className="historico-detalhes">
                      <h3>Itens da compra</h3>

                      <div className="historico-tabela-wrapper">
                        <table>
                          <thead>
                            <tr>
                              <th>Produto</th>
                              <th>Quantidade</th>
                              <th>Preço unitário</th>
                              <th>Subtotal</th>
                            </tr>
                          </thead>

                          <tbody>
                            {compra.itens.map((item) => (
                              <tr key={item.produto_id}>
                                <td>{item.produto_nome}</td>
                                <td>{item.quantidade}</td>
                                <td>
                                  {moeda.format(
                                    item.preco_unitario / 100
                                  )}
                                </td>
                                <td>
                                  {moeda.format(
                                    item.subtotal / 100
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        )}
      </section>
    </section>
  )
}
