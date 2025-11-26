export type OpenAIEndpoint = {
	url: string;
	apiKey: string;
	prefix?: string;
};

export type OllamaEndpoint = {
	url: string;
	prefix?: string;
};

export const MINI_MEDIATOR_OPENAI: OpenAIEndpoint = {
	url: 'http://localhost:11998/v1',
	apiKey: 'sk-proj-1234567890'
};

export const MINI_MEDIATOR_OLLAMA: OllamaEndpoint = {
	url: 'http://localhost:11998/ollama',
	prefix: 'ollama'
};
