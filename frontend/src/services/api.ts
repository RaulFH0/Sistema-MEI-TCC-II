const API_BASE = '/api'

export interface Produto {
  id: number
  nome: string
  preco: number
  quantidade: number
  descricao: string | null
  categoria: string | null
  criado_em: string
  atualizado_em: string
}

export interface ItemCompra {
  produto_nome: string
  quantidade: number
  preco_unitario: number
  subtotal: number
}

export interface Compra {
  pedido_confirmado: boolean
  compra_id: number
  cliente_nome: string
  itens: ItemCompra[]
  valor_total: number
  requisicao_repetida: boolean
}

export interface RespostaAtendimento {
  resposta: string
  acao_executada: string
  sucesso: boolean
  dados?: {
    tempo_ms?: number
    pedido?: Compra
  } | null
}

export async function listarProdutos(): Promise<Produto[]> {
  const resposta = await fetch(`${API_BASE}/produtos`)

  if (!resposta.ok) {
    throw new Error('Não foi possível carregar os produtos.')
  }

  return resposta.json()
}

export async function enviarMensagem(
  mensagem: string,
  chaveIdempotencia: string
): Promise<RespostaAtendimento> {
  const resposta = await fetch(`${API_BASE}/atender`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': chaveIdempotencia,
    },
    body: JSON.stringify({ mensagem }),
  })

  const dados = await resposta.json()

  if (!resposta.ok) {
    const detalhe = dados?.detail
    const mensagemErro =
      typeof detalhe === 'string'
        ? detalhe
        : detalhe?.mensagem || 'Erro ao processar atendimento.'

    throw new Error(mensagemErro)
  }

  return dados as RespostaAtendimento
}