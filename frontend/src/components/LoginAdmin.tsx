import { useState, type FormEvent } from 'react'
import { realizarLogin, type SessaoAdmin } from '../services/auth'
import './LoginAdmin.css'

interface LoginAdminProps {
  aoAutenticar: (sessao: SessaoAdmin) => void
}

export default function LoginAdmin({
  aoAutenticar,
}: LoginAdminProps) {
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')

  async function enviarFormulario(
    evento: FormEvent<HTMLFormElement>
  ) {
    evento.preventDefault()

    if (carregando) return

    setCarregando(true)
    setErro('')

    try {
      const sessao = await realizarLogin(usuario, senha)
      aoAutenticar(sessao)
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : 'Não foi possível realizar o login.'
      )
    } finally {
      setCarregando(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-brand">
          <div className="login-brand-icon">M</div>
          <div>
            <h1>Sistema MEI</h1>
            <p>Gestão inteligente</p>
          </div>
        </div>

        <div className="login-heading">
          <h2>Acesso administrativo</h2>
          <p>
            Entre com suas credenciais para acessar
            o painel de gerenciamento.
          </p>
        </div>

        <form onSubmit={enviarFormulario}>
          <label htmlFor="login-usuario">
            Usuário
          </label>

          <input
            id="login-usuario"
            type="text"
            value={usuario}
            onChange={(evento) =>
              setUsuario(evento.target.value)
            }
            autoComplete="username"
            required
            disabled={carregando}
          />

          <label htmlFor="login-senha">
            Senha
          </label>

          <input
            id="login-senha"
            type="password"
            value={senha}
            onChange={(evento) =>
              setSenha(evento.target.value)
            }
            autoComplete="current-password"
            required
            disabled={carregando}
          />

          {erro && (
            <p className="login-error" role="alert">
              {erro}
            </p>
          )}

          <button
            type="submit"
            className="login-submit"
            disabled={carregando}
          >
            {carregando
              ? 'Entrando...'
              : 'Entrar no painel'}
          </button>
        </form>

        <p className="login-footer">
          Protótipo acadêmico — TCC II
        </p>
      </section>
    </main>
  )
}