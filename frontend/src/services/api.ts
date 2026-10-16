
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
  estoque_minimo: number
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


export async function configurarEstoqueMinimo(
  produtoId: number,
  estoqueMinimo: number
): Promise<Produto> {
  const resposta = await fetch(
    `/api/produtos/${produtoId}/estoque-minimo`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        estoque_minimo: estoqueMinimo,
      }),
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


export interface ItemOrcamento {
  produto_id: number
  produto_nome: string
  quantidade: number
  preco_unitario_centavos: number
  subtotal_centavos: number
}

export interface OrcamentoLoja {
  cliente_nome: string
  itens: ItemOrcamento[]
  valor_total_centavos: number
  mensagem: string
}

export async function gerarOrcamentoLoja(
  clienteNome: string,
  itens: Array<{
    produto_id: number
    quantidade: number
  }>
): Promise<OrcamentoLoja> {
  const resposta = await fetch('/api/loja/orcamento', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      cliente_nome: clienteNome,
      itens,
    }),
  })

  const dados: unknown = await resposta.json()

  if (!resposta.ok) {
    let mensagem = 'Não foi possível calcular o orçamento.'

    if (
      typeof dados === 'object' &&
      dados !== null &&
      'detail' in dados &&
      typeof dados.detail === 'string'
    ) {
      mensagem = dados.detail
    }

    throw new ApiError(mensagem, resposta.status)
  }

  return dados as OrcamentoLoja
}


export interface PedidoConfirmadoLoja {
  pedido_confirmado: boolean
  compra_id: number
  cliente_nome: string
  itens: Array<{
    produto_nome: string
    quantidade: number
    preco_unitario: number
    subtotal: number
  }>
  valor_total: number
  requisicao_repetida: boolean
}

export interface RespostaConfirmacaoLoja {
  sucesso: boolean
  acao_executada: string
  pedido: PedidoConfirmadoLoja
}

export interface SolicitacaoConfirmacaoLoja {
  cliente_nome: string
  itens: Array<{
    produto_id: number
    quantidade: number
  }>
  valor_total_centavos: number
}

export async function confirmarPedidoLoja(
  solicitacao: SolicitacaoConfirmacaoLoja,
  chaveIdempotencia: string
): Promise<RespostaConfirmacaoLoja> {
  const resposta = await fetch('/api/loja/confirmar', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': chaveIdempotencia,
    },
    body: JSON.stringify(solicitacao),
  })

  let dados: unknown

  try {
    dados = await resposta.json()
  } catch {
    throw new ApiError(
      'Não foi possível interpretar a resposta. ' +
      'Não inicie outro pedido antes de verificar a tentativa.',
      resposta.status
    )
  }

  if (!resposta.ok) {
    let mensagem = 'Não foi possível confirmar o pedido.'

    if (
      typeof dados === 'object' &&
      dados !== null &&
      'detail' in dados &&
      typeof dados.detail === 'string'
    ) {
      mensagem = dados.detail
    }

    throw new ApiError(mensagem, resposta.status)
  }

  return dados as RespostaConfirmacaoLoja
}
