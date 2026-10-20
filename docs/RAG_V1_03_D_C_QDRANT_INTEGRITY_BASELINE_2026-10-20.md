# CodeBridge RAG V1.03-D-C — Protecao de integridade Qdrant Local

Data 2026-10-20
Estado TESTADO EM MODO SOMENTE LEITURA
Git referencia 0663047

## Mudanca

O preflight de manutencao e a verificacao apos atualizacao agora exigem comparacao do indice publico inteiro
O controle considera o manifesto o arquivo SQLite e a arvore de arquivos do Qdrant Local
O hash do Qdrant utiliza caminhos relativos ordenados tamanho e SHA256 de cada arquivo
Diretorio vazio ausente ou com symlink invalida a verificacao
Nenhuma etapa escreve no indice publico

## Referencia da instalacao atual

Manifesto SHA256 eeb40201617444898f9f327fe73b2c50cd73d079b682f6576ac5f60ebf84fd1c
SQLite SHA256 5bf26a6dd4e26334899b043a608ac3c8e316b7712e24b6ca1c17b7f9342cb764
Qdrant SHA256 18ed78113780dd9e12489aff4e0ddad4674f4ea458af37b69262847f9d4578e5c
Qdrant arquivos 4
Qdrant bytes 98178081

## Limite

A correspondencia SHA confirma integridade dos bytes verificados naquele momento
Nao substitui teste de consulta vetorial nem prova que atualizacao instalada foi bem-sucedida
A V1.03-D-C continua aberta ate manutencao offline autorizada e teste Jina real com Python embutido sem sys.path temporario
