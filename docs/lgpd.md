# LGPD: mapeamento de dados pessoais (rascunho de 13/10)

Este arquivo lista o que a API guarda sobre pessoas, onde fica, quem acessa e o que ainda falta.
Foi escrito lendo o `schema.sql`, `api/models.py`, `api/auditoria.py`, `docs/auth.md` e o
`render.yaml`, nao testando o sistema em producao. Nao e parecer juridico e o projeto nao esta
"em conformidade" com a Lei 13.709/2018. As bases legais da secao 4 sao propostas pro grupo e pro
professor revisarem; um advogado ou o orientador precisa confirmar antes de qualquer uso real.

O seed de demo (`docs/seed-demo.md`) usa doadores e lotes ficticios e ONGs com dados publicos da
Receita. Nao conferi o que ha de fato no banco de producao. Tudo abaixo vale pro dia em que alguem
cadastrar dado de uma pessoa de verdade.

## 1. Que dados pessoais existem

Dado pessoal e o que identifica uma pessoa natural (art. 5, I). CNPJ de ONG e de empresa nao e dado
pessoal (empresario individual e a excecao que vale checar). CPF, e-mail e telefone de pessoa fisica sao. Nenhuma coluna guarda dado sensivel (art. 5,
II): nada de saude, religiao, origem racial ou biometria.

| Dado | Onde | De quem | Pra que serve | Quem acessa pela API |
|---|---|---|---|---|
| Nome | `doadores.nome` | doador (pessoa fisica ou nome da empresa) | identificar quem doa | admin; o proprio doador; ONG nao le doador direto |
| CPF ou CNPJ | `doadores.documento`, so os digitos | doador | evitar cadastro duplicado (`unique`) | admin; o proprio doador |
| Telefone, e-mail | `doadores.telefone`, `doadores.email` (opcionais) | doador | contato pra combinar a coleta | admin; o proprio doador |
| Cidade, estado, latitude, longitude | `doadores` | doador | calcular distancia ate a ONG | admin; o proprio doador |
| E-mail de login | `usuarios.email` | doador, ONG e admin | autenticar | admin (`GET /usuarios`) |
| Senha | `usuarios.senha_hash`, argon2 | os mesmos | autenticar | ninguem; nenhuma rota devolve o hash |
| IP do cliente | log de auditoria, campo `ip` | quem chama a API | rastrear abuso e erro | quem tem acesso ao painel do Render |
| Id do usuario | log de auditoria | usuario logado | saber quem mudou o que | idem |

Alguns pontos sobre esses dados:

- Latitude e longitude do doador podem apontar a casa de uma pessoa fisica. O schema nao guarda rua
  nem numero, mas a coordenada pode ser exata. Sem decisao do grupo sobre o nivel de precisao.
- O IP no log e dado pessoal. O log nao grava corpo de pedido nem querystring, entao CPF, CNPJ,
  e-mail e telefone nao aparecem nele (regra no cabecalho de `api/auditoria.py`, coberta por
  `test_auditoria_registra_o_pedido_sem_dado_pessoal` em `api/tests/test_erros.py`).
- As ONGs guardam CNPJ, nome, endereco e capacidade: dado de pessoa juridica. Se uma ONG cadastrar
  e-mail de uma pessoa como login, ele entra na linha da tabela acima.
- O backup que o script de reset gera (`infra/db/reset_demo.py`, ainda na branch do Rafael) sai
  sem o hash de senha e fica em `backups/`, fora do git. Na `main` de hoje esse script nao existe.

## 2. Quem mais toca nesses dados

| Terceiro | O que recebe | Onde | Observacao |
|---|---|---|---|
| Supabase | o banco inteiro (tabelas acima) | AWS `us-east-2`, Ohio | RLS ligado em todas as tabelas, sem policy: a API REST do Supabase nao le nada, so a nossa API (dono das tabelas) |
| Render | logs da API (IP, id de usuario, rota, status) e a imagem | Ohio | plano free. Nao verifiquei por quanto tempo o Render guarda log nesse plano |
| Cloudflare (na frente do Render) | todo o trafego HTTP | rede propria | o Render usa; nao contratamos nem configuramos |
| GitHub | codigo, sem `.env`, sem dado de banco | EUA | o repo tem so placeholders (conferido em 13/10) |

Os dois servicos que guardam dado estao nos EUA. Isso e transferencia internacional (art. 33) e
precisa de uma das hipoteses do artigo (por exemplo, clausulas contratuais do provedor ou
consentimento especifico). Nao li os termos do Supabase nem do Render pra esse fim; fica como
pendencia.

## 3. O que a API ja faz pela protecao (art. 46)

Estas medidas existem no repo; a coluna da direita diz onde conferir.

| Medida | Onde conferir |
|---|---|
| Login com JWT de 30 minutos, tres papeis, sem cadastro aberto | `docs/auth.md` |
| Cada papel so le o que e dele (doador so o proprio cadastro e os proprios lotes) | `api/tests/test_acesso_negado.py`, 120 casos |
| Senha so como hash argon2, de 10 a 128 caracteres | `api/seguranca.py` |
| Bloqueio apos 5 erros de login em 15 minutos, limite de pedidos por rota | `docs/limites.md` |
| HTTPS na URL publica do Render | terminado pelo Render, nao pelo nosso codigo |
| Erro 500 e 422 sem stack trace e sem eco do valor enviado | `api/erros.py` |
| Log sem corpo de pedido e sem querystring | `api/auditoria.py` |
| Container sem root, `.env` fora da imagem e fora do git | `api/Dockerfile`, `.dockerignore`, `.gitignore` |
| Segredos so em variavel de ambiente | `.env.example`, `render.yaml` |

Limites que o grupo conhece e que contam aqui: o token nao e revogavel antes dos 30 minutos, a
contagem de tentativas de login fica na memoria do processo, e o Supabase free nao tem backup
automatico.

## 4. Base legal e finalidade (proposta, a confirmar)

Finalidade unica: ligar quem tem alimento sobrando a uma ONG que pode receber, com registro do que
foi doado. Nao ha uso do dado pra publicidade, venda ou treino do modelo (o modelo de prioridade
usa so validade, quantidade, categoria e armazenamento do lote, nunca dado do doador).

| Titular | Base proposta (art. 7) | Por que |
|---|---|---|
| Doador pessoa fisica | consentimento (inciso I) ou execucao de procedimento ligado a contrato a pedido do titular (inciso V) | quem se cadastra pede a doacao; precisa de aviso claro e de uma acao afirmativa de aceite, que hoje nao existe porque nao ha tela |
| Usuario da API (e-mail e senha) | inciso V, o mesmo | sem login nao ha como ligar o doador aos proprios lotes |
| IP no log | legitimo interesse (inciso IX) | seguranca e deteccao de abuso; precisa de teste de balanceamento escrito, que nao existe |

Principios que o projeto pode defender hoje (art. 6): necessidade (e-mail e telefone sao opcionais,
sem rua nem data de nascimento) e seguranca. O que ainda nao se defende: transparencia e livre
acesso, porque nao ha aviso de privacidade pro titular (art. 9).

## 5. Direitos do titular (art. 18) contra o que a API entrega

| Direito | O que existe | Lacuna |
|---|---|---|
| Confirmar e acessar os dados | `GET /doadores/{id}` devolve o cadastro ao proprio doador logado | pessoa sem login nao tem como pedir; nao ha canal |
| Corrigir | `PUT /doadores/{id}`, parcial. Documento e tipo de pessoa nao mudam | corrigir CPF errado exige o admin apagar e recriar |
| Eliminar | `DELETE /doadores/{id}`, so admin | volta 409 se o doador tem lote. Lote com doacao nao pode ser apagado e doacao nao tem DELETE (e o registro do que foi recebido). Na pratica, doador com historico nao some do banco |
| Portabilidade | o JSON do `GET` serve de copia | sem endpoint de exportacao nem formato definido |
| Revogar consentimento | nada | nao ha fluxo |
| Informacao sobre compartilhamento | esta tabela da secao 2 | nao chega ao titular |

A tensao mais concreta e a de eliminar: manter a doacao registrada tem justificativa (prestar contas
do que a ONG recebeu), mas isso precisa ser dito ao titular e talvez resolvido com anonimizacao
(trocar nome e contato por um marcador e manter o registro). Nao implementei isso.

## 6. Retencao

Nao ha prazo definido nem rotina de exclusao. O dado fica no banco ate o admin apagar. Proposta pra
discussao: doador sem lote ha mais de 12 meses e conta de usuario inativa ha mais de 12 meses
entram numa lista de revisao do admin. O numero e palpite do Rafael, sem base legal.

## 7. Incidente

Se houver vazamento de dado pessoal, o controlador comunica a ANPD e os titulares em prazo
razoavel (art. 48). Nao ha plano escrito. Minimo pra ter: quem do grupo recebe o alerta, onde ver
os logs (painel do Render, procurar o `request_id`), como trocar `JWT_SECRET` e a senha do banco
(painel do Render e do Supabase) e como avisar. No Render, `SUPABASE_DB_URL` e `JWT_SECRET` ficam no painel (e a url do banco tambem no `.env` de
quem desenvolve); trocar o `JWT_SECRET` invalida todos os tokens.

## 8. Pendencias antes de usar com dado real

Ordem do que mais pesa:

1. Definir quem e o controlador (o grupo? a faculdade? a ONG?) e o encarregado (art. 41), com e-mail
   de contato. Hoje nao ha ninguem nomeado.
2. Escrever e publicar o aviso de privacidade, com finalidade, terceiros (secao 2) e canal do titular.
3. Fluxo de aceite no cadastro do doador e registro de quando aceitou (coluna nova).
4. Decidir o que fazer com eliminacao de doador que tem doacao (anonimizar).
5. Conferir os termos do Supabase e do Render sobre transferencia internacional.
6. Definir prazo de retencao e quem executa a limpeza.
7. Registro das operacoes de tratamento (art. 37): esta tabela e um comeco.
8. Decidir a precisao da coordenada do doador pessoa fisica.
9. Revisao por advogado ou pelo orientador.

Itens 3, 4 e 6 mexem em schema e API; com o congelamento de features valendo, ficam como proximos
passos na defesa.
