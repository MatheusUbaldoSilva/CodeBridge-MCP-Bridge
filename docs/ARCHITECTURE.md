# Arquitetura — CodeBridge 2.0 MCP Bridge

## Motivação

O Browser Bridge provou o conceito de automação. O MCP Bridge substitui a camada de comunicação do navegador por uma integração MCP dedicada.

## Separação das versões

**CodeBridge 1.x — Browser Bridge** permanece funcional e independente.

**CodeBridge 2.0 — MCP Bridge** é um projeto novo, com repositório e ciclo de desenvolvimento próprios.

## Fluxo alvo

1. ChatGPT envia uma operação pelo MCP.
2. Remote Desktop Commander encaminha a solicitação ao CodeBridge 2.0.
3. O CodeBridge valida alvo, política e estado.
4. A solicitação passa pela fila e aprovação.
5. O terminal persistente executa a operação.
6. O resultado é registrado localmente.
7. O resultado estruturado retorna ao ChatGPT.
## Invariantes

- o CodeBridge continua sendo a autoridade local de execução;
- o transporte MCP não executa comandos fora do fluxo do CodeBridge;
- cada solicitação recebe identidade própria e resultado correlacionado;
- uma perda de conexão não pode duplicar automaticamente uma operação mutável;
- resultados só são consumidos após confirmação;
- cancelamento de fila e parada de execução são operações distintas;
- PowerShell, CMD e SSH seguem contratos equivalentes de execução e retorno.

## Integração do agente remoto

Quando o núcleo estiver estabilizado, o Remote Desktop Commander deverá poder iniciar junto com o CodeBridge 2.0, preferencialmente em segundo plano, com indicador visual de conexão MCP. O encerramento também deverá ser controlado pelo aplicativo.
