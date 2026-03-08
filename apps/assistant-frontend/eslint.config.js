import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default [
  {
    ignores: ['.svelte-kit/**', 'build/**', 'dist/**', 'node_modules/**'],
  },
  {
    files: ['**/*.{js,mjs,cjs}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    ...js.configs.recommended,
  },
  ...tseslint.configs.recommended.map((config) => ({
    ...config,
    files: ['**/*.ts'],
    languageOptions: {
      ...(config.languageOptions ?? {}),
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      ...(config.rules ?? {}),
      'no-undef': 'off',
    },
  })),
];
