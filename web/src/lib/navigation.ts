/** The in-app page the reader arrived from, recorded by the root layout. */
let previous: URL | null = null;

export function recordNavigation(from: URL | null): void {
	previous = from;
}

/** True when going back in history returns to a page under `pathname`. */
export function cameFrom(pathname: string): boolean {
	return previous !== null && previous.pathname === pathname;
}
