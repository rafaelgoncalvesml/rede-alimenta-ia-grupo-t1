# Autenticacao e papeis (dia 15)

## O que foi decidido

| Decisao | Escolha | Por que |
|---|---|---|
| JWT ou API key | **JWT** (HS256, 30 min) | A chave estatica nao diz de quem e o pedido. Sem isso nao da pra barrar um doador de abrir o lote de outro. O token leva `papel` e `doador_id` ou `ong_id` |
| Senha | argon2 (`argon2-cffi`) | Biblioteca madura, nao escrevi hash na mao. Senha de 10 a 128 caracteres |
| Quem cria usuario | so o admin (`POST /usuarios`) | Cadastro aberto precisa de decisao do grupo (verificar e-mail, CNPJ) e de captcha. Ficou fora |
| Primeiro admin | `ADMIN_EMAIL` e `ADMIN_PASSWORD` no ambiente | Criado na subida se nao existir. Sem as variaveis, nada e criado |
| Segredo | `JWT_SECRET`, minimo 32 caracteres | Sem ele a API nao sobe (falha cedo, nao assina token com chave vazia) |
| Negado | 403 pra papel ou dono errado, 401 pra sem token ou token ruim | Os dois com `detail` generico |

## Quem pode o que

| Rota | admin | doador | ong |
|---|---|---|---|
| `POST /usuarios`, `GET /usuarios` | sim | 403 | 403 |
| `POST /doadores`, `GET /doadores`, `DELETE /doadores/{id}` | sim | 403 | 403 |
| `GET` e `PUT /doadores/{id}` | sim | so o proprio | 403 |
| `POST /ongs`, `DELETE /ongs/{id}` | sim | 403 | 403 |
| `GET /ongs`, `GET /ongs/{id}` | sim | sim | sim |
| `PUT /ongs/{id}` | sim | 403 | so a propria |
| `POST /lotes` | sim | so em nome dele | 403 |
| `GET /lotes` | todos | so os dele | so os que recebeu |
| `GET /lotes/{id}` | sim | so o dele | so se recebeu |
| `PUT` e `DELETE /lotes/{id}` | sim | so o dele | 403 |
| `POST /doacoes` | sim | so de lote dele | 403 |
| `GET /doacoes`, `GET /doacoes/{id}` | todas | as dos lotes dele | as dela |

"Recebeu" quer dizer doacao `confirmada` pra aquela ONG. Se a reserva cai e a doacao vira
`cancelada`, o lote some da lista da ONG.

## Limites que ficam de fora (de proposito ou por falta de tempo)

- **Token nao e revogavel.** Usuario apagado ou rebaixado continua valendo ate o token vencer
  (30 min). Trocar isso pede consulta ao banco a cada pedido, e hoje cada consulta ao Supabase
  leva 0,6 a 2 s.
- **Sem refresh token e sem logout.** Passou 30 min, loga de novo.
- **Limite de tentativas na memoria do processo.** Serve pro Render com um worker. Com varios
  workers cada um conta o seu. E por e-mail: quem erra 5 vezes o e-mail de outra pessoa trava o
  login dela por 15 min. Aceitei porque o limite por IP nao funciona atras do proxy (o IP que
  chega e o do proxy).
- **403 em vez de 404 pra recurso alheio:** quem esta logado consegue descobrir que um id de lote
  existe (404 vs 403). Os ids sao sequenciais de qualquer jeito.
- **Nao ha rate limit geral**, so no login. Rate limit do matching e limite de payload sao do dia 18.
- **Tabela `usuarios` nao foi aplicada no Supabase.** Esta em `infra/db/schema.sql`; os testes
  rodam em memoria. O caminho Postgres de usuarios nao foi exercitado contra o banco.
- **O `doador` nao pode marcar a entrega**: `PUT /lotes/{id}` com `doado` e do doador dono ou do
  admin, nao da ONG. Se o grupo quiser que a ONG confirme o recebimento, e uma rota nova.
- **O Streamlit ainda nao manda token** (e nao existe no repo). Quando entrar, guarda o token em
  `st.session_state` e manda no cabecalho.
