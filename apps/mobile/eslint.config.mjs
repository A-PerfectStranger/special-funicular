import tseslint from 'typescript-eslint';
export default tseslint.config(
  { ignores: ['android/**', 'ios/**', 'dist/**', '.expo/**'] },
  ...tseslint.configs.recommended,
);
