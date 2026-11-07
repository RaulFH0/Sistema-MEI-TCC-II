import { useCallback, useEffect, useState } from 'react'
import LoginAdmin from './LoginAdmin'
import {
  cabecalhosAdmin,
  ApiError,
} from '../services/api'
import {
  consultarSessao,
  type SessaoAdmin,
} from '../services/auth'

type StatusCadastro = 'pendente' | 'aprovado' | 'rejeitado'

interface Solicitacao {
  id: number
  nome_completo: string
  email: string
  cnpj: string
  telefone: string
  nome_estabelecimento: string
  status: StatusCadastro
  criado_em: string
  analisado_em: string | null
  analisado_por: string | null
  observacao_admin: string | null
}

async function tratarErro(resposta: Response): Promise<never> {
  let mensagem = 'Nao foi possivel concluir a operacao.'

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
    // Mantem a mensagem padrao.
  }

  throw new ApiError(mensagem, resposta.status)
}

function mensagemErro(falha: unknown): string {
  return falha instanceof Error
    ? falha.message
    : 'Ocorreu um erro inesperado.'
}

function formatarData(valor: string | null): string {
  if (!valor) return '?'

  const data = new Date(valor.endsWith('Z') ? valor : `${valor}Z`)

  return Number.isNaN(data.getTime())
    ? valor
    : data.toLocaleString('pt-BR')
}

export default function SolicitacoesMEIAdmin() {
  const [sessao, setSessao] = useState<SessaoAdmin | null>(null)
  const [verificando, setVerificando] = useState(true)
  const [status, setStatus] = useState<StatusCadastro>('pendente')
  const [solicitacoes, setSolicitacoes] = useState<Solicitacao[]>([])
  const [carregando, setCarregando] = useState(false)
  const [processandoId, setProcessandoId] = useState<number | null>(null)
  const [revisao, setRevisao] = useState(0)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')

  useEffect(() => {
    let ativo = true

    consultarSessao()
      .then(resultado => {
        if (ativo) setSessao(resultado)
      })
      .catch(falha => {
        if (ativo) setErro(mensagemErro(falha))
      })
      .finally(() => {
        if (ativo) setVerificando(false)
      })

    return () => { ativo = false }
  }, [])

  const carregar = useCallback(async (
    filtro: StatusCadastro,
    sinal?: AbortSignal
  ): Promise<Solicitacao[]> => {
    const resposta = await fetch(
      `/api/admin/solicitacoes-mei?status=${filtro}`,
      {
        credentials: 'same-origin',
        cache: 'no-store',
        signal: sinal,
      }
    )

    if (!resposta.ok) {
      return tratarErro(resposta)
    }

    const dados: unknown = await resposta.json()

    if (!Array.isArray(dados)) {
      throw new Error('Formato inesperado das solicitacoes.')
    }

    return dados as Solicitacao[]
  }, [])

  useEffect(() => {
    if (!sessao) {
      setSolicitacoes([])
      return
    }

    const controlador = new AbortController()
    let ativo = true

    setCarregando(true)

    carregar(status, controlador.signal)
      .then(dados => {
        if (ativo) setSolicitacoes(dados)
      })
      .catch(falha => {
        if (!ativo || controlador.signal.aborted) return

        if (falha instanceof ApiError && falha.status === 401) {
          setSessao(null)
        }

        setErro(mensagemErro(falha))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })

    return () => {
      ativo = false
      controlador.abort()
    }
  }, [sessao, status, revisao, carregar])

  async function decidir(
    solicitacao: Solicitacao,
    decisao: 'aprovar' | 'rejeitar'
  ) {
    if (processandoId !== null || carregando) return

    const confirmar = window.confirm(
      decisao === 'aprovar'
        ? `Aprovar ${solicitacao.nome_completo} e criar o estabelecimento ${solicitacao.nome_estabelecimento}?`
        : `Rejeitar a solicitacao de ${solicitacao.nome_completo}?`
    )

    if (!confirmar) return

    let observacao = ''

    if (decisao === 'rejeitar') {
      const resposta = window.prompt(
        'Motivo da rejeicao (opcional, ate 500 caracteres):',
        ''
      )

      if (resposta === null) return
      observacao = resposta.trim()

      if (observacao.length > 500) {
        setErro('A observacao deve ter ate 500 caracteres.')
        return
      }
    }

    setErro('')
    setSucesso('')
    setProcessandoId(solicitacao.id)

    try {
      const resposta = await fetch(
        `/api/admin/solicitacoes-mei/${solicitacao.id}/${decisao}`,
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: cabecalhosAdmin(),
          ...(decisao === 'rejeitar'
            ? { body: JSON.stringify({ observacao }) }
            : {}),
        }
      )

      if (!resposta.ok) {
        return await tratarErro(resposta)
      }

      setSucesso(
        decisao === 'aprovar'
          ? 'Solicitacao aprovada. Conta e estabelecimento criados.'
          : 'Solicitacao rejeitada.'
      )
    } catch (falha) {
      setErro(mensagemErro(falha))
    } finally {
      setProcessandoId(null)
      setRevisao(atual => atual + 1)
    }
  }

  if (verificando) {
    return (
      <main style={{ padding: 32 }}>
        <p>Verificando acesso administrativo...</p>
      </main>
    )
  }

  if (!sessao) {
    return (
      <>
        {erro && <p role="alert" style={{ padding: 16 }}>{erro}</p>}
        <LoginAdmin
          aoAutenticar={resultado => {
            setErro('')
            setSessao(resultado)
          }}
        />
      </>
    )
  }

  return (
    <main style={{
      maxWidth: 1100,
      margin: '0 auto',
      padding: 24,
    }}>
      <nav style={{ marginBottom: 24 }}>
        <a href="/">Voltar ao painel administrativo</a>
      </nav>

      <h1>Solicitacoes de cadastro MEI</h1>
      <p>
        Analise os pedidos antes de autorizar o acesso
        de novos empreendedores a plataforma.
      </p>

      <div style={{
        display: 'flex',
        gap: 12,
        flexWrap: 'wrap',
        alignItems: 'center',
        margin: '24px 0',
      }}>
        <label htmlFor="filtro-cadastro">Situacao:</label>

        <select
          id="filtro-cadastro"
          value={status}
          onChange={evento => {
            setErro('')
            setSucesso('')
            setStatus(evento.target.value as StatusCadastro)
          }}
          disabled={processandoId !== null}
        >
          <option value="pendente">Pendentes</option>
          <option value="aprovado">Aprovadas</option>
          <option value="rejeitado">Rejeitadas</option>
        </select>

        <button
          type="button"
          onClick={() => setRevisao(atual => atual + 1)}
          disabled={carregando || processandoId !== null}
        >
          Atualizar lista
        </button>
      </div>

      {erro && <p role="alert">{erro}</p>}
      {sucesso && <p role="status">{sucesso}</p>}

      {carregando ? (
        <p>Carregando solicitacoes...</p>
      ) : solicitacoes.length === 0 ? (
        <p>Nenhuma solicitacao encontrada neste filtro.</p>
      ) : (
        <div style={{
          display: 'grid',
          gap: 16,
        }}>
          {solicitacoes.map(solicitacao => (
            <article
              key={solicitacao.id}
              style={{
                border: '1px solid #d1d5db',
                borderRadius: 12,
                padding: 20,
                background: '#fff',
              }}
            >
              <h2 style={{ marginTop: 0 }}>
                {solicitacao.nome_estabelecimento}
              </h2>

              <p><strong>Empreendedor:</strong> {solicitacao.nome_completo}</p>
              <p><strong>E-mail:</strong> {solicitacao.email}</p>
              <p><strong>CNPJ:</strong> {solicitacao.cnpj}</p>
              <p><strong>Telefone:</strong> {solicitacao.telefone}</p>
              <p><strong>Solicitado em:</strong> {formatarData(solicitacao.criado_em)}</p>
              <p><strong>Status:</strong> {solicitacao.status}</p>

              {solicitacao.analisado_em && (
                <p>
                  <strong>Analisado em:</strong>
                  {' '}{formatarData(solicitacao.analisado_em)}
                </p>
              )}

              {solicitacao.analisado_por && (
                <p>
                  <strong>Analisado por:</strong>
                  {' '}{solicitacao.analisado_por}
                </p>
              )}

              {solicitacao.observacao_admin && (
                <p>
                  <strong>Observacao:</strong>
                  {' '}{solicitacao.observacao_admin}
                </p>
              )}

              {solicitacao.status === 'pendente' && (
                <div style={{
                  display: 'flex',
                  gap: 12,
                  flexWrap: 'wrap',
                  marginTop: 20,
                }}>
                  <button
                    type="button"
                    disabled={processandoId !== null}
                    onClick={() => void decidir(solicitacao, 'aprovar')}
                  >
                    {processandoId === solicitacao.id
                      ? 'Processando...'
                      : 'Aprovar cadastro'}
                  </button>

                  <button
                    type="button"
                    disabled={processandoId !== null}
                    onClick={() => void decidir(solicitacao, 'rejeitar')}
                  >
                    Rejeitar cadastro
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </main>
  )
}
