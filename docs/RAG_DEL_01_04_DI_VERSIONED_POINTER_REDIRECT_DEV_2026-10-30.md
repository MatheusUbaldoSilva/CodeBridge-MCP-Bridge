# RAG-DEL-01.04-DI — Proteção de redirecionamento do ponteiro versionado (DEV)

## Alteração

O leitor production_generation_read._read_pointer verifica agora is_symlink e is_junction para active-generation.json antes de abrir ou interpretar o JSON. Se o ponteiro for um redirecionamento, retorna erro fail-closed, mesmo com um nome de geração aparentemente válido. O controle anterior de caminho da pasta generations e a validação dos stores foram preservados.

## Evidências

Em TemporaryDirectory/CodeBridge/rag, os testes cobrem:
- pointer comum: continua selecionando uma geração versionada sintética com lock Win32 real;
- is_symlink simulado via unittest.mock: recusa o pointer e libera o lock, permitindo leitura subsequente segura;
- tentativa de criar symlink real no Windows: DISPENSADA (WinError 1314: privilégios de criação de link simbólico ausentes). Esse caso não foi confirmado no host; não apresentá-lo como PASS.

Regressão após o patch: RAG-DEL 291 testes (288 PASS, 3 SKIP); generation_transition_journal 14 PASS; test_p3_* 16 PASS. RAG-AUTO non-MCP 241 testes havia passado na revisão anterior (236 PASS, 5 SKIP).

## Pendências

Certificar redirecionamento por junction real em ambiente de teste com permissão adequada, readers legados GUI/MCP, recuperação de journal, workers durante troca e participação global dos locks. Não foi executada troca real, remoção de documentos, mudança da Stable ou push.