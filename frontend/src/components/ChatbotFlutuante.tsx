import { useEffect, useRef, useState } from 'react'
import AtendimentoIA from './AtendimentoIA'
import './ChatbotFlutuante.css'

type ChatbotFlutuanteProps = {
  slug: string
}

export default function ChatbotFlutuante({
  slug,
}: ChatbotFlutuanteProps) {
  const [aberto, setAberto] = useState(false)

  const botaoRef = useRef<HTMLButtonElement>(null)
  const fecharRef = useRef<HTMLButtonElement>(null)

  function fecharAtendimento() {
    setAberto(false)
    botaoRef.current?.focus()
  }

  useEffect(() => {
    if (aberto) {
      fecharRef.current?.focus()
    }
  }, [aberto])

  useEffect(() => {
    function verificarTecla(evento: KeyboardEvent) {
      if (evento.key === 'Escape' && aberto) {
        setAberto(false)
        botaoRef.current?.focus()
      }
    }

    window.addEventListener('keydown', verificarTecla)

    return () => {
      window.removeEventListener(
        'keydown',
        verificarTecla
      )
    }
  }, [aberto])

  return (
    <aside className="chatbot-flutuante">
      <section
        id="chatbot-flutuante-janela"
        className="chatbot-flutuante-janela"
        role="dialog"
        aria-label="Assistente inteligente da loja"
        aria-modal="false"
        hidden={!aberto}
      >
        <header className="chatbot-flutuante-topo">
          <div className="chatbot-flutuante-marca">
            <span
              className="chatbot-flutuante-avatar"
              aria-hidden="true"
            >
              IA
            </span>

            <div>
              <strong>Assistente da loja</strong>
              <small>Atendimento com IA</small>
            </div>
          </div>

          <button
            ref={fecharRef}
            type="button"
            className="chatbot-flutuante-fechar"
            onClick={fecharAtendimento}
            aria-label="Fechar atendimento"
          >
            {'\u00D7'}
          </button>
        </header>

        <div className="chatbot-flutuante-corpo">
          <AtendimentoIA slug={slug} />
        </div>
      </section>

      <button
        ref={botaoRef}
        type="button"
        className="chatbot-flutuante-botao"
        aria-expanded={aberto}
        aria-controls="chatbot-flutuante-janela"
        aria-label={
          aberto
            ? 'Fechar assistente da loja'
            : 'Abrir assistente da loja'
        }
        onClick={() => {
          if (aberto) {
            fecharAtendimento()
          } else {
            setAberto(true)
          }
        }}
      >
        {aberto ? (
          <span aria-hidden="true">{'\u00D7'}</span>
        ) : (
          <svg
            width="27"
            height="27"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 9 9 0 0 1-4-.9L3 21l1.9-5.5a9 9 0 0 1-.9-4A8.5 8.5 0 0 1 12.5 3h.5a8.5 8.5 0 0 1 8 8v.5Z" />
          </svg>
        )}
      </button>
    </aside>
  )
}
