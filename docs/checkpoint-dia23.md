# Checkpoint do dia 23 (producao)

Conferido em 12/10 (noite) contra o GitHub (`origin/main` e as branches abertas) e contra a API
publica. Mesma regra dos checkpoints anteriores: o que nao aparece no repo vai como "nao esta no
repo". Nao ha branch nem commit do Anthony, do Gustavo ou do Charles alem dos uploads do Charles
de 29/09; tudo que entrou na `main` desde entao e do Rafael.

## O que e do Rafael (dia 23): feito

| Item | Resultado |
|---|---|
| Testar ponta a ponta em producao | `python -m infra.db.testar_producao` contra `https://rede-alimenta-ia-api.onrender.com`: **17 verificacoes, 0 falhas**. Cadastro, prioridade do modelo, doacao, repeticao (409), entrega, KPIs, recusas (teto, categoria), 401 sem token. O script cria um admin descartavel no banco, apaga tudo no fim e confere a contagem de linhas: **igual antes e depois** |
| Medir cold start | **22,4 s** no primeiro pedido depois de 18 min parado (`/health`); 0,25 s nos seguintes |
| Primeiro `POST /lotes` em producao | **9,8 s** (carrega o modelo); o segundo, 0,33 s |
| Plano de abertura da URL | Em `docs/deploy-render.md`: acordar o servico e fazer um `POST /lotes` de aquecimento uns 5 minutos antes |
| IP do cliente atras do Render | Medido (`X-Forwarded-For` e forjavel, `CF-Connecting-IP` nao) e implementado: `CONFIAR_CF_CONNECTING_IP=1`. Conferido nos logs do Render: o campo `ip` mostra o IP real. Forjar o cabecalho da 403 no Cloudflare |

Os 9,8 s do primeiro lote mudam o plano da demo: o aquecimento nao e opcional. Sem ele a
primeira pessoa que cadastrar um lote espera 10 s com a tela parada.

**Uma medida cada, de uma maquina, num dia.** Servem de ordem de grandeza.

## O que nao deu pra medir

- **Memoria e CPU no Render.** A aba Metrics do plano free so mostra rede; memoria e CPU exigem
  plano pago. O que sei: a API subiu, atendeu o teste inteiro (modelo carregado) e a linha de
  eventos nao tem reinicio por falta de memoria. O numero de verdade (136 a 140 MiB) e do
  container local, nao do Render. A tarefa de memoria e do Charles (dia 22).
- **Carga.** Nao rodei teste de carga. O limite de 120 pedidos por minuto por usuario ou IP esta
  testado, mas so em teste automatico.

## Checklist da Semana 4 contra o repo

| Item | Estado | Dono |
|---|---|---|
| API publica, com banco em nuvem em producao | **feito** | Rafael |
| Frontend publico | **nao esta no repo** (`app/` so tem `.gitkeep` desde o dia 7) | Gustavo |
| Dashboard final, KPIs rotulados e mapa de calor | **nao esta no repo** | Gustavo |
| Checklist LGPD (`docs/lgpd.md`) | **nao esta no repo** | Anthony |
| SAST final com tabela de vulnerabilidades | **parcial**: `docs/security/trivy-imagem.md` (Trivy, rodado por mim). Falta Bandit nesse formato e `docs/security/testes.md` | Anthony |
| README completo | existe, mas nao foi revisado pra Semana 4 (dia 25) | todos |
| Roteiro do pitch e primeiro ensaio | **nao esta no repo** | todos |

Os endpoints que o dashboard vai consumir existem e estao no ar (`/kpis/impacto`, `/kpis/ia`,
doacoes, lotes). O que falta e quem os consuma.

## Itens do dia 23 dos outros

| Dono | Tarefa do roadmap | Estado |
|---|---|---|
| Anthony | `docs/lgpd.md` | nao esta no repo |
| Gustavo | secao de seguranca no dashboard | nao ha dashboard |
| Charles | KPIs de IA com o `metrics.json` | o endpoint `/kpis/ia` le o `metrics.json` (feito por mim, dia 17); a tela que o mostra nao existe |

## Matching (issue #8)

Continua aberta e e o buraco maior do projeto: o fluxo vai de cadastro a doacao sem passo de
matching, e a ONG da doacao e escolhida na mao. Faltam 5 dias de producao (dia 24 a 27) antes do
congelamento. Se for entrar, precisa de dono hoje; se nao for, o texto da defesa tem que dizer
que nao entrou.

## Pendencias do grupo

1. **Aval nos tetos e na regra da doacao** (`docs/decisoes.md`): ainda so palpite do Rafael.
2. **Frontend e dashboard.** Sem eles nao ha demo visual; o Plano B e o Swagger em `/docs`.
3. **LGPD.** O sistema guarda CPF/CNPJ, e-mail e telefone de doadores. Sem o mapeamento nao da
   pra dizer o que guardamos e por que.
4. **Pipeline em CI** (ruff, pytest, Bandit, Trivy, build) e `docker-compose`: nao existem. O
   deploy hoje e manual, pelo painel do Render.
5. **Rotacionar o usuario do Atlas** (o valor antigo continua no historico do git).

## Pendencias do Rafael pro dia 24

Script de reset da demo e backup do seed no banco em nuvem. O seed de demo e do Charles e nao
chegou ao repo; o script de reset pode ser feito sem ele, apagando so o que o fluxo cria, mas o
backup do seed precisa do arquivo.
