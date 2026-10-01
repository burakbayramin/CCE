// Next resolves `server-only` through its own bundler conditions. Vitest runs
// plain Node, so the guard is aliased to a no-op here and the security
// behaviour it protects is asserted directly in media.test.ts.
export {};
