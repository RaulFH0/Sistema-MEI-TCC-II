
import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import {
  listarProdutos,
  listarProdutosLoja,
  gerarOrcamentoLoja,
  gerarOrcamentoLojaMei,
  confirmarPedidoLoja,
  confirmarPedidoLojaMei,
  ApiError,
  type Produto,
  type OrcamentoLoja,
  type SolicitacaoConfirmacaoLoja,
  type RespostaConfirmacaoLoja,
} from '../services/api'

import './LojaCliente.css'

const CHAVE_PENDENTE = 'sistema-mei-loja-pedido-pendente-v1'


type LojaClienteProps = {
  slug?: string
}

function chavePendentePorLoja(slug?: string): string {
  return slug
    ? `sistema-mei-loja-pedido-pendente-v2:${slug}`
    : CHAVE_PENDENTE
}


const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})


type TentativaPendente = {
  chave: string
  solicitacao: SolicitacaoConfirmacaoLoja
  lojaSlug?: string
}


type SituacaoFalha = 'incerta' | 'rejeitada' | null

function formatarCentavos(valor: number) {
  return moeda.format(valor / 100)
}

function lerTentativaPendente(
  chaveArmazenamento: string,
  slug?: string
): TentativaPendente | null {
  try {
    const salvo = sessionStorage.getItem(chaveArmazenamento)

    if (!salvo) return null

    const valor: unknown = JSON.parse(salvo)

    if (
      typeof valor !== 'object' ||
      valor === null ||
      !('chave' in valor) ||
      !('solicitacao' in valor) ||
      typeof valor.chave !== 'string' ||
      !valor.chave ||
      typeof valor.solicitacao !== 'object' ||
      valor.solicitacao === null
    ) {
      return null
    }

    const solicitacao = valor.solicitacao as Record<string, unknown>

    if (
      typeof solicitacao.cliente_nome !== 'string' ||
      !Array.isArray(solicitacao.itens) ||
      solicitacao.itens.length === 0 ||
      !Number.isSafeInteger(solicitacao.valor_total_centavos) ||
      Number(solicitacao.valor_total_centavos) <= 0 ||
      !solicitacao.itens.every(
        (item: unknown) =>
          typeof item === 'object' &&
          item !== null &&
          'produto_id' in item &&
          'quantidade' in item &&
          Number.isSafeInteger(item.produto_id) &&
          Number(item.produto_id) > 0 &&
          Number.isSafeInteger(item.quantidade) &&
          Number(item.quantidade) > 0 &&
          Number(item.quantidade) <= 50
      )
    ) {
      return null
    }

    if (
      slug
        ? !('lojaSlug' in valor) || valor.lojaSlug !== slug
        : 'lojaSlug' in valor
    ) {
      return null
    }

    return valor as TentativaPendente
  } catch {
    return null
  }
}

export default function LojaCliente({
  slug,
}: LojaClienteProps) {
  const chavePendente = chavePendentePorLoja(slug)
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [quantidades, setQuantidades] =
    useState<Record<number, number>>({})

  const [busca, setBusca] = useState('')
  const [clienteNome, setClienteNome] = useState('')

  const [carregando, setCarregando] = useState(true)
  const [calculando, setCalculando] = useState(false)
  const [confirmando, setConfirmando] = useState(false)

  const [erro, setErro] = useState('')
  const [erroOrcamento, setErroOrcamento] = useState('')
  const [erroConfirmacao, setErroConfirmacao] = useState('')

  const [orcamento, setOrcamento] = useState<OrcamentoLoja | null>(null)

  const [pendente, setPendente] = useState<TentativaPendente | null>(
    () => lerTentativaPendente(chavePendente, slug)
  )

  const [situacaoFalha, setSituacaoFalha] =
    useState<SituacaoFalha>(null)

  const [confirmacao, setConfirmacao] =
    useState<RespostaConfirmacaoLoja | null>(null)

  const revisaoRef = useRef(0)
  const confirmandoRef = useRef(false)
  const calculandoRef = useRef(false)

  const bloqueado = pendente !== null || confirmacao !== null

  // ============================================================
  // CARREGAR CATALOGO
  // ============================================================

  useEffect(() => {
    let ativo = true

    async function carregar() {
      try {
        const dados = slug
          ? await listarProdutosLoja(slug)
          : await listarProdutos()

        if (ativo) {
          setProdutos(dados)
          setErro('')
        }
      } catch (falha) {
        if (ativo) {
          setErro(
            falha instanceof Error
              ? falha.message
              : 'Não foi possível carregar os produtos.'
          )
        }
      } finally {
        if (ativo) {
          setCarregando(false)
        }
      }
    }

    void carregar()

    return () => {
      ativo = false
    }
  }, [slug])

  // ============================================================
  // CATALOGO E CARRINHO
  // ============================================================

  const catalogo = useMemo(() => {
    const termo = busca.trim().toLocaleLowerCase('pt-BR')

    return produtos.filter((produto) =>
      produto.nome.toLocaleLowerCase('pt-BR').includes(termo)
    )
  }, [produtos, busca])

  const carrinho = useMemo(() => {
    return produtos
      .filter((produto) => (quantidades[produto.id] ?? 0) > 0)
      .map((produto) => ({
        produto,
        quantidade: quantidades[produto.id],
      }))
  }, [produtos, quantidades])

  const totalEstimado = carrinho.reduce(
    (total, item) =>
      total + item.produto.preco * item.quantidade,
    0
  )

  function invalidarOrcamento() {
    revisaoRef.current += 1
    setOrcamento(null)
    setErroOrcamento('')
  }

  function alterarQuantidade(produto: Produto, diferenca: number) {
    if (bloqueado) return

    const atual = quantidades[produto.id] ?? 0

    const proxima = Math.max(
      0,
      Math.min(50, produto.quantidade, atual + diferenca)
    )

    if (proxima === atual) return

    invalidarOrcamento()

    setQuantidades((anterior) => ({
      ...anterior,
      [produto.id]: proxima,
    }))
  }

  function alterarNome(valor: string) {
    if (bloqueado) return

    if (valor !== clienteNome) {
      invalidarOrcamento()
      setClienteNome(valor)
    }
  }

  // ============================================================
  // CALCULAR ORCAMENTO
  // ============================================================

  async function calcularOrcamento(
    evento: FormEvent<HTMLFormElement>
  ) {
    evento.preventDefault()

    if (calculandoRef.current || bloqueado) return

    const nome = clienteNome.trim()

    if (!nome || carrinho.length === 0) {
      setErroOrcamento(
        'Informe seu nome e selecione pelo menos um produto.'
      )
      return
    }

    const revisao = ++revisaoRef.current

    calculandoRef.current = true
    setCalculando(true)
    setErroOrcamento('')
    setOrcamento(null)

    try {
      const itens = carrinho.map(({ produto, quantidade }) => ({
        produto_id: produto.id,
        quantidade,
      }))

      const resultado = slug
        ? await gerarOrcamentoLojaMei(slug, nome, itens)
        : await gerarOrcamentoLoja(nome, itens)

      if (revisao !== revisaoRef.current) return

      setOrcamento(resultado)
    } catch (falha) {
      if (revisao !== revisaoRef.current) return

      setErroOrcamento(
        falha instanceof Error
          ? falha.message
          : 'Não foi possível calcular o orçamento.'
      )
    } finally {
      calculandoRef.current = false
      setCalculando(false)
    }
  }

  // ============================================================
  // ENVIAR CONFIRMACAO
  // ============================================================

  async function enviarConfirmacao(tentativa: TentativaPendente) {
    if (confirmandoRef.current) return

    if (
      slug
        ? tentativa.lojaSlug !== slug
        : tentativa.lojaSlug !== undefined
    ) {
      setErroConfirmacao(
        'Esta tentativa pertence a outro estabelecimento.'
      )
      return
    }

    confirmandoRef.current = true

    setConfirmando(true)
    setErroConfirmacao('')
    setSituacaoFalha(null)

    try {
      const resposta = slug
        ? await confirmarPedidoLojaMei(
            slug,
            tentativa.solicitacao,
            tentativa.chave
          )
        : await confirmarPedidoLoja(
            tentativa.solicitacao,
            tentativa.chave
          )

      setConfirmacao(resposta)
      setPendente(null)

      sessionStorage.removeItem(chavePendente)
    } catch (falha) {
      const rejeicaoDefinitiva =
        falha instanceof ApiError &&
        [404, 409, 422].includes(falha.status)

      setSituacaoFalha(
        rejeicaoDefinitiva ? 'rejeitada' : 'incerta'
      )

      setErroConfirmacao(
        falha instanceof Error
          ? falha.message
          : 'Não foi possível verificar a confirmação.'
      )

      // Preserva a mesma chave e solicitacao
      // para evitar confirmar outro pedido por acidente.
    } finally {
      confirmandoRef.current = false
      setConfirmando(false)
    }
  }

  function iniciarConfirmacao() {
    if (
      !orcamento ||
      bloqueado ||
      calculandoRef.current ||
      confirmandoRef.current
    ) {
      return
    }

    const solicitacao: SolicitacaoConfirmacaoLoja = {
      cliente_nome: orcamento.cliente_nome,
      itens: orcamento.itens.map((item) => ({
        produto_id: item.produto_id,
        quantidade: item.quantidade,
      })),
      valor_total_centavos: orcamento.valor_total_centavos,
    }

    const confirmado = window.confirm(
      `Confirmar o pedido de ${orcamento.cliente_nome} ` +
      `no valor de ${formatarCentavos(
        orcamento.valor_total_centavos
      )}?\n\n` +
      'Esta operação registra a compra e desconta o estoque.'
    )

    if (!confirmado) return

    const tentativa: TentativaPendente = {
      chave: crypto.randomUUID(),
      solicitacao,
      ...(slug ? { lojaSlug: slug } : {}),
    }

    try {
      // Guardar antes de enviar ao backend.
      sessionStorage.setItem(
        chavePendente,
        JSON.stringify(tentativa)
      )
    } catch {
      setErroConfirmacao(
        'Não foi possível armazenar a tentativa com segurança. ' +
        'A compra não foi enviada.'
      )
      return
    }

    setPendente(tentativa)
    void enviarConfirmacao(tentativa)
  }

  function verificarTentativa() {
    if (!pendente) return

    void enviarConfirmacao(pendente)
  }

  function descartarTentativaRejeitada() {
    if (
      !pendente ||
      situacaoFalha !== 'rejeitada' ||
      confirmandoRef.current
    ) {
      return
    }

    const autorizado = window.confirm(
      'A tentativa foi rejeitada pela API.\n\n' +
      'Deseja liberar um novo orçamento?'
    )

    if (!autorizado) return

    sessionStorage.removeItem(chavePendente)

    setPendente(null)
    setSituacaoFalha(null)
    setErroConfirmacao('')
    setOrcamento(null)

    invalidarOrcamento()
  }

  function novoPedido() {
    if (!confirmacao || confirmandoRef.current) return

    setConfirmacao(null)
    setPendente(null)
    setOrcamento(null)
    setQuantidades({})
    setClienteNome('')
    setErroConfirmacao('')
    setErroOrcamento('')
    setSituacaoFalha(null)

    invalidarOrcamento()
  }

  // ============================================================
  // INTERFACE
  // ============================================================

  return (
    <div className="loja-cliente">
      <header className="loja-cabecalho">
        <div className="loja-conteudo">
          <div className="loja-marca">
            <span className="loja-logo">M</span>

            <div>
              <strong>Minha Loja</strong>
              <small>Atendimento pelo Sistema MEI</small>
            </div>
          </div>
        </div>
      </header>

      <main className="loja-conteudo">
        <section className="loja-apresentacao">
          <p>SEJA BEM-VINDO</p>
          <h1>Faça seu pedido</h1>

          <span>
            Escolha seus produtos, confira o orçamento
            e confirme sua compra pelo celular.
          </span>
        </section>

        {pendente && (
          <section
            className="loja-pendente"
            aria-label="Confirmação pendente"
          >
            <h2>
              {situacaoFalha === 'rejeitada'
                ? 'Pedido não confirmado'
                : 'Verificação de pedido pendente'}
            </h2>

            <p>
              Cliente: <strong>
                {pendente.solicitacao.cliente_nome}
              </strong>
            </p>

            <p>
              Valor aprovado:{' '}
              <strong>
                {formatarCentavos(
                  pendente.solicitacao.valor_total_centavos
                )}
              </strong>
            </p>

            {erroConfirmacao && (
              <p className="loja-erro" role="alert">
                {erroConfirmacao}
              </p>
            )}

            {situacaoFalha === 'rejeitada' ? (
              <>
                <p>
                  A API rejeitou a solicitação. Verifique o
                  motivo antes de solicitar outro orçamento.
                </p>

                <button
                  type="button"
                  className="loja-botao-secundario"
                  onClick={descartarTentativaRejeitada}
                  disabled={confirmando}
                >
                  Liberar novo orçamento
                </button>
              </>
            ) : (
              <>
                <p>
                  Não crie outro pedido enquanto a confirmação
                  anterior não tiver sido verificada.
                </p>

                <button
                  type="button"
                  className="loja-botao-principal"
                  disabled={confirmando}
                  onClick={verificarTentativa}
                >
                  {confirmando
                    ? 'Verificando pedido...'
                    : 'Verificar tentativa anterior'}
                </button>
              </>
            )}
          </section>
        )}

        {confirmacao && (
          <section
            className="loja-comprovante"
            aria-label="Comprovante da compra"
          >
            <h2>
              {confirmacao.pedido.requisicao_repetida
                ? 'Compra já registrada'
                : 'Compra confirmada!'}
            </h2>

            <p>
              Compra #{confirmacao.pedido.compra_id} de{' '}
              {confirmacao.pedido.cliente_nome}
            </p>

            <div className="loja-itens-carrinho">
              {confirmacao.pedido.itens.map((item, indice) => (
                <div
                  className="loja-item-carrinho"
                  key={`${item.produto_nome}-${indice}`}
                >
                  <span>
                    {item.quantidade} × {item.produto_nome}
                  </span>

                  <strong>
                    {moeda.format(item.subtotal)}
                  </strong>
                </div>
              ))}
            </div>

            <div className="loja-total">
              <span>Total confirmado</span>
              <strong>
                {moeda.format(confirmacao.pedido.valor_total)}
              </strong>
            </div>

            <p className="loja-observacao">
              {confirmacao.pedido.requisicao_repetida
                ? 'Nenhuma nova compra foi registrada no reenvio.'
                : 'Seu pedido foi registrado no sistema da loja.'}
            </p>

            <button
              type="button"
              className="loja-botao-principal"
              onClick={novoPedido}
            >
              Fazer novo pedido
            </button>
          </section>
        )}

        <section className="loja-catalogo">
          <div className="loja-titulo-secao">
            <div>
              <h2>Produtos disponíveis</h2>
              <p>Adicione produtos ao seu carrinho.</p>
            </div>

            <input
              type="search"
              placeholder="Buscar produto..."
              aria-label="Buscar produto"
              value={busca}
              onChange={(evento) => setBusca(evento.target.value)}
            />
          </div>

          {erro && (
            <p className="loja-erro" role="alert">{erro}</p>
          )}

          {carregando ? (
            <p>Carregando produtos...</p>
          ) : erro ? (
            <p>Não foi possível carregar o catálogo.</p>
          ) : catalogo.length === 0 ? (
            <p>Nenhum produto encontrado.</p>
          ) : (
            <div className="loja-produtos">
              {catalogo.map((produto) => {
                const quantidade = quantidades[produto.id] ?? 0
                const disponivel = produto.quantidade > 0

                return (
                  <article
                    className="loja-produto"
                    key={produto.id}
                  >
                    <div className="loja-produto-informacoes">
                      <span className="loja-produto-categoria">
                        {produto.categoria || 'Produto'}
                      </span>

                      <h3>{produto.nome}</h3>

                      <strong>
                        {moeda.format(produto.preco)}
                      </strong>

                      <small>
                        {disponivel
                          ? `${produto.quantidade} unidades disponíveis`
                          : 'Produto indisponível'}
                      </small>
                    </div>

                    <div className="loja-controle-quantidade">
                      <button
                        type="button"
                        disabled={bloqueado || quantidade === 0}
                        onClick={() =>
                          alterarQuantidade(produto, -1)
                        }
                        aria-label={`Remover uma unidade de ${produto.nome}`}
                      >
                        −
                      </button>

                      <span>{quantidade}</span>

                      <button
                        type="button"
                        disabled={
                          bloqueado ||
                          !disponivel ||
                          quantidade >= produto.quantidade ||
                          quantidade >= 50
                        }
                        onClick={() =>
                          alterarQuantidade(produto, 1)
                        }
                        aria-label={`Adicionar uma unidade de ${produto.nome}`}
                      >
                        +
                      </button>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>

        <section className="loja-carrinho">
          <h2>Meu carrinho</h2>

          {carrinho.length === 0 ? (
            <p>Seu carrinho está vazio.</p>
          ) : (
            <>
              <div className="loja-itens-carrinho">
                {carrinho.map(({ produto, quantidade }) => (
                  <div
                    className="loja-item-carrinho"
                    key={produto.id}
                  >
                    <span>
                      {quantidade} × {produto.nome}
                    </span>

                    <strong>
                      {moeda.format(
                        produto.preco * quantidade
                      )}
                    </strong>
                  </div>
                ))}
              </div>

              <div className="loja-total">
                <span>Total estimado</span>

                <strong>
                  {moeda.format(totalEstimado)}
                </strong>
              </div>

              <p className="loja-observacao">
                O orçamento oficial será calculado pelo servidor
                antes de registrar uma compra.
              </p>
            </>
          )}

          <form
            className="loja-formulario"
            onSubmit={calcularOrcamento}
          >
            <label htmlFor="loja-cliente-nome">
              Seu nome
            </label>

            <input
              id="loja-cliente-nome"
              type="text"
              maxLength={120}
              required
              placeholder="Digite seu nome"
              value={clienteNome}
              disabled={bloqueado}
              onChange={(evento) =>
                alterarNome(evento.target.value)
              }
            />

            <button
              type="submit"
              className="loja-botao-principal"
              disabled={
                bloqueado ||
                calculando ||
                carregando ||
                !!erro ||
                carrinho.length === 0
              }
            >
              {calculando
                ? 'Calculando orçamento...'
                : 'Calcular orçamento'}
            </button>

            {erroOrcamento && (
              <p className="loja-erro" role="alert">
                {erroOrcamento}
              </p>
            )}
          </form>
        </section>

        {orcamento && !confirmacao && !pendente && (
          <section
            className="loja-orcamento"
            aria-label="Orçamento oficial"
          >
            <div className="loja-orcamento-cabecalho">
              <span>ORÇAMENTO OFICIAL</span>
              <h2>Confira seu pedido</h2>

              <p>
                Cliente: {orcamento.cliente_nome}
              </p>
            </div>

            <div className="loja-itens-carrinho">
              {orcamento.itens.map((item) => (
                <div
                  className="loja-item-carrinho"
                  key={item.produto_id}
                >
                  <div className="loja-orcamento-item">
                    <strong>{item.produto_nome}</strong>

                    <small>
                      {item.quantidade} ×{' '}
                      {formatarCentavos(
                        item.preco_unitario_centavos
                      )}
                    </small>
                  </div>

                  <strong>
                    {formatarCentavos(
                      item.subtotal_centavos
                    )}
                  </strong>
                </div>
              ))}
            </div>

            <div className="loja-total">
              <span>Total do orçamento</span>

              <strong>
                {formatarCentavos(
                  orcamento.valor_total_centavos
                )}
              </strong>
            </div>

            <div className="loja-orcamento-aviso" role="status">
              <strong>Orçamento calculado com sucesso.</strong>

              <p>
                Nenhuma compra foi registrada ainda.
                Os valores e a disponibilidade serão
                conferidos novamente na confirmação.
              </p>
            </div>

            <button
              type="button"
              className="loja-botao-principal loja-confirmar"
              onClick={iniciarConfirmacao}
            >
              Confirmar pedido
            </button>

            {erroConfirmacao && (
              <p className="loja-erro" role="alert">
                {erroConfirmacao}
              </p>
            )}
          </section>
        )}
      </main>
    </div>
  )
}
