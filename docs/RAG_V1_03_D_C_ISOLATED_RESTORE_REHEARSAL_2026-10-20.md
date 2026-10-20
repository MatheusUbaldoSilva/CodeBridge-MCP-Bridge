# CodeBridge V1.03-D-C — ensaio de restauracao isolada

Data 2026-10-20
Estado TESTADO EM LABORATORIO, INSTALACAO REAL NAO MODIFICADA

## Cobertura

- Snapshot completo da subarvore runtime/python em um ZIP externo com SHA256 por arquivo
- Verificacao de hashes em streaming com limite de tamanho de arquivo e de pacote
- Ensaio explicito de extracao somente para uma pasta temporaria nova, fora da instalacao
- Verificacao do SHA256 apos a extracao
- Recusa de destino existente, dentro da instalacao ou ancestral da instalacao
- Recusa de ZIP adulterado antes de criar o destino
- Nenhum restore, instalacao, kill, shutdown ou publicacao RAG automaticos

## Limites

Esse ensaio demonstra apenas que o conteudo do ZIP pode ser extraido e verificado
Nao demonstra recuperacao do CodeBridge completo, da interface, do MCP ou da instalacao com todos os arquivos
O operador precisa autorizar manutencao offline e garantir canal de recuperacao independente

## Commits

b7df74c: ensaio de restauracao em diretorio temporario
3269321: limites do ZIP e inclusao no futuro instalador
211f0f3: testes contra adulteracao e sobrescrita de diretorio existente

## Proxima etapa

Auditar regressao instalada e RAG, checar Git, registrar checkpoint
Depois da autorizacao especifica executar apenas fluxo oficial com CodeBridge fechado
Validar Python instalado sem sys.path temporario e testar Jina real em staging isolado
Comparar manifesto e SQLite publico via SHA256 e confirmar MCP READY
Nao considerar D-C fechada antes dessas comprovacoes
