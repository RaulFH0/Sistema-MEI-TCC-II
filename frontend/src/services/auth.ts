import { ApiError } from './api'

const API_BASE = '/api'

export interface SessaoAdmin {
  autenticado: boolean
  usuario: string
  csrf_token: string
}

// CSRF mantido apenas na memoria do navegador.
// O cookie de sessao pertence ao backend.
let csrfToken: string | null = null

async function lerResposta(
  resposta: Response
): Promise<unknown> {
  try {
    return await resposta.json()
  } catch {
    return null
  }
}

function obterMensagemErro(
  dados: unknown,
  mensagemPadrao: string
): string {
  if (
    typeof dados === 'object' &&
    dados !== null &&
    'detail' in dados &&
    typeof dados.detail === 'string'
  ) {
    return dados.detail
  }

  return mensagemPadrao
}

export function obterCsrfToken(): string | null {
  return csrfToken
}

export function limparAutenticacao(): void {
  csrfToken = null
}

export async function realizarLogin(
  usuario: string,
  senha: string
): Promise<SessaoAdmin> {
  limparAutenticacao()

  const resposta = await fetch(
    `${API_BASE}/auth/login`,
    {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        usuario,
        senha,
      }),
    }
  )

  const dados = await lerResposta(resposta)

  if (!resposta.ok) {
    throw new ApiError(
      obterMensagemErro(
        dados,
        'Usuário ou senha inválidos.'
      ),
      resposta.status
    )
  }

  const sessao = dados as SessaoAdmin

  if (
    !sessao ||
    sessao.autenticado !== true ||
    typeof sessao.csrf_token !== 'string' ||
    !sessao.csrf_token
  ) {
    throw new Error(
      'Resposta de autenticação inválida.'
    )
  }

  csrfToken = sessao.csrf_token

  return sessao
}

export async function consultarSessao(): Promise<
  SessaoAdmin | null
> {
  const resposta = await fetch(
    `${API_BASE}/auth/me`,
    {
      credentials: 'same-origin',
      cache: 'no-store',
    }
  )

  if (resposta.status === 401) {
    limparAutenticacao()
    return null
  }

  const dados = await lerResposta(resposta)

  if (!resposta.ok) {
    throw new ApiError(
      obterMensagemErro(
        dados,
        'Não foi possível verificar a sessão.'
      ),
      resposta.status
    )
  }

  const sessao = dados as SessaoAdmin

  if (
    !sessao ||
    sessao.autenticado !== true ||
    typeof sessao.csrf_token !== 'string' ||
    !sessao.csrf_token
  ) {
    throw new Error(
      'Dados da sessão inválidos.'
    )
  }

  csrfToken = sessao.csrf_token

  return sessao
}

export async function realizarLogout(): Promise<void> {
  const token = csrfToken

  if (!token) {
    throw new Error(
      'Token CSRF indisponível. Verifique a sessão.'
    )
  }

  const resposta = await fetch(
    `${API_BASE}/auth/logout`,
    {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRF-Token': token,
      },
    }
  )

  if (!resposta.ok) {
    const dados = await lerResposta(resposta)

    if (resposta.status === 401) {
      limparAutenticacao()
    }

    throw new ApiError(
      obterMensagemErro(
        dados,
        'Não foi possível encerrar a sessão.'
      ),
      resposta.status
    )
  }

  limparAutenticacao()
}