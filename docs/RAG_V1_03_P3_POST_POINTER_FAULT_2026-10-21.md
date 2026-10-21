# RAG V1.03 P3 ? Falha injetada apos trocar pointer, antes da verificacao

Data: 2026-10-21. Teste com raiz temporaria, sem instalacao ou publicacao.

test_p3_post_pointer_recovery_isolated.py executa publish_validated_generation em diretorio fake CodeBridge/rag, com readiness READY apenas como stub para atingir a operacao de escrita do pointer. Injeta OSError no _verify_target_after_pointer, depois de _atomic_json ter registrado journal PREPARED e pointer candidato.

Verificacoes PASS:
- Journal e pointer candidato persistem apos falha.
- production_generation_read recusa acesso com recovery required enquanto journal pendente.
- rollback_pending_to_legacy esperado remove pointer ativo e journal, arquiva pointer candidato, conserva a candidata e dados legacy originais imutaveis.

Limitacao: lock e readiness foram mockados, pois foco e a janela de falha do escritor. Os testes anteriores validaram LockFileEx em processos Windows separados. Nao demonstra que a publicacao real e autorizada. GO_LIVE_BLOCKED; nenhum arquivo do RAG publico foi alterado.

Teste adicional: rollback solicitado com candidate ID diferente do journal e recusado, sem alterar os bytes originais do pointer ou journal da fixture. Duas provas nesse arquivo de testes, ambas PASS.

Terceira prova: tentativa de ativacao sem string de autorizacao especifica falha antes de criar journal ou pointer em diretorio temporario.
