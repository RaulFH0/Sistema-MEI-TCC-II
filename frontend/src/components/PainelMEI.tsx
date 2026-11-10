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
    } catch (falha) {
      setErro(mensagemErro(falha))
    } finally {
      setSaindo(false)
    }
  }

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
      <section style={{ marginTop: 32 }}>
        <h2>Cadastrar produto</h2>

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
      </section>

      <section style={{ marginTop: 36 }}>
        <h2>Produtos do meu estabelecimento</h2>

        {carregando ? (
          <p>Carregando produtos...</p>
        ) : produtos.length === 0 ? (
          <p>Nenhum produto cadastrado nesta loja.</p>
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
                  <th>Acao</th>
                </tr>
              </thead>
              <tbody>
                {produtos.map(produto => (
                  <tr key={produto.id}>
                    <td>{produto.nome}</td>
                    <td>{moeda.format(produto.preco)}</td>
                    <td>{produto.quantidade}</td>
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
        </>
      ) : aba === 'vendas' ? (
        <MinhasVendasMEI />
      ) : (
        <DashboardMEI />
      )}
    </main>
  )
}
