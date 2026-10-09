# RAG-017 — Recuperação por documento (investigação corretiva)

## Resultado
Executado contra o mesmo índice persistente READY, com 100 consultas e ground truth congelados. A estratégia agrega evidência por caminho de arquivo, em lugar de deixar chunks repetidos dominar as primeiras posições. Nenhuma alteração foi aplicada ao motor de produção.

| Agregação | k | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|---:|
| sum_decay | 5 | 0.83 | 0.89 | 0.588702 |
| sum_decay | 10 | 0.82 | 0.89 | 0.594095 |
| sum_decay | 15 | 0.82 | 0.91 | 0.587512 |
| sum_decay | 20 | 0.83 | 0.91 | 0.584147 |
| reciprocal | 5 | 0.84 | 0.90 | 0.563702 |
| chunk_rrf | 60 | 0.80 | 0.88 | 0.504825 |

## Interpretação
- Recall@5 >= 0.80 e Recall@10 >= 0.90 são viáveis em variantes experimentais.
- Nenhuma variante atingiu MRR >= 0.60 ao mesmo tempo.
- Este foi um estudo de parâmetros no próprio benchmark conhecido, **não** validação independente e não estabelece generalização.
- A fórmula sum_decay soma por caminho os sinais RRF, atenuando repetições do mesmo arquivo por lista. Nenhuma regra por ID ou alteração do ground truth foi feita.

## Estado
Qualidade de produção **BLOCKED**. Índice persistente READY e intacto. Não habilitar indexação automática nem go-live. Não avançar ao RAG-017-J como certificado de produção.

## Próxima correção necessária
Investigar reranker verdadeiramente semântico no nível de documento, com conjunto independente de validação e limites de latência/RAM/VRAM. Validar source_type, projeto, branch e path sob regressão, e só alterar o pipeline após comprovar ganhos sustentados nas três métricas congeladas.
