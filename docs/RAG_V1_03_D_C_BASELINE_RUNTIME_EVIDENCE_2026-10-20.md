# V1.03-D-C — Revisao de seguranca da baseline e runtime isolado

Data: 2026-10-20
Estado: LABORATORIO VALIDADO — INSTALACAO ATIVA NAO ALTERADA

## Mudancas verificadas

- a713b51 exige SHA256 hexadecimal completo e metadados validos para baseline historica
- 5a68b9f registra a evidencia e as pendencias
- bef2b91 protege o calculo de SHA quando o manifesto ou SQLite desaparece durante abertura

## Testes

- 63 testes do instalador PASS
- 284 testes de RAG incremental PASS
- Jina Code real em Python embarcado com sys.path injetado somente para laboratorio PASS — 1 teste em 5 segundos
- Indice publico comparado contra baseline historica: PUBLIC_INDEX_UNCHANGED
- Git local origin sincronizados em bef2b91 antes deste documento

## Limite de liberacao

O teste com caminhos injetados nao demonstra que a instalacao oficial tem os pacotes
Runtime oficial ainda requer manutencao offline autorizada com CodeBridge fechado e canal independente de recuperacao
A fase D-C somente sera concluida apos teste Jina no runtime sem sys.path temporario, integridade publica e MCP READY
