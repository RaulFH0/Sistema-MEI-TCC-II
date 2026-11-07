import { useState, type FormEvent } from 'react'
import { ApiError } from '../services/api'
import './LoginAdmin.css'

interface Props {
  aoVoltar: () => void
}

interface SolicitacaoCadastro {
  nome_completo: string
  email: string
  cnpj: string
  telefone: string
  nome_estabelecimento: string
  senha: string
}

async function enviarSolicitacao(
  dados: SolicitacaoCadastro
): Promise<void> {
  const resposta = await fetch(
    '/api/cadastro-mei/solicitar',
    {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(dados),
    }
  )

  if (!resposta.ok) {
    let mensagem = 'Nao foi possivel enviar sua solicitacao.'

    try {
      const dadosErro: unknown = await resposta.json()

      if (
        typeof dadosErro === 'object' &&
        dadosErro !== null &&
        'detail' in dadosErro &&
        typeof dadosErro.detail === 'string'
      ) {
        mensagem = dadosErro.detail
      }
    } catch {
      // Mantem mensagem padrao.
    }

    throw new ApiError(mensagem, resposta.status)
  }

  if (resposta.status !== 202) {
    throw new Error(
      'Resposta inesperada do servidor ao solicitar cadastro.'
    )
  }
}

export default function RegistroMEI({ aoVoltar }: Props) {
  const [nome, setNome] = useState('')
  const [email, setEmail] = useState('')
  const [cnpj, setCnpj] = useState('')
  const [telefone, setTelefone] = useState('')
  const [estabelecimento, setEstabelecimento] = useState('')
  const [senha, setSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [enviado, setEnviado] = useState(false)
  const [erro, setErro] = useState('')

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (enviando || enviado) return

    setErro('')

    if (senha !== confirmacao) {
      setErro('As senhas informadas nao coincidem.')
      return
    }

    if (senha.length < 10 || senha.length > 128) {
      setErro('A senha deve conter de 10 a 128 caracteres.')
      return
    }

    const cnpjNumerico = cnpj.replace(/\D/g, '')

    if (cnpjNumerico.length !== 14) {
      setErro('Informe um CNPJ com 14 digitos.')
      return
    }

    setEnviando(true)

    try {
      await enviarSolicitacao({
        nome_completo: nome.trim(),
        email: email.trim().toLowerCase(),
        cnpj: cnpjNumerico,
        telefone: telefone.trim(),
        nome_estabelecimento: estabelecimento.trim(),
        senha,
      })

      setSenha('')
      setConfirmacao('')
      setEnviado(true)
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : 'Erro ao enviar a solicitacao.'
      )
    } finally {
      setEnviando(false)
    }
  }

  if (enviado) {
    return (
      <main className="login-page">
        <section className="login-card">
          <div className="login-heading">
            <h1>Solicitacao recebida!</h1>
            <p role="status">
              Seu cadastro foi encaminhado para analise
              do administrador do Sistema MEI.
            </p>
            <p>
              A conta ainda nao esta ativa. O acesso
              somente sera liberado apos a aprovacao.
            </p>
          </div>

          <button
            type="button"
            className="login-submit"
            onClick={aoVoltar}
          >
            Voltar ao login
          </button>
        </section>
      </main>
    )
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-brand">
          <div className="login-brand-icon">M</div>
          <div>
            <h1>Sistema MEI</h1>
            <p>Solicitacao de acesso</p>
          </div>
        </div>

        <div className="login-heading">
          <h2>Registre seu negocio</h2>
          <p>
            Preencha seus dados para solicitar acesso
            a plataforma. O cadastro sera analisado
            antes da liberacao.
          </p>
        </div>

        <form onSubmit={enviar}>
          <label htmlFor="registro-nome">
            Nome completo
          </label>
          <input
            id="registro-nome"
            type="text"
            value={nome}
            onChange={e => setNome(e.target.value)}
            maxLength={150}
            autoComplete="name"
            disabled={enviando}
            required
          />

          <label htmlFor="registro-email">E-mail</label>
          <input
            id="registro-email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            maxLength={254}
            autoComplete="email"
            disabled={enviando}
            required
          />

          <label htmlFor="registro-cnpj">CNPJ do MEI</label>
          <input
            id="registro-cnpj"
            type="text"
            inputMode="numeric"
            placeholder="00.000.000/0000-00"
            value={cnpj}
            onChange={e => setCnpj(e.target.value)}
            maxLength={18}
            disabled={enviando}
            required
          />

          <label htmlFor="registro-telefone">
            Telefone para contato
          </label>
          <input
            id="registro-telefone"
            type="tel"
            value={telefone}
            onChange={e => setTelefone(e.target.value)}
            maxLength={20}
            autoComplete="tel"
            disabled={enviando}
            required
          />

          <label htmlFor="registro-loja">
            Nome do estabelecimento
          </label>
          <input
            id="registro-loja"
            type="text"
            value={estabelecimento}
            onChange={e => setEstabelecimento(e.target.value)}
            maxLength={150}
            disabled={enviando}
            required
          />

          <label htmlFor="registro-senha">
            Crie uma senha
          </label>
          <input
            id="registro-senha"
            type="password"
            value={senha}
            onChange={e => setSenha(e.target.value)}
            minLength={10}
            maxLength={128}
            autoComplete="new-password"
            disabled={enviando}
            required
          />

          <label htmlFor="registro-confirmar-senha">
            Confirme a senha
          </label>
          <input
            id="registro-confirmar-senha"
            type="password"
            value={confirmacao}
            onChange={e => setConfirmacao(e.target.value)}
            minLength={10}
            maxLength={128}
            autoComplete="new-password"
            disabled={enviando}
            required
          />

          {erro && (
            <p className="login-error" role="alert">
              {erro}
            </p>
          )}

          <button
            type="submit"
            className="login-submit"
            disabled={enviando}
          >
            {enviando
              ? 'Enviando solicitacao...'
              : 'Solicitar cadastro'}
          </button>
        </form>

        <p className="login-footer">
          Ja possui uma conta?{' '}
          <button
            type="button"
            onClick={aoVoltar}
            disabled={enviando}
          >
            Fazer login
          </button>
        </p>
      </section>
    </main>
  )
}
