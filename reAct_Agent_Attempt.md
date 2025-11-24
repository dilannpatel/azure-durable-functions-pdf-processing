

## Uses Azure for orchestration, Ollama for local intelligence, and LangChain for the cognitive reasoning (the Agent).

ReAct Agent is different. You give it a Goal and a Toolbox, and it writes its own code on the fly to solve the problem.

Create tools using the @tool decorators, which are just Python functions but the @tools tells the AI how and when to use them.


The Prompt: downloads a famouse prompt template that forces the AI into a specific behaviour lop



Summary of the Flow

User uploads PDF -> Event Grid triggers Azure.

Azure Orchestrator wakes up and hires two workers:

Worker A (Embedder): Chunks the PDF, turns it into math (vectors) via Ollama, saves a searchable index.

Worker B (Agent): Reads the PDF text. Enters a "ReAct Loop" where it repeatedly asks Ollama "What tool should I use?" -> runs tool -> reports back -> repeats, until a full analysis is generated.

Orchestrator gathers results from both workers and saves the final JSON report to Blob Storage.

