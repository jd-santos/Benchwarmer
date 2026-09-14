import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';

const defaultApiOrigin = 'http://127.0.0.1:8000';

function resolveApiOrigin(value: string): string {
	let url: URL;
	try {
		url = new URL(value);
	} catch {
		throw new Error('BENCHWARMER_API_ORIGIN must be a valid absolute URL.');
	}

	if (
		!['http:', 'https:'].includes(url.protocol) ||
		url.username !== '' ||
		url.password !== '' ||
		url.pathname !== '/' ||
		url.search !== '' ||
		url.hash !== ''
	) {
		throw new Error(
			'BENCHWARMER_API_ORIGIN must be an HTTP(S) origin without credentials or a path.'
		);
	}

	return url.origin;
}

const apiOrigin = resolveApiOrigin(process.env.BENCHWARMER_API_ORIGIN ?? defaultApiOrigin);

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: adapter({ fallback: '200.html' })
		}),
		svelteTesting()
	],
	server: {
		proxy: {
			'/api': {
				target: apiOrigin,
				changeOrigin: true
			}
		}
	},
	test: {
		expect: { requireAssertions: true },
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'server',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
