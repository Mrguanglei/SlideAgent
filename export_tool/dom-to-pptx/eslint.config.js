import globals from 'globals';
import pluginJs from '@eslint/js';
import pluginPrettier from 'eslint-config-prettier';

export default [
  { ignores: ['dist/**'] },
  { files: ['**/*.js'], languageOptions: { sourceType: 'module', globals: globals.browser } },
  pluginJs.configs.recommended,
  pluginPrettier,
  {
    rules: {
      // Custom rules or overrides
      'no-unused-vars': 'warn',
      'no-undef': 'warn',
    },
  },
];
