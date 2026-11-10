import { ApiError } from './api'

export interface ItemVendaMEI {
  produto_id: number
  produto_nome: string
  quantidade: number
  preco_unitario: number
  subtotal: number
}

export interface VendaMEI {
  id: number
  cliente_nome: string
  valor_total: number
  status: string
  criado_em: string
  itens: ItemVendaMEI[]
}

export async function listarVendasMei(): Promise<VendaMEI[]> {
  const resposta = await fetch('/api/mei/compras?limite=100', {
    credentials: 'same-origin',
    cache: 'no-store',
  })

  if (!resposta.ok) {
    throw new ApiError(
      resposta.status === 401
        ? 'Sessao MEI expirada. Entre novamente.'
        : 'Nao foi possivel consultar as vendas.',
      resposta.status
    )
  }

  const dados: unknown = await resposta.json()

  if (!Array.isArray(dados)) {
    throw new Error('Resposta de vendas inesperada.')
  }

  return dados as VendaMEI[]
}
