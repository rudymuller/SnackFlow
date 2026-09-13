# Diagrama de classes atual

Este diagrama representa a estrutura atual do projeto SnackFlow, incluindo as principais classes e suas dependencias.

```mermaid
classDiagram
    class App {
        +homeScreen()
        +_build_sidebar()
        +_render_main_menu_in_window()
    }

    class Style {
        +COLORS
        +style_button()
        +style_heading()
        +style_subtitle()
    }

    class DBProxy {
        +connect()
        +execute()
        +query_one()
        +query_all()
        +transaction()
        +close()
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

    class LancheView {
        -db
        +abrir()
        +close()
        -_create_table()
        -_create_form()
        -_create_actions()
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
        +adicionar_item()
        +remover_item()
        +atualizar_estado()
        +fechar_pedido()
        +cancelar_pedido()
    }

    class Pedidos {
        +adicionar()
        +atualizar()
        +listar()
        +obter()
        +excluir()
        +_expandir_lanches()
        +_alocar_itens()
        +abrir_menu()
    }

    class User {
        <<dataclass>>
        +nome
        +sobrenome
        +cpf
        +nome_usuario
        +senha
        +data_admissao
        +tipo_acesso
    }

    class Usuario {
        +adicionar()
        +listar()
        +obter()
        +atualizar()
        +remover()
    }

    class AuthResult {
        <<dataclass>>
        +success
        +message
        +user
    }

    class AuthService {
        +authenticate()
    }

    class Login {
        +show()
        +authenticate()
    }

    App --|> Style : herda
    App ..> Login : abre
    App ..> AuthService : usa
    App ..> LancheView : abre
    App ..> Estoque : abre
    App ..> Pedidos : abre

    AuthService ..> Usuario : consulta
    AuthService ..> AuthResult : retorna
    Usuario ..> User : cria e retorna
    Usuario --> DBProxy : usa

    LancheView --> Lanche : edita e salva
    LancheView --> DBProxy : consulta estoque e receitas
    Lanche --> LancheRepository : delega persistencia
    Lanche --> DBProxy : cria ingredientes novos
    LancheRepository --> DBProxy : executa SQL

    Estoque --> DBProxy : executa SQL
    Pedidos --> DBProxy : executa SQL
    Pedidos ..> Lanche : expande receitas
    Pedidos --> EstadoPedido : usa
    Pedido --> EstadoPedido : possui estado

    note for Lanche "Modelo de dominio: regras da receita e unidades"
    note for LancheRepository "Persistencia das tabelas lanches e lanche_itens"
    note for LancheView "Interface Tkinter separada do modelo"
    note for Pedidos "No codigo atual, Pedidos aparece aninhada dentro de Pedido"
```

## Organizacao atual

- `Lanche` representa o modelo e as regras da receita.
- `LancheRepository` concentra o acesso as tabelas `lanches` e `lanche_itens`.
- `LancheView` concentra a interface Tkinter do cadastro de lanches.
- `DBProxy` centraliza a conexao e a execucao de comandos SQLite.
- `Estoque` controla os itens e suas compras.
- `Pedidos` transforma uma receita em itens do estoque antes de realizar a baixa.
- `App` coordena a navegacao e herda os estilos visuais de `Style`.

## Observacao importante

O arquivo `Pedidos.py` atualmente declara a classe `Pedidos` dentro da classe `Pedido`. O diagrama mostra as duas classes separadamente para facilitar a leitura, mas registra essa diferenca na anotacao. Essa estrutura pode ser corrigida em uma etapa futura de refatoracao.
