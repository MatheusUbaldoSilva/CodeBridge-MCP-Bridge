# PATCH NOTES CodeBridge RAG V1.03-D-C — Restoration rehearsal
Data 2026-10-20
Estado: LABORATORIO VALIDADO / INSTALACAO ATIVA INALTERADA

## Mudancas

- Criado ensaio de restauracao de snapshot do Python em scratch isolado
- Cada arquivo extraido e validado por hash SHA256
- CLI independente usa dry-run como padrao
- Bloqueios para destino existente, ancestral, dentro da instalacao ou ZIP adulterado
- Controle de tamanho maximo e uso de memoria limitado em verificacoes
- Proibido seguir symlink no diretorio raiz do runtime Python
- Ensaios e testes nao acionam o worker automatico ou atualizacao de indice

## Evidencias desta janela

48 testes instalador aprovados
284 testes RAG incrementais aprovados em duas passagens
Dry-run do Python instalado contabilizou 7854 arquivos e 762300601 bytes, sem criar ZIP
Manifesto publico SHA256 eeb40201617444898f9f327fe73b2c50cd73d079b682f6576ac5f60ebf84fd1c
SQLite publico SHA256 5bf26a6dd4e26334899b043a608ac3c8e316b7712e24b6ca1c17b7f9342cb764
Os dois hashes permaneceram identicos na auditoria read-only
Git remoto sincronizado e dois arquivos historicos sujos preservados
CodeBridge 2.0.11-prealpha READY e RAG legacy READY 210 docs e 8761 chunks
Jina Text e Jina Code descarregados no termino

## Bloqueadores reais

Runtime instalado ainda sem caminho raiz Python, import rag e qdrant-client
Nao houve backup completo da instalacao real nem manutencao offline
Restauracao de runtime Python sintetico nao garante restauracao da aplicacao inteira
E necessario controle independente, autorizacao explicita do operador, ensaio de recuperacao completo,
atualizacao com CodeBridge fechado e teste com Jina real no Python instalado sem sys.path temporario
Fase V1.03-D-C permanece ABERTA
