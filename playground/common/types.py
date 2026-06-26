from anthropic.types import Message
from anthropic.types.beta import BetaMessage

# Streaming code-execution / Files API features when beta-namespaced
# messages. Regular and beta messages are structurally identical for our
# purposes (same `.usage`, `.model`, `.content` discriminators), so this
# union lets shared code accept either without bifurcating the codebase.
AnyMessage = Message | BetaMessage
