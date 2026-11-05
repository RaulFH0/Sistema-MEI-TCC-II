
import { useRef, useState } from 'react'
import type { FormEvent } from 'react'

import {
  ApiError,
  enviarMensagem,
  enviarMensagemLojaMei,
  type RespostaAtendimento,
} from '../services/api'

import './AtendimentoIA.css'

type Solicitacao = {
  mensagem: string
  chave: string
  lojaSlug?: string
}

type AtendimentoIAProps = {
  slug?: string
}

type TipoErro = 'conflito' | 'validacao' | 'incerto' | null

const CHAVE_ARMAZENAMENTO = 'sistema-mei-atendimento-pendente-v1'

function chaveAtendimentoPorLoja(slug?: string): string {
  return slug
    ? `sistema-mei-atendimento-pendente-v2:${slug}`
    : CHAVE_ARMAZENAMENTO
}

const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

function recuperarSolicitacao(
  chaveArmazenamento: string,
  slug?: string
): Solicitacao | null {
  try {
    const salvo = sessionStorage.getItem(chaveArmazenamento)

    if (!salvo) return null

    const dados: unknown = JSON.parse(salvo)

    if (
      typeof dados !== 'object' ||
      dados === null ||
      !('mensagem' in dados) ||
      !('chave' in dados) ||
      typeof dados.mensagem !== 'string' ||
      typeof dados.chave !== 'string' ||
      !dados.mensagem.trim() ||
      !dados.chave.trim()
    ) {
      return null
    }

    if (
      slug
        ? !('lojaSlug' in dados) || dados.lojaSlug !== slug
        : 'lojaSlug' in dados
    ) {
      return null
    }

    return {
      mensagem: dados.mensagem,
      chave: dados.chave,
      ...(slug ? { lojaSlug: slug } : {}),
    }
  } catch {
    return null
  }
}

function salvarSolicitacao(
  dados: Solicitacao,
  chaveArmazenamento: string
): void {
  sessionStorage.setItem(
    chaveArmazenamento,
    JSON.stringify(dados)
  )
}

function removerSolicitacao(chaveArmazenamento: string): void {
  sessionStorage.removeItem(chaveArmazenamento)
}

export default function AtendimentoIA({
  slug,
}: AtendimentoIAProps) {
  const chaveArmazenamento = chaveAtendimentoPorLoja(slug)
  const [solicitacao, setSolicitacao] = useState<
    Solicitacao | null
  >(() => recuperarSolicitacao(chaveArmazenamento, slug))

  const [mensagem, setMensagem] = useState(() => {
    return recuperarSolicitacao(chaveArmazenamento, slug)?.mensagem ?? ''
  })

  const [ultimaMensagem, setUltimaMensagem] = useState(() => {
    return recuperarSolicitacao(chaveArmazenamento, slug)?.mensagem ?? ''
  })

  const [resultado, setResultado] = useState<
    RespostaAtendimento | null
  >(null)

  const [erro, setErro] = useState('')
  const [tipoErro, setTipoErro] = useState<TipoErro>(null)
  const [enviando, setEnviando] = useState(false)

  // Impede dois envios simultaneos no mesmo componente.
  const enviandoRef = useRef(false)

  const compra = resultado?.dados?.pedido

  async function processar(dados: Solicitacao) {
    if (enviandoRef.current) return

    if (
      slug
        ? dados.lojaSlug !== slug
        : dados.lojaSlug !== undefined
    ) {
      setErro('Esta tentativa pertence a outra loja.')
      setTipoErro('incerto')
      return
    }

    enviandoRef.current = true
    setEnviando(true)
    setErro('')
    setTipoErro(null)
    setResultado(null)

    try {
      const resposta = slug
        ? await enviarMensagemLojaMei(
            slug,
            dados.mensagem,
            dados.chave
          )
        : await enviarMensagem(
            dados.mensagem,
            dados.chave
          )

      if (!resposta.sucesso) {
        throw new Error(
          resposta.resposta ||
            'O atendimento nao foi confirmado.'
        )
      }

      // Somente uma confirmacao recebida pela API
      // encerra automaticamente a tentativa pendente.
      setResultado(resposta)
      setUltimaMensagem(dados.mensagem)

      removerSolicitacao(chaveArmazenamento)
      setSolicitacao(null)
      setMensagem('')
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : 'Falha de comunicacao com a API.'
      )

      if (falha instanceof ApiError) {
        if (falha.status === 409) {
          setTipoErro('conflito')
        } else if (falha.status === 422) {
          setTipoErro('validacao')
        } else {
          setTipoErro('incerto')
        }
      } else {
        setTipoErro('incerto')
      }

      // Nao excluir mensagem nem chave nesta etapa.
      // Uma falha de rede nao garante que a compra falhou.
    } finally {
      enviandoRef.current = false
      setEnviando(false)
    }
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()

    if (enviandoRef.current || solicitacao !== null) {
      return
    }

    const texto = mensagem.trim()

    if (!texto) return

    const novaSolicitacao: Solicitacao = {
      mensagem: texto,
      chave: crypto.randomUUID(),
      ...(slug ? { lojaSlug: slug } : {}),
    }

    try {
      // Salvar ANTES de enviar para o backend.
      salvarSolicitacao(novaSolicitacao, chaveArmazenamento)
    } catch {
      setErro(
        'Nao foi possivel proteger esta solicitacao ' +
          'no armazenamento da sessao. ' +
          'Nenhum pedido foi enviado.'
      )
      setTipoErro('incerto')
      return
    }

    setSolicitacao(novaSolicitacao)
    setUltimaMensagem(texto)
    setResultado(null)
    setErro('')
    setTipoErro(null)

    void processar(novaSolicitacao)
  }

  function tentarNovamente() {
    if (!solicitacao || enviandoRef.current) {
      return
    }

    if (tipoErro === 'conflito' || tipoErro === 'validacao') {
      return
    }

    // Reutiliza os dados originais, sem modificacoes.
    void processar(solicitacao)
  }

  function iniciarNovoAtendimento() {
    if (enviandoRef.current) return

    // Nao descartamos automaticamente uma tentativa
    // que pode ter sido registrada no servidor.
    if (solicitacao && tipoErro !== 'conflito') {
      return
    }

    try {
      removerSolicitacao(chaveArmazenamento)
    } catch {
      setErro('Nao foi possivel limpar a tentativa anterior.')
      return
    }

    setSolicitacao(null)
    setMensagem('')
    setUltimaMensagem('')
    setResultado(null)
    setErro('')
    setTipoErro(null)
  }

  return (
    <section className="atendimento">
      <header className="atendimento-header">
        <p className="eyebrow">ASSISTENTE INTELIGENTE</p>
        <h1>Atendimento com IA</h1>
        <p className="subtitle">
          Registre pedidos utilizando linguagem natural.
        </p>
      </header>

      <div className="chat-container">
        <div className="chat-conteudo">
          <div className="chat-boas-vindas">
            <div className="chat-avatar">IA</div>

            <h2>Como posso ajudar?</h2>

            <p>
              Informe seu nome, os produtos e as
              quantidades desejadas.
            </p>

            <p className="chat-exemplo">
              Exemplo: Sou Ana e quero comprar 2 pacotes
              de Arroz e 1 pacote de Feijao.
            </p>
          </div>

          {solicitacao && !enviando && !erro && (
            <div className="chat-aviso" role="status">
              <strong>Tentativa anterior recuperada</strong>
              <p>
                Esta solicitacao ainda precisa de confirmacao.
                Utilize o botao abaixo para consultar o
                resultado com a mesma chave.
              </p>

              <button
                type="button"
                onClick={tentarNovamente}
              >
                Verificar tentativa anterior
              </button>
            </div>
          )}

          {ultimaMensagem && (
            <div className="chat-linha usuario">
              <div className="chat-balao usuario">
                {ultimaMensagem}
              </div>
            </div>
          )}

          {enviando && (
            <div className="chat-linha assistente">
              <div className="chat-balao assistente">
                <strong>Processando pedido...</strong>

                <p className="chat-detalhe">
                  Aguarde a confirmacao da compra no banco
                  de dados. Nao feche a pagina.
                </p>
              </div>
            </div>
          )}

          {resultado && (
            <div className="chat-linha assistente">
              <div className="chat-balao assistente">
                <strong>
                  {compra?.requisicao_repetida
                    ? 'Compra recuperada'
                    : 'Compra confirmada'}
                </strong>

                <p>{resultado.resposta}</p>

                {compra && (
                  <div className="chat-comprovante">
                    <div className="chat-comprovante-topo">
                      <strong>
                        Compra #{compra.compra_id}
                      </strong>

                      <span>{compra.cliente_nome}</span>
                    </div>

                    {compra.itens.map((item, indice) => (
                      <div
                        className="chat-item"
                        key={`${item.produto_nome}-${indice}`}
                      >
                        <span>
                          {item.quantidade}x{' '}
                          {item.produto_nome}
                        </span>

                        <strong>
                          {moeda.format(item.subtotal)}
                        </strong>
                      </div>
                    ))}

                    <div className="chat-total">
                      <span>Total</span>

                      <strong>
                        {moeda.format(compra.valor_total)}
                      </strong>
                    </div>
                  </div>
                )}

                {resultado.dados?.tempo_ms != null && (
                  <p className="chat-detalhe">
                    Tempo de processamento:{' '}
                    {resultado.dados.tempo_ms} ms
                  </p>
                )}

                <button
                  className="chat-novo"
                  type="button"
                  onClick={iniciarNovoAtendimento}
                >
                  Novo atendimento
                </button>
              </div>
            </div>
          )}

          {erro && (
            <div className="chat-erro" role="alert">
              <strong>Atendimento nao confirmado na tela</strong>

              <p>{erro}</p>

              {tipoErro === 'conflito' ? (
                <>
                  <p>
                    Esta chave foi associada a uma mensagem
                    diferente. Nao tente reutiliza-la para
                    outro pedido.
                  </p>

                  <button
                    type="button"
                    onClick={iniciarNovoAtendimento}
                    disabled={enviando}
                  >
                    Iniciar nova solicitacao
                  </button>
                </>
              ) : tipoErro === 'validacao' ? (
                <p>
                  Os dados foram rejeitados pela API.
                  Esta tentativa foi preservada para
                  verificacao. Corrija a solicitacao
                  apenas apos confirmar que nao houve compra.
                </p>
              ) : (
                <>
                  <p>
                    A compra pode ter sido registrada antes
                    da falha de comunicacao. Reenvie os mesmos
                    dados para verificar o resultado.
                  </p>

                  <button
                    type="button"
                    onClick={tentarNovamente}
                    disabled={enviando || !solicitacao}
                  >
                    Tentar novamente com a mesma chave
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        <form
          className="chat-formulario"
          onSubmit={enviar}
        >
          <label htmlFor="mensagem-pedido">
            Mensagem do pedido
          </label>

          <textarea
            id="mensagem-pedido"
            placeholder="Ex.: Sou Ana e quero 2 Arroz e 1 Feijao..."
            value={mensagem}
            onChange={(evento) =>
              setMensagem(evento.target.value)
            }
            rows={3}
            disabled={enviando || solicitacao !== null}
            required
          />

          <div className="chat-acoes">
            <small>
              {solicitacao
                ? 'Tentativa pendente: mensagem e chave preservadas.'
                : 'Uma nova solicitacao recebe uma chave exclusiva.'}
            </small>

            <button
              type="submit"
              disabled={
                enviando ||
                solicitacao !== null ||
                !mensagem.trim()
              }
            >
              {enviando
                ? 'Processando...'
                : 'Enviar pedido'}
            </button>
          </div>
        </form>
      </div>
    </section>
  )
}
