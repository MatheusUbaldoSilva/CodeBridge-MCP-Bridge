"""Dicas de proxima acao para as respostas de erro das ferramentas MCP.

Motivo: um modelo de IA menos potente trava quando recebe so um error_type
(ex.: "timed_out") sem saber o que fazer. hint_for() mapeia os erros conhecidos
para uma instrucao curta da proxima acao, para a IA se recuperar sem precisar
entender o sistema por dentro -- menos chamada de ferramenta errada.

Funcao pura, sem dependencias de terceiros: facil de testar e de adotar em
qualquer ponto que monte o dicionario de erro (ex.: um campo next_action no
modelo base ProtocolOutcome, ou no retorno de uma ferramenta). O casamento e
por substring no error_type/estado, caixa ignorada, entao serve tanto para
"timed_out" quanto para "CodeBridgeUnavailable".
"""
from __future__ import annotations

# chave (minuscula) -> dica de proxima acao
_HINTS = {
    "one_at_a_time": "Ja ha um comando em execucao. Aguarde com codebridge_wait "
                     "ou pare com codebridge_stop antes de iniciar outro.",
    "busy": "Ja ha um comando em execucao. Aguarde com codebridge_wait ou pare "
            "com codebridge_stop antes de iniciar outro.",
    "not_connected": "Nenhum dispositivo conectado. Abra o app CodeBridge na "
                     "maquina alvo e tente de novo.",
    "not_found": "O execution_id nao existe mais. Inicie o comando de novo com "
                 "codebridge_exec.",
    "handshake": "Handshake nao confirmado. Chame codebridge_status para "
                 "reestabelecer a sessao.",
    "timed_out": "Recuperavel: chame codebridge_wait de novo com o mesmo "
                 "execution_id e cursor ate state=FINISHED.",
    "timeout": "Recuperavel: chame codebridge_wait de novo com o mesmo "
               "execution_id e cursor ate state=FINISHED.",
    "unavailable": "A ponte ficou indisponivel por um instante. Repita a mesma "
                   "chamada; se persistir, veja se o app CodeBridge esta aberto.",
    "invalid": "Confira os parametros da chamada: ha valor ou nome invalido.",
}

# ordem de teste: do mais especifico para o mais generico
_ORDER = (
    "one_at_a_time", "not_connected", "not_found", "handshake",
    "timed_out", "timeout", "unavailable", "busy", "invalid",
)

_GENERICO = "Erro recuperavel: repita a mesma chamada."


def hint_for(error_type, *, recoverable=None):
    """Dica curta de proxima acao para um erro, ou None se nao houver.

    error_type: o tipo/estado do erro (qualquer string); casamento por
      substring, caixa ignorada.
    recoverable: quando conhecido; True faz cair na dica generica de repetir
      caso o error_type nao case com nenhuma dica especifica.
    """
    if error_type:
        low = str(error_type).lower()
        for key in _ORDER:
            if key in low:
                return _HINTS[key]
    if recoverable:
        return _GENERICO
    return None
