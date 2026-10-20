# CodeBridge RAG V1.03-D-C — Historico da integridade persistida

Data 2026-10-20
Status LABORATORIO APROVADO / INSTALACAO ATIVA PRESERVADA

## Incrementos desta janela

a4ca6b9 baseline incompleto nao gera excecao e resulta bloqueio
3309ced arquivo Qdrant ausente durante hash resulta bloqueio
666ec7d junctions e redirecionamentos Windows recusados
1222029 handoff da defesa de fingerprints
9bc4665 baseline historico JSON versionado e comparador contra indice real
6847636 linha de comando para comparar baseline historico sem alterar disco

## Referencia oficial

docs/RAG_V1_03_D_C_PUBLIC_INDEX_BASELINE_2026-10-20.json

## Execucao

python -m installer.runtime_fingerprints --install-root "<instalacao CodeBridge>" --rag-state "<estado RAG>" --compare-baseline docs/RAG_V1_03_D_C_PUBLIC_INDEX_BASELINE_2026-10-20.json

Saida observada PUBLIC_INDEX_UNCHANGED para manifesto SQLite e Qdrant
Erros ou referencia ausente devem produzir codigo de retorno 2

## Testes

60 testes do instalador OK
284 testes incrementais RAG OK
Git 6847636 = origin

## Pendencias para V1.03-D-C

A instalacao ativa ainda nao encontra rag nem qdrant_client no Python embutido
Falta janela de manutencao com aplicativo fechado e recuperacao independente
Apos update oficial validar Jina real sem injetar sys.path e comparar com esta referencia historica
Fase continua aberta
