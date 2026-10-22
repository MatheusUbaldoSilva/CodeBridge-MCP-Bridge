# P9-B ? Preview NSIS atualizado apos reinicio real

Data: 2026-10-22
Status: PREVIEW GERADO E AUDITADO, NAO INSTALADO.

A release limpa foi exportada do commit exato
2d99ed46435b44d25d5200cfa74a18f1ec24c4a8,
ignorando os tres arquivos preexistentes dirty/untracked do repo.

Artefato local:
%LOCALAPPDATA%\CodeBridge-MCP-Bridge\release_staging\P9B_CURRENT_2d99ed4\
CodeBridge-P9B-CURRENT-2d99ed4-GUARDED-Preview.exe
SHA256 0898124096989d62fd438395bc6f01baa031516f2579860daf275471272e3223
Tamanho 27271347 bytes.
Estado CLEAN_OFFLINE_INSTALLER_READY.
Auditoria P9B_NSIS_GIT_PAYLOAD_VERIFIED,
264 entries, 7 modulos MCP/RAG comparados byte a byte com Git,
0 Python nao commitado, NSIS guard presente.

Snapshot exclusivamente dos destinos sobrescritos pelo NSIS:
FULL_NSIS_PREINSTALL_SNAPSHOT.zip
SHA256 ad8d8c6397a1421a5858fb2f1b1746cfbda941d378cedd7b268b3931bb5fdf0d
258 destinos de installer, 236 arquivos existentes instalados.
INSTALLER_ROLLBACK_SNAPSHOT_VERIFIED.
INSTALLED_BASELINE_MATCH: 236/236.
ISOLATED_INSTALLER_RESTORE_REHEARSED: 236/236.
Nao houve restore em producao, NSIS executado ou alteracao do RAG.

O preview e o backup estao atrelados aos SHA256 acima:
NAO misturar com arquivos de P9B_CURRENT_c7b0a46.
Essas provas NAO constituem aprovacao para aplicar update
enquanto GUI/MCP estao rodando; guard oficial continua ativo.

Ensaio separado de reinicio real anterior:
journal LOCAL_MCP_RECOVERED_PUBLIC_RECHECK_REQUIRED;
recuperacao GUI/MCP/tunnel confirmada por canal independente e
handshake publico ChatGPT CBMCP/1 READY. P9-B continua aberta.

## Gate operacional atual e regressao

A rotina official_update_preflight encontrou unicamente:
ACTIVE_MCP_MUST_SHUT_DOWN e ACTIVE_CODEBRIDGE_GUI_MUST_SHUT_DOWN.
Nao existe autorizacao para disparar NSIS com esses processos vivos.
Independente de uma parada anterior recuperada com sucesso, a
prova de aus?ncia deve ser revalidada na hora do update real.
Instalador de preview segue nao promovido e nao executado.
O conjunto de 165 testes P9-B + lifecycle + NSIS voltou a passar
APOS a recuperacao publica da stack.

## Gate de par SHA256

A checagem adicional identificou um erro de transcricao no hash
anterior do snapshot (65 caracteres). Corrigido apos leitura
SHA256 direta do ZIP no disco; nenhuma alteracao no arquivo ZIP.
O modulo rag_p9b_artifact_pair_gate.py confirmou
ARTIFACT_PAIR_VERIFIED_ONLY, com 236 arquivos conferidos,
installer e snapshot ligados pelo manifesto interno e os dois
hashes corretos. O resultado nao autoriza NSIS nem altera instalado.
