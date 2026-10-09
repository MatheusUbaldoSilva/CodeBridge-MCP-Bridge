# RAG-017 — Segundo estágio de relevância com cross-encoder local

## Resultado desta intervenção
Criado adaptador local isolado `rag/ranking/local_cross_encoder.py` para reordenar candidatos já autorizados via endpoint `/reranking` do llama.cpp. Por padrão não é registrado no MCP e não modifica o índice persistente.

Criado benchmark `benchmarks/evaluate_rag017_cross_encoder.py` que consulta o índice persistente, recupera candidatos usando Jina Text/Code, agrega por documento e executa o reranker opcional para as 100 perguntas congeladas. Calcula Recall@5, Recall@10, MRR e latência p95 extra da etapa. O relatório somente é escrito após avaliação real completa, sem valores artificiais.

## Bloqueio observado
- Modelos presentes no computador: Jina de embeddings de texto e código. **Nenhum cross-encoder dedicado identificado como instalado**.
- O endpoint de reranking `http://127.0.0.1:8081/health` não respondeu. O benchmark falhou explicitamente com `A dedicated local cross-encoder at port 8081 is REQUIRED`; **não produziu métricas falsas**.
- Não foi realizado download de pesos, mudança no instalador, publicação de modelo, ativação de processo persistente nem alteração de produção.

## Garantias do adaptador
- Aceita somente endpoint HTTP no loopback e caminho `/reranking` ou `/rerank`.
- Bloqueia mistura de project_id, payloads inválidos, respostas com índices repetidos ou faltantes e notas não finitas.
- Nunca insere novos documentos; apenas reordena os resultados previamente filtrados.
- Tem timeout de rede e limite de tamanho da resposta, lote máximo de 64 candidatos e até 6000 caracteres por conteúdo.
- O score de relevância do modelo é mantido separado da ordenação original dos chunks.

## Próximos requisitos
1. Selecionar **modelo cross-encoder compatível com o build atual do llama.cpp**, validar licença/origem, memória de GPU e formato do endpoint; modelos modernos Jina podem exigir build ou fork específico.
2. Instalar e iniciar o modelo num processo local isolado, com política de exclusão mútua em relação aos embeddings para respeitar a VRAM disponível.
3. Reexecutar o benchmark real, validação com perguntas independentes, cold/warm, VRAM/RAM e segurança por namespace.
4. Só aprovar após Recall@5 >= 0.80, Recall@10 >= 0.90, MRR >= 0.60 **simultaneamente** no cenário validado, mantendo todos os thresholds originais.

## Estado
Índice persistente READY; gate de produção BLOCKED. RAG-017-J não iniciado.
