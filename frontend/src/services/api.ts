
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

export class ApiError extends Error {
  status: number

  constructor(mensagem: string, status: number) {
    super(mensagem)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function listarProdutos(): Promise<Produto[]> {
  const resposta = await fetch(`${API_BASE}/produtos`)

  if (!resposta.ok) {
    throw new ApiError(
      'Não foi possível carregar os produtos.',
      resposta.status
    )
  }

  return (await resposta.json()) as Produto[]
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
        : detalhe?.mensagem ||
          'Não foi possível processar o atendimento.'

    throw new ApiError(mensagemErro, resposta.status)
  }

  return dados as RespostaAtendimento
}



export interface ItemHistorico {
  produto_id: number
  produto_nome: string
  quantidade: number
  preco_unitario: number
  subtotal: number
}

export interface CompraHistorico {
  id: number
  cliente_nome: string
  valor_total: number
  status: string
  criado_em: string
  itens: ItemHistorico[]
}

export async function listarCompras(
  limite = 50
): Promise<CompraHistorico[]> {
  const resposta = await fetch(
    `/api/compras?limite=${limite}`
  )

  if (!resposta.ok) {
    throw new ApiError(
      'Não foi possível carregar o histórico de compras.',
      resposta.status
    )
  }

  return (await resposta.json()) as CompraHistorico[]
}



export interface NovoProduto {
  nome: string
  preco: number
  quantidade: number
  descricao: string
  categoria: string
}

function mensagemErroApi(dados: unknown): string {
  if (typeof dados === 'object' && dados !== null && 'detail' in dados) {
    const detalhe = dados.detail

    if (typeof detalhe === 'string') {
      return detalhe
    }
  }

  return 'Não foi possível concluir a operação.'
}

export async function cadastrarProduto(
  produto: NovoProduto
): Promise<Produto> {
  const resposta = await fetch('/api/produtos', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(produto),
  })

  const dados: unknown = await resposta.json()

  if (!resposta.ok) {
    throw new ApiError(
      mensagemErroApi(dados),
      resposta.status
    )
  }

  return dados as Produto
}

export async function atualizarEstoque(
  produtoId: number,
  quantidade: number
): Promise<Produto> {
  const resposta = await fetch(
    `/api/produtos/${produtoId}/estoque`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ quantidade }),
    }
  )

  const dados: unknown = await resposta.json()

  if (!resposta.ok) {
    throw new ApiError(
      mensagemErroApi(dados),
      resposta.status
    )
  }

  return dados as Produto
}
