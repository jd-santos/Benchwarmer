import { test as base, expect } from '@playwright/test';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import path from 'node:path';

const webRoot = path.resolve(import.meta.dirname, '../..');
const repositoryRoot = path.resolve(webRoot, '..');
const fixturePath = path.join(repositoryRoot, 'tests/fixtures/sources.json');
const builtUiRoot = path.join(webRoot, 'build');

interface ManagedProcess {
	child: ChildProcess;
	command: string;
	output: string[];
	startError?: Error;
}

export interface Foundation {
	apiUrl: string;
	webUrl: string;
	dataRoot: string;
	restart: () => Promise<void>;
	stop: () => Promise<void>;
}

function allocatePort(): Promise<number> {
	return new Promise((resolve, reject) => {
		const server = createServer();
		server.unref();
		server.on('error', reject);
		server.listen(0, '127.0.0.1', () => {
			const address = server.address();
			if (address === null || typeof address === 'string') {
				server.close();
				reject(new Error('could not allocate a loopback port'));
				return;
			}
			server.close((error) => {
				if (error) reject(error);
				else resolve(address.port);
			});
		});
	});
}

function run(command: string, args: string[], cwd: string, environment: NodeJS.ProcessEnv): void {
	const result = spawnSync(command, args, { cwd, env: environment, encoding: 'utf8' });
	if (result.status !== 0) {
		const detail = [result.stdout, result.stderr].filter(Boolean).join('\n').trim();
		throw new Error(`${command} ${args.join(' ')} failed${detail ? `:\n${detail}` : ''}`);
	}
}

function start(
	command: string,
	args: string[],
	cwd: string,
	environment: NodeJS.ProcessEnv
): ManagedProcess {
	const child = spawn(command, args, {
		cwd,
		env: environment,
		detached: process.platform !== 'win32',
		stdio: ['ignore', 'pipe', 'pipe']
	});
	const managed: ManagedProcess = { child, command: `${command} ${args.join(' ')}`, output: [] };
	const collect = (chunk: Buffer) => {
		managed.output.push(chunk.toString());
		if (managed.output.length > 40) managed.output.shift();
	};
	child.stdout?.on('data', collect);
	child.stderr?.on('data', collect);
	child.on('error', (error) => {
		managed.startError = error;
	});
	return managed;
}

function processFailure(process: ManagedProcess): Error {
	if (process.startError) {
		return new Error(`${process.command} could not start`, { cause: process.startError });
	}
	const detail = process.output.join('').trim();
	return new Error(
		`${process.command} exited before becoming ready${detail ? `:\n${detail}` : ''}`
	);
}

async function waitUntilReady(url: string, process: ManagedProcess): Promise<void> {
	const deadline = Date.now() + 20_000;
	while (Date.now() < deadline) {
		if (process.startError) throw processFailure(process);
		if (process.child.exitCode !== null) throw processFailure(process);
		try {
			const response = await fetch(url);
			if (response.ok) return;
		} catch {
			// The process is still starting.
		}
		await new Promise((resolve) => setTimeout(resolve, 100));
	}
	throw new Error(`${process.command} did not become ready within 20 seconds`);
}

async function stopProcess(managed: ManagedProcess): Promise<void> {
	if (managed.child.exitCode !== null || managed.child.pid === undefined) return;
	const exited = new Promise<void>((resolve) => managed.child.once('exit', () => resolve()));
	try {
		if (process.platform === 'win32') managed.child.kill('SIGTERM');
		else process.kill(-managed.child.pid, 'SIGTERM');
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error;
	}
	const stopped = await Promise.race([
		exited.then(() => true),
		new Promise<false>((resolve) => setTimeout(() => resolve(false), 5_000))
	]);
	if (!stopped) {
		try {
			if (process.platform === 'win32') managed.child.kill('SIGKILL');
			else process.kill(-managed.child.pid, 'SIGKILL');
		} catch (error) {
			if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error;
		}
		await exited;
	}
}

export async function startFoundation(): Promise<Foundation> {
	const dataRoot = await mkdtemp(path.join(tmpdir(), 'benchwarmer-playwright-'));
	let api: ManagedProcess | undefined;
	let stopped = false;
	const apiPort = await allocatePort();
	const apiUrl = `http://127.0.0.1:${apiPort}`;
	const apiEnvironment = {
		...process.env,
		BENCHWARMER_DATA_ROOT: dataRoot,
		BENCHWARMER_UI_ROOT: builtUiRoot
	};

	const startApi = async () => {
		api = start(
			'uv',
			[
				'run',
				'uvicorn',
				'benchwarmer.api.app:create_app',
				'--factory',
				'--host',
				'127.0.0.1',
				'--port',
				String(apiPort)
			],
			repositoryRoot,
			apiEnvironment
		);
		await waitUntilReady(`${apiUrl}/api/v1/health`, api);
	};

	const stop = async () => {
		if (stopped) return;
		stopped = true;
		if (api) await stopProcess(api);
		await rm(dataRoot, { recursive: true, force: true });
	};

	try {
		run('npm', ['run', 'build'], webRoot, process.env);
		run('uv', ['run', 'alembic', 'upgrade', 'head'], repositoryRoot, apiEnvironment);
		run(
			'uv',
			['run', 'python', '-m', 'benchwarmer.services.fixtures', '--load', fixturePath],
			repositoryRoot,
			apiEnvironment
		);
		await startApi();

		return {
			apiUrl,
			webUrl: apiUrl,
			dataRoot,
			restart: async () => {
				if (api) await stopProcess(api);
				await startApi();
			},
			stop
		};
	} catch (error) {
		await stop();
		throw error;
	}
}

interface WorkerFixtures {
	foundation: Foundation;
}

export const test = base.extend<Record<never, never>, WorkerFixtures>({
	foundation: [
		async ({ browserName }, use) => {
			if (browserName !== 'chromium') {
				throw new Error(`the foundation harness requires Chromium, received ${browserName}`);
			}
			const foundation = await startFoundation();
			try {
				await use(foundation);
			} finally {
				await foundation.stop();
			}
		},
		{ scope: 'worker' }
	]
});

export { expect };
