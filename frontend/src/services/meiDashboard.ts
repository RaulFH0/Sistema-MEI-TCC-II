import { ApiError } from './api'

export type PeriodoDashboard =
  | 'hoje'
  | '7d'
  | '30d'
  | 'personalizado'

export interface EvolucaoDiaria {
  data: string
  pedidos: number
  valor_centavos: number
}

export interface ResumoDashboard {
  periodo: PeriodoDashboard
  inicio: string
  fim: string
  pedidos_confirmados: number
  valor_total_centavos: number
  ticket_medio_centavos: number
  unidades_vendidas: number
  evolucao_diaria: EvolucaoDiaria[]
}

export async function consultarDashboardMei(
  periodo: PeriodoDashboard,
  inicio?: string,
  fim?: string
): Promise<ResumoDashboard> {
  const parametros = new URLSearchParams({ periodo })

  if (periodo === 'personalizado') {
    if (!inicio || !fim) {
      throw new Error('Informe as duas datas.')
    }
    parametros.set('inicio', inicio)
    parametros.set('fim', fim)
  }

  const resposta = await fetch(
    `/api/mei/dashboard?${parametros.toString()}`,
    {
      credentials: 'same-origin',
      cache: 'no-store',
    }
  )

  if (!resposta.ok) {
    throw new ApiError(
      resposta.status === 401
        ? 'Sessao expirada. Entre novamente no painel MEI.'
        : 'Nao foi possivel consultar o dashboard.',
      resposta.status
    )
  }

  return await resposta.json() as ResumoDashboard
}
