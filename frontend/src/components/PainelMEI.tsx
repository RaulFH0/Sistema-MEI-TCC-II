import './PainelMEI.css'
import { useEffect, useState, type FormEvent } from 'react'
import LoginMEI from './LoginMEI'
import MinhasVendasMEI from './MinhasVendasMEI'
import DashboardMEI from './DashboardMEI'
import MinhaLojaVirtual from './MinhaLojaVirtual'
import {
  consultarSessaoMei,
  limparSessaoMei,
  logoutMei,
  type SessaoMEI,
} from '../services/authMei'
import {
  listarProdutosMei,
  cadastrarProdutoMei,
  atualizarEstoqueMei,
  atualizarEstoqueMinimoMei,
  type ProdutoMEI,
} from '../services/meiProdutos'

const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

function mensagemErro(falha: unknown): string {
  return falha instanceof Error
    ? falha.message
    : 'Nao foi possivel concluir a operacao.'
}

export default function PainelMEI() {
  const [sessao, setSessao] = useState<SessaoMEI | null>(null)
  const [aba, setAba] = useState<'produtos' | 'vendas' | 'dashboard'>('produtos')
  const [verificando, setVerificando] = useState(true)
  const [produtos, setProdutos] = useState<ProdutoMEI[]>([])
  const [carregando, setCarregando] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [saindo, setSaindo] = useState(false)
  const [versao, setVersao] = useState(0)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')

  const [nome, setNome] = useState('')
  const [preco, setPreco] = useState('')
  const [quantidade, setQuantidade] = useState('0')
  const [categoria, setCategoria] = useState('')
  const [descricao, setDescricao] = useState('')

  const [produtoEditando, setProdutoEditando] =
    useState<number | null>(null)
  const [estoqueNovo, setEstoqueNovo] = useState('')
  const [buscaProduto, setBuscaProduto] = useState('')
  const [somenteEsgotados, setSomenteEsgotados] = useState(false)
  const [somenteAtencao, setSomenteAtencao] = useState(false)
  const [minimoEditando, setMinimoEditando] = useState<number | null>(null)
  const [minimoNovo, setMinimoNovo] = useState('')

  const [estoqueGestaoId, setEstoqueGestaoId] = useState('')
  const [estoqueGestaoQtd, setEstoqueGestaoQtd] = useState('')
  const [minimoGestaoId, setMinimoGestaoId] = useState('')
  const [minimoGestaoQtd, setMinimoGestaoQtd] = useState('')

  useEffect(() => {
    let ativo = true

    consultarSessaoMei()
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

  useEffect(() => {
    setProdutos([])

    if (!sessao) return

    let ativo = true
    setCarregando(true)

    listarProdutosMei()
      .then(resultado => {
        if (ativo) {
          const produtosDaLoja = resultado.every(
            produto =>
              produto.estabelecimento_id ===
              sessao.estabelecimento_id
          )

          if (!produtosDaLoja) {
            throw new Error(
              'A API retornou produto de outro estabelecimento.'
            )
          }

          setProdutos(resultado)
        }
      })
      .catch(falha => {
        if (!ativo) return

        if (
          typeof falha === 'object' &&
          falha !== null &&
          'status' in falha &&
          falha.status === 401
        ) {
          limparSessaoMei()
          setSessao(null)
        }

        setErro(mensagemErro(falha))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })

    return () => { ativo = false }
  }, [sessao, versao])

  async function cadastrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (salvando || !sessao) return

    const valor = Number(preco.replace(',', '.'))
    const quantidadeNumero = Number(quantidade)

    if (
      !nome.trim() ||
      !Number.isFinite(valor) ||
      valor <= 0 ||
      !Number.isSafeInteger(quantidadeNumero) ||
      quantidadeNumero < 0
    ) {
      setErro('Informe nome, preco e quantidade validos.')
      return
    }

    setSalvando(true)
    setErro('')
    setSucesso('')

    try {
      await cadastrarProdutoMei({
        nome: nome.trim(),
        preco: valor,
        quantidade: quantidadeNumero,
        categoria: categoria.trim(),
        descricao: descricao.trim(),
      })

      setNome('')
      setPreco('')
      setQuantidade('0')
      setCategoria('')
      setDescricao('')
      setSucesso('Produto cadastrado com sucesso.')
      setVersao(anterior => anterior + 1)
    } catch (falha) {
      setErro(mensagemErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  async function salvarEstoque(produtoId: number) {
    if (salvando || !sessao) return

    const valor = Number(estoqueNovo)

    if (
      !estoqueNovo.trim() ||
      !Number.isSafeInteger(valor) ||
      valor < 0
    ) {
      setErro('Informe uma quantidade inteira valida.')
      return
    }

    setSalvando(true)
    setErro('')
    setSucesso('')

    try {
      await atualizarEstoqueMei(produtoId, valor)
      setProdutoEditando(null)
      setEstoqueNovo('')
      setSucesso('Estoque atualizado com sucesso.')
      setVersao(anterior => anterior + 1)
    } catch (falha) {
      setErro(mensagemErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  async function salvarEstoqueMinimo(produtoId: number) {
    if (salvando || !sessao) return

    const valor = Number(minimoNovo)

    if (
      !minimoNovo.trim() ||
      !Number.isSafeInteger(valor) ||
      valor < 0
    ) {
      setErro('Informe um limite minimo inteiro e valido.')
      return
    }

    setSalvando(true)
    setErro('')
    setSucesso('')

    try {
      await atualizarEstoqueMinimoMei(produtoId, valor)
      setMinimoEditando(null)
      setMinimoNovo('')
      setSucesso('Estoque minimo atualizado com sucesso.')
      setVersao(anterior => anterior + 1)
    } catch (falha) {
      setErro(mensagemErro(falha))
    } finally {
      setSalvando(false)
    }
  }


  async function atualizarEstoqueGestao(
    evento: FormEvent<HTMLFormElement>
  ) {
    evento.preventDefault()
    if (salvando || !sessao) return

    const id = Number(estoqueGestaoId)
    const valor = Number(estoqueGestaoQtd)

    if (
      !estoqueGestaoQtd.trim() ||
      !Number.isSafeInteger(id) ||
      id <= 0 ||
      !Number.isSafeInteger(valor) ||
      valor < 0 ||
      !produtos.some(produto => produto.id === id)
    ) {
      setErro('Selecione um produto e informe uma quantidade valida.')
      return
    }

    setSalvando(true)
    setErro('')
    setSucesso('')

    try {
      await atualizarEstoqueMei(id, valor)
      setSucesso('Quantidade em estoque atualizada com sucesso.')
      setVersao(anterior => anterior + 1)
    } catch (falha) {
      setErro(mensagemErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  async function atualizarMinimoGestao(
    evento: FormEvent<HTMLFormElement>
  ) {
    evento.preventDefault()
    if (salvando || !sessao) return

    const id = Number(minimoGestaoId)
    const valor = Number(minimoGestaoQtd)

    if (
      !minimoGestaoQtd.trim() ||
      !Number.isSafeInteger(id) ||
      id <= 0 ||
      !Number.isSafeInteger(valor) ||
      valor < 0 ||
      !produtos.some(produto => produto.id === id)
    ) {
      setErro('Selecione um produto e informe um limite valido.')
      return
    }

    setSalvando(true)
    setErro('')
    setSucesso('')

    try {
      await atualizarEstoqueMinimoMei(id, valor)
      setSucesso('Estoque minimo atualizado com sucesso.')
      setVersao(anterior => anterior + 1)
    } catch (falha) {
      setErro(mensagemErro(falha))
    } finally {
      setSalvando(false)
    }
  }

  async function sair() {
    if (saindo) return

    setSaindo(true)
    setErro('')
    setSucesso('')

    try {
      await logoutMei()
      setProdutos([])
      setSessao(null)
      setProdutoEditando(null)
      setMinimoEditando(null)
      setMinimoNovo('')
    } catch (falha) {
      setErro(mensagemErro(falha))
    } finally {
      setSaindo(false)
    }
  }


  // Indicadores calculados somente com produtos do MEI logado.
  const totalProdutos = produtos.length
  const totalUnidades = produtos.reduce(
    (total, produto) => total + produto.quantidade,
    0
  )
  const totalEsgotados = produtos.filter(
    produto => produto.quantidade === 0
  ).length
  const totalBaixo = produtos.filter(
    produto => produto.quantidade > 0 &&
      produto.quantidade <= produto.estoque_minimo
  ).length

  const produtosFiltrados = produtos.filter(produto => {
    const termo = buscaProduto.trim().toLocaleLowerCase('pt-BR')
    const conteudo = `${produto.nome} ${produto.categoria ?? ''}`
      .toLocaleLowerCase('pt-BR')

    return (
      conteudo.includes(termo) &&
      (!somenteEsgotados || produto.quantidade === 0) &&
      (!somenteAtencao ||
        produto.quantidade <= produto.estoque_minimo)
    )
  })

  if (verificando) {
    return (
      <main style={{ padding: 32 }}>
        <p>Verificando sessao do empreendedor...</p>
      </main>
    )
  }

  if (!sessao) {
    return (
      <>
        {erro && (
          <p role="alert" style={{ padding: 16 }}>
            {erro}
          </p>
        )}
        <LoginMEI
          aoAutenticar={novaSessao => {
            setErro('')
            setSucesso('')
            setSessao(novaSessao)
          }}
        />
      </>
    )
  }

  return (
    <main className="mei-painel" style={{
      maxWidth: 1100,
      margin: '0 auto',
      padding: 24,
    }}>
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 16,
      }}>
        <div>
          <h1>Meu painel MEI</h1>
          <p>
            Estabelecimento #{sessao.estabelecimento_id}
            {sessao.email ? ` ? ${sessao.email}` : ''}
          </p>
        </div>

        <button
          type="button"
          onClick={sair}
          disabled={saindo || salvando}
        >
          {saindo ? 'Saindo...' : 'Encerrar sessao'}
        </button>
      </header>

      <MinhaLojaVirtual
        slug={sessao.slug}
        nome={sessao.nome_estabelecimento}
      />

      {erro && <p role="alert">{erro}</p>}
      {sucesso && <p role="status">{sucesso}</p>}

      <nav aria-label="Navegacao do painel MEI" style={{
        display: 'flex',
        gap: 12,
        flexWrap: 'wrap',
        marginTop: 24,
      }}>
        <button
          type="button"
          aria-pressed={aba === 'produtos'}
          onClick={() => setAba('produtos')}
        >
          Produtos e estoque
        </button>
        <button
          type="button"
          aria-pressed={aba === 'vendas'}
          onClick={() => setAba('vendas')}
        >
          Minhas vendas
        </button>
        <button
          type="button"
          aria-pressed={aba === 'dashboard'}
          onClick={() => setAba('dashboard')}
        >
          Dashboard
        </button>
      </nav>


      {aba === 'produtos' ? (
        <>
      <section
        className="mei-estoque-visao"
        aria-label="Visao geral do estoque"
      >
        <div className="mei-estoque-titulo">
          <div>
            <h2>Produtos e estoque</h2>
            <p>
              Acompanhe seus produtos e as quantidades
              disponiveis no estabelecimento.
            </p>
          </div>
          <button
            type="button"
            disabled={carregando}
            onClick={() => setVersao(anterior => anterior + 1)}
          >
            {carregando ? 'Atualizando...' : 'Atualizar'}
          </button>
        </div>

        <div className="mei-estoque-cards">
          <article className="mei-estoque-card">
            <span>Produtos cadastrados</span>
            <strong>{carregando ? '...' : totalProdutos}</strong>
            <small>Tipos de produtos</small>
          </article>

          <article className="mei-estoque-card">
            <span>Unidades em estoque</span>
            <strong>{carregando ? '...' : totalUnidades}</strong>
            <small>Total disponivel</small>
          </article>

          <article className="mei-estoque-card">
            <span>Produtos sem estoque</span>
            <strong>{carregando ? '...' : totalEsgotados}</strong>
            <small>Quantidade zerada</small>
          </article>

          <article className="mei-estoque-card mei-estoque-card-baixo">
            <span>Produtos com estoque baixo</span>
            <strong>{carregando ? '...' : totalBaixo}</strong>
            <small>Quantidade positiva ate o limite minimo</small>
          </article>
        </div>

        {!carregando && totalEsgotados > 0 && (
          <div className="mei-estoque-alerta" role="status">
            Atencao: {totalEsgotados}{' '}
            {totalEsgotados === 1
              ? 'produto esta sem estoque.'
              : 'produtos estao sem estoque.'}
          </div>
        )}
        {!carregando && totalBaixo > 0 && (
          <div className="mei-estoque-alerta" role="status">
            Atencao: {totalBaixo} {totalBaixo === 1
              ? 'produto precisa de reposicao.'
              : 'produtos precisam de reposicao.'}
          </div>
        )}
      </section>

      <section className="mei-inventario">
        <h2>Inventario do meu estabelecimento</h2>
        <p className="mei-inventario-descricao">
          Consulte seus produtos, quantidades e limites
          minimos de reposicao.
        </p>
        <div className="mei-estoque-filtros">
          <input
            type="search"
            aria-label="Pesquisar produtos"
            placeholder="Pesquisar produto ou categoria..."
            value={buscaProduto}
            onChange={evento => setBuscaProduto(evento.target.value)}
          />
          <label>
            <input
              type="checkbox"
              checked={somenteEsgotados}
              onChange={evento =>
                setSomenteEsgotados(evento.target.checked)
              }
            />
            Mostrar somente produtos sem estoque
          </label>
          <label>
            <input
              type="checkbox"
              checked={somenteAtencao}
              onChange={evento =>
                setSomenteAtencao(evento.target.checked)
              }
            />
            Mostrar produtos que precisam de atencao
          </label>
        </div>


        {carregando ? (
          <p>Carregando produtos...</p>
        ) : produtos.length === 0 ? (
          <p>Nenhum produto cadastrado nesta loja.</p>
        ) : produtosFiltrados.length === 0 ? (
          <p>Nenhum produto encontrado para os filtros atuais.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              textAlign: 'left',
            }}>
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>Preco</th>
                  <th>Estoque</th>
                  <th>Limite minimo</th>
                  <th>Situacao</th>
                  <th>Configurar limite</th>
                  <th>Acao</th>
                </tr>
              </thead>
              <tbody>
                {produtosFiltrados.map(produto => (
                  <tr key={produto.id}>
                    <td>{produto.nome}</td>
                    <td>{moeda.format(produto.preco)}</td>
                    <td>{produto.quantidade}</td>
                    <td>{produto.estoque_minimo}</td>
                    <td>
                      <span className={`mei-estoque-situacao ${
                        produto.quantidade === 0 ? 'esgotado' :
                        produto.quantidade <= produto.estoque_minimo ?
                        'baixo' : 'normal'
                      }`}>
                        {produto.quantidade === 0 ? 'Sem estoque' :
                          produto.quantidade <= produto.estoque_minimo ?
                          'Estoque baixo' : 'Disponivel'}
                      </span>
                    </td>
                    <td>
                      {minimoEditando === produto.id ? (
                        <div className="mei-estoque-edicao">
                          <input
                            type="number"
                            min="0"
                            step="1"
                            aria-label={`Novo estoque minimo de ${produto.nome}`}
                            value={minimoNovo}
                            onChange={evento =>
                              setMinimoNovo(evento.target.value)
                            }
                          />
                          <button
                            type="button"
                            disabled={salvando}
                            onClick={() =>
                              void salvarEstoqueMinimo(produto.id)
                            }
                          >
                            Salvar
                          </button>
                          <button
                            type="button"
                            disabled={salvando}
                            onClick={() => setMinimoEditando(null)}
                          >
                            Cancelar
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          disabled={salvando}
                          onClick={() => {
                            setMinimoEditando(produto.id)
                            setMinimoNovo(
                              String(produto.estoque_minimo)
                            )
                          }}
                        >
                          Alterar limite
                        </button>
                      )}
                    </td>
                    <td>
                      {produtoEditando === produto.id ? (
                        <div style={{
                          display: 'flex',
                          gap: 8,
                          flexWrap: 'wrap',
                        }}>
                          <input
                            type="number"
                            min="0"
                            step="1"
                            aria-label={
                              `Novo estoque de ${produto.nome}`
                            }
                            value={estoqueNovo}
                            onChange={e =>
                              setEstoqueNovo(e.target.value)
                            }
                            style={{ width: 90 }}
                          />
                          <button
                            type="button"
                            disabled={salvando}
                            onClick={() =>
                              void salvarEstoque(produto.id)
                            }
                          >
                            Salvar
                          </button>
                          <button
                            type="button"
                            disabled={salvando}
                            onClick={() => setProdutoEditando(null)}
                          >
                            Cancelar
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setProdutoEditando(produto.id)
                            setEstoqueNovo(
                              String(produto.quantidade)
                            )
                          }}
                        >
                          Atualizar estoque
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="mei-gerenciar">
        <div className="mei-gerenciar-cabecalho">
          <h2>Gerenciar produtos</h2>
          <p>
            Cadastre produtos, atualize quantidades
            e configure alertas de reposicao.
          </p>
        </div>

        <div className="mei-gerenciar-grade">
          <div className="mei-gerenciar-card">

        <h3>Cadastrar novo produto</h3>

        <form onSubmit={cadastrar} style={{
          display: 'grid',
          gap: 12,
          maxWidth: 540,
        }}>
          <label htmlFor="mei-produto-nome">Nome</label>
          <input
            id="mei-produto-nome"
            value={nome}
            onChange={e => setNome(e.target.value)}
            maxLength={150}
            required
          />

          <label htmlFor="mei-produto-preco">
            Preco em reais
          </label>
          <input
            id="mei-produto-preco"
            type="number"
            min="0.01"
            step="0.01"
            value={preco}
            onChange={e => setPreco(e.target.value)}
            required
          />

          <label htmlFor="mei-produto-quantidade">
            Quantidade inicial
          </label>
          <input
            id="mei-produto-quantidade"
            type="number"
            min="0"
            step="1"
            value={quantidade}
            onChange={e => setQuantidade(e.target.value)}
            required
          />

          <label htmlFor="mei-produto-categoria">
            Categoria
          </label>
          <input
            id="mei-produto-categoria"
            value={categoria}
            onChange={e => setCategoria(e.target.value)}
          />

          <label htmlFor="mei-produto-descricao">
            Descricao
          </label>
          <textarea
            id="mei-produto-descricao"
            value={descricao}
            onChange={e => setDescricao(e.target.value)}
            rows={3}
          />

          <button type="submit" disabled={salvando}>
            {salvando ? 'Salvando...' : 'Cadastrar produto'}
          </button>
        </form>

          </div>

          <div className="mei-gerenciar-card">
            <h3>Atualizar estoque</h3>

            <form onSubmit={atualizarEstoqueGestao}>
              <label htmlFor="mei-gestao-estoque-produto">
                Produto
              </label>

              <select
                id="mei-gestao-estoque-produto"
                value={estoqueGestaoId}
                onChange={evento => {
                  const id = evento.target.value
                  const produto = produtos.find(
                    item => String(item.id) === id
                  )
                  setEstoqueGestaoId(id)
                  setEstoqueGestaoQtd(
                    produto ? String(produto.quantidade) : ''
                  )
                }}
                required
              >
                <option value="">Selecione um produto</option>
                {produtos.map(produto => (
                  <option key={produto.id} value={produto.id}>
                    {produto.nome}
                  </option>
                ))}
              </select>

              <label htmlFor="mei-gestao-estoque-quantidade">
                Nova quantidade total
              </label>

              <input
                id="mei-gestao-estoque-quantidade"
                type="number"
                min="0"
                step="1"
                value={estoqueGestaoQtd}
                onChange={evento =>
                  setEstoqueGestaoQtd(evento.target.value)
                }
                required
              />

              <p className="mei-gerenciar-ajuda">
                A quantidade informada substitui o estoque
                atual. Nao representa uma entrada adicional.
              </p>

              <button
                type="submit"
                disabled={salvando || !estoqueGestaoId}
              >
                {salvando ? 'Salvando...' : 'Atualizar estoque'}
              </button>
            </form>
          </div>

          <div className="mei-gerenciar-card">
            <h3>Configurar estoque minimo</h3>

            <form onSubmit={atualizarMinimoGestao}>
              <label htmlFor="mei-gestao-minimo-produto">
                Produto
              </label>

              <select
                id="mei-gestao-minimo-produto"
                value={minimoGestaoId}
                onChange={evento => {
                  const id = evento.target.value
                  const produto = produtos.find(
                    item => String(item.id) === id
                  )
                  setMinimoGestaoId(id)
                  setMinimoGestaoQtd(
                    produto ? String(produto.estoque_minimo) : ''
                  )
                }}
                required
              >
                <option value="">Selecione um produto</option>
                {produtos.map(produto => (
                  <option key={produto.id} value={produto.id}>
                    {produto.nome}
                  </option>
                ))}
              </select>

              <label htmlFor="mei-gestao-minimo-quantidade">
                Quantidade minima
              </label>

              <input
                id="mei-gestao-minimo-quantidade"
                type="number"
                min="0"
                step="1"
                value={minimoGestaoQtd}
                onChange={evento =>
                  setMinimoGestaoQtd(evento.target.value)
                }
                required
              />

              <p className="mei-gerenciar-ajuda">
                Define o limite desejado de estoque.
                O sistema sinaliza quando a quantidade
                atinge ou fica abaixo desse limite.
              </p>

              <button
                type="submit"
                disabled={salvando || !minimoGestaoId}
              >
                {salvando ? 'Salvando...' : 'Salvar estoque minimo'}
              </button>
            </form>
          </div>
        </div>
      </section>
        </>
      ) : aba === 'vendas' ? (
        <MinhasVendasMEI />
      ) : (
        <DashboardMEI />
      )}
    </main>
  )
}
