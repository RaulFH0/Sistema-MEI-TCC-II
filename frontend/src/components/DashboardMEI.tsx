import { useEffect, useState } from 'react'
import {
  consultarDashboardMei,
  type PeriodoDashboard,
  type ResumoDashboard,
} from '../services/meiDashboard'
import './DashboardMEI.css'

const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

function reais(centavos: number): string {
  return moeda.format(centavos / 100)
}

function formatarDia(valor: string): string {
  const partes = valor.slice(0, 10).split('-')
  if (partes.length !== 3) return valor
  return `${partes[2]}/${partes[1]}/${partes[0]}`
}

export default function DashboardMEI() {
  const [periodo, setPeriodo] =
    useState<PeriodoDashboard>('30d')
  const [inicio, setInicio] = useState('')
  const [fim, setFim] = useState('')
  const [aplicado, setAplicado] = useState<{
    periodo: PeriodoDashboard
    inicio?: string
    fim?: string
  }>({ periodo: '30d' })
  const [versao, setVersao] = useState(0)
  const [dados, setDados] =
    useState<ResumoDashboard | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true

    consultarDashboardMei(
      aplicado.periodo,
      aplicado.inicio,
      aplicado.fim
    )
      .then(resultado => {
        if (ativo) {
          setDados(resultado)
          setErro('')
        }
      })
      .catch(falha => {
        if (ativo) {
          setDados(null)
          setErro(
            falha instanceof Error
              ? falha.message
              : 'Falha ao consultar indicadores.'
          )
        }
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })

    return () => { ativo = false }
  }, [aplicado, versao])

  function aplicarFiltro() {
    if (periodo === 'personalizado') {
      if (!inicio || !fim || inicio > fim) {
        setErro('Informe um intervalo de datas valido.')
        return
      }
    }

    setErro('')
    setCarregando(true)
    setAplicado({
      periodo,
      inicio: periodo === 'personalizado'
        ? inicio : undefined,
      fim: periodo === 'personalizado'
        ? fim : undefined,
    })
    setVersao(valor => valor + 1)
  }

  const maior = Math.max(
    1,
    ...(dados?.evolucao_diaria.map(
      item => item.valor_centavos
    ) ?? [])
  )

  return (
    <section className="mei-dashboard">
      <header className="mei-dashboard-cabecalho">
        <div>
          <h2>Visao geral da minha loja</h2>
          <p>
            Acompanhe os pedidos registrados no seu negocio.
          </p>
        </div>
      </header>

      <div className="mei-dashboard-filtros">
        <label htmlFor="mei-dashboard-periodo">
          Periodo
        </label>
        <select
          id="mei-dashboard-periodo"
          value={periodo}
          onChange={evento =>
            setPeriodo(
              evento.target.value as PeriodoDashboard
            )
          }
        >
          <option value="hoje">Hoje</option>
          <option value="7d">Ultimos 7 dias</option>
          <option value="30d">Ultimos 30 dias</option>
          <option value="personalizado">
            Personalizado
          </option>
        </select>

        {periodo === 'personalizado' && (
          <div className="mei-dashboard-datas">
            <label>
              Inicio
              <input
                type="date"
                value={inicio}
                onChange={evento =>
                  setInicio(evento.target.value)
                }
              />
            </label>
            <label>
              Fim
              <input
                type="date"
                value={fim}
                onChange={evento =>
                  setFim(evento.target.value)
                }
              />
            </label>
          </div>
        )}

        <button
          type="button"
          onClick={aplicarFiltro}
          disabled={carregando}
        >
          {carregando ? 'Consultando...' : 'Aplicar filtro'}
        </button>
      </div>

      {erro && <p className="mei-dashboard-erro" role="alert">
        {erro}
      </p>}

      {carregando && (
        <p role="status">Carregando indicadores...</p>
      )}

      {!carregando && dados && (
        <>
          <p className="mei-dashboard-periodo">
            Periodo: {formatarDia(dados.inicio)}
            {' ate '}
            {formatarDia(dados.fim)}
          </p>

          <div className="mei-dashboard-indicadores">
            <article className="mei-dashboard-card">
              <span>Valor dos pedidos confirmados</span>
              <strong>
                {reais(dados.valor_total_centavos)}
              </strong>
            </article>

            <article className="mei-dashboard-card">
              <span>Pedidos confirmados</span>
              <strong>{dados.pedidos_confirmados}</strong>
            </article>

            <article className="mei-dashboard-card">
              <span>Ticket medio</span>
              <strong>
                {reais(dados.ticket_medio_centavos)}
              </strong>
            </article>

            <article className="mei-dashboard-card">
              <span>Unidades vendidas</span>
              <strong>{dados.unidades_vendidas}</strong>
            </article>
          </div>

          <div className="mei-dashboard-grafico">
            <h3>Evolucao dos pedidos</h3>

            {dados.evolucao_diaria.length === 0 ? (
              <p>Nenhum pedido confirmado neste periodo.</p>
            ) : (
              <div className="mei-dashboard-barras">
                {dados.evolucao_diaria.map(dia => (
                  <div
                    className="mei-dashboard-dia"
                    key={dia.data}
                  >
                    <span>{reais(dia.valor_centavos)}</span>
                    <div className="mei-dashboard-trilha">
                      <div
                        className="mei-dashboard-barra"
                        style={{
                          height: `${Math.max(
                            5,
                            dia.valor_centavos / maior * 100
                          )}%`,
                        }}
                      />
                    </div>
                    <small>{formatarDia(dia.data)}</small>
                  </div>
                ))}
              </div>
            )}
          </div>

          <p className="mei-dashboard-observacao">
            Indicadores de pedidos confirmados no sistema.
            Nao representam necessariamente pagamentos
            recebidos nem lucro.
          </p>
        </>
      )}
    </section>
  )
}
