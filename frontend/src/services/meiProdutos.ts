import { ApiError } from './api'
import { obterCsrfMei } from './authMei'

const BASE = '/api/mei/produtos'

export interface ProdutoMEI {
  id: number
  estabelecimento_id: number
  nome: string
  preco: number
  quantidade: number
  descricao?: string | null
  categoria?: string | null
}

export interface NovoProdutoMEI {
  nome: string
  preco: number
  quantidade: number
  descricao: string
  categoria: string
}

async function respostaErro(
  resposta: Response,
  padrao: string
): Promise<never> {
  let mensagem = padrao

  try {
    const dados: unknown = await resposta.json()

    if (
      typeof dados === 'object' &&
      dados !== null &&
      'detail' in dados &&
      typeof dados.detail === 'string'
    ) {
      mensagem = dados.detail
    }
  } catch {
    // Mantem mensagem padrao.
  }

  throw new ApiError(mensagem, resposta.status)
}

function cabecalhosEscrita(): Record<string, string> {
  const csrf = obterCsrfMei()

  if (!csrf) {
    throw new ApiError(
      'Sessao MEI indisponivel. Entre novamente.',
      401
    )
  }

  return {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrf,
  }
}

export async function listarProdutosMei():
  Promise<ProdutoMEI[]> {
  const resposta = await fetch(BASE, {
    credentials: 'same-origin',
    cache: 'no-store',
  })

  if (!resposta.ok) {
    return respostaErro(
      resposta,
      'Nao foi possivel listar os produtos.'
    )
  }

  const dados: unknown = await resposta.json()

  if (!Array.isArray(dados)) {
    throw new Error('Resposta de produtos inesperada.')
  }

  return dados as ProdutoMEI[]
}

export async function cadastrarProdutoMei(
  produto: NovoProdutoMEI
): Promise<void> {
  const resposta = await fetch(BASE, {
    method: 'POST',
    credentials: 'same-origin',
    headers: cabecalhosEscrita(),
    body: JSON.stringify(produto),
  })

  if (!resposta.ok) {
    return respostaErro(
      resposta,
      'Nao foi possivel cadastrar o produto.'
    )
  }
}

export async function atualizarEstoqueMei(
  produtoId: number,
  novaQuantidade: number
): Promise<void> {
  if (
    !Number.isSafeInteger(produtoId) ||
    produtoId <= 0 ||
    !Number.isSafeInteger(novaQuantidade) ||
    novaQuantidade < 0
  ) {
    throw new Error('Produto ou quantidade invalida.')
  }

  const resposta = await fetch(
    `${BASE}/${produtoId}/estoque`,
    {
      method: 'PATCH',
      credentials: 'same-origin',
      headers: cabecalhosEscrita(),
      body: JSON.stringify({
        nova_quantidade: novaQuantidade,
      }),
    }
  )

  if (!resposta.ok) {
    return respostaErro(
      resposta,
      'Nao foi possivel atualizar o estoque.'
    )
  }
}
