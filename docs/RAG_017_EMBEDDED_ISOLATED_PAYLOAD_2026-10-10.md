RAG-017 — Prova de imports do Python embutido no payload isolado (2026-10-10)

A receita NSIS exclusiva de teste instalou 83 fontes RAG em %TEMP%\CodeBridge-RAG017-Isolated-Retest-20261010. Com o Python 3.13.15 embutido da instalação, PYTHONPATH sozinho não expôs o diretório do teste por causa da configuração isolada do Python. A ferramenta benchmarks/rag017_isolated_embedded_probe.py injeta exclusivamente na memória do processo o caminho do payload (sys.path.insert) e testa os imports.

Resultado real: rag=true, mcp=true, pydantic=true, numpy=false, qdrant_client=false; isolated_import_ok=true, deployment_ready=false, exit code 2. O módulo RAG pode ser importado para alguns caminhos com o pacote copiado, mas o runtime embutido não está pronto para acessar o índice Qdrant local. Não se modificou python313._pth, nem se instalaram bibliotecas no runtime principal.

O rollback NSIS integral continua não certificado; o ensaio de restauração de arquivo no diretório TEMP não cobre chaves de registro, atalhos, dependências e processos. Não executar o instalador principal no host até haver validação isolada de dependências nativas e rollback. Gate RAG-017-J BLOCKED.
