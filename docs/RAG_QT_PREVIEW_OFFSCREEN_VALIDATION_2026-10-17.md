# Central RAG   Revalidacao Qt da interface
Data: 2026-10-17
Estado: SUITE ESPECIFICA APROVADA; NAO EH LIBERACAO DE PRODUCAO.

A bateria `tests/test_rag_panel_qt_preview.py` importa PySide6 e nao
funciona no Python 3.13 do Windows ou no ambiente author_mcp/.venv
porque ambos nao possuem PySide6. A instalacao do CodeBridge contem
PySide6 no Python embarcado:
`%LOCALAPPDATA%\\Programs\\CodeBridge\\runtime\\python\\python.exe`.

Comando reproduzivel no CMD, sem abrir janela:
`set "QT_QPA_PLATFORM=offscreen"`
`"%LOCALAPPDATA%\\Programs\\CodeBridge\\runtime\\python\\python.exe" -m unittest discover -s tests -p test_rag_panel_qt_preview.py -q`

Resultado observado: 7 testes, OK, exit 0. Qt emitiu aviso sobre
fonte ausente em `PySide6/lib/fonts` sem falha funcional neste ensaio.
No Windows CMD, usar aspas em `set "QT_QPA_PLATFORM=offscreen"`;
sem aspas, um espaco residual causou falha ao buscar plugin
`offscreen ` e exit -1073740791.

A validacao e somente para a suite Qt de preview, nao substitui
testes end-to-end da GUI, funcionalidade operacional, indexacao real
ou seguranca de backup.
