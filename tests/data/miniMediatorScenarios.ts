import { MiniMediatorFixtureAdapter } from '../utils/miniMediatorFixtureAdapter';
import { MINI_MEDIATOR_DETERMINISTIC_OPENAI, type MiniMediatorModel } from './miniMediatorModels';

export class MiniMediatorScenario {
	public model: MiniMediatorModel;
	private fixtureAdapter: MiniMediatorFixtureAdapter;
	private input: string;
	private output: string;
	public name: string;

	constructor(
		model: MiniMediatorModel,
		name: string,
		public fixturePath: string = 'tests/mocks/mini-mediator/fixtures/models/deterministic.json'
	) {
		this.model = model;
		this.name = name;
		this.fixtureAdapter = new MiniMediatorFixtureAdapter(this.fixturePath);
		this.input = this.fixtureAdapter.getScenarioInput(name);
		this.output = this.fixtureAdapter.getScenarioResponse(name);
	}

	public getInput(): string {
		return this.input;
	}

	public getOutput(): string {
		return this.output;
	}

	public getScenarioResponseChunk(chunkIndex: number): string {
		return this.fixtureAdapter.getScenarioResponseChunk(this.name, chunkIndex);
	}

	/**
	 * Gets the maximum pause duration (in seconds) defined for this scenario's streaming profile.
	 *
	 * This is derived from the `pause_profile` in the fixture, falling back to defaults if needed.
	 */
	public getMaxPauseSeconds(): number {
		return this.fixtureAdapter.getMaxPauseSeconds(this.name);
	}

	/**
	 * Returns a recommended "warmup" timeout in milliseconds for waiting until
	 * the first few chunks of the response have been streamed.
	 *
	 * This uses the scenario's target tokens-per-second and chunking configuration,
	 * with a safety factor and clamped to a sane range.
	 *
	 * @param desiredChunks - How many chunks we want to be reasonably sure have arrived.
	 */
	public getRecommendedWarmupMs(desiredChunks: number = 2): number {
		return this.fixtureAdapter.getRecommendedWarmupMs(this.name, desiredChunks);
	}
}

export const MINI_MEDIATOR_SCENARIO_BASIC_CHAT = new MiniMediatorScenario(
	MINI_MEDIATOR_DETERMINISTIC_OPENAI,
	'basic-chat'
);
export const MINI_MEDIATOR_SCENARIO_BASIC_CHAT_FOLLOW_UP = new MiniMediatorScenario(
	MINI_MEDIATOR_DETERMINISTIC_OPENAI,
	'basic-chat-follow-up'
);
export const MINI_MEDIATOR_SCENARIO_SLOW_STREAM_PAUSE = new MiniMediatorScenario(
	MINI_MEDIATOR_DETERMINISTIC_OPENAI,
	'slow-stream-pause'
);
