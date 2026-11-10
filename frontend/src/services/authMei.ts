import { ApiError } from './api'

const API_BASE = '/api'

export interface SessaoMEI {
  autenticado: boolean
  usuario_mei_id: number
  estabelecimento_id: number
  slug?: string | null
  nome_estabelecimento?: string | null
  email?: string
  csrf_token: string
}

let csrfMei: string | null = null

export function obterCsrfMei(): string | null {
  return csrfMei
}

export function limparSessaoMei(): void {
  csrfMei = null
}

async function interpretar(resposta: Response): Promise<unknown> {
  try {
    return await resposta.json()
  } catch {
    return null
  }
}

function mensagem(dados: unknown, padrao: string): string {
  if (
    typeof dados === 'object' &&
    dados !== null &&
    'detail' in dados &&
    typeof dados.detail === 'string'
  ) {
    return dados.detail
  }

  return padrao
}

function validarSessao(dados: unknown): SessaoMEI {
  if (
    typeof dados !== 'object' ||
    dados === null ||
    !('autenticado' in dados) ||
    dados.autenticado !== true ||
    !('usuario_mei_id' in dados) ||
    typeof dados.usuario_mei_id !== 'number' ||
    !('estabelecimento_id' in dados) ||
    typeof dados.estabelecimento_id !== 'number' ||
    !('csrf_token' in dados) ||
    typeof dados.csrf_token !== 'string' ||
    !dados.csrf_token
  ) {
    throw new Error('Resposta de sessao MEI invalida.')
  }

  const sessao = dados as unknown as SessaoMEI
  csrfMei = sessao.csrf_token
  return sessao
}

export async function loginMei(
  email: string,
  senha: string
): Promise<SessaoMEI> {
  limparSessaoMei()

  const resposta = await fetch(`${API_BASE}/auth/mei/login`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim(), senha }),
  })

  const dados = await interpretar(resposta)

  if (!resposta.ok) {
    throw new ApiError(
      mensagem(dados, 'Credenciais invalidas.'),
      resposta.status
    )
  }

  return validarSessao(dados)
}

export async function consultarSessaoMei():
  Promise<SessaoMEI | null> {
  const resposta = await fetch(`${API_BASE}/auth/mei/me`, {
    credentials: 'same-origin',
    cache: 'no-store',
  })

  if (resposta.status === 401) {
    limparSessaoMei()
    return null
  }

  const dados = await interpretar(resposta)

  if (!resposta.ok) {
    throw new ApiError(
      mensagem(dados, 'Erro ao verificar sessao MEI.'),
      resposta.status
    )
  }

  return validarSessao(dados)
}

export async function logoutMei(): Promise<void> {
  if (!csrfMei) {
    throw new ApiError(
      'Sessao indisponivel. Atualize a pagina.',
      401
    )
  }

  const resposta = await fetch(`${API_BASE}/auth/mei/logout`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-CSRF-Token': csrfMei },
  })

  if (!resposta.ok) {
    const dados = await interpretar(resposta)

    if (resposta.status === 401) {
      limparSessaoMei()
    }

    throw new ApiError(
      mensagem(dados, 'Erro ao sair do painel MEI.'),
      resposta.status
    )
  }

  limparSessaoMei()
}
