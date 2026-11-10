import './MinhasVendasMEI.css'
import { useEffect, useState } from 'react'
import { listarVendasMei, type VendaMEI } from '../services/meiCompras'

const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

export default function MinhasVendasMEI() {
  const [vendas, setVendas] = useState<VendaMEI[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [versao, setVersao] = useState(0)

  useEffect(() => {
    let ativo = true

    listarVendasMei()
      .then(dados => {
        if (ativo) setVendas(dados)
      })
      .catch(falha => {
        if (ativo) {
          setErro(
            falha instanceof Error
              ? falha.message
              : 'Erro ao consultar vendas.'
          )
        }
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })

    return () => { ativo = false }
  }, [versao])

  function atualizar() {
    setErro('')
    setCarregando(true)
    setVersao(valor => valor + 1)
  }

  return (
    <section className="mei-vendas" style={{ marginTop: 28 }}>
      <h2>Minhas vendas</h2>
      <p>Pedidos registrados no seu estabelecimento.</p>

      <button
        type="button"
        onClick={atualizar}
        disabled={carregando}
      >
        Atualizar vendas
      </button>

      {erro && <p role="alert">{erro}</p>}

      {carregando ? (
        <p>Carregando vendas...</p>
      ) : erro ? (
        <p>Verifique sua sessao e tente novamente.</p>
      ) : vendas.length === 0 ? (
        <p>Nenhum pedido registrado nesta loja.</p>
      ) : (
        <>
          <p>Exibindo ate os 100 pedidos mais recentes.</p>

          {vendas.map(venda => (
            <article
              key={venda.id}
              style={{
                border: '1px solid #e2e8f0',
                borderRadius: 12,
                background: '#fff',
                padding: 20,
                marginTop: 16,
              }}
            >
              <h3>Pedido #{venda.id}</h3>
              <p>Cliente: {venda.cliente_nome}</p>
              <p>
                Data: {venda.criado_em}
              </p>
              <p>Status: {venda.status}</p>
              <strong>
                Total: {moeda.format(venda.valor_total / 100)}
              </strong>

              <details style={{ marginTop: 12 }}>
                <summary>Ver itens do pedido</summary>
                <ul>
                  {venda.itens.map((item, indice) => (
                    <li key={indice}>
                      {item.produto_nome} ? {item.quantidade}
                      {' x '}
                      {moeda.format(item.preco_unitario / 100)}
                      {' = '}
                      {moeda.format(item.subtotal / 100)}
                    </li>
                  ))}
                </ul>
              </details>
            </article>
          ))}
        </>
      )}
    </section>
  )
}
