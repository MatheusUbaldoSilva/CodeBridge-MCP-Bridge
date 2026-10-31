# RAG-DEL-01.04-DQ-E-B — Auditoria de snapshots GUI/MCP sem alteracao (DEV)

## Caminhos reais identificados

O launcher utiliza C:/Users/Matheus/CodeBridge-Launcher/launcher.py, CodeBridge-Stable e os snapshots CodeBridge-Stable-Candidate-<commit>. O candidato selecionado no momento da auditoria foi 570bb17. O caminho legado AppData/Local/Programs/CodeBridge nao estava presente e NAO foi usado como prova da GUI instalada.

## Evidencia read-only

- Stable GUI rag_panel.py: existe, SHA256 F4728B357E11244F58683B673BDBB9834F63E42D85D6F4EE48C70EB3AF820C68, sem read_pinned_public_document_inventory.
- Candidato 570bb17: mesmo SHA GUI do Stable; igualmente sem leitor publico pinado.
- DEV rag_panel.py: SHA256 B5BF49C59536381A0A422840D72863B22F8B6EF685B4458BC3E92729D488FBD2, com referencia a read_pinned_public_document_inventory.
- Helper rag/runtime/knowledge_deletion_public_inventory_read.py: presente no DEV, ausente no Stable e candidato.
- MCP mcp_server.py: Stable e candidato declararam codebridge_rag_generation_probe em source, mas o probe nao esta exposto na superficie da conexao atual. Hashes MCP snapshot e DEV divergentes.
- Processo GUI observado com comando apontando para o repositorio DEV, nao Stable. O processo iniciou antes da ultima data de modificacao do arquivo DEV rag_panel.py. Nao se pode atestar codigo efetivamente carregado em memoria a partir do arquivo no disco.
- Sem instalacao, reinicio, alteracao de candidate selection ou promocao da Stable.

## Componente novo

rag/runtime/knowledge_deletion_dqeb_snapshot_audit_dev.py compara DEV, Stable e candidate em modo somente leitura, calculando SHA256, evidencia de declaracoes e presenca do helper. O resultado SEMPRE marca live_python_modules_attested, connected_mcp_probe_attested e safe_to_activate como False. O source comparison nao atesta nenhum processo.

4 testes novos passam. Regressao RAG-DEL: 350 executados (346 PASS, 4 SKIP); RAG-AUTO sem MCP: 241 (236 PASS, 5 SKIP); total 591, 582 PASS, 9 SKIP, zero falhas.

## Pendencias

DQ-E-C: instrumento de probe realmente exposto e verificado no MCP conectado; comparacao do hash/commit da GUI que estiver carregada, sem depender do disco; worker semantico real com guard nao reentrante e pinned generation; fila operacional READY_FOR_REVIEW; reconciliacao/arquivamento dos journals. Qualquer piloto de exclusao somente com autorizacao explicita, apos homologacao. Nenhuma ativacao autorizada nesta fase.