# RAG V1.03-D-C — complemento do handoff de ensaio de restauracao

Data 2026-10-20
Estado LABORATORIO APROVADO  PRODUCAO NAO ATUALIZADA
HEAD inicial b210827

## Commits adicionais desta janela

b7df74c introduz ensaio da extracao de snapshot Python em scratch isolado
3269321 integra utilitario ao instalador futuro e aplica limite de tamanho de ZIP
211f0f3 valida falhas por adulteracao de ZIP e pasta destino existente
0614747 documenta limites do ensaio isolado
91baef2 bloqueia origem runtime Python por symlink e valida dry-run real com 7854 arquivos totalizando 762300601 bytes sem gravar ZIP
024bc47 adiciona CLI do ensaio com dry-run padrao

## Seguranca e evidencias

Nao foi gerado backup ZIP do CodeBridge real nem restaurado qualquer diretorio instalado
A restauracao sintetica ocorre apenas fora da instalacao e confirma hashes
O dry-run nao altera o sistema e o modo explicito nao inclui indice publico
48 testes de instalador aprovados incluindo subprocess CLI e adversarial
284 testes incrementais RAG aprovados nesta janela antes dos dois ultimos patches pequenos

## Escopo pendente

A prova de restaurar runtime Python NAO e prova de restaurar toda instalacao CodeBridge
A manutencao instalada segue dependente de aprovacao especifica do operador e controle independente
Falta atualizar Python instalado quando CodeBridge estiver fechado
Validar embeddings Jina no Python sem sys.path temporario, integridade publica e MCP READY
