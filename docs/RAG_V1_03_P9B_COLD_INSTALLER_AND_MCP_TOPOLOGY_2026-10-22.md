# CodeBridge RAG V1.03 — P9-B: ensaio completo do NSIS e topologia MCP

Data: 2026-10-22
Estado: P9-B ABERTA. Testes OFFLINE; nenhum update real aplicado.
Branch: rag-017-optimized-inference-after-candidate

## Evidencia de boot do pacote completo

Foi ensaiado o instalador de prévia construido sobre o commit
6a117afe34a2bb63b11476ece9530002d7244bf8:

%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\
P9B_POSTUPDATE_6a117af\CodeBridge-P9B-POSTUPDATE-GUARDED-Preview.exe

SHA-256:
e492b2b9287201a4cdd9b306143868d1ab976a8f1b1ec427875dc3216b891af9

Snapshot que acompanha esse EXATO executável:
%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\
P9B_POSTUPDATE_6a117af\FULL_NSIS_PREINSTALL_SNAPSHOT.zip

SHA-256:
daab08743893cd06914e5ea7c2de7cec35a5119342e479476b9d69fb3f77c93c

Resultado:
COLD_INSTALLER_READONLY_REHEARSAL_PASS

Verificações de fato realizadas em diretório descartável:
1. Proveniência dos sete módulos MCP e código temporário do instalador
   contra o commit Git; nenhum Python não versionado no pacote.
2. Backup de 236 arquivos antigos para 258 destinos NSIS:
   identidade por SHA e base instalada ainda exatamente original.
3. Extração do NSIS completo em pasta temporária, NÃO na instalação.
4. Import do MCP com o Python portátil atualmente instalado, sem
   inicializar listener de rede ou substituir o serviço em produção.
5. Registro único de codebridge_rag_queue_bootstrap, default
   execute=false, argumentos de confirmação presentes.
6. Leitura do status público RAG usando o código extraído:
   READY / v1_delta_1ae1d01ea84f4e / 211 docs / 8774 chunks.
7. Chamada via dispatcher real FastMCP no processo isolado,
   sem argumento execute=true ou confirmação. Retorno:
   BOOTSTRAP_PLAN_ONLY / executed=false / safe_to_publish=false.
8. Base instalada revalidada sem alterações depois do ensaio.

Os testes novos da suíte foram ampliados de seis para oito e depois
dez cenários de validação: todos PASS. NÃO foi verificado o handshake
HTTP do MCP em produção ou reconexão do túnel depois de update.

## Descoberta da topologia de processos

Código: installer/rag_p9b_mcp_process_topology.py.
Testes sintéticos: 7 PASS.
Estado real: MCP_INDEPENDENT_PROCESS_OWNERSHIP_UNVERIFIED.

Inspeção somente leitura do sistema:
- Interface atual: pythonw.exe, PID 1376.
- Adapter MCP: PID 10768, filho da interface 1376.
- Túnel: PID 5608, filho da interface 1376.
- Servidor MCP principal: PID 9300, registrado como filho de
  PID 10720 que não consta como processo ativo.
- O MCP 9300 NÃO está na árvore da interface atualmente aberta.
- Isso NÃO prova de forma definitiva a origem histórica do processo,
  mas impede pressupor que a GUI atual gerencia seu ciclo de vida.
- Sem encerramentos, adoções, mudanças no MCP ou atualização de arquivos.

## Conclusão e próximo passo real

O risco de incompatibilidade de código no instalador foi bastante
reduzido por um teste de importação, status e dispatch offline.
Continua faltando provar controle do ciclo completo de vida:
desligar GUI + MCP remanescente por mecanismo suportado,
aplicar NSIS com ambos realmente parados, relançar e recuperar
túnel, MCP e sessão ChatGPT.

O updater/NSIS tem guard que BLOQUEIA enquanto a GUI ou MCP
estiverem vivos. Não usar outro executor para contornar bloqueio.
Não executar prévia como atualização automática da branch main.
Não ativar fila/scheduler ou publicar geração nesta fase.

Após atualização autorizada e reconexão efetiva:
1. Checar versão, tool list e saúde RAG.
2. Chamar codebridge_rag_queue_bootstrap sem argumentos.
3. Avaliar ponteiro/geração e autorização explícita de bootstrap.
4. Inicializar somente fila SQLite e fence por caminho MCP oficial.
5. Ensaio único supervisionado e nova auditoria de integridade.
6. Git + revisão diff + commit + auditoria pós-commit + patch notes
   antes de qualquer fechamento da P9-B.

Regressões preexistentes e arquivos locais não versionados
permaneceram intactos.
