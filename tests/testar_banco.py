from database.models import init_db, SessionLocal
from database.models import LogSistema, Pedido, Produto

init_db()
db = SessionLocal()

print("=== PRODUTOS ===")
produtos = db.query(Produto).all()
for p in produtos:
    print(f"  {p.id} | {p.nome} | R${p.preco} | Qtd: {p.quantidade}")

print("\n=== PEDIDOS ===")
pedidos = db.query(Pedido).all()
for p in pedidos:
    print(f"  {p.id} | {p.cliente_nome} | {p.produto_nome} | {p.status}")

print("\n=== LOGS DO SISTEMA ===")
logs = db.query(LogSistema).all()
for l in logs:
    print(f"  {l.id} | {l.acao} | {l.tempo_ms}ms | sucesso: {l.sucesso}")
    print(f"       entrada: {l.entrada_usuario[:80]}")
    print(f"       resposta: {l.resposta_agente[:80]}")

db.close()