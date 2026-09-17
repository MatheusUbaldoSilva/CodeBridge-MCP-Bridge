class CommandFailure(RuntimeError):
    def __init__(self, message, output="", exit_code=None):
        super().__init__(message)
        self.output = str(output)
        self.exit_code = exit_code


class PowerShellCommandError(CommandFailure):
    pass


class PowerShellCommandCancelled(CommandFailure):
    pass


class PowerShellSessionInterrupted(CommandFailure):
    pass


class SSHCommandError(CommandFailure):
    pass


class SSHCommandCancelled(CommandFailure):
    pass


class SSHSessionInterrupted(CommandFailure):
    pass
