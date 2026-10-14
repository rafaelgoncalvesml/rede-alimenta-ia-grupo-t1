# LGPD: dados pessoais no projeto (v1, Anthony)

Escrito a partir do codigo e do `infra/db/schema.sql` de 13/10. Tudo o que e **[GRUPO]**
precisa de decisao do grupo; eu nao inventei a resposta. Todos os dados de demonstracao sao
**SIMULADOS** (CNPJs/CPFs ficticios, e-mails `.local`). Nao e parecer juridico.

## 1. Inventario de dados pessoais

| Dado | Onde | Titular | Quem ve pela API |
|---|---|---|---|
| nome, documento (CPF/CNPJ), telefone, e-mail, cidade/UF, lat/long | `doadores` | doador (pode ser pessoa fisica) | admin e o proprio doador |
| e-mail, hash da senha (argon2), papel | `usuarios` | usuario | so o admin lista; hash nunca sai |
| nome, CNPJ, endereco | `ongs` | pessoa juridica (em regra nao e dado pessoal) | ver RBAC em `docs/auth.md` |
| descricao, quantidade, validade | `lotes` | nao e dado pessoal (texto livre: risco de alguem escrever dado pessoal) | conforme RBAC |
| IP, rota, status, request_id, usuario | log de auditoria | quem chama a API | so quem tem acesso ao log do Render |

Corpo da requisicao e querystring **nao** vao pro log (`api/auditoria.py`). Testado em
`api/tests/test_seguranca.py` (token, documento e senha nao aparecem no log).

## 2. Principios (art. 6) e o que o projeto faz

- **Finalidade e necessidade:** so se coleta o que o match precisa. Telefone e e-mail do doador
  sao opcionais no schema. Latitude/longitude servem pra distancia.
- **Seguranca (art. 46):** senha com argon2, JWT 30 min, RBAC testado (120 casos), limites de
  taxa, TLS no Render e no Supabase, RLS ligado nas 5 tabelas, container sem root.
- **Prevencao:** testes de ataque em `api/tests/test_seguranca.py`; STRIDE em `docs/stride.md`.
- **Transparencia e livre acesso:** ainda nao ha aviso de privacidade nem endpoint do titular.

## 3. Base legal (art. 7) [GRUPO]

Proposta: execucao de contrato/procedimentos preliminares (inciso V) para doador e ONG que se
cadastram para doar/receber; legitimo interesse (IX) para log de seguranca. **Consentimento
nao e a base proposta**, mas se o grupo escolher consentimento, hoje nao existe onde guardar.

## 3b. Mascaramento de CPF/CNPJ

Hoje a API **nao mascara**: devolve o documento inteiro, mas so para o admin e para o proprio
doador (`docs/auth.md`). O log nunca guarda o documento. Proposta [GRUPO]: o admin recebe o CPF
mascarado nas listagens (`***.456.789-**`) e ve o numero inteiro so ao abrir um doador. Tela do
Gustavo e regra da API do Rafael; nao esta implementada.

## 4. Lacunas reais do codigo (nao esta feito)

| Lacuna | Direito/artigo | Proposta |
|---|---|---|
| Nao ha coluna de consentimento/aceite | art. 7, 8 | `consentimento_lgpd boolean`, `consentimento_em timestamptz`, `consentimento_versao text` em `doadores` e `usuarios` (migracao do Rafael) |
| `DELETE /doadores/{id}` devolve 409 se houver lotes ou usuario | art. 18, VI (eliminacao) | endpoint de anonimizacao: troca nome, documento, telefone e e-mail por valores neutros, mantem os lotes para estatistica |
| Nao ha exportacao dos dados do titular | art. 18, II e V | `GET /doadores/{id}` ja devolve os dados ao dono; falta formato de portabilidade (JSON basta) |
| Nao ha prazo de retencao | art. 15, 16 | [GRUPO] definir (ex.: apagar/anonimizar X meses apos inatividade) |
| Texto livre em `lotes.descricao` pode conter dado pessoal | art. 6, III | aviso na tela; limite de 500 caracteres ja existe |

## 5. Transferencia internacional (art. 33)

Supabase (`us-east-2`, EUA) e Render (`ohio`, EUA) tratam dados fora do Brasil. Mitigacao
atual: so dados **SIMULADOS** na demonstracao. Se virar producao real, [GRUPO] avaliar clausulas
contratuais dos provedores (art. 33, II) ou regiao brasileira.

## 6. Contato e papeis [GRUPO]

- Controlador: [GRUPO: quem?]
- Encarregado (art. 41) e canal do titular: [GRUPO: e-mail a definir]

## 7. Incidente (art. 48)

1. Conter: trocar `JWT_SECRET` (invalida todos os tokens) e a senha do banco no Supabase.
2. Levantar escopo pelo log de auditoria (request_id, rota, IP) e pelo Supabase.
3. Comunicar ANPD e titulares em prazo razoavel se houver risco relevante.
4. Registrar o ocorrido e a correcao em `docs/security/vulnerabilidades.md`.

## 8. Checklist

- [x] Inventario de dados
- [x] Log sem corpo/querystring (testado)
- [x] Senha em hash, RBAC, limites
- [ ] Mascaramento de CPF/CNPJ nas listagens [GRUPO]
- [ ] Base legal decidida [GRUPO]
- [ ] Consentimento no schema
- [ ] Anonimizacao/eliminacao
- [ ] Retencao definida [GRUPO]
- [ ] Encarregado e canal do titular [GRUPO]
- [ ] Aviso de privacidade na tela (Gustavo)