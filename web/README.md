# Benchwarmer web

This directory contains the SvelteKit TypeScript client. npm and the committed
lockfile are the supported package-management path.

## Install

```sh
npm ci
```

## Developing

```sh
npm run dev
```

## Checks

```sh
npm run check
npm run lint
npm run test:unit -- --run
```

## Production build

The accepted configuration uses `adapter-static`, disables SSR, and writes a
`200.html` SPA fallback:

```sh
npm run build
```
