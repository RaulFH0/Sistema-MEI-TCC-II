import { useState } from 'react'
import './MinhaLojaVirtual.css'

type Props = {
  slug?: string | null
  nome?: string | null
}

export default function MinhaLojaVirtual({ slug, nome }: Props) {
  const [aviso, setAviso] = useState('')

  const valido =
    typeof slug === 'string' &&
    /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)

  if (!valido || !slug) {
    return (
      <section className="mei-loja-virtual">
        <h2>Minha loja virtual</h2>
        <p>
          O endereco publico da loja ainda nao esta disponivel.
          Verifique o cadastro do estabelecimento.
        </p>
      </section>
    )
  }

  const endereco = new URL(
    `/lojas/${encodeURIComponent(slug)}`,
    window.location.origin
  ).href

  async function copiarLink() {
    try {
      await navigator.clipboard.writeText(endereco)
      setAviso('Link copiado! Compartilhe com seus clientes.')
    } catch {
      setAviso(
        'Nao foi possivel copiar automaticamente. ' +
        'Selecione o endereco acima para copiar.'
      )
    }
  }

  return (
    <section className="mei-loja-virtual" aria-label="Minha loja virtual">
      <div className="mei-loja-virtual-topo">
        <span className="mei-loja-virtual-icone" aria-hidden="true">
          ??
        </span>
        <div>
          <h2>Minha loja virtual</h2>
          <p>
            {nome
              ? `${nome} ? compartilhe sua loja com os clientes.`
              : 'Compartilhe sua loja com os clientes.'}
          </p>
        </div>
      </div>

      <label htmlFor="mei-endereco-publico">
        Link exclusivo da loja
      </label>
      <input
        id="mei-endereco-publico"
        type="text"
        value={endereco}
        readOnly
        onFocus={evento => evento.currentTarget.select()}
        aria-label="Endereco publico da minha loja"
      />

      <div className="mei-loja-virtual-acoes">
        <button type="button" onClick={() => void copiarLink()}>
          Copiar link
        </button>
        <a
          href={endereco}
          target="_blank"
          rel="noopener noreferrer"
          className="mei-loja-virtual-abrir"
        >
          Abrir minha loja
        </a>
      </div>

      {aviso && <p role="status">{aviso}</p>}

      <p className="mei-loja-virtual-observacao">
        O link funciona neste ambiente. Para compartilhar com
        clientes externos, a plataforma precisa estar publicada
        em um endereco acessivel pela internet.
      </p>
    </section>
  )
}
