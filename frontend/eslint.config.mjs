// Flat ESLint config (ESLint 9). Ports the former .eslintrc.cjs — eslint:recommended
// + @typescript-eslint/recommended + react/recommended + prettier — scoped to the
// TypeScript sources (matching the old `eslint . --ext .ts,.tsx`).
//
// typescript-eslint's recommended config also disables the core ESLint rules that the
// TypeScript compiler already covers (no-undef, core no-unused-vars, …); tsc runs as a
// separate CI step and is the source of truth for those.
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import react from 'eslint-plugin-react';
import prettier from 'eslint-config-prettier';
import globals from 'globals';

export default tseslint.config(
  { ignores: ['node_modules/', 'dist/', 'build/', 'coverage/'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: { react },
    settings: { react: { version: 'detect' } },
    rules: {
      ...react.configs.flat.recommended.rules,
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': 'warn',
      'react/react-in-jsx-scope': 'off',
    },
  },
  prettier,
);
