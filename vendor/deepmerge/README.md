# Temporary security backport

Upstream: `deepmerge@4.3.1`, `dist/cjs.js`, MIT license preserved in LICENSE.
GHSA-gcqx-w48m-w2h4 has no upstream fixed version as of 2026-11-07.
Expo 56 uses this function for config/plugin merges. Downgrading or changing the
Expo major to hide the advisory is not an acceptable fix.

This local override preserves upstream behavior except that `__proto__`,
`constructor` and `prototype` keys are rejected in BOTH source and target copies.
That prevents the output object's prototype from being changed by attacker input,
including a target with a deliberately enumerable own `__proto__` property.
Nested objects and arrays use the same recursive guard. This is a project patch,
not an official upstream release. npm audit does not audit local source; the
advisory regression runs explicitly in `npm test` and must remain mandatory.
Remove the override after upgrading to an official compatible fix and rerunning
the config/export/native-build regressions.
