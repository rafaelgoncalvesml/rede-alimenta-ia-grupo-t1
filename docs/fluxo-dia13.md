# Fluxo completo e bugs (dia 13)

Rodado em 30/09 pelo Rafael, na API em memoria (`STORAGE=memory`, sem tocar o Supabase),
direto pelo `TestClient`. O que existe hoje na branch: doador, ONG, lote com prioridade do
modelo, doacao e entrega (`PUT /lotes/{id}` pra `doado`). **Nao existe** `POST /matching` na
API nem tela do Streamlit (`app/` so tem `.gitkeep`), entao o passo de matching e a tela ficaram
de fora. Falta a rodada com eles quando entrarem.

## As 3 rodadas

| | Doador | ONG | Lote | Prioridade / tipo | Doacao | Repetir doacao | Entrega |
|---|---|---|---|---|---|---|---|
| 1 | PJ, SP | cap. 500 kg, hortifruti e laticinios | tomate, 20 kg, vence em 3 dias, refrigerado | media / hortifruti | 201 | 409 | 200 |
| 2 | PF (CPF com mascara), RJ | cap. 50 kg, graos | arroz integral, 8,5 kg, 90 dias, ambiente, tipo informado | baixa / nao_pereciveis | 201 | 409 | 200 |
| 3 | PJ, MG | cap. 0 kg, sem necessidades | leite uht, 300 kg, vence em 1 dia, ambiente | media / nao_pereciveis | 201 | 409 | 200 |

Na primeira tentativa da rodada 2 eu mandei `tipo: "graos"` e voltou 422. Esta certo (so
valem as 6 categorias), mas levantou o bug 1 abaixo.

Alem do caminho feliz, testei 18 entradas ruins (JSON quebrado, NaN, Infinity, texto de 1 MB,
id gigante, status invalido...). Quatro viraram correcao hoje; o resto ja respondia certo.

## Corrigido hoje (Rafael)

| Bug | Antes | Agora |
|---|---|---|
| `capacidade_kg` com `NaN`, `Infinity` ou `1e999` na ONG | 500 em texto puro (a propria resposta 422 nao serializava o NaN) | 422 |
| Qualquer excecao nao tratada | 500 `text/plain` "Internal Server Error", sem como achar no log | 500 JSON generico + `request_id` + stack no log |
| JSON malformado | 422 | 400 |
| `descricao` de 1 MB aceita e gravada; `tipo` sem limite | 201 | 422 (500 e 50 caracteres; o maior do dataset tem 47) |

Tambem: resposta 422 nao devolve mais o valor recebido, e erro do Postgres por valor fora do
limite (id maior que bigint, texto com byte nulo) vira 422 em vez de 500. Esse ultimo foi
testado com excecao simulada; **nao** contra o Supabase real.

## Issues pra abrir (rascunho, ainda nao criadas no GitHub)

1. **`ONG.necessidades` e `Lote.tipo` usam vocabularios diferentes.** Dono: Rafael (modelo da
   ONG) e Charles (matching). A ONG aceita texto livre ("graos", "hortifruti"); o lote so tem as 6
   categorias do modelo (`hortifruti`, `padaria`, `laticinios`, `carnes_peixes`, `preparados`,
   `nao_pereciveis`). "graos" nunca casa com nada, e o matching por necessidade volta vazio.
   Proposta: validar `necessidades` contra as 6 categorias em `api/models.py`.
2. **Falta `POST /matching/{lote_id}` e a tela.** Dono: Charles (matching), Gustavo (tela). O
   roadmap do dia 12 manda integrar os dois, e a demo do dia 14 pede lote, prioridade, matching e
   doacao. Hoje o fluxo para na doacao.
3. **`POST /doacoes` aceita ONG sem capacidade ou sem a necessidade.** Dono: Rafael, decisao do
   grupo. Rodada 3: lote de 300 kg confirmado pra ONG com `capacidade_kg = 0` e sem
   `necessidades`. O README do dia 12 diz que `distancia_km` e `score` sao informativos por
   enquanto, mas o servidor tambem nao confere capacidade. Decidir se confere ou se isso fica so
   no matching.
4. **`.pytest_cache/` e `__pycache__/` estao versionados.** Dono: Charles (subiu pelo upload do
   GitHub; 26 arquivos). Estao no `.gitignore`, mas ja entraram, e o `git status` fica sujo a cada
   `pytest`. Correcao: `git rm -r --cached .pytest_cache` e os `__pycache__`.
5. **Sem limite superior em `quantidade_kg`, `capacidade_kg` e `validade`.** Dono: Rafael, baixa
   prioridade. `1e308` kg e `9999-12-31` sao aceitos. A defesa do `docs/ia.md` contra erro de
   unidade depende de validar no cadastro, e hoje so valida `> 0`. Precisa de um teto de
   negocio que o grupo escolha; nao inventei um.
6. **`.env.example` traz o ref do projeto Supabase e o usuario do Atlas.** Dono: Anthony. Nao e
   senha (vem `[SUA-SENHA]`), mas e identificador de producao num arquivo versionado. Trocar por
   placeholder.

## Nao conferido

- Nada disso rodou contra o Supabase: os numeros acima sao da API em memoria.
- `pip-audit` e `gitleaks` nao estao instalados na maquina. Troquei so o codigo da API hoje, sem
  dependencia nova; a busca por padroes de chave nos arquivos versionados (`git grep`) nao achou
  nada, e o `.env` nao esta versionado.
