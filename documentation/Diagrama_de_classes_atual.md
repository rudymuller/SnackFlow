# Diagrama de classes atual

Este diagrama representa as classes existentes no codigo do SnackFlow. As classes de interface usam Tkinter; as classes de persistencia acessam o SQLite por meio de `DBProxy`.

```mermaid
classDiagram
    class Style {
        +COLORS
        +ICONS
        +style_button(button, tone)
        +style_heading(label)
        +style_subtitle(label)
        +add_footer(parent)
    }

    class App {
        +homeScreen(root)
        +showMenutype(login_instance)
        +_new_menu_window(login_instance, title)
        +_build_sidebar(sidebar, content, win, login_instance)
    }

    class Login {
        +show()
        +authenticate(username, password)
    }

    class MenuAdmin {
        +render()
        +open_pedidos()
    }

    class MenuFunc {
        +render()
        +open_placeholder(title)
        +open_estoque()
    }

    class AuthService {
        -user_repo
        +authenticate(username, password)
    }

    class AuthResult {
        <<class>>
        +ok
        +user
        +access_type
    }

    class User {
        <<dataclass>>
        +id
        +nome
        +sobrenome
        +nome_usuario
        +senha
        +tipo_acesso
        +dados_usuario()
    }

    class Usuario {
        -db
        +adicionar()
        +listar()
        +obter()
        +obter_por_nome_usuario()
        +atualizar()
        +remover()
    }

    class Lanche {
        +id
        +nome
        +preco
        +dadosLanche
        +incluirItem()
        +atualizarItem()
        +excluirItem()
        +salvar()
        +obter()
        +listar()
        +componentes()
        +garantir_item_no_estoque()
    }

    class LancheRepository {
        -db
        +salvar()
        +obter_dados()
        +listar()
        +excluir()
    }

    class Estoque {
        +CATEGORIAS
        +UNIDADES
        +adicionar()
        +adicionar_compra()
        +atualizar()
        +remover()
        +obter()
        +listar()
        +abrir_menu()
    }

    class EstadoPedido {
        <<enumeration>>
        ABERTO
        EM_PRODUCAO
        EM_CONSUMO
        FECHADO
        CANCELADO
    }

    class Pedido {
        +id
        +cliente
        +itens
        +estado
        +adicionar_item(item)
        +remover_item(item)
        +atualizar_estado(novo_estado)
        +fechar_pedido()
        +cancelar_pedido()
    }

    class Pedidos {
        <<nested class: Pedido.Pedidos>>
        -db
        -is_admin
        +adicionar()
        +atualizar()
        +listar()
        +obter()
        +excluir()
        +abrir_menu()
    }

    class ContaPagarRepository {
        -db
        +salvar()
        +listar()
        +remover()
        +atualizar_vencidas()
    }

    class Gastos {
        -gastos
        +salvar()
        +listar()
        +remover()
    }

    class GastosView {
        +abrir()
    }

    class RelatorioVendasRepository {
        -db
        +consultar(data)
    }

    class RelatorioVendasView {
        +abrir()
        +close()
    }

    class BalancoMensalRepository {
        -db
        +consultar(mes)
    }

    class BalancoMensalView {
        +abrir()
        +close()
    }

    class LancheView {
        -db
        +abrir()
        +close()
    }

    class DBProxy {
        +connect()
        +execute()
        +query_one()
        +query_all()
        +transaction()
        +close()
    }

    App --|> Style
    App ..> Login : abre
    App ..> AuthService : usa
    App ..> MenuAdmin : cria
    App ..> MenuFunc : cria
    MenuAdmin --> App
    MenuAdmin --> Login
    MenuFunc --> App
    MenuFunc --> Login
    Login ..> AuthService : autentica
    AuthService --> Usuario : consulta
    AuthService ..> AuthResult : retorna
    Usuario ..> User : cria
    Usuario --> DBProxy
    Lanche --> LancheRepository : delega
    LancheRepository --> DBProxy
    LancheView --> Lanche
    LancheView --> DBProxy
    Estoque --> DBProxy
    Pedido --> EstadoPedido
    Pedidos --> DBProxy
    Pedidos ..> Lanche : expande receita
    Pedidos ..> EstadoPedido
    Gastos --> ContaPagarRepository
    ContaPagarRepository --> DBProxy
    GastosView --> Gastos
    RelatorioVendasRepository --> DBProxy
    RelatorioVendasView --> RelatorioVendasRepository
    BalancoMensalRepository --> DBProxy
    BalancoMensalView --> BalancoMensalRepository

    note for Pedidos "A classe continua aninhada dentro de Pedido em Pedidos.py."
    note for AuthResult "O codigo usa o atributo ok, nao success."
```

## Organizacao atual

- `App`, `Login`, `MenuAdmin`, `MenuFunc` e as classes `*View` formam a camada de interface Tkinter.
- `Lanche`, `Estoque`, `Pedido`, `Pedidos`, `Gastos` e `Usuario` concentram regras e operacoes do dominio.
- `LancheRepository`, `ContaPagarRepository`, `RelatorioVendasRepository` e `BalancoMensalRepository` organizam consultas e persistencia.
- `DBProxy` centraliza a conexao e a execucao de comandos SQLite.
- `AuthService` autentica contas padrao e usuarios persistidos, retornando `AuthResult`.

## Observacao

O arquivo `Pedidos.py` declara `Pedidos` dentro de `Pedido`. O diagrama exibe a classe aninhada separadamente para facilitar a leitura, mas registra a relacao com a anotacao `nested class: Pedido.Pedidos`.
