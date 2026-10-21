# RAG V1.03 P2 ? Baseline fechado e merge isolado comprovados

Data: 2026-10-21. Operador autorizou continuidade da manutencao, incluindo parada controlada, sem publicacao.

## Captura real protegida

- Remote Desktop MatheusPC funcionou como rota de monitoramento e recuperacao independente do MCP.
- Tentativa pelo contexto Remote Desktop nao tinha permissao para encerrar MCP; abortada antes de copiar.
- Rotina isolada em TEMP executada no contexto CodeBridge, com recuperacao automatica no finally: parou apenas mcp_server.py PID 5936, manteve interface PID 1376, adaptador PID 10768 e tunel PID 5608.
- Validou SHA do manifesto, SQLite e arvore Qdrant contra baseline publico antes da parada. Depois confirmou ausencia do listener MCP e abertura exclusiva dos arquivos; repetiu verificacoes e validou hashes origem/destino apos copiar.
- Captura em C:\Users\Matheus\AppData\Local\Temp\codebridge-rag-p2-closed-baseline\legacy: 210 documentos, 8761 chunks, 8761 vetores e 210 entradas de manifesto; VALIDATED_OFFLINE_NOT_PUBLISHED.
- Recuperacao automatica iniciou novo MCP PID 9300, porta 8765, CodeBridge READY. Rotina terminou FINISHED source_unmodified=true.
- Nenhuma copia do Qdrant publico foi feita com servidor MCP anterior em execucao; nenhum pointer foi alterado.

## Merge offline do delta P1

- Fonte aprovada rag/runtime/incremental_scheduler_gate.py, SHA256 decodificado 6d0e790e82ee9bea7f163cf0b5244accc794a87bf6032d97144f73ab21c3feed.
- Delta isolado de 1 documento, 2 chunks, 2 vetores.
- stage_incremental_bundle juntou baseline fechado e delta isolado em C:\Users\Matheus\AppData\Local\Temp\codebridge-rag-p2-closed-baseline\candidate-merged-211.
- validate_incremental_bundle retornou VALIDATED_OFFLINE_NOT_PUBLISHED: 211 documentos, 8763 chunks, 8763 vetores, 211 entradas de manifesto.
- Delta exato de manifesto: 1 fonte nova aprovada, 0 removidas e 0 antigas modificadas. SHA coincide com fonte auditada; proveniencia Git no documento indexado 515d9e68d162d5949049c9c4f33aca516b48cbdc.
- Tres SHA da geracao publica continuaram iguais ao baseline apos captura e merge; dois arquivos Git dirty historicos preservados.

## Limites

Captura e merge sao evidencia apenas para P2, nao para promocao do candidato. TEMP e armazenamento transitorio, exige revalidacao futura. Publicacao, troca de pointer, worker/scheduler e rollback real de producao continuam NAO AUTORIZADOS. P3 exige provas de reader/writer lock, journal e runtime MCP, e consentimento especifico para qualquer eventual corte real.
