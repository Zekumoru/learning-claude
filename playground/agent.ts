import { query } from '@anthropic-ai/claude-agent-sdk';

const messages = query({
  prompt: 'Look at the current directory and tell me what files are here.',
  options: {
    allowedTools: ['Glob', 'Read'],
    permissionMode: 'dontAsk',
  },
});

for await (const message of messages) {
  switch (message.type) {
    case 'assistant': {
      for (const block of message.message.content) {
        if (block.type === 'text') {
          console.log(block.text);
        }
      }
      break;
    }

    case 'result': {
      console.log('\nDone.');
      console.log('Turns:', message.num_turns);
      console.log('Cost:', message.total_cost_usd);
      break;
    }
  }
}
