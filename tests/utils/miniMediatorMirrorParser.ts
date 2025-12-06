export interface MirrorMessage {
	role?: string;
	content?: unknown;
	[key: string]: unknown;
}

export interface MirrorRequestPayload {
	model?: string;
	messages?: MirrorMessage[];
	[key: string]: unknown;
}

/**
 * Extracts the JSON payload from a mirror model response string.
 *
 * Mirror models respond with text like:
 *
 *   "Received request with data:\n```json\n{ ... }\n```"
 *
 * In the UI, this is rendered as plain text where the JSON object appears
 * inline (e.g., under a CodeMirror code block) without backticks.
 *
 * This helper:
 *   1) Prefers an explicit ```json code block (or any ``` block as a fallback)
 *   2) Otherwise, assumes there is a single JSON object in the text and
 *      returns the substring between the first `{` and the last `}` that
 *      parses as valid JSON.
 *
 * @throws If no JSON-looking payload can be found.
 */
export function extractMirrorJsonBlock(raw: string): string {
	// Prefer an explicit ```json code block
	const jsonCodeBlockRegex = /```json\s*([\s\S]*?)```/i;
	const jsonMatch = raw.match(jsonCodeBlockRegex);
	if (jsonMatch?.[1]) {
		return jsonMatch[1].trim();
	}

	// Fallback: any triple-backtick code block
	const genericCodeBlockRegex = /```([\s\S]*?)```/;
	const genericMatch = raw.match(genericCodeBlockRegex);
	if (genericMatch?.[1]) {
		return genericMatch[1].trim();
	}

	// Fallback: attempt to sniff out a single JSON object anywhere in the string.
	// This matches both the raw mirror response and the rendered CodeMirror text:
	//
	//   "Received request with data:\n{\n  ...\n}\n"
	//
	// We conservatively take the substring from the first `{` to the last `}` and
	// require that it parses as valid JSON.
	const firstBrace = raw.indexOf('{');
	const lastBrace = raw.lastIndexOf('}');
	if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
		const candidate = raw.slice(firstBrace, lastBrace + 1).trim();
		try {
			JSON.parse(candidate);
			return candidate;
		} catch {
			// Ignore and fall through to the final error below.
		}
	}

	throw new Error('Could not find JSON code block in mirror response text');
}

/**
 * Parses a mirror model response string into the original request payload
 * that the model received.
 *
 * The returned object is expected to have a `messages` array, but this function
 * is intentionally tolerant and will not enforce a strict schema beyond basic
 * object-ness.
 *
 * @param raw - The full text content of the mirror model's response.
 */
export function parseMirrorRequestPayload(raw: string): MirrorRequestPayload {
	const json = extractMirrorJsonBlock(raw);
	const parsed = JSON.parse(json);

	if (!parsed || typeof parsed !== 'object') {
		throw new Error('Mirror response JSON did not parse into an object');
	}

	return parsed as MirrorRequestPayload;
}

/**
 * Returns the content of the first user-role message from the mirror payload.
 *
 * This is useful for assertions like "what was messages[0].content as seen by the model?"
 *
 * @throws If no user message with string content can be found.
 */
export function getFirstUserMessageContentFromMirrorResponse(raw: string): string {
	const payload = parseMirrorRequestPayload(raw);
	const messages = Array.isArray(payload.messages) ? payload.messages : [];

	if (messages.length === 0) {
		throw new Error('Mirror payload does not contain any messages');
	}

	const userMessage = messages.find((m) => m.role === 'user') ?? messages[0];

	if (!userMessage || typeof userMessage.content !== 'string') {
		throw new Error('No user message with string content found in mirror payload');
	}

	return userMessage.content;
}

/**
 * Returns all user-role message contents from the mirror payload, in order.
 *
 * If there are no user messages, this returns an empty array.
 */
export function getAllUserMessageContentsFromMirrorResponse(raw: string): string[] {
	const payload = parseMirrorRequestPayload(raw);
	const messages = Array.isArray(payload.messages) ? payload.messages : [];

	return messages
		.filter((m) => m.role === 'user' && typeof m.content === 'string')
		.map((m) => m.content as string);
}
