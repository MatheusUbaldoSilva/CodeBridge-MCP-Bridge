# P9-B ? Integridade do journal reiniciavel

RollbackJournal.resume agora confere, antes de permitir
continuacao do journal incompleto, que todos os estados
pertencem ao escopo SHELL_, que cada evento possui detalhes
validos e que nenhum evento terminal de recuperacao ja
ocorreu em qualquer posicao da sequencia.

Novos testes:
- recusa journal contendo sucesso terminal seguido de
  outro evento;
- recusa estado arbitrario nao pertencente ao protocolo.

Isso endurece a protecao contra reexecucao indevida.
Nao autentica criptograficamente o journal; a identidade
continua vinculada a area descartavel de laboratorio e
aos arquivos de snapshot autorizados.
