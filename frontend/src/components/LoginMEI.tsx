import { useState, type FormEvent } from 'react'
import RegistroMEI from './RegistroMEI'
import { loginMei, type SessaoMEI } from '../services/authMei'
import './LoginAdmin.css'

interface Props {
  aoAutenticar: (sessao: SessaoMEI) => void
}

export default function LoginMEI({ aoAutenticar }: Props) {
  const [registrando, setRegistrando] = useState(false)
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (carregando) return

    setCarregando(true)
    setErro('')

    try {
      const sessao = await loginMei(email, senha)
      setSenha('')
      aoAutenticar(sessao)
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : 'Nao foi possivel entrar.'
      )
    } finally {
      setCarregando(false)
    }
  }

  if (registrando) {
    return (
      <RegistroMEI aoVoltar={() => setRegistrando(false)} />
    )
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-brand">
          <div className="login-brand-icon">M</div>
          <div>
            <h1>Sistema MEI</h1>
            <p>Gestao inteligente do seu negocio</p>
          </div>
        </div>

        <div className="login-heading">
          <h2>Acesso do empreendedor</h2>
          <p>Entre com o e-mail e a senha da sua conta MEI.</p>
        </div>

        <form onSubmit={enviar}>
          <label htmlFor="mei-email">E-mail</label>
          <input
            id="mei-email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={e => setEmail(e.target.value)}
            disabled={carregando}
            required
          />

          <label htmlFor="mei-senha">Senha</label>
          <input
            id="mei-senha"
            type="password"
            autoComplete="current-password"
            value={senha}
            onChange={e => setSenha(e.target.value)}
            disabled={carregando}
            required
          />

          {erro && <p className="login-error" role="alert">{erro}</p>}

          <button
            className="login-submit"
            type="submit"
            disabled={carregando}
          >
            {carregando ? 'Entrando...' : 'Entrar no meu painel'}
          </button>
        </form>

        <p className="login-footer">
          Nao tem uma conta?{' '}
          <button
            type="button"
            onClick={() => setRegistrando(true)}
            disabled={carregando}
          >
            Registre-se
          </button>
        </p>

        <p className="login-footer">
          Area exclusiva do empreendedor ? TCC II
        </p>
      </section>
    </main>
  )
}
