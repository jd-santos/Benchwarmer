import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const appStyles = readFileSync(new URL('./app.css', import.meta.url), 'utf8');

const adjacentBackgroundSelectors = [
	['page root', ':root'],
	['html page', 'html'],
	['header and default desktop links', '.app-header'],
	['default navigation button', '.app-navigation__toggle'],
	['expanded navigation button', ".app-navigation__toggle[aria-expanded='true']"],
	['hovered navigation link', '.app-navigation__links a:hover'],
	['current-page navigation link', ".app-navigation__links a[aria-current='page']"],
	['narrow-screen default links', '.app-navigation__links']
] as const;

function escapeRegExp(value: string) {
	return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function hexDeclaration(selector: string, property: string) {
	const rulePattern = new RegExp(`${escapeRegExp(selector)}\\s*\\{([^}]*)\\}`, 'g');
	const declarationPattern = new RegExp(
		`(?:^|;)\\s*${escapeRegExp(property)}\\s*:\\s*(#[\\da-f]{6})\\s*;`,
		'i'
	);
	const values = [...appStyles.matchAll(rulePattern)].flatMap(([, declarations]) => {
		const declaration = declarations.match(declarationPattern);
		return declaration ? [declaration[1]] : [];
	});

	expect(values, `${selector} should declare one ${property}`).toHaveLength(1);
	return values[0]!;
}

function relativeLuminance(color: string) {
	const channels = color
		.slice(1)
		.match(/.{2}/g)!
		.map((channel) => Number.parseInt(channel, 16) / 255)
		.map((channel) => (channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4));

	return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

function contrastRatio(first: string, second: string) {
	const lighter = Math.max(relativeLuminance(first), relativeLuminance(second));
	const darker = Math.min(relativeLuminance(first), relativeLuminance(second));

	return (lighter + 0.05) / (darker + 0.05);
}

describe('application focus indicator', () => {
	it('contrasts with every adjacent shell background', () => {
		const focusRule = appStyles.match(
			/a:focus-visible,\s*button:focus-visible,\s*\[tabindex='-1'\]:focus-visible\s*{([^}]*)}/
		)?.[1];
		const outline = focusRule?.match(/outline:\s*0\.2rem solid (#[\da-f]{6});/i);

		expect(focusRule).toContain('outline-offset: 0.2rem');
		expect(outline).not.toBeNull();

		for (const [context, selector] of adjacentBackgroundSelectors) {
			const background = hexDeclaration(selector, 'background');
			expect(contrastRatio(outline![1], background), context).toBeGreaterThan(3);
		}
	});
});
